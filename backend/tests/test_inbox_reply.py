"""Phase A.6 coverage for the reply templates + dispatcher.

Critical behaviours:
  - Templates render in founder voice (first-person, descriptive only)
  - Ticker template handles missing/unknown symbols gracefully
  - render_template_for() routes to the right renderer + extracts cashtag
  - Dispatcher honours bot_enabled / channel_enabled / dry_run gates
  - send_tier_2_auto_reply is idempotent against already-handled messages
  - send_tier_2_auto_reply falls back to Tier 1 when template can't render

A regression in the voice-rule tests = the bot starts using prescriptive
language ("buy", "you should") which breaks the AFSL publisher-exemption
posture. Treat those as legal-critical.
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import get_settings
from app.models import InboundMessage, Ticker
from app.services import inbox_kill_switch, inbox_reply


@pytest.fixture(autouse=True)
def _reset_settings():
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()
    yield
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()


def _make_message(
    *, channel: str = "reddit_dm", body: str = "", author: str = "alice",
    status: str = "new", tier: int | None = None,
) -> InboundMessage:
    return InboundMessage(
        id=1,
        channel=channel,
        channel_msg_id=f"{channel}:abc123",
        author=author,
        subject=None,
        body=body,
        received_at=datetime.now(UTC),
        tier=tier,
        status=status,
    )


def _make_ticker(symbol="NVDA", score=87.2, signal="HIGH CONVICTION") -> Ticker:
    return Ticker(
        symbol=symbol,
        name=symbol,
        sector="Technology",
        asset_class="equity",
        score=score,
        signal=signal,
        price=900.0,
        change_pct_1d=2.1,
        change_pct_5d=4.4,
        change_pct_1m=15.0,
        volume=12345678,
        sub_trend=88, sub_rs=85, sub_fundamentals=80,
        sub_momentum=90, sub_macro=72, sub_smart_money=92,
        confidence_pct=95.0,
        reason="trend + smart money both top decile",
    )


# ── Template rendering ──────────────────────────────────────────────────────


class TestVoiceRules:
    """Legal posture: descriptive language only, never prescriptive.
    `buy`, `sell`, `you should`, `recommend` are all disallowed in any
    template body. Regressions here break the publisher-exemption from
    AFSL."""

    @pytest.mark.parametrize("body", [
        inbox_reply.render_pricing(),
        inbox_reply.render_trial(),
        inbox_reply.render_thanks(),
        inbox_reply.render_tier_1_5_ack(),
        inbox_reply.render_ticker_score("NVDA", _make_ticker()),
        inbox_reply.render_ticker_score("FAKEZZZ", None),
    ])
    def test_no_prescriptive_language(self, body: str):
        lower = body.lower()
        for banned in (
            " buy ", " sell ", "you should",
            "we recommend", "i recommend",
            "guaranteed", "will moon", "going to ",
        ):
            assert banned not in lower, (
                f"Banned prescriptive phrase {banned!r} in template body:\n{body}"
            )

    @pytest.mark.parametrize("body", [
        inbox_reply.render_pricing(),
        inbox_reply.render_trial(),
        inbox_reply.render_thanks(),
        inbox_reply.render_tier_1_5_ack(),
    ])
    def test_first_person_singular(self, body: str):
        """Founder is solo — replies are 'I', never 'we'. (Templates may
        say 'we won't' in places where it'd sound weird; this test is the
        regression guard but doesn't have to be absolutist.)"""
        # Soft check: must not start with "We" (the common offender).
        assert not body.strip().startswith("We "), (
            f"Reply starts with 'We', should be first-person singular:\n{body}"
        )

    def test_no_signature(self):
        """Voice-rule: bot replies are UNSIGNED. The body IS the voice —
        no '— Christian' / '— Chamara' at the end."""
        for renderer in (
            inbox_reply.render_pricing, inbox_reply.render_trial,
            inbox_reply.render_thanks, inbox_reply.render_tier_1_5_ack,
        ):
            body = renderer()
            assert "Christian" not in body, f"Reply contains 'Christian' signature: {renderer.__name__}"
            assert "Chamara" not in body, f"Reply contains 'Chamara' name: {renderer.__name__}"
            assert not body.rstrip().endswith("Christian"), renderer.__name__
            assert not body.rstrip().endswith("— Christian"), renderer.__name__


class TestTickerScoreTemplate:
    def test_known_ticker_includes_score_and_breakdown(self):
        t = _make_ticker("NVDA", 87.2, "HIGH CONVICTION")
        body = inbox_reply.render_ticker_score("NVDA", t)
        assert "$NVDA" in body
        assert "87.2/100" in body
        assert "HIGH CONVICTION" in body
        # All six factor labels present
        for label in ("Trend", "RS", "Fundamentals", "Smart Money", "Macro", "Momentum"):
            assert label in body, f"missing factor label {label!r}: {body}"
        assert "tapeline.io/t/NVDA" in body

    def test_lowercase_symbol_normalised(self):
        t = _make_ticker("aapl", 65.0, "CONSTRUCTIVE")
        body = inbox_reply.render_ticker_score("aapl", t)
        # Symbol should appear uppercase in the human-readable body
        assert "$AAPL" in body
        # URL too
        assert "tapeline.io/t/AAPL" in body

    def test_leading_dollar_sign_stripped(self):
        t = _make_ticker("TSLA", 55.0, "CONSTRUCTIVE")
        body = inbox_reply.render_ticker_score("$TSLA", t)
        # Should render as $TSLA, not $$TSLA
        assert "$$" not in body
        assert "$TSLA" in body

    def test_unknown_ticker_polite_fallback(self):
        body = inbox_reply.render_ticker_score("FAKEZZZ", None)
        # Should NOT pretend to know — should explicitly say it's not in
        # the universe
        assert "FAKEZZZ" in body
        assert "universe" in body.lower()
        # And must not contain a fake score
        assert "/100" not in body

    def test_ticker_with_null_score_is_treated_as_unknown(self):
        """A Ticker row exists but the worker hasn't scored it yet (null
        score) — should fall through to the 'not in universe' message,
        not crash or render '/100' with no number."""
        t = _make_ticker("NEW", 0, "")
        t.score = None
        t.signal = None
        body = inbox_reply.render_ticker_score("NEW", t)
        assert "NEW" in body
        assert "universe" in body.lower()
        assert "None" not in body  # belt + braces — no Python None leaked


# ── render_template_for ─────────────────────────────────────────────────────


class TestRenderTemplateFor:
    @pytest.mark.asyncio
    async def test_unknown_template_key_returns_none(self):
        mock_session = MagicMock()
        result = await inbox_reply.render_template_for(
            "totally-fake-key", "hello", mock_session,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_pricing_template_resolves(self):
        mock_session = MagicMock()
        result = await inbox_reply.render_template_for(
            "pricing", "how much is it", mock_session,
        )
        assert result is not None
        assert "Pro" in result
        assert "Premium" in result

    @pytest.mark.asyncio
    async def test_ticker_score_with_no_cashtag_returns_none(self):
        """Classifier should never call ticker_score without a cashtag,
        but defensive: caller (send_tier_2_auto_reply) downgrades to
        manual review when this returns None."""
        mock_session = MagicMock()
        result = await inbox_reply.render_template_for(
            "ticker_score", "no cashtags here", mock_session,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_ticker_score_with_cashtag_hits_db(self):
        """Extracts $NVDA from the body, calls session.get(Ticker, 'NVDA'),
        renders the template with the returned Ticker."""
        fake_ticker = _make_ticker("NVDA", 87.2, "HIGH CONVICTION")
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=fake_ticker)

        result = await inbox_reply.render_template_for(
            "ticker_score", "what's the score for $NVDA?", mock_session,
        )
        mock_session.get.assert_awaited_once_with(Ticker, "NVDA")
        assert result is not None
        assert "$NVDA" in result
        assert "87.2/100" in result


# ── Dispatcher ──────────────────────────────────────────────────────────────


class TestDispatchReply:
    @pytest.mark.asyncio
    async def test_bot_disabled_skips_send(self, monkeypatch):
        monkeypatch.setenv("INBOX_BOT_ENABLED", "false")
        get_settings.cache_clear()

        message = _make_message(channel="email", author="x@y.com")
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()

        with patch.object(inbox_reply, "_adapter_for") as mock_adapter:
            result = await inbox_reply.dispatch_reply(
                message, "hello", mock_session,
            )

        assert result.sent is False
        assert result.error == "bot_disabled"
        mock_adapter.assert_not_called()
        # Status MUST NOT change — message stays 'new' so a re-enable
        # picks it up on the next tick.
        assert message.status == "new"

    @pytest.mark.asyncio
    async def test_channel_disabled_skips_send(self, monkeypatch):
        monkeypatch.setenv("INBOX_REDDIT_ENABLED", "false")
        get_settings.cache_clear()

        message = _make_message(channel="reddit_dm")
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()

        with patch.object(inbox_reply, "_adapter_for") as mock_adapter:
            result = await inbox_reply.dispatch_reply(
                message, "hello", mock_session,
            )

        assert result.sent is False
        assert "channel_disabled" in (result.error or "")
        mock_adapter.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_logs_but_skips_upstream(self, monkeypatch):
        monkeypatch.setenv("INBOX_DRY_RUN", "true")
        get_settings.cache_clear()

        message = _make_message(channel="email", author="x@y.com")
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()

        with patch.object(inbox_reply, "_adapter_for") as mock_adapter:
            result = await inbox_reply.dispatch_reply(
                message, "hello", mock_session,
            )

        assert result.sent is True
        assert result.upstream_id == "dry-run"
        mock_adapter.assert_not_called()
        # Status reflects dry-run mode so the admin UI can distinguish it
        assert message.status.startswith("dry_run_")
        assert message.handled_at is not None

    @pytest.mark.asyncio
    async def test_successful_send_marks_handled(self):
        message = _make_message(channel="email", author="x@y.com")
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()

        async def _fake_adapter(_msg, _body):
            return inbox_reply.ReplyResult(sent=True, upstream_id="resend-123")

        with patch.object(
            inbox_reply, "_adapter_for", AsyncMock(return_value=_fake_adapter),
        ):
            result = await inbox_reply.dispatch_reply(
                message, "hello", mock_session, new_status="auto_replied",
            )

        assert result.sent is True
        assert result.upstream_id == "resend-123"
        assert message.status == "auto_replied"
        assert message.handled_at is not None

    @pytest.mark.asyncio
    async def test_failed_send_leaves_status_alone(self):
        """Failed sends MUST leave status unchanged so the next worker
        tick retries. Setting status=error would silently drop the
        retry path."""
        message = _make_message(channel="email", author="x@y.com")
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()

        async def _fake_adapter(_msg, _body):
            return inbox_reply.ReplyResult(
                sent=False, error="timeout",
            )

        with patch.object(
            inbox_reply, "_adapter_for", AsyncMock(return_value=_fake_adapter),
        ):
            result = await inbox_reply.dispatch_reply(
                message, "hello", mock_session,
            )

        assert result.sent is False
        # Status untouched
        assert message.status == "new"
        assert message.handled_at is None


class TestSendTier2AutoReply:
    @pytest.mark.asyncio
    async def test_idempotent_against_already_handled(self):
        """Auto-replied / approved / sent messages must no-op on a
        re-tick — otherwise the poller can double-send."""
        message = _make_message(
            channel="email", author="x@y.com", status="auto_replied",
        )
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()

        result = await inbox_reply.send_tier_2_auto_reply(
            message, "pricing", mock_session,
        )
        assert result.sent is False
        assert "already_handled" in (result.error or "")

    @pytest.mark.asyncio
    async def test_template_render_failure_downgrades_to_tier_1(self):
        """If the classifier picked 'ticker_score' but no cashtag is in
        the body, we MUST NOT send a half-baked reply — downgrade to
        Tier 1 manual review."""
        message = _make_message(
            channel="email", author="x@y.com",
            body="actually I have no cashtag here", status="new",
        )
        mock_session = MagicMock()
        mock_session.commit = AsyncMock()

        result = await inbox_reply.send_tier_2_auto_reply(
            message, "ticker_score", mock_session,
        )
        assert result.sent is False
        assert "template_render_failed" in (result.error or "")
        assert message.tier == 1
        assert "founder review" in (message.tier_reason or "").lower()
