"""Phase B integration coverage for the inbox router.

Tests cover:
  - Idempotency: same channel + channel_msg_id is a no-op
  - Tier 2 with template → renders canonical reply
  - Tier 1 fallback → stores classified, no auto-reply
  - Tier 3 spam → stores ignored, no auto-reply
  - Telegram alert is a clean no-op when chat_id env var isn't set

These tests don't hit the real Resend API or live ticker API.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import InboundMessage
from app.services import inbox_templates
from app.services.inbox_router import handle_inbound, mark_sent
from app.services.inbox_telegram_alert import alert_founder


def _msg_id() -> str:
    return f"msg-{uuid.uuid4().hex[:10]}"


@pytest.mark.asyncio
async def test_tier_3_spam_stores_ignored_no_reply():
    async with SessionLocal() as session:
        result = await handle_inbound(
            session,
            channel="email",
            channel_msg_id=_msg_id(),
            author="spammer@example.com",
            body="Join my telegram channel for 100x signals!",
            received_at=datetime.now(UTC),
            subject="🚀 PUMP ALERT",
        )
        assert result.tier == 3
        assert result.auto_reply_text is None
        assert result.message.status == "ignored"
        assert not result.already_handled


@pytest.mark.asyncio
async def test_tier_2_pricing_renders_canonical_reply():
    async with SessionLocal() as session:
        result = await handle_inbound(
            session,
            channel="email",
            channel_msg_id=_msg_id(),
            author="curious@example.com",
            body="Hey — how does your pricing work?",
            received_at=datetime.now(UTC),
            subject="Pricing question",
        )
        assert result.tier == 2
        assert result.auto_reply_text is not None
        assert "$24.99" in result.auto_reply_text or "$29.99" in result.auto_reply_text
        assert "Premium trial" in result.auto_reply_text
        assert result.message.status == "auto_replied"


@pytest.mark.asyncio
async def test_tier_2_thanks_renders_canonical_reply():
    async with SessionLocal() as session:
        result = await handle_inbound(
            session,
            channel="email",
            channel_msg_id=_msg_id(),
            author="fan@example.com",
            body="Love this tool!",
            received_at=datetime.now(UTC),
        )
        assert result.tier == 2
        assert result.auto_reply_text is not None
        lo = result.auto_reply_text.lower()
        assert "kind words" in lo or "thanks" in lo


@pytest.mark.asyncio
async def test_tier_1_long_methodology_question_stores_classified():
    body = (
        "Quick methodology question on the Smart Money pillar — "
        "how do you weight insider Form 4 buys when the same insider "
        "has been a serial buyer over multiple quarters? Genuine "
        "curiosity, not gotcha. The 90-day window in your formula "
        "would catch the latest buy but ignore the pattern."
    )
    async with SessionLocal() as session:
        result = await handle_inbound(
            session,
            channel="email",
            channel_msg_id=_msg_id(),
            author="trader@hedgefund.com",
            body=body,
            received_at=datetime.now(UTC),
            subject="Smart Money pillar methodology",
        )
        assert result.tier == 1
        assert result.auto_reply_text is None
        assert result.message.status == "classified"


@pytest.mark.asyncio
async def test_idempotent_on_duplicate_channel_msg_id():
    """Polling the same Reddit comment twice should no-op the second
    time and return the existing row."""
    dup_id = f"t1_{uuid.uuid4().hex[:10]}"
    async with SessionLocal() as session:
        first = await handle_inbound(
            session,
            channel="reddit_comment",
            channel_msg_id=dup_id,
            author="someone",
            body="$NVDA score?",
            received_at=datetime.now(UTC),
        )
        await session.commit()
        assert not first.already_handled
        first_id = first.message.id

    async with SessionLocal() as session:
        second = await handle_inbound(
            session,
            channel="reddit_comment",
            channel_msg_id=dup_id,
            author="someone",
            body="$NVDA score?",
            received_at=datetime.now(UTC),
        )
        assert second.already_handled
        assert second.message.id == first_id


@pytest.mark.asyncio
async def test_mark_sent_updates_status():
    async with SessionLocal() as session:
        result = await handle_inbound(
            session,
            channel="email",
            channel_msg_id=_msg_id(),
            author="anyone@example.com",
            body="How does the free trial work?",
            received_at=datetime.now(UTC),
        )
        msg_id = result.message.id
        await session.commit()

    async with SessionLocal() as session:
        when = datetime.now(UTC)
        await mark_sent(session, msg_id, when=when)
        await session.commit()

    async with SessionLocal() as session:
        row = (await session.execute(
            select(InboundMessage).where(InboundMessage.id == msg_id)
        )).scalar_one()
        assert row.status == "sent"
        assert row.handled_at is not None


# --- Template renderers (no DB) --------------------------------------------

@pytest.mark.asyncio
async def test_pricing_template_returns_string():
    result = await inbox_templates.render("pricing", "any body")
    assert isinstance(result, str)
    assert "$24.99" in result or "$29.99" in result


@pytest.mark.asyncio
async def test_trial_template_mentions_no_card():
    result = await inbox_templates.render("trial", "free trial?")
    assert isinstance(result, str)
    assert "no card" in result.lower() or "no credit" in result.lower()


@pytest.mark.asyncio
async def test_thanks_template_invites_ticker_question():
    result = await inbox_templates.render("thanks", "love this")
    assert isinstance(result, str)
    assert "ticker" in result.lower() or "$NVDA" in result


@pytest.mark.asyncio
async def test_unknown_template_returns_none():
    result = await inbox_templates.render("nonexistent_template", "anything")
    assert result is None


@pytest.mark.asyncio
async def test_ticker_score_template_handles_missing_cashtag():
    """If the body has no cashtag, ticker_score render returns None
    (caller falls back to LLM/Tier 1 routing)."""
    result = await inbox_templates.render("ticker_score", "no cashtag here")
    assert result is None


# --- Telegram alert (no-op when chat_id unset) -----------------------------

@pytest.mark.asyncio
async def test_alert_founder_noops_when_chat_id_unset():
    """alert_founder() must NOT raise when env var isn't configured —
    dev environments don't have a chat_id."""
    async with SessionLocal() as session:
        msg = InboundMessage(
            channel="email",
            channel_msg_id=_msg_id(),
            author="someone@example.com",
            subject="test",
            body="long message that triggered tier 1",
            received_at=datetime.now(UTC),
            tier=1,
            tier_reason="rule-based didn't match; needs review",
            suggested_reply=None,
            status="classified",
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)

    with patch("app.services.inbox_telegram_alert.settings") as mock_settings:
        mock_settings.inbox_founder_telegram_chat_id = ""
        mock_settings.telegram_bot_token = ""
        result = await alert_founder(msg)
    assert result is False  # skipped, not raised
