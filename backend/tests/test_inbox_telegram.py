"""Phase D coverage for the Telegram inbound + approval flow.

Critical behaviours:
  - Founder's /approve_<id> dispatches the suggested_reply, marks approved
  - Founder's /reject_<id> marks status='rejected', no send fires
  - Founder's /edit_<id> sets edit-state; next plain text becomes reply
  - Edit-state has 10-min TTL; stale entries don't consume founder text
  - Non-founder DM goes through classify+route (inserts InboundMessage)
  - Unknown founder command stays quiet (returns handled=False)
  - Already-handled messages can't be re-approved/rejected
  - Approve with no draft prompts to /edit instead of crashing
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import get_settings
from app.db import session_scope
from app.models import InboundMessage
from app.services import inbox_kill_switch, telegram_inbox


FOUNDER_CHAT = "12345"


def _unique_msg_id(prefix: str) -> str:
    """SQLite test.db is shared across runs; unique ids avoid replay
    collisions on the (channel, channel_msg_id) unique constraint."""
    import uuid
    return f"<{prefix}-{uuid.uuid4().hex}@x>"


@pytest.fixture(autouse=True)
def _reset():
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()
    telegram_inbox._reset_edit_state_for_tests()
    yield
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()
    telegram_inbox._reset_edit_state_for_tests()


@pytest.fixture
def founder_env(monkeypatch):
    monkeypatch.setenv("INBOX_FOUNDER_TELEGRAM_CHAT_ID", FOUNDER_CHAT)
    get_settings.cache_clear()


# ── Command parsing ────────────────────────────────────────────────────────


class TestCommandParsing:
    """Verify the parsers match what Telegram actually sends — both bare
    `/approve_123` (DM) and `/approve_123@bot` (group chat suffix)."""

    @pytest.mark.parametrize("text,expected_id", [
        ("/approve_42", 42),
        ("/approve 42", 42),
        ("/approve_42@TapelineBot", 42),
        ("/APPROVE_42", 42),  # case-insensitive
    ])
    def test_approve_regex(self, text, expected_id):
        m = telegram_inbox._APPROVE_RE.match(text)
        assert m is not None, f"failed to match {text!r}"
        assert int(m.group(1)) == expected_id

    @pytest.mark.parametrize("text", [
        "/approve",       # no id
        "approve_42",     # no leading slash
        "/approveall",    # not the command
        "hello world",
    ])
    def test_approve_regex_no_match(self, text):
        assert telegram_inbox._APPROVE_RE.match(text) is None

    def test_edit_regex(self):
        m = telegram_inbox._EDIT_RE.match("/edit_99")
        assert m is not None
        assert int(m.group(1)) == 99

    def test_reject_regex(self):
        m = telegram_inbox._REJECT_RE.match("/reject_7@bot")
        assert m is not None
        assert int(m.group(1)) == 7


# ── Founder commands ───────────────────────────────────────────────────────


class TestFounderApprove:
    @pytest.mark.asyncio
    async def test_approve_with_draft_dispatches(self, founder_env):
        async with session_scope() as session:
            row = InboundMessage(
                channel="email", channel_msg_id=_unique_msg_id("approve-test"),
                author="trader@example.com", body="long msg",
                status="classified", tier=1, tier_reason="real",
                suggested_reply="here's my reply",
                received_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            msg_id = row.id

        async with session_scope() as session:
            with (
                patch("app.services.inbox_reply._adapter_for", AsyncMock(return_value=AsyncMock(
                    return_value=MagicMock(sent=True, error=None, upstream_id="resend-x"),
                ))),
                patch("app.services.telegram.send_message", AsyncMock(return_value=True)),
            ):
                outcome = await telegram_inbox.handle_founder_command(
                    FOUNDER_CHAT, f"/approve_{msg_id}", session,
                )

        assert outcome["handled"] is True
        assert outcome["reason"] == "approved"
        assert outcome["sent"] is True
        # Status check
        async with session_scope() as session:
            after = await session.get(InboundMessage, msg_id)
            assert after.status == "approved"
            assert after.handled_at is not None

    @pytest.mark.asyncio
    async def test_approve_missing_id_responds_not_found(self, founder_env):
        async with session_scope() as session:
            with patch("app.services.telegram.send_message", AsyncMock(return_value=True)) as mock_send:
                outcome = await telegram_inbox.handle_founder_command(
                    FOUNDER_CHAT, "/approve_999999", session,
                )
        assert outcome["reason"] == "not_found"
        mock_send.assert_awaited_once()
        chat_arg, body_arg = mock_send.call_args[0]
        assert "not found" in body_arg.lower()

    @pytest.mark.asyncio
    async def test_approve_with_no_draft_prompts_edit(self, founder_env):
        async with session_scope() as session:
            row = InboundMessage(
                channel="email", channel_msg_id=_unique_msg_id("no-draft"),
                author="trader@x.com", body="msg",
                status="classified", tier=1, suggested_reply=None,
                received_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            msg_id = row.id

        async with session_scope() as session:
            with patch("app.services.telegram.send_message", AsyncMock(return_value=True)) as mock_send:
                outcome = await telegram_inbox.handle_founder_command(
                    FOUNDER_CHAT, f"/approve_{msg_id}", session,
                )
        assert outcome["reason"] == "no_draft"
        body = mock_send.call_args[0][1]
        assert "/edit" in body

    @pytest.mark.asyncio
    async def test_approve_already_handled_returns_warning(self, founder_env):
        async with session_scope() as session:
            row = InboundMessage(
                channel="email", channel_msg_id=_unique_msg_id("already"),
                author="trader@x.com", body="msg",
                status="auto_replied",  # already done
                tier=2,
                received_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            msg_id = row.id

        async with session_scope() as session:
            with patch("app.services.telegram.send_message", AsyncMock(return_value=True)) as mock_send:
                outcome = await telegram_inbox.handle_founder_command(
                    FOUNDER_CHAT, f"/approve_{msg_id}", session,
                )
        assert outcome["reason"] == "already_handled"
        body = mock_send.call_args[0][1]
        assert "already handled" in body.lower()


class TestFounderReject:
    @pytest.mark.asyncio
    async def test_reject_marks_status_no_send(self, founder_env):
        async with session_scope() as session:
            row = InboundMessage(
                channel="email", channel_msg_id=_unique_msg_id("reject-test"),
                author="spammer@x.com", body="msg",
                status="classified", tier=1,
                suggested_reply="don't send me",
                received_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            msg_id = row.id

        async with session_scope() as session:
            with (
                patch("app.services.inbox_reply._adapter_for") as mock_adapter,
                patch("app.services.telegram.send_message", AsyncMock(return_value=True)),
            ):
                outcome = await telegram_inbox.handle_founder_command(
                    FOUNDER_CHAT, f"/reject_{msg_id}", session,
                )
        assert outcome["reason"] == "rejected"
        # No adapter call — we explicitly didn't send
        mock_adapter.assert_not_called()

        async with session_scope() as session:
            after = await session.get(InboundMessage, msg_id)
            assert after.status == "rejected"
            assert after.handled_at is not None


class TestEditStateMachine:
    @pytest.mark.asyncio
    async def test_edit_then_text_dispatches_with_new_body(self, founder_env):
        async with session_scope() as session:
            row = InboundMessage(
                channel="email", channel_msg_id=_unique_msg_id("edit-test"),
                author="trader@x.com", body="msg",
                status="classified", tier=1,
                suggested_reply="original draft",
                received_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            msg_id = row.id

        # Step 1: /edit_<id> sets edit-state
        async with session_scope() as session:
            with patch("app.services.telegram.send_message", AsyncMock(return_value=True)):
                step1 = await telegram_inbox.handle_founder_command(
                    FOUNDER_CHAT, f"/edit_{msg_id}", session,
                )
        assert step1["reason"] == "edit_mode_set"
        assert FOUNDER_CHAT in telegram_inbox._edit_state

        # Step 2: plain text → becomes the reply
        async with session_scope() as session:
            with (
                patch("app.services.inbox_reply._adapter_for", AsyncMock(return_value=AsyncMock(
                    return_value=MagicMock(sent=True, error=None, upstream_id="resend-y"),
                ))),
                patch("app.services.telegram.send_message", AsyncMock(return_value=True)),
            ):
                step2 = await telegram_inbox.handle_founder_command(
                    FOUNDER_CHAT, "actually here's a better reply", session,
                )
        assert step2["reason"] == "edit_applied"
        # Edit-state consumed
        assert FOUNDER_CHAT not in telegram_inbox._edit_state

        async with session_scope() as session:
            after = await session.get(InboundMessage, msg_id)
            assert after.suggested_reply == "actually here's a better reply"
            assert after.status == "approved"

    @pytest.mark.asyncio
    async def test_stale_edit_state_expires(self, founder_env):
        """Edit state older than the TTL should not consume the next
        message — founder might have walked away from the keyboard."""
        # Plant a stale edit state
        telegram_inbox._edit_state[FOUNDER_CHAT] = (
            42, datetime.now(UTC) - timedelta(minutes=20),
        )

        async with session_scope() as session:
            outcome = await telegram_inbox.handle_founder_command(
                FOUNDER_CHAT, "random message", session,
            )
        # Reason should be 'founder_unknown_command' — stale state was GC'd
        assert outcome["reason"] == "founder_unknown_command"


class TestNonFounderDM:
    @pytest.mark.asyncio
    async def test_non_founder_dm_classified(self, founder_env):
        """A random stranger DMs the bot — should classify + insert
        InboundMessage."""
        import uuid
        nonce = uuid.uuid4().hex
        async with session_scope() as session:
            with patch("app.services.inbox_pipeline.classify_and_route", AsyncMock()) as mock_pipeline:
                outcome = await telegram_inbox.handle_inbound_dm(
                    chat_id="99999",
                    text="hi, what's the score for $NVDA?",
                    author="random_user",
                    upstream_id=nonce,
                    session=session,
                )
        assert outcome["handled"] is True
        assert "id" in outcome
        mock_pipeline.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_non_founder_dm_replay_no_double_classify(self, founder_env):
        """Same upstream_id POSTed twice → second call is replay no-op."""
        import uuid
        nonce = uuid.uuid4().hex
        async with session_scope() as session:
            with patch("app.services.inbox_pipeline.classify_and_route", AsyncMock()) as mock_pipeline:
                await telegram_inbox.handle_inbound_dm(
                    chat_id="888", text="hello", author="user",
                    upstream_id=nonce, session=session,
                )
                await telegram_inbox.handle_inbound_dm(
                    chat_id="888", text="hello", author="user",
                    upstream_id=nonce, session=session,
                )
        # Only the first one calls the pipeline
        assert mock_pipeline.await_count == 1


class TestDispatcher:
    @pytest.mark.asyncio
    async def test_dispatcher_routes_founder_vs_stranger(self, founder_env):
        """handle_telegram_update should send founder messages to the
        command handler and strangers to the inbound classifier."""
        founder_update = {
            "message": {
                "chat": {"id": int(FOUNDER_CHAT)},
                "text": "/approve_999",
                "from": {"username": "founder"},
                "message_id": 1,
            }
        }
        async with session_scope() as session:
            with (
                patch.object(telegram_inbox, "handle_founder_command", AsyncMock(return_value={"handled": True})) as mock_fc,
                patch.object(telegram_inbox, "handle_inbound_dm", AsyncMock(return_value={"handled": True})) as mock_dm,
            ):
                await telegram_inbox.handle_telegram_update(founder_update, session)
        mock_fc.assert_awaited_once()
        mock_dm.assert_not_called()

        stranger_update = {
            "message": {
                "chat": {"id": 99999},
                "text": "hello",
                "from": {"username": "random"},
                "message_id": 2,
            }
        }
        async with session_scope() as session:
            with (
                patch.object(telegram_inbox, "handle_founder_command", AsyncMock(return_value={"handled": True})) as mock_fc,
                patch.object(telegram_inbox, "handle_inbound_dm", AsyncMock(return_value={"handled": True})) as mock_dm,
            ):
                await telegram_inbox.handle_telegram_update(stranger_update, session)
        mock_dm.assert_awaited_once()
        mock_fc.assert_not_called()
