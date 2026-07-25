"""Compliance guard for the per-ticker reason phrase banks (mock_feed).

The reason string is user-facing on every scanner row and /t/ page. Its clauses
are selected purely from the six factor sub-scores, and five of the six are
still synthesised rather than sourced (see polygon_feed). So a clause may only
describe a factor SCORE — never assert a specific external event, and never
apply an evaluative adjective to the security. This test fails the build if a
banned term is reintroduced into any bank, since the static copy-compliance
linter does not scan this runtime-generated text.
"""
from __future__ import annotations

import re

from app.services import mock_feed

# Every phrase bank feeding _render_reason.
_BANKS = [
    "_TREND_STRONG_UP", "_TREND_UP", "_TREND_DOWN", "_TREND_STRONG_DOWN",
    "_RS_STRONG_UP", "_RS_UP", "_RS_DOWN", "_RS_STRONG_DOWN",
    "_FUND_STRONG", "_FUND_GOOD", "_FUND_WEAK",
    "_MOM_STRONG", "_MOM_WEAK",
    "_SMART_BUYING", "_SMART_SELLING",
    "_MACRO_TAILWIND", "_MACRO_HEADWIND",
    "_NEUTRAL",
]

# (a) Evaluative adjectives on the security.
_EVALUATIVE = [
    "exceptional", "best-in-class", "solid", "weak", "bullish", "bearish",
    "outstanding", "superior", "dominant", "strongest", "weakest",
    "by a wide margin", "leading", "badly", "healthy", "favourable",
    "constructive", "supportive", "deteriorating",
]
# (b) Specific external events / readings the system has NOT verified.
_FABRICATED_EVENT = [
    "form 4", "congress", "insider", "rsi", "dma", "vix", "12-month",
    "6-month", "breadth", "thrust", "breakout", "moving average",
    "form4", "filing", "disclosed",
]

_BANNED = [t.lower() for t in _EVALUATIVE + _FABRICATED_EVENT]


def _all_phrases() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name in _BANKS:
        for phrase in getattr(mock_feed, name):
            out.append((name, phrase))
    return out


def test_no_banned_terms_in_any_reason_bank() -> None:
    offenders: list[str] = []
    for name, phrase in _all_phrases():
        low = phrase.lower()
        for term in _BANNED:
            # word-ish boundary so "trend" != "uptrend" etc.
            if re.search(rf"(?<![a-z]){re.escape(term)}", low):
                offenders.append(f"{name}: {phrase!r} contains {term!r}")
    assert not offenders, "Reason banks contain banned terms:\n" + "\n".join(offenders)


def test_render_reason_output_is_clean_across_score_space() -> None:
    """Sweep the factor score space; no rendered reason may carry a banned term."""
    for v in range(0, 101, 5):
        text = mock_feed._render_reason("TEST", "Technology", v, v, v, v, v, v).lower()
        hits = [t for t in _BANNED if re.search(rf"(?<![a-z]){re.escape(t)}", text)]
        assert not hits, f"score={v} rendered {text!r} with banned {hits}"


def test_banks_are_non_empty() -> None:
    for name in _BANKS:
        assert getattr(mock_feed, name), f"{name} is empty"
