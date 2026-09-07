"""Canonical ticker-symbol shape validation — shared by ingestion + serving.

A real US symbol is an uppercase letter followed by up to 11 more uppercase
letters/digits or the structural separators . = / ^ - (class shares like
BRK.B / BRK-B, futures continuous contracts like CL=F / ZC=F).

NOT index notation. This docstring used to cite "^GSPC" as a supported
example, which contradicted the leading-letter rule stated two paragraphs
below — `VALID_SYMBOL_RE.match("^GSPC")` has always been None. The regex is
the correct half: nothing in the app ingests an index (the discovered
universe is CS/ADRC/ETF/ETV/ETS/ETN — see
`polygon_feed.VENDOR_TYPE_TO_ASSET_CLASS`), and relaxing the leading-letter
rule to admit them would also admit the separator-and-digit junk it exists to
reject. The caret stays legal in non-leading positions, where it is harmless.

Anything else is NOT a ticker and must never be ingested as one
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

#: Crypto pairs, in the vendor's namespaced form: X:BTCUSD, X:ETHUSD.
#:
#: The `X:` prefix is not cosmetic — it is the whole reason crypto can be
#: ingested at all. A bare "SOL" is BOTH Solana and Emeren Group, a real NYSE
#: solar company, and on 2026-09-03 production published Solana's $64 under
#: Emeren's $1.94 ticker (also EOS/Eaton Vance, BGB/Blackstone, LEO/BNY
#: Mellon). Keeping the vendor's prefix makes that collision impossible by
#: construction: `X:SOLUSD` cannot be typed, stored or served as `SOL`.
#:
#: Kept as a SEPARATE pattern rather than widened into VALID_SYMBOL_RE, so a
#: caller has to opt in. `clean_symbol` still rejects these by default — the
#: sheet parser must never accept one, because the sheet is where the
#: collision came from.
VALID_CRYPTO_SYMBOL_RE = re.compile(r"^X:[A-Z0-9]{2,12}USD$")


def clean_symbol(raw_ticker: Any, *, allow_crypto: bool = False) -> str | None:
    """Normalize a raw symbol to its canonical form, or None if it isn't one.

    Strips surrounding whitespace and uppercases (so " ivv " → "IVV"), then
    validates the shape. Returns None for junk so callers can skip the row
    (ingestion) or return 404 (serving).

    `allow_crypto` additionally admits the vendor's namespaced pair form
    (X:BTCUSD). It is opt-in per caller and defaults to False so that the one
    place a collision has actually happened — the workbook parser, which reads
    a human-typed column — cannot start accepting them by accident. Only the
    dedicated crypto feed passes True.
    """
    s = (str(raw_ticker) if raw_ticker is not None else "").strip().upper()
    if not s or s == "TICKER":
        return None
    if allow_crypto and VALID_CRYPTO_SYMBOL_RE.match(s):
        return s
    if not VALID_SYMBOL_RE.match(s):
        return None
    return s


def is_crypto_symbol(symbol: Any) -> bool:
    """True for a namespaced crypto pair (X:BTCUSD).

    Serving surfaces use this to label a row and to keep coins out of rankings
    built for equities — a coin and a stock scoring 70 do not mean the same
    thing, because two of the six factors cannot exist for a coin.
    """
    s = (str(symbol) if symbol is not None else "").strip().upper()
    return bool(VALID_CRYPTO_SYMBOL_RE.match(s))


def crypto_display_symbol(symbol: Any) -> str | None:
    """"X:BTCUSD" -> "BTC", for display only.

    NEVER use this as a key. It is exactly the collapse that published a
    token's price under a real company's ticker; it exists so a page can show
    "BTC" as a heading while every lookup still uses the namespaced form.
    """
    s = (str(symbol) if symbol is not None else "").strip().upper()
    if not VALID_CRYPTO_SYMBOL_RE.match(s):
        return None
    return s[2:-3]
