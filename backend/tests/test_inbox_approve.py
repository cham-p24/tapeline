"""Regression coverage for founder approval + Telegram callback dispatch.

Guards three bugs found in the 2026-05 line-by-line audit of the inbox bot:

  - **Approve sends synchronously** on the message's own channel and only
    then marks 'sent'. There is no background drain, so a failed/skipped
    send must leave the row at 'approved' for a manual retry — never flip
    it to 'sent'. (audit #1, #4)
  - **The Telegram inline Approve/Reject buttons are reachable.** They ride
    the single unified webhook (Telegram allows one URL per bot), dispatched
    through `process_telegram_update`. A founder button tap must actually
    invoke `_approve_core` / `_reject_core`; a non-action update must return
    None so the webhook's account-link flow still runs. (audit #2)

All external adapters (Resend / Telegram / PRAW) are mocked — no network.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import InboundMessage
from app.routers import inbox as inbox_router


def _msg_id() -> str:
    return f"msg-{uuid.uuid4().hex[:10]}"


async def _insert(
    channel: str,
    *,
    author: str,
    suggested_reply: str | None,
    status: str = "classified",
    subject: str | None = "hi",
) -> int:
    """Insert a Tier 1 InboundMessage and return its id. channel_msg_id is
    always unique so re-running against a persisted test DB never collides
    on the (channel, channel_msg_id) unique constraint."""
    async with SessionLocal() as session:
        msg = InboundMessage(
            channel=channel,
            channel_msg_id=_msg_id(),
            author=author,
            subject=subject,
            body="inbound body that triggered tier 1",
            received_at=datetime.now(UTC),
            tier=1,
            tier_reason="needs founder voice",
            suggested_reply=suggested_reply,
            status=status,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg.id


async def _status(msg_id: int) -> str:
    async with SessionLocal() as session:
        row = (await session.execute(
            select(InboundMessage).where(InboundMessage.id == msg_id)
        )).scalar_one()
        return row.status


# ── _approve_core: per-channel synchronous send ────────────────────────────


class TestApproveCore:
    @pytest.mark.asyncio
    async def test_email_sends_and_marks_sent(self):
        msg_id = await _insert(
            "email", author="reply@example.com",
            suggested_reply="Thanks — here's the detail.",
        )
        with patch(
            "app.services.email.send_email",
            new=AsyncMock(return_value={"id": "re_123"}),
        ) as mock_send:
            async with SessionLocal() as session:
                result = await inbox_router._approve_core(session, msg_id, None)

        assert result["ok"] is True
        assert result["status"] == "sent"
        mock_send.assert_awaited_once()
        kwargs = mock_send.call_args.kwargs
        assert kwargs["to"] == "reply@example.com"
        assert "Thanks" in kwargs["text"]
        assert await _status(msg_id) == "sent"

    @pytest.mark.asyncio
    async def test_email_skipped_stays_approved(self):
        """No API key / undeliverable → nothing went out, so the row must
        NOT be recorded as sent. It stays 'approved' for a manual retry."""
        msg_id = await _insert(
            "email", author="reply@example.com", suggested_reply="Here you go.",
        )
        with patch(
            "app.services.email.send_email",
            new=AsyncMock(return_value={"skipped": True, "reason": "no_api_key"}),
        ):
            async with SessionLocal() as session:
                result = await inbox_router._approve_core(session, msg_id, None)

        assert result["ok"] is False
        assert result["error"] == "send_skipped"
        assert result["reason"] == "no_api_key"
        assert await _status(msg_id) == "approved"

    @pytest.mark.asyncio
    async def test_email_exception_stays_approved(self):
        msg_id = await _insert(
            "email", author="reply@example.com", suggested_reply="Here you go.",
        )
        with patch(
            "app.services.email.send_email",
            new=AsyncMock(side_effect=RuntimeError("resend 500")),
        ):
            async with SessionLocal() as session:
                result = await inbox_router._approve_core(session, msg_id, None)

        assert result["ok"] is False
        assert result["error"] == "send_failed"
        assert await _status(msg_id) == "approved"

    @pytest.mark.asyncio
    async def test_reddit_sends_via_adapter(self):
        msg_id = await _insert(
            "reddit_comment", author="u/someone", suggested_reply="Appreciate it.",
        )
        with patch(
            "app.services.reddit_inbox.send_reddit_reply",
            new=AsyncMock(return_value=True),
        ) as mock_reply:
            async with SessionLocal() as session:
                result = await inbox_router._approve_core(session, msg_id, None)

        assert result["ok"] is True
        assert result["status"] == "sent"
        mock_reply.assert_awaited_once()
        assert await _status(msg_id) == "sent"

    @pytest.mark.asyncio
    async def test_reddit_failure_stays_approved(self):
        msg_id = await _insert(
            "reddit_dm", author="u/someone", suggested_reply="Appreciate it.",
        )
        with patch(
            "app.services.reddit_inbox.send_reddit_reply",
            new=AsyncMock(return_value=False),
        ):
            async with SessionLocal() as session:
                result = await inbox_router._approve_core(session, msg_id, None)

        assert result["ok"] is False
        assert result["error"] == "send_failed"
        assert result["channel"] == "reddit_dm"
        assert await _status(msg_id) == "approved"

    @pytest.mark.asyncio
    async def test_telegram_sends_via_send_message(self):
        msg_id = await _insert(
            "telegram", author="555123",
            suggested_reply="Got it — thanks for the note.",
        )
        with patch(
            "app.services.telegram.send_message",
            new=AsyncMock(return_value=True),
        ) as mock_send:
            async with SessionLocal() as session:
                result = await inbox_router._approve_core(session, msg_id, None)

        assert result["ok"] is True
        mock_send.assert_awaited_once_with("555123", "Got it — thanks for the note.")
        assert await _status(msg_id) == "sent"

    @pytest.mark.asyncio
    async def test_reply_text_overrides_suggested(self):
        """The 'edit' flow: an explicit reply_text wins over the LLM draft."""
        msg_id = await _insert(
            "telegram", author="555123", suggested_reply="ORIGINAL draft.",
        )
        with patch(
            "app.services.telegram.send_message",
            new=AsyncMock(return_value=True),
        ) as mock_send:
            async with SessionLocal() as session:
                result = await inbox_router._approve_core(
                    session, msg_id, "EDITED reply.",
                )

        assert result["ok"] is True
        mock_send.assert_awaited_once_with("555123", "EDITED reply.")

    @pytest.mark.asyncio
    async def test_no_reply_text_errors(self):
        msg_id = await _insert("email", author="x@example.com", suggested_reply=None)
        async with SessionLocal() as session:
            result = await inbox_router._approve_core(session, msg_id, None)
        assert result["ok"] is False
        assert result["error"] == "no_reply_text"

    @pytest.mark.asyncio
    async def test_not_found(self):
        async with SessionLocal() as session:
            result = await inbox_router._approve_core(session, 99_999_999, "hi")
        assert result["ok"] is False
        assert result["error"] == "not_found"

    @pytest.mark.asyncio
    async def test_already_sent_is_noop(self):
        msg_id = await _insert(
            "email", author="x@example.com", suggested_reply="hi", status="sent",
        )
        with patch(
            "app.services.email.send_email",
            new=AsyncMock(return_value={"id": "x"}),
        ) as mock_send:
            async with SessionLocal() as session:
                result = await inbox_router._approve_core(session, msg_id, None)
        assert result["ok"] is True
        assert result.get("already_sent") is True
        mock_send.assert_not_awaited()


# ── process_telegram_update: inline-button + command dispatch ──────────────


def _callback_payload(
    *, data: str, from_id: str, message_id: int = 4242, chat_id: str = "999",
) -> dict:
    return {
        "update_id": 1,
        "callback_query": {
            "id": "cb-1",
            "from": {"id": int(from_id)},
            "data": data,
            "message": {"message_id": message_id, "chat": {"id": int(chat_id)}},
        },
    }


class TestProcessTelegramUpdate:
    @pytest.mark.asyncio
    async def test_founder_approve_callback_dispatches_send(self):
        """A founder tapping ✅ Approve on the alert card must invoke the
        real send, ack the button, and update the card."""
        msg_id = await _insert(
            "email", author="reply@example.com", suggested_reply="Here's the answer.",
        )
        payload = _callback_payload(data=f"inbox:approve:{msg_id}", from_id="999")
        with patch("app.routers.inbox.settings") as mock_settings, \
             patch("app.services.telegram.answer_callback_query",
                   new=AsyncMock(return_value=True)) as mock_ack, \
             patch("app.services.telegram.edit_message_text",
                   new=AsyncMock(return_value=True)) as mock_edit, \
             patch("app.services.email.send_email",
                   new=AsyncMock(return_value={"id": "re_1"})) as mock_send:
            mock_settings.inbox_founder_telegram_chat_id = "999"
            async with SessionLocal() as session:
                result = await inbox_router.process_telegram_update(payload, session)

        assert result is not None
        assert result["ok"] is True
        assert result["action"] == "approve"
        assert result["msg_id"] == msg_id
        assert result["result"]["ok"] is True
        mock_send.assert_awaited_once()   # email actually went out
        mock_ack.assert_awaited_once()    # spinner cleared
        mock_edit.assert_awaited_once()   # card updated to final state
        assert await _status(msg_id) == "sent"

    @pytest.mark.asyncio
    async def test_founder_reject_callback_marks_ignored(self):
        msg_id = await _insert(
            "email", author="reply@example.com", suggested_reply="draft",
        )
        payload = _callback_payload(data=f"inbox:reject:{msg_id}", from_id="999")
        with patch("app.routers.inbox.settings") as mock_settings, \
             patch("app.services.telegram.answer_callback_query",
                   new=AsyncMock(return_value=True)), \
             patch("app.services.telegram.edit_message_text",
                   new=AsyncMock(return_value=True)), \
             patch("app.services.email.send_email", new=AsyncMock()) as mock_send:
            mock_settings.inbox_founder_telegram_chat_id = "999"
            async with SessionLocal() as session:
                result = await inbox_router.process_telegram_update(payload, session)

        assert result["action"] == "reject"
        assert result["result"]["status"] == "ignored"
        mock_send.assert_not_awaited()    # reject never sends a reply
        assert await _status(msg_id) == "ignored"

    @pytest.mark.asyncio
    async def test_non_founder_callback_is_acked_not_actioned(self):
        msg_id = await _insert(
            "email", author="reply@example.com", suggested_reply="draft",
        )
        payload = _callback_payload(data=f"inbox:approve:{msg_id}", from_id="111")
        with patch("app.routers.inbox.settings") as mock_settings, \
             patch("app.services.telegram.answer_callback_query",
                   new=AsyncMock(return_value=True)) as mock_ack, \
             patch("app.services.email.send_email", new=AsyncMock()) as mock_send:
            mock_settings.inbox_founder_telegram_chat_id = "999"
            async with SessionLocal() as session:
                result = await inbox_router.process_telegram_update(payload, session)

        assert result["ignored"] == "non_founder"
        mock_send.assert_not_awaited()
        mock_ack.assert_awaited_once()    # acked so the stranger sees no forever-spinner
        assert await _status(msg_id) == "classified"   # untouched

    @pytest.mark.asyncio
    async def test_malformed_callback_data_ignored(self):
        payload = _callback_payload(data="garbage", from_id="999")
        with patch("app.routers.inbox.settings") as mock_settings, \
             patch("app.services.telegram.answer_callback_query",
                   new=AsyncMock(return_value=True)) as mock_ack:
            mock_settings.inbox_founder_telegram_chat_id = "999"
            async with SessionLocal() as session:
                result = await inbox_router.process_telegram_update(payload, session)

        assert result["ignored"] == "unknown_callback"
        mock_ack.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_command_returns_none_for_link_flow(self):
        """A /start account-link message must fall through (return None) so
        the unified webhook's link-flow handles it. This is the guard that
        inbox dispatch doesn't swallow normal Telegram traffic."""
        payload = {
            "update_id": 7,
            "message": {
                "message_id": 1,
                "from": {"id": 999},
                "chat": {"id": 999},
                "text": "/start abc123",
            },
        }
        with patch("app.routers.inbox.settings") as mock_settings:
            mock_settings.inbox_founder_telegram_chat_id = "999"
            async with SessionLocal() as session:
                result = await inbox_router.process_telegram_update(payload, session)
        assert result is None

    @pytest.mark.asyncio
    async def test_stranger_message_returns_none(self):
        payload = {
            "update_id": 8,
            "message": {
                "message_id": 2,
                "from": {"id": 111},
                "chat": {"id": 111},
                "text": "hello bot",
            },
        }
        with patch("app.routers.inbox.settings") as mock_settings:
            mock_settings.inbox_founder_telegram_chat_id = "999"
            async with SessionLocal() as session:
                result = await inbox_router.process_telegram_update(payload, session)
        assert result is None

    @pytest.mark.asyncio
    async def test_founder_approve_command_dispatches(self):
        """The text-command fallback: /approve_<id> from the founder sends
        the reply and confirms back via DM."""
        msg_id = await _insert(
            "email", author="reply@example.com", suggested_reply="draft",
        )
        payload = {
            "update_id": 9,
            "message": {
                "message_id": 3,
                "from": {"id": 999},
                "chat": {"id": 999},
                "text": f"/approve_{msg_id}",
            },
        }
        with patch("app.routers.inbox.settings") as mock_settings, \
             patch("app.services.telegram.send_message",
                   new=AsyncMock(return_value=True)) as mock_confirm, \
             patch("app.services.email.send_email",
                   new=AsyncMock(return_value={"id": "re_2"})) as mock_email:
            mock_settings.inbox_founder_telegram_chat_id = "999"
            async with SessionLocal() as session:
                result = await inbox_router.process_telegram_update(payload, session)

        assert result["via"] == "command"
        assert result["result"]["ok"] is True
        mock_email.assert_awaited_once()    # the email reply went out
        mock_confirm.assert_awaited_once()  # confirmation DM to founder
        assert await _status(msg_id) == "sent"
