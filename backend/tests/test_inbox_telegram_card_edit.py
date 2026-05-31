"""Coverage for the in-place Telegram alert-card edit.

When the founder approves or rejects a Tier 1 inbound (via web UI OR
Telegram callback), the original alert card should edit to show
"✅ Approved · sent at HH:MM UTC" / "🗑️ Rejected at HH:MM UTC" so the
founder has a visual cue which Tier 1s they've handled without
stacking confirmation messages on the chat.

Tests:
  - `alert_founder` captures + persists telegram_alert_message_id
  - `alert_founder` returns False + leaves id null when send fails
  - `edit_card_to_done(approved)` builds the right body + calls edit
  - `edit_card_to_done(rejected)` collapses to header-only
  - No-op cleanly when telegram_alert_message_id is null
  - No-op cleanly when chat_id / bot_token missing
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.config import get_settings
from app.models import InboundMessage
from app.services import inbox_telegram_alert, telegram


@pytest.fixture(autouse=True)
def _reset_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _make_message(tid: int | None = None) -> InboundMessage:
    return InboundMessage(
        id=42,
        channel="email",
        channel_msg_id="card-edit-test",
        author="trader@example.com",
        subject="hi",
        body="long thoughtful methodology question…",
        received_at=datetime.now(UTC),
        tier=1,
        tier_reason="Real retail trader, factor-model question",
        suggested_reply="Quick note on factor orthogonality.",
        status="classified",
        telegram_alert_message_id=tid,
    )


class TestAlertFounder:
    @pytest.mark.asyncio
    async def test_stores_message_id_on_success(self, monkeypatch):
        monkeypatch.setenv("INBOX_FOUNDER_TELEGRAM_CHAT_ID", "12345")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        get_settings.cache_clear()
        # The module-level `settings` capture in inbox_telegram_alert is
        # frozen at import; patch the attribute directly so the new env
        # values are seen.
        monkeypatch.setattr(
            inbox_telegram_alert.settings, "inbox_founder_telegram_chat_id", "12345",
        )
        monkeypatch.setattr(
            inbox_telegram_alert.settings, "telegram_bot_token", "test-token",
        )

        msg = _make_message()
        with patch.object(
            telegram, "send_message_with_id", AsyncMock(return_value=999),
        ) as mock_send:
            ok = await inbox_telegram_alert.alert_founder(msg)
        assert ok is True
        assert msg.telegram_alert_message_id == 999
        # Confirm we sent to the right chat with HTML parse mode + inline kb
        args, kwargs = mock_send.call_args
        assert args[0] == "12345"
        assert kwargs["parse_mode"] == "HTML"
        assert "inline_keyboard" in kwargs["reply_markup"]

    @pytest.mark.asyncio
    async def test_returns_false_and_no_id_when_send_fails(self, monkeypatch):
        monkeypatch.setattr(
            inbox_telegram_alert.settings, "inbox_founder_telegram_chat_id", "12345",
        )
        monkeypatch.setattr(
            inbox_telegram_alert.settings, "telegram_bot_token", "test-token",
        )

        msg = _make_message()
        with patch.object(
            telegram, "send_message_with_id", AsyncMock(return_value=None),
        ):
            ok = await inbox_telegram_alert.alert_founder(msg)
        assert ok is False
        assert msg.telegram_alert_message_id is None

    @pytest.mark.asyncio
    async def test_no_chat_id_skips_send(self, monkeypatch):
        monkeypatch.setattr(
            inbox_telegram_alert.settings, "inbox_founder_telegram_chat_id", "",
        )
        msg = _make_message()
        with patch.object(telegram, "send_message_with_id") as mock_send:
            ok = await inbox_telegram_alert.alert_founder(msg)
        assert ok is False
        mock_send.assert_not_called()


class TestEditCardToDone:
    @pytest.mark.asyncio
    async def test_approved_includes_sent_reply(self, monkeypatch):
        monkeypatch.setattr(
            inbox_telegram_alert.settings, "inbox_founder_telegram_chat_id", "12345",
        )
        monkeypatch.setattr(
            inbox_telegram_alert.settings, "telegram_bot_token", "test-token",
        )

        msg = _make_message(tid=999)
        sent_text = "Quick note on factor orthogonality."
        with patch.object(
            telegram, "edit_message_text", AsyncMock(return_value=True),
        ) as mock_edit:
            ok = await inbox_telegram_alert.edit_card_to_done(
                msg, action="approved", sent_reply=sent_text,
            )
        assert ok is True
        args = mock_edit.call_args[0]
        assert args[0] == "12345"
        assert args[1] == 999
        body = args[2]
        assert "Approved" in body
        assert "trader@example.com" in body
        assert sent_text in body

    @pytest.mark.asyncio
    async def test_rejected_collapses_card(self, monkeypatch):
        monkeypatch.setattr(
            inbox_telegram_alert.settings, "inbox_founder_telegram_chat_id", "12345",
        )
        monkeypatch.setattr(
            inbox_telegram_alert.settings, "telegram_bot_token", "test-token",
        )

        msg = _make_message(tid=999)
        with patch.object(
            telegram, "edit_message_text", AsyncMock(return_value=True),
        ) as mock_edit:
            ok = await inbox_telegram_alert.edit_card_to_done(msg, action="rejected")
        assert ok is True
        body = mock_edit.call_args[0][2]
        assert "Rejected" in body
        # Rejected cards must NOT leak any suggested reply / body preview —
        # they're a clean "this was dropped" state.
        assert msg.suggested_reply not in body

    @pytest.mark.asyncio
    async def test_no_op_when_alert_id_is_null(self, monkeypatch):
        """If the alert never sent (tid=None), edit should be a clean no-op."""
        monkeypatch.setattr(
            inbox_telegram_alert.settings, "inbox_founder_telegram_chat_id", "12345",
        )
        monkeypatch.setattr(
            inbox_telegram_alert.settings, "telegram_bot_token", "test-token",
        )

        msg = _make_message(tid=None)
        with patch.object(telegram, "edit_message_text") as mock_edit:
            ok = await inbox_telegram_alert.edit_card_to_done(msg, action="approved")
        assert ok is False
        mock_edit.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_op_when_chat_id_missing(self, monkeypatch):
        monkeypatch.setattr(
            inbox_telegram_alert.settings, "inbox_founder_telegram_chat_id", "",
        )
        msg = _make_message(tid=999)
        with patch.object(telegram, "edit_message_text") as mock_edit:
            ok = await inbox_telegram_alert.edit_card_to_done(msg, action="approved")
        assert ok is False
        mock_edit.assert_not_called()
