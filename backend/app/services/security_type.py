"""TEMPORARY stand-in for Audit/Bugs' security_type module (their PR owns it).

This copy exists only so the non-common exclusion can be built and tested
before that PR merges. It follows the agreed contract exactly:
`is_non_common_listing(symbol, name, universe)` and
`is_common_stock(symbol, name, asset_class, universe)`, pure and synchronous.
When theirs lands, this file is dropped in the rebase and theirs wins.
"""
from __future__ import annotations

import re
from collections.abc import Set as AbstractSet

_EQUITY_CLASSES = frozenset({"equity", "stock"})

# Named exactly like their issuer's common stock, so neither name nor symbol
# grammar can tell them apart: Strategy's four preferreds are all "Strategy
# Inc", like MSTR; CIG and PBR.A are the preferred ADRs of CEMIG and Petrobras.
_KNOWN_NON_COMMON = frozenset({"STRK", "STRC", "STRF", "STRD", "CIG", "PBR.A"})

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
    symbol: str | None, name: str | None, universe: AbstractSet[str] = frozenset(),
) -> bool:
    s = (symbol or "").strip()
    n = (name or "").strip()
    if s.upper() in _KNOWN_NON_COMMON:
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
    symbol: str | None, name: str | None, asset_class: str | None,
    universe: AbstractSet[str] = frozenset(),
) -> bool:
    if (asset_class or "").strip().lower() not in _EQUITY_CLASSES:
        return False
    return not is_non_common_listing(symbol, name, universe)


__all__ = ["is_common_stock", "is_non_common_listing"]
