"""Crypto rows must never enter the equity/ETF universe.

The crypto symbol namespace COLLIDES with real US listings, and the sheet feed
writes by symbol. Measured on production 2026-09-03, four real securities were
being published with a token's price:

  SOL  Emeren Group Ltd (NYSE solar, ~$1.94)   published at $64.45   (Solana)
  EOS  Eaton Vance Enhanced Equity Income II   published at $0.0625  (EOS token)
  BGB  Blackstone Strategic Credit 2027 Term   published at $1.8568
  LEO  BNY Mellon Strategic Municipals Inc     published at $6.15    (UNUS SED LEO)

Each carried a six-factor score and a CAUTION/NEUTRAL label on a public
per-ticker page with JSON-LD, under a no-AFSL publisher posture. A false
statement of fact about a named real security is the most serious defect this
product can produce — worse than serving nothing at all.

Separately, the model cannot score a token even without the collision: no Form
4 filings and no company fundamentals means ~45% of the composite weight is a
constant, so no token can exceed 77.5/100 and "HIGH CONVICTION" is unreachable
by construction. Crypto is a different product with a different factor set and
a different benchmark — not a universe extension.

These tests drive the real parser, because the failure was in what it returned.
"""
from __future__ import annotations

import pytest

from app.services.sheet_feed import (
    is_unrecognised_asset_class,
    normalize_asset_class,
    parse_all_signals_csv,
)

# Minimal ALL SIGNALS shape. The parser reads by column NAME (csv.DictReader),
# so only the names it actually looks up need to be present.
_HEADER = "Ticker,Asset Class,Conviction,Score,Price"


def _csv(*rows: str) -> str:
    return "\n".join([_HEADER, *rows])


def test_a_crypto_row_is_dropped_entirely() -> None:
    """The load-bearing one. SOL is BOTH Solana and a real NYSE listing."""
    rows = parse_all_signals_csv(_csv(
        "SOL,₿ crypto,HIGH,37.3,64.45",
        "AAPL,📈 stock,HIGH,71.0,225.10",
    ))
    symbols = {r["symbol"] for r in rows}
    assert "SOL" not in symbols, (
        "a crypto row reached the equity universe — this is the production "
        "defect: it overwrites the real listing's price by symbol"
    )
    assert "AAPL" in symbols, "dropping crypto must not drop equities"


def test_every_crypto_spelling_the_sheet_uses_is_dropped() -> None:
    """Emoji decoration and the clean value must both be caught."""
    for label in ("₿ crypto", "crypto", "Crypto", "cryptocurrency", " ₿  CRYPTO "):
        rows = parse_all_signals_csv(_csv(f"TESTX,{label},MED,50.0,1.00"))
        assert not rows, f"crypto label {label!r} was not dropped"


def test_normalize_still_maps_crypto_so_the_guard_can_see_it() -> None:
    """The drop depends on this mapping; pin it so a map edit cannot silently
    re-open the door."""
    assert normalize_asset_class("₿ crypto") == "crypto"
    assert normalize_asset_class("cryptocurrency") == "crypto"
    # And the classes that must keep flowing.
    assert normalize_asset_class("📈 stock") == "equity"
    assert normalize_asset_class("🥇 commodity etf") == "etf"


def test_equities_and_etfs_are_untouched() -> None:
    rows = parse_all_signals_csv(_csv(
        "SPY,🏦 index etf,MED,60.0,540.00",
        "MSFT,📈 stock,HIGH,74.0,410.00",
        "GLD,🥇 commodity etf,MED,55.0,190.00",
    ))
    assert {r["symbol"] for r in rows} == {"SPY", "MSFT", "GLD"}


def test_the_four_known_collisions_cannot_return() -> None:
    """Named explicitly so a regression is unambiguous in the failure output."""
    collisions = {
        "SOL": "Emeren Group Ltd",
        "EOS": "Eaton Vance Enhanced Equity Income Fund II",
        "BGB": "Blackstone Strategic Credit 2027 Term Fund",
        "LEO": "BNY Mellon Strategic Municipals Inc",
    }
    for sym, real_name in collisions.items():
        rows = parse_all_signals_csv(_csv(f"{sym},₿ crypto,HIGH,37.3,64.45"))
        assert not rows, (
            f"{sym} came through as crypto — in production that overwrote "
            f"{real_name!r} with a token's price on a public page"
        )


# ---------------------------------------------------------------------------
# The spelling hole, closed 2026-09-05.
#
# The guard above read `normalize_asset_class(...) == "crypto"`, which is true
# only for spellings already in `_ASSET_CLASS_MAP`. Every OTHER label the sheet
# might carry normalised to None, sailed through, and was written as an
# ordinary listing — i.e. the exact defect this file exists to prevent, one
# spreadsheet edit away.
#
# Watched failing first, per the house rule, with the helper present but the
# guard reverted to `== "crypto"`: 7 failed, 15 passed. Worth recording WHICH
# 7, because the split says what each half of the fix does:
#
#   - The six `test_a_class_we_cannot_read_is_refused_not_guessed` cases went
#     red. Only the unrecognised-drop closes those.
#   - `test_other_crypto_spellings_are_dropped` went GREEN on the old guard —
#     widening `_ASSET_CLASS_MAP` alone is enough for a named synonym.
#   - `test_a_blank_asset_class_still_passes` was green throughout. That is
#     the point of including it: it is the regression the fix could cause.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label", [
    "token", "coin", "digital asset", "digital currency",
    "cryptocurrencies", "crypto currency",
])
def test_other_crypto_spellings_are_dropped(label: str) -> None:
    """A synonym is not a loophole.

    Each of these is a label a human might reasonably type for a token. Under
    the old `== "crypto"` guard every one of them was published.
    """
    rows = parse_all_signals_csv(_csv(f"SOL,{label},HIGH,88,64.45"))
    assert rows == [], f"{label!r} was published as a listing"


@pytest.mark.parametrize("label", [
    "web3", "defi", "spot token", "🪙 shiny thing", "asset", "???",
])
def test_a_class_we_cannot_read_is_refused_not_guessed(label: str) -> None:
    """Fail closed on anything unclassifiable, not just on known crypto.

    This is the general form of the bug. We cannot enumerate every label the
    sheet will ever carry, so the rule is "publish what we understand", not
    "drop what we recognise as bad".
    """
    rows = parse_all_signals_csv(_csv(f"EOS,{label},HIGH,88,0.0625"))
    assert rows == [], f"unclassifiable {label!r} was published as a listing"


@pytest.mark.parametrize("label", ["", "   ", "\t"])
def test_a_blank_asset_class_still_passes(label: str) -> None:
    """Load-bearing in the other direction, and the reason this is not a
    blanket 'drop anything that does not classify'.

    Sheet-governed ETFs — SPY, QQQ, IWM, GLD and the rest of the benchmarks —
    leave Asset Class empty by design. If blank were treated as suspicious,
    the drop would take out the benchmarks the whole scorecard is measured
    against. "Said nothing" and "said something we do not understand" are
    different facts.
    """
    rows = parse_all_signals_csv(_csv(f"SPY,{label},HIGH,88,655.0"))
    assert len(rows) == 1, "a blank Asset Class must still ingest"
    assert rows[0]["symbol"] == "SPY"
    assert rows[0]["asset_class"] is None, "blank means unset, not a guess"


def test_blank_and_unreadable_are_distinguishable() -> None:
    """The distinction the guard depends on, asserted directly.

    `normalize_asset_class` returns None for both, so the guard cannot use it
    alone — that collapse is what let the hole exist.
    """
    # "digital asset" deliberately does NOT appear here: it is now a known
    # crypto spelling, so it normalises to "crypto" and the first arm of the
    # guard catches it. Writing this test against it was my own mistake and
    # the run caught it — the example has to be a label the map genuinely
    # does not contain, or it proves nothing about the second arm.
    assert normalize_asset_class("") is None
    assert normalize_asset_class("web3") is None

    assert is_unrecognised_asset_class("") is False
    assert is_unrecognised_asset_class("   ") is False
    assert is_unrecognised_asset_class(None) is False
    assert is_unrecognised_asset_class("web3") is True
    assert is_unrecognised_asset_class("🪙 shiny thing") is True

    # A label we DO understand is not unrecognised, decoration and all.
    assert is_unrecognised_asset_class(" 📈 stock ") is False
    assert is_unrecognised_asset_class("₿ crypto") is False


def test_a_real_equity_row_is_untouched_by_all_of_this() -> None:
    """The guard must not cost the universe a single legitimate listing."""
    rows = parse_all_signals_csv(_csv("AAPL,📈 stock,HIGH,88,320.68"))
    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["asset_class"] == "equity"
