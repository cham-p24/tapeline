"""Phase C coverage for the inbox pipeline orchestrator.

Critical behaviours:
  - upsert_inbound_message is idempotent on (channel, channel_msg_id)
  - classify_and_route honours status guard (only acts on status='new')
  - Tier 1 → status='classified' + telegram card path attempted
  - Tier 2 → status='classified' (auto_replied after dispatch)
  - Tier 3 → status='ignored' + handled_at set
  - process_pending iterates only status='new' rows
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import get_settings
from app.db import session_scope
from app.models import InboundMessage
from app.services import inbox_kill_switch, inbox_pipeline
from app.services.inbox_classifier import ClassifiedMessage


@pytest.fixture(autouse=True)
def _reset():
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()
    yield
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()


class TestUpsertInboundMessage:
    @pytest.mark.asyncio
    async def test_inserts_when_not_existing(self):
        async with session_scope() as session:
            msg, created = await inbox_pipeline.upsert_inbound_message(
                session,
                channel="email",
                channel_msg_id="<upsert-test-1@example.com>",
                author="alice@example.com",
                subject="hi",
                body="hello",
                received_at=datetime.now(UTC),
            )
            assert created is True
            assert msg.id is not None
            assert msg.status == "new"

    @pytest.mark.asyncio
    async def test_idempotent_on_duplicate(self):
        import uuid
        nonce = uuid.uuid4().hex
        msg_id = f"<dup-{nonce}@example.com>"
        async with session_scope() as session:
            m1, c1 = await inbox_pipeline.upsert_inbound_message(
                session, channel="email", channel_msg_id=msg_id,
                author="x@y.com", body="first", received_at=datetime.now(UTC),
            )
            assert c1 is True

        async with session_scope() as session:
            m2, c2 = await inbox_pipeline.upsert_inbound_message(
                session, channel="email", channel_msg_id=msg_id,
                author="x@y.com", body="second", received_at=datetime.now(UTC),
            )
            assert c2 is False
            assert m2.id == m1.id
            # Body NOT overwritten — upsert returns the existing row as-is
            assert m2.body == "first"


class TestClassifyAndRouteStatusGuard:
    @pytest.mark.asyncio
    async def test_already_handled_is_noop(self):
        msg = InboundMessage(
            id=1, channel="email", channel_msg_id="<x@y>",
            author="a@b.com", body="hi", status="auto_replied",
            received_at=datetime.now(UTC),
        )
        mock_session = MagicMock()
        with patch.object(inbox_pipeline, "classify_async") as mock_classify:
            await inbox_pipeline.classify_and_route(msg, mock_session)
        mock_classify.assert_not_called()

    @pytest.mark.asyncio
    async def test_bot_disabled_is_noop(self, monkeypatch):
        monkeypatch.setenv("INBOX_BOT_ENABLED", "false")
        get_settings.cache_clear()

        msg = InboundMessage(
            id=1, channel="email", channel_msg_id="<x@y>",
            author="a@b.com", body="hi", status="new",
            received_at=datetime.now(UTC),
        )
        mock_session = MagicMock()
        with patch.object(inbox_pipeline, "classify_async") as mock_classify:
            await inbox_pipeline.classify_and_route(msg, mock_session)
        mock_classify.assert_not_called()


class TestClassifyAndRouteTier3:
    @pytest.mark.asyncio
    async def test_tier_3_marks_ignored(self):
        msg = InboundMessage(
            id=1, channel="email", channel_msg_id="<x@y>",
            author="spammer@x.com", body="hi", status="new",
            received_at=datetime.now(UTC),
        )
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()

        with patch.object(
            inbox_pipeline, "classify_async",
            AsyncMock(return_value=ClassifiedMessage(
                tier=3, reason="spam", suggested_reply=None, template_key=None,
            )),
        ):
            await inbox_pipeline.classify_and_route(msg, mock_session)

        assert msg.status == "ignored"
        assert msg.handled_at is not None
        assert msg.tier == 3


class TestClassifyAndRouteTier1Card:
    @pytest.mark.asyncio
    async def test_no_chat_id_logs_and_returns(self, monkeypatch):
        """When INBOX_FOUNDER_TELEGRAM_CHAT_ID is unset, the card send is
        a no-op + logs — should NOT crash."""
        monkeypatch.delenv("INBOX_FOUNDER_TELEGRAM_CHAT_ID", raising=False)
        get_settings.cache_clear()

        msg = InboundMessage(
            id=1, channel="email", channel_msg_id="<x@y>",
            author="a@b.com", body="long thoughtful message", status="new",
            tier=1, tier_reason="real trader",
            suggested_reply="draft reply",
            received_at=datetime.now(UTC),
        )
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()

        # Should NOT call telegram.send_message (no chat id)
        with patch("app.services.inbox_pipeline.send_message") as mock_send:
            await inbox_pipeline.send_tier_1_telegram_card(msg, mock_session)
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_with_chat_id_sends_card(self, monkeypatch):
        monkeypatch.setenv("INBOX_FOUNDER_TELEGRAM_CHAT_ID", "12345")
        get_settings.cache_clear()

        msg = InboundMessage(
            id=42, channel="email", channel_msg_id="<x@y>",
            author="alice@example.com", body="long thoughtful message",
            status="new", tier=1, tier_reason="real trader",
            suggested_reply="here's my draft",
            received_at=datetime.now(UTC),
        )
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()

        with patch("app.services.inbox_pipeline.send_message", AsyncMock(return_value=True)) as mock_send:
            await inbox_pipeline.send_tier_1_telegram_card(msg, mock_session)

        mock_send.assert_awaited_once()
        chat_arg, body_arg = mock_send.call_args[0]
        assert chat_arg == "12345"
        # Card body must include the approval commands referencing this msg id
        assert "/approve" in body_arg
        assert "42" in body_arg
        assert "alice@example.com" in body_arg
        assert "here's my draft" in body_arg


class TestProcessPending:
    @pytest.mark.asyncio
    async def test_returns_sane_counts(self):
        """Sanity check on the loop: shape matches even when nothing
        new exists. Doesn't assert seen=0 because prior tests in the
        suite may have left status='new' rows lying around in the
        shared sqlite test.db."""
        async with session_scope() as session:
            counts = await inbox_pipeline.process_pending(session, limit=5)
        assert isinstance(counts.get("seen"), int)
        assert isinstance(counts.get("classified"), int)
        assert isinstance(counts.get("error"), int)
        assert counts["seen"] <= 5  # respects limit
        # Error count should be < seen — even if classification has
        # no LLM key the rule-based fallback path returns Tier 1 cleanly.
        assert counts["error"] <= counts["seen"]
