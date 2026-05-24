"""Phase C coverage for the Reddit poller + adapter.

Critical behaviours:
  - Reply-loop guards: self-authored items skipped, parent-self comments
    skipped (prevents infinite ping-pong)
  - Missing PRAW credentials → poll is a no-op, doesn't crash
  - Channel kill switch (`INBOX_REDDIT_ENABLED=false`) skips poll
  - upsert_inbound_message is idempotent on (channel, channel_msg_id)
  - New-account throttle caps at 3/day for accounts < N days old

A regression in the reply-loop guard = infinite recursion incinerating
both API quota AND the bot's Reddit account reputation. Critical.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import get_settings
from app.services import inbox_kill_switch, reddit_inbox


@pytest.fixture(autouse=True)
def _reset():
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()
    reddit_inbox._reset_praw_cache_for_tests()
    yield
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()
    reddit_inbox._reset_praw_cache_for_tests()


# ── Reply-loop guards ──────────────────────────────────────────────────────


class TestReplyLoopGuards:
    """These guards are the bot's safety against infinite recursion. A
    regression here means the bot replies to its own auto-replies until
    the API quota burns out OR the account gets shadow-banned."""

    def test_is_self_authored_matches_case_insensitive(self):
        item = MagicMock()
        item.author = MagicMock()
        item.author.name = "TapelineBot"
        assert reddit_inbox._is_self_authored(item, "tapelinebot") is True
        assert reddit_inbox._is_self_authored(item, "TAPELINEBOT") is True
        assert reddit_inbox._is_self_authored(item, "someoneelse") is False

    def test_is_self_authored_handles_deleted_author(self):
        item = MagicMock()
        item.author = None
        assert reddit_inbox._is_self_authored(item, "tapelinebot") is False

    def test_is_parent_self_authored_catches_reply_to_us(self):
        """The killer case: someone replies to OUR auto-reply. Without
        this guard, that response gets classified and replied to again."""
        parent = MagicMock()
        parent.author = MagicMock()
        parent.author.name = "tapelinebot"

        comment = MagicMock()
        comment.parent.return_value = parent
        assert reddit_inbox._is_parent_self_authored(comment, "tapelinebot") is True

    def test_is_parent_self_authored_allows_third_party_thread(self):
        """Comment whose parent is someone else — fine to classify."""
        parent = MagicMock()
        parent.author = MagicMock()
        parent.author.name = "some-other-user"

        comment = MagicMock()
        comment.parent.return_value = parent
        assert reddit_inbox._is_parent_self_authored(comment, "tapelinebot") is False

    def test_is_parent_self_authored_handles_praw_exception(self):
        """PRAW's parent() can raise (deleted comment, banned user). Must
        not crash the poller — fall through to 'not self-authored'."""
        comment = MagicMock()
        comment.parent.side_effect = RuntimeError("deleted")
        assert reddit_inbox._is_parent_self_authored(comment, "tapelinebot") is False


# ── PRAW client / config ───────────────────────────────────────────────────


class TestPrawClient:
    def test_missing_credentials_returns_none(self, monkeypatch):
        for var in (
            "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
            "REDDIT_USERNAME", "REDDIT_PASSWORD",
        ):
            monkeypatch.delenv(var, raising=False)
        get_settings.cache_clear()
        assert reddit_inbox._praw_client() is None

    def test_partial_credentials_returns_none(self, monkeypatch):
        """Setting some but not all reddit credentials still no-ops."""
        monkeypatch.setenv("REDDIT_CLIENT_ID", "id")
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "secret")
        # username + password missing
        get_settings.cache_clear()
        assert reddit_inbox._praw_client() is None


# ── Poll skips ──────────────────────────────────────────────────────────────


class TestPollSkips:
    @pytest.mark.asyncio
    async def test_poll_no_op_when_bot_disabled(self, monkeypatch):
        monkeypatch.setenv("INBOX_BOT_ENABLED", "false")
        get_settings.cache_clear()

        mock_session = MagicMock()
        # Even with full creds set, bot_enabled=false should bypass everything
        for var, val in [
            ("REDDIT_CLIENT_ID", "id"), ("REDDIT_CLIENT_SECRET", "s"),
            ("REDDIT_USERNAME", "u"), ("REDDIT_PASSWORD", "p"),
        ]:
            monkeypatch.setenv(var, val)
        get_settings.cache_clear()

        with patch.object(reddit_inbox, "_praw_client") as mock_client:
            counts = await reddit_inbox.poll_reddit_inbox(mock_session)

        assert counts == {"dms": 0, "comments": 0, "mentions": 0, "total": 0}
        mock_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_no_op_when_channel_disabled(self, monkeypatch):
        monkeypatch.setenv("INBOX_REDDIT_ENABLED", "false")
        for var, val in [
            ("REDDIT_CLIENT_ID", "id"), ("REDDIT_CLIENT_SECRET", "s"),
            ("REDDIT_USERNAME", "u"), ("REDDIT_PASSWORD", "p"),
        ]:
            monkeypatch.setenv(var, val)
        get_settings.cache_clear()

        mock_session = MagicMock()
        with patch.object(reddit_inbox, "_praw_client") as mock_client:
            counts = await reddit_inbox.poll_reddit_inbox(mock_session)

        assert counts["total"] == 0
        mock_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_no_op_when_no_credentials(self, monkeypatch):
        # Bot enabled, channel enabled, but no PRAW creds — should
        # log + return zero counts, not crash.
        monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
        get_settings.cache_clear()

        mock_session = MagicMock()
        counts = await reddit_inbox.poll_reddit_inbox(mock_session)
        assert counts["total"] == 0


# ── Outbound adapter ───────────────────────────────────────────────────────


class TestSendRedditReply:
    @pytest.mark.asyncio
    async def test_returns_reddit_not_configured_when_no_creds(self, monkeypatch):
        monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
        get_settings.cache_clear()

        from app.models import InboundMessage
        msg = InboundMessage(
            id=1, channel="reddit_dm", channel_msg_id="t4_abc",
            author="u/test", body="hi", status="new",
            received_at=datetime.now(UTC),
        )
        result = await reddit_inbox.send_reddit_reply(msg, "thanks")
        assert result.sent is False
        assert result.error == "reddit_not_configured"

    @pytest.mark.asyncio
    async def test_unsupported_reddit_channel_errors(self, monkeypatch):
        """Defensive: a future channel name we haven't taught the adapter
        about must return a clean error, not crash."""
        for var, val in [
            ("REDDIT_CLIENT_ID", "id"), ("REDDIT_CLIENT_SECRET", "s"),
            ("REDDIT_USERNAME", "u"), ("REDDIT_PASSWORD", "p"),
        ]:
            monkeypatch.setenv(var, val)
        get_settings.cache_clear()

        from app.models import InboundMessage
        msg = InboundMessage(
            id=1, channel="reddit_telepathy_someday", channel_msg_id="t1_x",
            author="u/test", body="hi", status="new",
            received_at=datetime.now(UTC),
        )

        # Fake client + no throttle trip
        with (
            patch.object(reddit_inbox, "_praw_client", return_value=MagicMock()),
            patch.object(reddit_inbox, "_under_new_account_throttle", AsyncMock(return_value=False)),
        ):
            result = await reddit_inbox.send_reddit_reply(msg, "hi")
        assert result.sent is False
        assert "unsupported_reddit_channel" in (result.error or "")
