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

import io

from app.services.sheet_feed import normalize_asset_class, parse_all_signals_csv

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
