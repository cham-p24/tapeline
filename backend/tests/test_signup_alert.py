"""Founder alerts: a real-time ping on every signup and every subscription.

The delivery rule under test is "exactly one channel fires" — Telegram when
the founder chat id is configured, email otherwise. The email fallback is the
point: without it these alerts are a silent no-op until someone remembers to
set INBOX_FOUNDER_TELEGRAM_CHAT_ID, and revenue lands unannounced.
"""
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import telegram

_TG = SimpleNamespace(
    inbox_founder_telegram_chat_id="12345",
    telegram_bot_token="bot:tok",
    growth_digest_to="founder@example.com",
)
_NO_TG = SimpleNamespace(
    inbox_founder_telegram_chat_id="",
    telegram_bot_token="bot:tok",
    growth_digest_to="founder@example.com",
)


@pytest.mark.asyncio
async def test_notifies_founder_when_configured():
    with patch.object(telegram, "settings", _TG), \
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
async def test_falls_back_to_email_when_chat_id_unset():
    with patch.object(telegram, "settings", _NO_TG), \
         patch.object(telegram, "send_message", new=AsyncMock()) as send, \
         patch("app.services.email.send_email", new=AsyncMock()) as mail:
        await telegram.notify_founder_new_signup(
            email="x@y.com", tier="free", trial_ends_at=None, source="email",
        )
    send.assert_not_awaited()
    mail.assert_awaited_once()
    assert mail.call_args.kwargs["to"] == "founder@example.com"
    assert "x@y.com" in mail.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_telegram_and_email_never_both_fire():
    """Setting the chat id must swap the route, not double every alert."""
    with patch.object(telegram, "settings", _TG), \
         patch.object(telegram, "send_message", new=AsyncMock(return_value=True)), \
         patch("app.services.email.send_email", new=AsyncMock()) as mail:
        await telegram.notify_founder_new_signup(
            email="a@b.com", tier="premium", trial_ends_at=None, source="google",
        )
    mail.assert_not_awaited()


@pytest.mark.asyncio
async def test_never_raises_on_send_failure():
    with patch.object(telegram, "settings", _TG), \
         patch.object(telegram, "send_message", new=AsyncMock(side_effect=RuntimeError("down"))):
        # Must swallow — a notification failure can't break signup.
        await telegram.notify_founder_new_signup(
            email="z@y.com", tier="premium", trial_ends_at=None, source="google",
        )


@pytest.mark.asyncio
async def test_never_raises_when_email_fallback_fails():
    with patch.object(telegram, "settings", _NO_TG), \
         patch("app.services.email.send_email", new=AsyncMock(side_effect=RuntimeError("resend down"))):
        await telegram.notify_founder_new_signup(
            email="z@y.com", tier="premium", trial_ends_at=None, source="google",
        )


@pytest.mark.asyncio
async def test_subscription_alert_carries_tier_and_amount():
    with patch.object(telegram, "settings", _TG), \
         patch.object(telegram, "send_message", new=AsyncMock(return_value=True)) as send:
        await telegram.notify_founder_new_subscription(
            email="payer@example.com", tier="pro",
            billing_period="annual", amount=99.0, currency="usd",
        )
    body = send.call_args.args[1]
    assert "payer@example.com" in body
    assert "pro" in body
    assert "annual" in body
    assert "99.00 USD" in body


@pytest.mark.asyncio
async def test_subscription_alert_survives_missing_amount():
    """Stripe doesn't always expand price.unit_amount — don't crash on None."""
    with patch.object(telegram, "settings", _NO_TG), \
         patch("app.services.email.send_email", new=AsyncMock()) as mail:
        await telegram.notify_founder_new_subscription(
            email="payer@example.com", tier="premium",
            billing_period=None, amount=None, currency=None,
        )
    body = mail.call_args.kwargs["text"]
    assert "payer@example.com" in body
    assert "premium" in body
