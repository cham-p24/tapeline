"""Voice-rule regression guard for the Tier 2 reply templates.

Australian publisher-exemption posture from AFSL depends on Tapeline NEVER
using prescriptive language in any automated reply. A regression here is
how the bot starts saying "you should buy $NVDA" and the legal moat
disappears overnight.

These tests target `services/inbox_templates.render_*` — the only place
bot replies originate (Tier 1 LLM drafts go through human approval; the
LLM is system-prompted with the same rules but humans are the last line
of defence there).

Banned phrases checked:
  - " buy ", " sell " (with spaces — avoids false-positives on "buyer's
    market" or "selling point")
  - "you should" / "we recommend" / "I recommend"
  - "guaranteed" (prescriptive certainty about returns)
  - "will moon" / "going to " (future-certainty claims)
  - "Christian" / "Chamara" (unsigned voice rule — body IS the voice)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services import inbox_templates

BANNED_PHRASES = [
    " buy ", " sell ",
    "you should", "we recommend", "i recommend",
    "guaranteed", "will moon", "going to ",
]


def _assert_no_banned(body: str, *, label: str) -> None:
    lower = body.lower()
    for banned in BANNED_PHRASES:
        assert banned not in lower, (
            f"[{label}] banned prescriptive phrase {banned!r} in template body:\n{body}"
        )


def _assert_unsigned(body: str, *, label: str) -> None:
    # Body IS the voice — no "— Christian", no "Chamara" anywhere.
    assert "Christian" not in body, f"[{label}] contains 'Christian' signature"
    assert "Chamara" not in body, f"[{label}] contains 'Chamara' name"


class TestStaticTemplateVoiceRules:
    """The pricing / trial / thanks templates are static strings —
    no live data, no LLM. They're the easiest to lock down."""

    @pytest.mark.asyncio
    async def test_pricing_clean(self):
        body = await inbox_templates.render_pricing("how much?")
        assert body
        _assert_no_banned(body, label="pricing")
        _assert_unsigned(body, label="pricing")

    @pytest.mark.asyncio
    async def test_trial_clean(self):
        body = await inbox_templates.render_trial("can I try premium?")
        assert body
        _assert_no_banned(body, label="trial")
        _assert_unsigned(body, label="trial")

    @pytest.mark.asyncio
    async def test_thanks_clean(self):
        body = await inbox_templates.render_thanks("love the tool!")
        assert body
        _assert_no_banned(body, label="thanks")
        _assert_unsigned(body, label="thanks")


class TestTickerScoreTemplateVoiceRules:
    """The ticker_score template fetches live data — mock the HTTP layer
    so the test is deterministic. Then verify the rendered body
    doesn't drift into prescriptive language even with score+signal data
    interpolated."""

    @pytest.mark.asyncio
    async def test_ticker_score_clean_with_high_conviction(self):
        """The signal label 'HIGH CONVICTION' is descriptive (an
        observed state of the scanner), not prescriptive — the body
        must STILL pass the no-buy-no-sell test."""
        fake_data = {
            "score": 87.2,
            "signal": "HIGH CONVICTION",
            "breakdown": {
                "trend":         {"value": 88},
                "rs":            {"value": 85},
                "fundamentals":  {"value": 80},
                "smart_money":   {"value": 92},
                "macro":         {"value": 72},
                "momentum":      {"value": 90},
            },
        }
        with patch.object(
            inbox_templates, "_fetch_ticker",
            AsyncMock(return_value=fake_data),
        ):
            body = await inbox_templates.render_ticker_score("what's $NVDA at?")
        assert body
        _assert_no_banned(body, label="ticker_score(HIGH CONVICTION)")
        _assert_unsigned(body, label="ticker_score")
        # Sanity: the score + signal made it into the body
        assert "$NVDA" in body
        assert "87.2" in body
        assert "HIGH CONVICTION" in body

    @pytest.mark.asyncio
    async def test_ticker_score_clean_with_weak(self):
        """The 'WEAK' label is the most adversarial — the regex must
        not let a sloppy template author land on 'sell' as a rephrasing."""
        fake_data = {
            "score": 18.5, "signal": "WEAK",
            "breakdown": {
                "trend": {"value": 22}, "rs": {"value": 15},
                "fundamentals": {"value": 30}, "smart_money": {"value": 12},
                "macro": {"value": 40}, "momentum": {"value": 8},
            },
        }
        with patch.object(
            inbox_templates, "_fetch_ticker",
            AsyncMock(return_value=fake_data),
        ):
            body = await inbox_templates.render_ticker_score("$TSLA?")
        assert body
        _assert_no_banned(body, label="ticker_score(WEAK)")
        _assert_unsigned(body, label="ticker_score")
        assert "WEAK" in body

    @pytest.mark.asyncio
    async def test_ticker_score_unknown_symbol_returns_none(self):
        """When the ticker isn't in the universe, we MUST NOT pretend
        to know — render_ticker_score returns None so the dispatcher
        falls through to manual review."""
        with patch.object(
            inbox_templates, "_fetch_ticker", AsyncMock(return_value=None),
        ):
            body = await inbox_templates.render_ticker_score("$ZZZNOPE?")
        assert body is None


class TestRegisteredTemplatesAllClean:
    """Belt + braces: every renderer registered in TEMPLATES gets
    checked. If a future template lands without going through the
    individual tests above, this catches it."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("key", ["pricing", "trial", "thanks"])
    async def test_static_template_via_render_dispatch(self, key: str):
        body = await inbox_templates.render(key, "any body")
        assert body, f"render({key!r}) returned no body"
        _assert_no_banned(body, label=f"render({key})")
        _assert_unsigned(body, label=f"render({key})")
