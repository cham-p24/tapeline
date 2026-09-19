"""Symbols Tapeline does not cover, because nothing we hold can ever price them.

MEASURED IN PRODUCTION, 2026-09-19 (read-only)
----------------------------------------------
29 scored rows had no price and never could:

* 27 continuous-futures rows (ALI=F, BZ=F, CC=F, CL=F, ... ZW=F), asset_class
  ``future_commodity``, name equal to the symbol, sector ``Uncategorized``.
  Our market-data plan covers US stocks and ETFs, not futures, so the equity
  snapshot answers nothing for them. Every one had ``price`` and
  ``change_pct_1d`` NULL while ``updated_at`` was re-stamped on every pass, so
  a row with a dash for a price looked as fresh as any other. Two of the six
  factors (fundamentals, smart money) cannot exist for a future at all.
* 2 hyphen-spelled Berkshire rows, BRK-A and BRK-B. The vendor spells the class
  shares BRK.A and BRK.B, and those two rows ARE priced (BRK.B at 510.15 on the
  same pass). The hyphen rows were a second, never-priced copy of the same
  security, left over from when the workbook wrote Yahoo-style tickers.

None of the 29 is on a watchlist. One is on the public record: PA=F, flagged
2026-06-26. The record is immutable and is not touched here; the scorecard
pages read ``daily_scorecard``, not this module.

WHAT THIS DOES
--------------
A code-level exclusion, not a data purge: the rows stay in ``tickers``, so the
change is reversible and auditable by reading this file. They are dropped from
the snapshot universe (``services/universe.py``), refused at sheet ingest
(``sheet_feed._sheet_symbol``), filtered from every ranked surface through
``ticker_freshness.valid_composite_clauses`` (scanner, search, public signals,
the sitemap feed, the keyed API), and answered with a "Not covered" message by
``/api/ticker/{symbol}`` and the MCP server.

Commodity exposure stays: the ETFs named in the message are ordinary covered
rows, priced on every pass.
"""
from __future__ import annotations

from sqlalchemy.sql.elements import ColumnElement

from app.models import Ticker
from app.services.freshness import PASS_CADENCE_PHRASE, PRICE_DELAY_PHRASE
from app.services.symbols import vendor_share_class_symbol

#: Continuous-futures suffix (Yahoo-style): CL=F, GC=F, ZC=F.
FUTURES_SUFFIX = "=F"

#: What a futures symbol answers. Every ETF named here is a covered, priced row
#: (measured 2026-09-19: all five priced, scored and re-read on every pass).
#:
#: The wording drafted for this was "which are priced every minute". Two things
#: are wrong with that: the copy lint bans "every minute" about data, and the
#: prices are the vendor's, delayed about 15 minutes, re-read about every 60
#: seconds. So the sentence states both, from the freshness constants, which
#: frontend/lib/coverage.ts mirrors (pinned by tests/test_keyless_no_prices.py).
NOT_COVERED_FUTURES_MESSAGE = (
    "Not covered. Commodity exposure is available through USO, GLD, SLV, CPER "
    f"and CORN, which Tapeline re-prices {PASS_CADENCE_PHRASE} during US market "
    f"hours (prices {PRICE_DELAY_PHRASE})."
)


def is_futures_symbol(symbol: object) -> bool:
    """True for a continuous-futures symbol (ends in ``=F``)."""
    s = (str(symbol) if symbol is not None else "").strip().upper()
    return len(s) > len(FUTURES_SUFFIX) and s.endswith(FUTURES_SUFFIX)


def is_hyphen_class_share(symbol: object) -> bool:
    """True for a Yahoo-style class share the vendor spells with a dot (BRK-B).

    Uses the same narrow rule sheet ingest already maps (one letter after one to
    five letters), so ingest and serving agree about which symbols they mean.
    """
    s = (str(symbol) if symbol is not None else "").strip().upper()
    return vendor_share_class_symbol(s) != s


def not_covered_message(symbol: object) -> str | None:
    """The reason a symbol is not covered, or None when it is an ordinary symbol."""
    if is_futures_symbol(symbol):
        return NOT_COVERED_FUTURES_MESSAGE
    if is_hyphen_class_share(symbol):
        s = str(symbol).strip().upper()
        return (
            f"Not covered under this spelling. Tapeline covers this share class "
            f"as {vendor_share_class_symbol(s)}."
        )
    return None


def covered_clauses() -> list[ColumnElement[bool]]:
    """SQL predicates keeping only symbols that can be priced.

    ``%-_`` is "a hyphen followed by exactly one character at the end", a
    portable superset of ``is_hyphen_class_share`` (LIKE has no character
    classes). On 2026-09-19 the table held exactly two hyphenated symbols,
    BRK-A and BRK-B, so both predicates selected the same two rows; the vendor
    spells every class share it lists with a dot.
    """
    return [
        Ticker.symbol.notlike(f"%{FUTURES_SUFFIX}"),
        Ticker.symbol.notlike("%-_"),
    ]
