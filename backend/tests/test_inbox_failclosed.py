"""Inbox webhook auth must fail CLOSED in production.

Two pre-go-live hardening fixes: when the relevant secret is UNSET, the
endpoint rejects in production (instead of silently accepting), while staying
permissive in development/staging for local testing.
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.db import SessionLocal
from app.routers import inbox as inbox_router


def _callback_payload(*, data: str, from_id: str) -> dict:
    return {
        "callback_query": {
            "id": "cb-test",
            "from": {"id": from_id},
            "data": data,
            "message": {"message_id": 1, "chat": {"id": from_id}},
        }
    }


class TestResendSignatureFailClosed:
    def test_unset_secret_rejected_in_production(self):
        with patch("app.routers.inbox.settings") as s:
            s.resend_inbound_secret = ""
            s.app_env = "production"
            # No secret configured in prod -> unsigned webhook is rejected.
            assert inbox_router._verify_resend_signature(b"{}", None) is False

    def test_unset_secret_bypassed_in_development(self):
        with patch("app.routers.inbox.settings") as s:
            s.resend_inbound_secret = ""
            s.app_env = "development"
            # Local/dev convenience bypass is preserved.
            assert inbox_router._verify_resend_signature(b"{}", None) is True


class TestTelegramFounderFailClosed:
    @pytest.mark.asyncio
    async def test_unset_founder_rejects_callback_in_production(self):
        """In prod, an unset founder chat id means nobody is authorised — a
        stranger's button tap must NOT trigger a send."""
        payload = _callback_payload(data="inbox:approve:1", from_id="12345")
        with patch("app.routers.inbox.settings") as s, \
             patch("app.services.telegram.answer_callback_query",
                   new=AsyncMock(return_value=True)) as mock_ack, \
             patch("app.routers.inbox._approve_core",
                   new=AsyncMock(return_value={"ok": True})) as mock_approve:
            s.inbox_founder_telegram_chat_id = ""
            s.app_env = "production"
            async with SessionLocal() as session:
                result = await inbox_router.process_telegram_update(payload, session)

        assert result["ignored"] == "non_founder"   # fail closed
        mock_approve.assert_not_awaited()            # no action taken
        mock_ack.assert_awaited_once()               # spinner still cleared

    @pytest.mark.asyncio
    async def test_unset_founder_allowed_in_development(self):
        """Dev convenience preserved: with no founder id set, a tap still works
        locally so the bot is testable without configuring the chat id."""
        payload = _callback_payload(data="inbox:approve:1", from_id="12345")
        with patch("app.routers.inbox.settings") as s, \
             patch("app.services.telegram.answer_callback_query",
                   new=AsyncMock(return_value=True)), \
             patch("app.services.telegram.edit_message_text",
                   new=AsyncMock(return_value=True)), \
             patch("app.routers.inbox._approve_core",
                   new=AsyncMock(return_value={"ok": True})) as mock_approve:
            s.inbox_founder_telegram_chat_id = ""
            s.app_env = "development"
            async with SessionLocal() as session:
                result = await inbox_router.process_telegram_update(payload, session)

        assert result.get("ignored") != "non_founder"   # not rejected in dev
        mock_approve.assert_awaited_once()               # action proceeds
