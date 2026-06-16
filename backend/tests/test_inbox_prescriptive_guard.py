"""Runtime publisher-safety guard — server-side advice-language block.

Tapeline's AU publisher-exemption posture depends on NEVER emitting
prescriptive financial advice in an automated reply. Before this guard the
rule was enforced ONLY in tests against the static template renderers
(tests/test_inbox_voice_rules.py); there was no RUNTIME check on the wire, so
a Tier-1 LLM draft that drifted off the voice rules could be one-tap-approved
straight onto the channel, and a Tier-2 template interpolating a live API
`signal` label could auto-send unguarded.

These tests lock the guard down at three layers:
  - `find_prescriptive_phrase` unit semantics (boundaries, whitespace,
    false-positive safety).
  - `_approve_core` fails CLOSED on a banned draft — no send, row untouched.
  - The Tier-2 email auto-send path refuses to deliver a banned reply.

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
from app.services.inbox_router import find_prescriptive_phrase


def _msg_id() -> str:
    return f"msg-{uuid.uuid4().hex[:10]}"


async def _insert(
    channel: str,
    *,
    author: str,
    suggested_reply: str | None,
    status: str = "classified",
) -> int:
    async with SessionLocal() as session:
        msg = InboundMessage(
            channel=channel,
            channel_msg_id=_msg_id(),
            author=author,
            subject="hi",
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


# ── Unit: find_prescriptive_phrase ─────────────────────────────────────────


class TestFindPrescriptivePhrase:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("You should buy $NVDA now", "buy"),
            ("I'd sell that position", "sell"),
            ("you should wait for the breakout", "you should"),
            ("We recommend the Premium tier", "we recommend"),
            ("I recommend pulling the trigger", "i recommend"),
            ("guaranteed returns by Friday", "guaranteed"),
            ("this one will moon", "will moon"),
            ("it's going to rip higher", "going to"),
            # boundary at start / end of string
            ("buy now", "buy"),
            ("time to sell", "sell"),
            # whitespace / newline obfuscation collapses
            ("you   should consider it", "you should"),
            ("you\nshould look", "you should"),
        ],
    )
    def test_flags_banned(self, text: str, expected: str):
        assert find_prescriptive_phrase(text) == expected

    @pytest.mark.parametrize(
        "text",
        [
            "$NVDA scores 87.2/100 (HIGH CONVICTION).",
            "It's a buyer's market right now",          # 'buyer' must not trip ' buy '
            "That's a strong selling point",            # 'selling' must not trip ' sell '
            "The free tier covers the top 20 tickers.",
            "Thanks for the kind words.",
            "",
            "   ",
        ],
    )
    def test_publisher_safe_passes(self, text: str):
        assert find_prescriptive_phrase(text) is None


# ── _approve_core fails CLOSED on a banned reply ───────────────────────────


class TestApproveCoreGuard:
    @pytest.mark.asyncio
    async def test_banned_suggested_reply_blocks_send(self):
        """An LLM draft that drifted into advice must never go out — even on
        approve. The send adapter is NOT called and the row stays untouched."""
        msg_id = await _insert(
            "email", author="reply@example.com",
            suggested_reply="Honestly you should buy $NVDA before earnings.",
        )
        with patch(
            "app.services.email.send_email", new=AsyncMock(),
        ) as mock_send:
            async with SessionLocal() as session:
                result = await inbox_router._approve_core(session, msg_id, None)

        assert result["ok"] is False
        assert result["error"] == "prescriptive_language"
        assert result["phrase"] == "you should"
        mock_send.assert_not_awaited()           # nothing went on the wire
        assert await _status(msg_id) == "classified"   # row untouched, not 'sent'

    @pytest.mark.asyncio
    async def test_banned_edited_reply_text_blocks_send(self):
        """The founder's own typed override is guarded too — the guard is on
        the outbound text, not on its provenance."""
        msg_id = await _insert(
            "telegram", author="555123", suggested_reply="clean original draft.",
        )
        with patch(
            "app.services.telegram.send_message", new=AsyncMock(),
        ) as mock_send:
            async with SessionLocal() as session:
                result = await inbox_router._approve_core(
                    session, msg_id, "Sure — sell half and hold the rest.",
                )

        assert result["ok"] is False
        assert result["error"] == "prescriptive_language"
        assert result["phrase"] == "sell"
        mock_send.assert_not_awaited()
        assert await _status(msg_id) == "classified"

    @pytest.mark.asyncio
    async def test_clean_reply_still_sends(self):
        """Regression: a publisher-safe reply is unaffected by the guard."""
        msg_id = await _insert(
            "email", author="reply@example.com",
            suggested_reply="The scanner shows $NVDA at 87/100 (high conviction).",
        )
        with patch(
            "app.services.email.send_email",
            new=AsyncMock(return_value={"id": "re_ok"}),
        ) as mock_send:
            async with SessionLocal() as session:
                result = await inbox_router._approve_core(session, msg_id, None)

        assert result["ok"] is True
        assert result["status"] == "sent"
        mock_send.assert_awaited_once()
        assert await _status(msg_id) == "sent"


# ── Tier-2 email auto-send path refuses banned reply ───────────────────────


class TestTier2AutoSendGuard:
    @pytest.mark.asyncio
    async def test_tier2_autosend_blocked_on_banned_signal(self):
        """If a Tier-2 template ever renders a banned phrase (e.g. a live API
        `signal` label leaks 'sell'), the email auto-send is suppressed and
        the row is left for founder review rather than shipping advice."""

        class _Msg:
            id = 0

        class _Result:
            tier = 2
            auto_reply_text = "$ABC scores 12/100 — time to sell."
            already_handled = False
            message = _Msg()

        async def _fake_handle_inbound(*_a, **_kw):
            return _Result()

        payload = {
            "type": "email.received",
            "data": {
                "message_id": _msg_id(),
                "from": "curious@example.com",
                "subject": "score?",
                "text": "what's $ABC at?",
            },
        }

        # _verify_resend_signature returns True when no secret is configured
        # (dev bypass) so we can drive email_inbound directly with a fake Request.
        class _Req:
            async def body(self):
                return b"{}"

            async def json(self):
                return payload

        # email_inbound binds `handle_inbound` into its own module namespace at
        # import time, so patch the name on app.routers.inbox (not the service).
        with patch("app.routers.inbox.handle_inbound", new=_fake_handle_inbound), \
             patch("app.services.email.send_email", new=AsyncMock()) as mock_send:
            async with SessionLocal() as session:
                out = await inbox_router.email_inbound(
                    request=_Req(),               # type: ignore[arg-type]
                    svix_signature=None,
                    resend_signature=None,
                    session=session,
                )

        assert out["auto_replied"] is False
        assert out["blocked"] == "prescriptive_language"
        assert out["phrase"] == "sell"
        mock_send.assert_not_awaited()
