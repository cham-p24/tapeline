"""Canonical ticker-symbol shape validation — shared by ingestion + serving.

A real US symbol is an uppercase letter followed by up to 11 more uppercase
letters/digits or the structural separators . = / ^ - (class shares like
BRK.B / BRK-B, futures continuous contracts like CL=F / ZC=F, index notation
like ^GSPC). Anything else is NOT a ticker and must never be ingested as one
(see sheet_feed) nor served as a /t/{symbol} page (see routers.ticker):

  • blank cells / the literal "TICKER" header
  • section dividers ("--- INTERNATIONAL ---", "===")
  • summary em-dashes ("—")
  • decoration the signal-system writes into column A, e.g. the trophy badge
    "🏆 IVV" — which was ingested as a standalone symbol and produced duplicate
    ghost rows of real ETFs plus broken /t/🏆 IVV sitemap URLs.

Deliberately requires a LEADING LETTER so pure separators and digit/symbol
junk can't match, and forbids whitespace so space-decorated cells are
rejected. Verified false-positive-free against the live universe: every real
equity/ETF/futures symbol begins with a letter and uses only the allow-listed
characters, so none are rejected.
"""
from __future__ import annotations

import re
from typing import Any

VALID_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.=/^-]{0,11}$")


def clean_symbol(raw_ticker: Any) -> str | None:
    """Normalize a raw symbol to its canonical form, or None if it isn't one.

    Strips surrounding whitespace and uppercases (so " ivv " → "IVV"), then
    validates the shape. Returns None for junk so callers can skip the row
    (ingestion) or return 404 (serving).
    """
    s = (str(raw_ticker) if raw_ticker is not None else "").strip().upper()
    if not s or s == "TICKER":
        return None
    if not VALID_SYMBOL_RE.match(s):
        return None
    return s
