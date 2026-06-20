"""The founder gets a real-time Telegram ping on every new signup."""
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import telegram


@pytest.mark.asyncio
async def test_notifies_founder_when_configured():
    stub = SimpleNamespace(
        inbox_founder_telegram_chat_id="12345", telegram_bot_token="bot:tok"
    )
    with patch.object(telegram, "settings", stub), \
         patch.object(telegram, "send_message", new=AsyncMock(return_value=True)) as send:
        await telegram.notify_founder_new_signup(
            email="new@example.com", tier="premium",
            trial_ends_at=datetime(2026, 6, 30, tzinfo=UTC), source="email",
        )
    send.assert_awaited_once()
    body = send.call_args.args[1]
    assert "new@example.com" in body
    assert "premium" in body
    assert "2026-06-30" in body


@pytest.mark.asyncio
async def test_noop_when_chat_id_unset():
    stub = SimpleNamespace(inbox_founder_telegram_chat_id="", telegram_bot_token="bot:tok")
    with patch.object(telegram, "settings", stub), \
         patch.object(telegram, "send_message", new=AsyncMock()) as send:
        await telegram.notify_founder_new_signup(
            email="x@y.com", tier="free", trial_ends_at=None, source="email",
        )
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_never_raises_on_send_failure():
    stub = SimpleNamespace(
        inbox_founder_telegram_chat_id="12345", telegram_bot_token="bot:tok"
    )
    with patch.object(telegram, "settings", stub), \
         patch.object(telegram, "send_message", new=AsyncMock(side_effect=RuntimeError("down"))):
        # Must swallow — a notification failure can't break signup.
        await telegram.notify_founder_new_signup(
            email="z@y.com", tier="premium", trial_ends_at=None, source="google",
        )
