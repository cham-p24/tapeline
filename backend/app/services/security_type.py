"""Is a listing a company's common stock, or a preferred, note, ETN, warrant,
unit or right that trades under a ticker of the same issuer?

WHY THIS EXISTS. SEC lists several tickers under one CIK for many issuers, and
the insider pass has to decide which of them an issuer's Form 4 lines belong to
(`services/edgar_form4.py`, point 5). Since 2026-09-19 the answer is "every
COMMON-stock ticker of the CIK, and nothing else": Alphabet's insiders file
under GOOGL, but the filing is about Alphabet, and GOOG is Alphabet's common
stock too. A preferred, a note or an ETN is a different security with its own
terms; its issuer's insider sales say nothing about it. Until 2026-09-17 every
ticker of the CIK received the issuer's whole Form 4 set, so Strategy's STRK
preferred, JPM's VYLD ETN and notes such as GREEL and TMUSZ carried their
issuer's insider readings.

NO STORED FIELD STATES THE SECURITY TYPE. Discovery lets in whatever the vendor
types CS/ADRC, which includes preferreds and notes, and the sheet ingest writes
any symbol it receives as equity. The listing NAME and the SYMBOL GRAMMAR are
what we hold, so this module reads those - and, like `services/leverage.py`, is
honest about being a heuristic.

Detection is by listing name and symbol grammar because no stored field states
the security type; like `services/leverage.py`, it is written to under-claim
rather than over-claim, so a preferred whose name and symbol say nothing
(Strategy's STRK/STRF/STRD/STRC are named "Strategy Inc") is treated as common
and still receives the issuer's filings - unless it is named in
`_KNOWN_NON_COMMON` below, which exists for exactly those.

MEASURED 2026-09-18/19, read-only against all 11,973 production `tickers` rows
(the peer session "Clear smart-money scores after Form 4 ages out" built and
measured the predicate; this module ports it unchanged apart from the explicit
symbol list and reading the symbol upper-cased, as `tickers` stores it):

* 185 rows flagged non-common; every one reviewed by hand, 0 false positives
  (PENGU is undecidable from stored data and unscored).
* 125 hand labels, written before the predicate was run
  (`tests/test_security_type.py`): precision 38/38 - none of the 77 labelled
  commons is flagged; recall 38/48 raw. Five of the ten misses are labels, not
  errors, for Form 4 purposes (HONAV, LILAV, LILKV are when-issued common
  stock; MARPS and MTR are royalty trusts whose only listing is the trust's
  equity), so recall for attribution is 38/43. Four more are Strategy's
  preferreds, which `_KNOWN_NON_COMMON` now catches: with it, 42/42 and 42/48
  (42/43 for attribution; the one left is OBTC, a grantor trust's units and its
  only listed equity).
* Traps it handles: PFBC "Preferred Bank", PDC "... American Depositary
  Shares", WDH ("the right to receive"), MLP common units (ET, CAPL, KRP, SGU,
  BIP), "Series A/C Common Stock", and 29 "Preferred ... ETF" funds.

WHY A FALSE POSITIVE IS THE WORSE ERROR. Flagging a real common stock would
withhold its insider reading entirely; missing a preferred leaves it where the
2026-09-17 rule already left most of them. So a rule is only added here when it
has no false positive in the live table, and the known misses stay misses.

CONVENTION RISK. A future common stock could match the symbol-grammar rules
(`-P`, `.U`, a fifth letter U/R/W after a listed four-letter root). None does
today.
"""
from __future__ import annotations

import re
from collections.abc import Set as AbstractSet

from app.services.asset_class import ASSET_CLASS_SYNONYMS

_EQUITY_CLASSES = ASSET_CLASS_SYNONYMS["equity"]

#: Listings whose name and symbol say nothing about what they are.
#:
#: Strategy's four preferreds are named "Strategy Inc" exactly like MSTR, so
#: name and symbol grammar cannot tell them apart - and a predicate-only
#: fan-out would re-introduce #862's headline bug: STRK carrying MSTR's insider
#: sales. CIG (CEMIG's preferred ADR) and PBR.A (Petrobras's preferred ADR) are
#: named like their commons CIG.C and PBR; they are listed for completeness and
#: are harmless either way, since foreign private issuers file no Form 4.
_KNOWN_NON_COMMON: frozenset[str] = frozenset({"STRK", "STRC", "STRF", "STRD", "CIG", "PBR.A"})

_SYM_TEST = re.compile(r"^Z[A-Z]ZZT$")
_SYM_SUFFIX = re.compile(r"(\.PR[A-Z]?|-P[A-Z]?|[.-](U|UN|W|WS|WT|R|RT))$")
_SYM_NASDAQ_UR = re.compile(r"^[A-Z]{4}[UR]$")
_SYM_NASDAQ_W = re.compile(r"^[A-Z]{4}W$")
_ETN = re.compile(r"\betns?\b|exchange[- ]traded notes?\b|\bipath\b", re.I)
_ETF_WORD = re.compile(r"\betf\b", re.I)
_FUND_WORD = re.compile(r"\b(etf|fund)\b|exchange[- ]traded fund", re.I)
_DEBT = re.compile(r"\b(notes?|debentures?|bonds?)\b", re.I)
_DEBT_TERMS = re.compile(r"\bdue\b|\d%", re.I)
_PREFERRED = re.compile(
    r"\bpreferred (stock|shares?|units?)\b|\bpfd\b|\bnon-?cumulative\b|\bcumulative\b", re.I,
)
_DEPOSITARY = re.compile(r"\bdeposit[ao]ry shares\b", re.I)
_ADR = re.compile(r"\b(american|global) deposit[ao]ry\b", re.I)
_WARRANT_RIGHT = re.compile(r"\bwarrants?\b|\brights?\b(?! to\b)", re.I)
_UNITS = re.compile(r"\bunits?\b", re.I)
_UNITS_EQUITY = re.compile(r"common units|partner|beneficial interest", re.I)


def _is_placeholder(symbol: str, name: str) -> bool:
    return not name or name.upper() == symbol


def is_non_common_listing(
    symbol: str | None,
    name: str | None,
    universe: AbstractSet[str] = frozenset(),
) -> bool:
    """True when the listing is evidently NOT a company's common stock: a
    preferred, note, debenture, ETN, warrant, right, unit or test symbol.

    `universe` is the set of every `tickers.symbol`. It only feeds the
    fifth-letter U/R/W rules (OIMAU is a unit only because OIMA is listed), so
    without it those rules stay silent and the answer under-claims."""
    s = (symbol or "").strip().upper()
    n = (name or "").strip()
    if s in _KNOWN_NON_COMMON:
        return True
    if _SYM_TEST.search(s) or _SYM_SUFFIX.search(s):
        return True
    if _SYM_NASDAQ_UR.search(s) and s[:4] in universe:
        return True
    if _SYM_NASDAQ_W.search(s) and s[:4] in universe and _is_placeholder(s, n):
        return True
    if _ETN.search(n) and not _ETF_WORD.search(n):
        return True
    if not _FUND_WORD.search(n):
        if _DEBT.search(n) and _DEBT_TERMS.search(n):
            return True
        if _PREFERRED.search(n):
            return True
    if _DEPOSITARY.search(n) and not _ADR.search(n):
        return True
    if _WARRANT_RIGHT.search(n):
        return True
    return bool(_UNITS.search(n) and not _UNITS_EQUITY.search(n))


def is_common_stock(
    symbol: str | None,
    name: str | None,
    asset_class: str | None,
    universe: AbstractSet[str] = frozenset(),
) -> bool:
    """True for a listing in the equity bucket that is not evidently a
    preferred, note, ETN, warrant, unit or right; see the module docstring.

    Outside the equity bucket the answer is False: an ETF or ETN (stored as
    "etf") has no insiders of its own, and a row whose class is unknown is not
    KNOWN to be common stock."""
    if (asset_class or "").strip().lower() not in _EQUITY_CLASSES:
        return False
    return not is_non_common_listing(symbol, name, universe)
