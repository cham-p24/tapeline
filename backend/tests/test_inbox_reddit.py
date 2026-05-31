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


# ── Reply-target routing (the t3_-mention-as-reddit_comment bug) ────────────


class TestRedditReplyTarget:
    """Pure routing helper. Must key off the Reddit fullname prefix FIRST:
    a subreddit *mention* is stored under channel='reddit_comment' but its
    fullname is a t3_ submission. Routing on channel alone would call
    client.comment() on a submission id — which PRAW silently no-ops."""

    def test_comment_prefix(self):
        assert reddit_inbox._reddit_reply_target("reddit_comment", "t1_xyz") == ("comment", "xyz")

    def test_submission_prefix(self):
        assert reddit_inbox._reddit_reply_target("reddit_comment", "t3_sub") == ("submission", "sub")

    def test_dm_prefix(self):
        assert reddit_inbox._reddit_reply_target("reddit_dm", "t4_abc") == ("dm", "abc")

    def test_prefix_wins_over_channel(self):
        # mention: stored as reddit_comment but the fullname is a t3_ submission
        assert reddit_inbox._reddit_reply_target("reddit_comment", "t3_post") == ("submission", "post")
        # a t4_ DM mis-tagged as comment still routes to dm
        assert reddit_inbox._reddit_reply_target("reddit_comment", "t4_dm") == ("dm", "dm")

    def test_no_prefix_falls_back_to_channel(self):
        assert reddit_inbox._reddit_reply_target("reddit_dm", "rawid") == ("dm", "rawid")
        assert reddit_inbox._reddit_reply_target("reddit_comment", "rawid") == ("comment", "rawid")

    def test_none_id_is_safe(self):
        assert reddit_inbox._reddit_reply_target("reddit_comment", None) == ("comment", "")


class TestSendRedditReplyRouting:
    """send_reddit_reply must dispatch to the PRAW accessor that matches the
    fullname prefix. Client + new-account throttle are mocked so no network
    or DB introspection happens."""

    @staticmethod
    def _enable(monkeypatch):
        for var, val in [
            ("REDDIT_CLIENT_ID", "id"), ("REDDIT_CLIENT_SECRET", "s"),
            ("REDDIT_USERNAME", "u"), ("REDDIT_PASSWORD", "p"),
        ]:
            monkeypatch.setenv(var, val)
        monkeypatch.delenv("INBOX_DRY_RUN", raising=False)
        monkeypatch.delenv("INBOX_REDDIT_ENABLED", raising=False)
        monkeypatch.setenv("INBOX_BOT_ENABLED", "true")
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_mention_t3_routes_to_submission(self, monkeypatch):
        """The bug that mattered: a mention stored as reddit_comment with a
        t3_ fullname must reply via client.submission(), NOT client.comment()."""
        self._enable(monkeypatch)
        from app.models import InboundMessage
        msg = InboundMessage(
            id=1, channel="reddit_comment", channel_msg_id="t3_post",
            author="u/x", body="hi", status="classified",
            received_at=datetime.now(UTC),
        )
        client = MagicMock()
        reply_obj = MagicMock()
        reply_obj.id = "newcomment"
        client.submission.return_value.reply.return_value = reply_obj

        with patch.object(reddit_inbox, "_praw_client", return_value=client), \
             patch.object(reddit_inbox, "_under_new_account_throttle",
                          new=AsyncMock(return_value=False)):
            ok = await reddit_inbox.send_reddit_reply(msg, "the reply")

        assert ok is True
        client.submission.assert_called_once_with(id="post")
        client.submission.return_value.reply.assert_called_once_with("the reply")
        client.comment.assert_not_called()

    @pytest.mark.asyncio
    async def test_comment_t1_routes_to_comment(self, monkeypatch):
        self._enable(monkeypatch)
        from app.models import InboundMessage
        msg = InboundMessage(
            id=2, channel="reddit_comment", channel_msg_id="t1_c1",
            author="u/x", body="hi", status="classified",
            received_at=datetime.now(UTC),
        )
        client = MagicMock()
        reply_obj = MagicMock()
        reply_obj.id = "r1"
        client.comment.return_value.reply.return_value = reply_obj

        with patch.object(reddit_inbox, "_praw_client", return_value=client), \
             patch.object(reddit_inbox, "_under_new_account_throttle",
                          new=AsyncMock(return_value=False)):
            ok = await reddit_inbox.send_reddit_reply(msg, "the reply")

        assert ok is True
        client.comment.assert_called_once_with(id="c1")
        client.comment.return_value.reply.assert_called_once_with("the reply")
        client.submission.assert_not_called()

    @pytest.mark.asyncio
    async def test_dm_t4_routes_to_inbox_message(self, monkeypatch):
        self._enable(monkeypatch)
        from app.models import InboundMessage
        msg = InboundMessage(
            id=3, channel="reddit_dm", channel_msg_id="t4_d1",
            author="u/x", body="hi", status="classified",
            received_at=datetime.now(UTC),
        )
        client = MagicMock()

        with patch.object(reddit_inbox, "_praw_client", return_value=client), \
             patch.object(reddit_inbox, "_under_new_account_throttle",
                          new=AsyncMock(return_value=False)):
            ok = await reddit_inbox.send_reddit_reply(msg, "the reply")

        assert ok is True
        client.inbox.message.assert_called_once_with("d1")
        client.inbox.message.return_value.reply.assert_called_once_with("the reply")
        client.comment.assert_not_called()
        client.submission.assert_not_called()
