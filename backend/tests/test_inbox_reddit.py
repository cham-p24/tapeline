"""Coverage for the Reddit poller + outbound adapter.

Critical behaviours:
  - Reply-loop guards: self-authored items skipped, parent-self comments
    skipped (prevents infinite ping-pong)
  - Missing PRAW credentials → poll is a no-op, doesn't crash
  - Channel kill switch (`INBOX_REDDIT_ENABLED=false`) skips poll + send
  - send_reddit_reply errors gracefully on unconfigured / unsupported channel
  - New-account throttle structure exists (full throttle behaviour is
    covered indirectly via the DB SUM, which needs PRAW to introspect)

A regression in the reply-loop guard = infinite recursion incinerating
both API quota AND the bot's Reddit account reputation. Critical.
"""
from __future__ import annotations

from datetime import UTC, datetime
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
    """These guards are the bot's safety against infinite recursion."""

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
        monkeypatch.setenv("REDDIT_CLIENT_ID", "id")
        monkeypatch.setenv("REDDIT_CLIENT_SECRET", "secret")
        get_settings.cache_clear()
        assert reddit_inbox._praw_client() is None


# ── Poll skips ─────────────────────────────────────────────────────────────


class TestPollSkips:
    @pytest.mark.asyncio
    async def test_poll_no_op_when_bot_disabled(self, monkeypatch):
        monkeypatch.setenv("INBOX_BOT_ENABLED", "false")
        for var, val in [
            ("REDDIT_CLIENT_ID", "id"), ("REDDIT_CLIENT_SECRET", "s"),
            ("REDDIT_USERNAME", "u"), ("REDDIT_PASSWORD", "p"),
        ]:
            monkeypatch.setenv(var, val)
        get_settings.cache_clear()

        mock_session = MagicMock()
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
        monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
        get_settings.cache_clear()
        mock_session = MagicMock()
        counts = await reddit_inbox.poll_reddit_inbox(mock_session)
        assert counts["total"] == 0


# ── Outbound adapter ───────────────────────────────────────────────────────


class TestSendRedditReply:
    @pytest.mark.asyncio
    async def test_returns_false_when_no_creds(self, monkeypatch):
        monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
        get_settings.cache_clear()

        from app.models import InboundMessage
        msg = InboundMessage(
            id=1, channel="reddit_dm", channel_msg_id="t4_abc",
            author="u/test", body="hi", status="new",
            received_at=datetime.now(UTC),
        )
        ok = await reddit_inbox.send_reddit_reply(msg, "thanks")
        assert ok is False

    @pytest.mark.asyncio
    async def test_dry_run_short_circuits(self, monkeypatch):
        monkeypatch.setenv("INBOX_DRY_RUN", "true")
        for var, val in [
            ("REDDIT_CLIENT_ID", "id"), ("REDDIT_CLIENT_SECRET", "s"),
            ("REDDIT_USERNAME", "u"), ("REDDIT_PASSWORD", "p"),
        ]:
            monkeypatch.setenv(var, val)
        get_settings.cache_clear()

        from app.models import InboundMessage
        msg = InboundMessage(
            id=1, channel="reddit_dm", channel_msg_id="t4_abc",
            author="u/test", body="hi", status="new",
            received_at=datetime.now(UTC),
        )
        with patch.object(reddit_inbox, "_praw_client") as mock_client:
            ok = await reddit_inbox.send_reddit_reply(msg, "thanks")
        assert ok is True
        # dry-run must NOT have touched the client
        mock_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_channel_disabled_short_circuits(self, monkeypatch):
        monkeypatch.setenv("INBOX_REDDIT_ENABLED", "false")
        get_settings.cache_clear()

        from app.models import InboundMessage
        msg = InboundMessage(
            id=1, channel="reddit_dm", channel_msg_id="t4_abc",
            author="u/test", body="hi", status="new",
            received_at=datetime.now(UTC),
        )
        ok = await reddit_inbox.send_reddit_reply(msg, "thanks")
        assert ok is False
