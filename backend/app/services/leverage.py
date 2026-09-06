"""Leveraged / inverse fund detection, from the fund NAME.

WHY THIS EXISTS. On 2026-09-07 the anonymous top 10 at /api/scanner — the
first thing a visitor ever sees, and the artefact the public MCP server
republishes as "today's picks" — held two geared funds presented as ordinary
ranked results: CONX ("Direxion Daily COIN Bull 2X ETF") at rank 6 and BIB
("ProShares Ultra NASDAQ Biotechnology") at rank 8, both labelled STRONG SETUP.
A six-factor trend/RS read on a 2x daily-reset crypto-miner fund is not the same
kind of statement as the same read on an operating company, and nothing in the
codebase could tell the two apart.

NO VENDOR LEVERAGE FIELD EXISTS. Massive's reference data types these as plain
`ETF`/`ETV`, exactly like SPY. Finnhub's profile endpoint has no gearing field
for funds either. The fund's NAME is the only signal we actually hold, so this
module reads the name — and is honest about being a heuristic rather than a
lookup.

WHAT THIS IS AND IS NOT. `is_leveraged` is a FACT about a fund's structure, in
the same register as `asset_class`. It is never a judgement, a warning, or a
risk rating — the whole product posture depends on staying descriptive (see the
signal-label rules in CLAUDE.md), so nothing built on this flag may say
"risky", "avoid", or "dangerous".

────────────────────────────────────────────────────────────────────────────
WHY IT IS GATED ON THE ETF BUCKET
────────────────────────────────────────────────────────────────────────────
Every word that marks a geared fund is also an ordinary word in a company
name. Measured against all 11,781 live `tickers` rows on 2026-09-07:

    "Ultra"  →  Ultragenyx Pharmaceutical, Ultra Clean Holdings, Ultrapar
                Participacoes, Ultralife Corporation, KPET Ultra Paceline
    "Bear"   →  Build-A-Bear Workshop, BigBear.ai, Maplebear, RBC Bearings
    "Bull"   →  Bullfrog AI, Bullish, Webull
    "Long"   →  Longeveron, J-Long Group, Julong Holding, Elong Power
    "2X"     →  10X Genomics
    "T-Rex"  →  Trex Company, Cemtrex, Datacentrex

Word boundaries handle most of these but NOT all: a bare `\\bbear\\b` pattern
matches "Build-A-Bear Workshop" because a hyphen is a word boundary, and a
bare `\\b2x\\b` pattern matches "10X Genomics Inc". Those two are precisely
why the rules below are narrower than a word list AND why the public predicate
`is_leveraged_fund()` refuses to look at anything outside the ETF bucket
(`services.asset_class.bucket_of` == "etf").

Both defences are load-bearing, at different depths. The rules alone already
clear ten of the twelve names above — no rule here fires on a bare "Bear",
"Bull" or "Ultra". The bucket gate is what catches the last one: 10X Genomics
(TXG) is the ONLY equity in the live universe that the bare name matcher
flags, and it is excluded structurally rather than by a special case. Keep
both; each is the other's backstop for the name nobody has listed yet.

`is_leveraged_name()` is the bare name matcher, exposed for tests and for
callers that have already established they hold a fund. Do not call it on an
equity name.

────────────────────────────────────────────────────────────────────────────
THE RULES, AND WHAT EACH ONE COSTS
────────────────────────────────────────────────────────────────────────────
1. GEARED MULTIPLIER — a standalone `NX` token whose magnitude is not 1, or
   which carries a minus sign: `2X`, `3x`, `1.5X`, `1.25x`, `-1x`, `-3X`.
   This alone catches ~590 of the ~640 geared funds in the live universe
   (Direxion, ProShares, Tradr, T-Rex, Leverage Shares, GraniteShares,
   Defiance, MicroSectors, Corgi, Teucrium, Volatility Shares).

   A bare `1X`/`1x` is deliberately NOT geared on its own: "IncomeSTKd 1x
   Bitcoin & 1x Gold Premium ETF" and "IncomeSTKd 1x US Stocks & 1x Bitcoin
   Premium ETF" are unlevered, and 1x means exactly that. It becomes a flag
   only in rule 2.

2. DIRECTIONAL + MULTIPLIER — a direction word (`bull` / `bear` / `long` /
   `short`) anywhere in a name that also carries any multiplier token. This
   exists for the 22 Direxion `Bear 1X` funds: -1x IS inverse, and rule 1
   cannot see the sign because Direxion does not print one.

   Bull/Bear are deliberately NOT flagged on their own. In the live universe
   the only ETFs containing a standalone `bull`/`bear` and no multiplier are
   "TrueShares Quarterly Bull Hedge ETF", "TrueShares Quarterly Bear Hedge
   ETF", "Simplify Bond Bull ETF" and "AdvisorShares Ranger Equity Bear ETF".
   The last is a genuine short-only fund we therefore MISS; the first three
   are not geared and would be FALSE. Publishing a wrong fact on three rows
   is worse than under-claiming on one, so the conjunction stands.

3. THE WORD "LEVERAG…" — matched as a bare substring, not a word, because
   ETRACS prints "2xLeveraged" and "2xMonthly Pay Leveraged" with no space.
   Carve-out: "leveraged loan" is an ASSET CLASS (senior bank loans), not a
   geared fund — "State Street SPDR S&P Leveraged Loan ETF" holds loans at 1x.

4. THE WORD "INVERSE", and "geared".

5. "DOUBLE"/"TRIPLE" + LONG/SHORT — "DB Gold Double Long ETN",
   "DB Gold Double Short ETN" print their gearing in words, not digits.

6. PROSHARES + "ULTRA…", and "ULTRAPRO" anywhere.
   This one needs the issuer, and the reason is worth writing down. "Ultra"
   is ProShares' brand for its geared suite (Ultra = 2x, UltraPro = 3x,
   UltraShort = -2x). Everywhere ELSE in the fund industry, "ultra-short" is
   the ordinary bond-market adjective for the shortest-duration, LOWEST-
   volatility end of fixed income. 161 live ETFs contain "ultra" and the two
   populations are textually inseparable without the issuer:

       ProShares UltraShort Lehman 20+ Year Treasury   (-2x, geared)
       Vanguard Ultra-Short Treasury ETF                (1x, a bond fund)
       Angel Oak UltraShort Income ETF                  (1x, one word too)

   A "not followed by a bond noun" rule breaks on TBT/PST/UBT/UST/TTT, which
   are geared Treasury funds. So rule 6 asks who issued it. "UltraPro" needs
   no issuer — nobody else uses the token.

7. BARE INVERSE "SHORT" — the un-geared -1x suite prints no multiplier at
   all: "ProShares Short S&P500", "ProShares Short QQQ", "DB Gold Short ETN",
   "AdvisorShares Dorsey Wright Short ETF", "YieldMax Short TSLA Option
   Income Strategy ETF". "Short" is the single most overloaded word in the
   fund universe (265 live ETFs contain it), so it flags only when it is NOT:

     * preceded by "/" or by "long" — "Long/Short Equity", "Long-Short
       Equity", and "ProShares Long Online/Short Stores" name a two-sided
       strategy, not an inverse fund;
     * preceded by "ultra" with a separator — "Vanguard Ultra-Short Bond",
       "JPMorgan Ultra-Short Income", "PGIM Ultra Short Bond" and 18 more
       are the duration idiom again (rule 6's problem, arriving here through
       a different door). ProShares always writes its geared version as ONE
       word, "UltraShort", which the leading word-character guard already
       excludes from this rule and which rule 6 catches instead;
     * followed by a TENOR word (term / duration / maturity / horizon /
       dated) — "Short-Term Bond", "Short Duration High Yield", "Short
       Maturity", "Short Horizon" are all tenor, not direction;
     * in a name carrying a MUNICIPAL marker. "VanEck Short High Yield Muni",
       "VanEck Short Muni" and "T. Rowe Price Short Municipal Income" are
       short-duration muni funds whose prefix is textually identical to
       "ProShares Short High Yield" (which IS inverse). No inverse municipal
       ETF exists, so the muni marker is a safe absolute exclusion.

WHAT IT DELIBERATELY MISSES. A fund whose name does not state its gearing —
"UPAR Ultra Risk Parity ETF" runs ~1.4x, "AdvisorShares Ranger Equity Bear
ETF" is short-only — is not flagged. A name-based heuristic can only report
what the name says, and this module would rather under-claim than assert a
structural fact that the name does not support.

Grounding: `backend/tests/test_leverage_detection.py` runs this against a
fixture of REAL fund and company names pulled from the live universe on
2026-09-07, in both directions.
"""
from __future__ import annotations

import re

from app.services.asset_class import bucket_of

#: A standalone leverage multiplier token: 2X, 3x, 1.5X, -3x, "2 X".
#: The lookbehind rejects a digit/letter/dot immediately before the number, so
#: "V2X, Inc." and the "5X" inside "1.5X" never start a match; the lookahead
#: rejects a following alphanumeric so "Xtrackers" and "XRP" cannot end one.
_MULTIPLIER = re.compile(
    r"(?<![A-Za-z0-9.])(-?)(\d+(?:\.\d+)?)\s*[Xx](?![A-Za-z0-9])"
)

#: Direction words. Only meaningful alongside a multiplier — see rule 2.
_DIRECTIONAL = re.compile(r"\b(?:bull|bear|long|short)\b", re.IGNORECASE)

#: "leveraged", "leverage", "2xLeveraged" (no word boundary — ETRACS runs the
#: multiplier straight into the word), plus "geared" and "inverse".
_LEVERAGE_WORD = re.compile(r"leverag|\bgeared\b|\binverse\b", re.IGNORECASE)

#: Senior bank loans are an asset class called "leveraged loans". A fund that
#: holds them is not itself geared.
_LEVERAGED_LOAN = re.compile(r"leveraged\s+loan", re.IGNORECASE)

#: "Double Long", "Triple Short" — gearing spelled out in words.
_WORD_MULTIPLE = re.compile(
    r"\b(?:double|triple)[\s-]+(?:long|short)\b", re.IGNORECASE
)

#: ProShares' geared brand. "UltraPro" is unique enough to stand alone;
#: "Ultra"/"UltraShort" need the issuer — see rule 6 in the module docstring.
_ULTRAPRO = re.compile(r"ultra\s*pro", re.IGNORECASE)
_PROSHARES = re.compile(r"\bpro\s?shares\b", re.IGNORECASE)
_ULTRA = re.compile(r"\bultra", re.IGNORECASE)

#: Bare inverse "Short" — see rule 7 for every exclusion and why it is there.
_BARE_SHORT = re.compile(
    r"(?<![/\w])"                       # not "Long/Short", not "Ultrashort"
    r"(?<!\blong )(?<!\blong-)"         # not "Long Short" / "Long-Short"
    r"(?<!\bultra )(?<!\bultra-)"       # not "Ultra Short" / "Ultra-Short"
    r"\bshort\b"
    r"(?![\s-]*(?:term|duration|maturity|horizon|dated)\b)",
    re.IGNORECASE,
)

#: Municipal-bond markers. Their presence means a "Short" in the name is a
#: tenor, never a direction: no inverse municipal ETF exists.
_MUNI = re.compile(
    r"\b(?:muni|munis|municipal|tax[-\s]?free|tax[-\s]?exempt|tax[-\s]?aware)\b",
    re.IGNORECASE,
)


def is_leveraged_name(name: str | None) -> bool:
    """True when a FUND name states leveraged or inverse exposure.

    Pure name matching, with no asset-class check of its own. Passing an
    equity name here will produce false positives by design — "Build-A-Bear
    Workshop" and "10X Genomics Inc" both match. Callers holding a raw ticker
    row want `is_leveraged_fund()` instead; this is for tests and for callers
    that already know they hold a fund.
    """
    if not name:
        return False
    n = name.strip()
    if not n:
        return False

    # Rules 3, 4 — the words that say it outright.
    if _LEVERAGE_WORD.search(n) and not _LEVERAGED_LOAN.search(n):
        return True

    # Rule 5 — gearing spelled out.
    if _WORD_MULTIPLE.search(n):
        return True

    # Rules 1, 2 — numeric multipliers.
    mults = _MULTIPLIER.findall(n)
    if mults:
        for sign, magnitude in mults:
            if sign == "-" or float(magnitude) != 1.0:
                return True
        # Every multiplier present is a bare 1x. Geared only when the name
        # also states a direction — "Bear 1X" is inverse; "1x Gold" is not.
        if _DIRECTIONAL.search(n):
            return True

    # Rule 6 — ProShares' Ultra family.
    if _ULTRAPRO.search(n):
        return True
    if _PROSHARES.search(n) and _ULTRA.search(n):
        return True

    # Rule 7 — bare inverse "Short".
    return not _MUNI.search(n) and bool(_BARE_SHORT.search(n))


def is_leveraged_fund(name: str | None, asset_class: str | None) -> bool:
    """True when this row is a leveraged or inverse FUND.

    The ETF-bucket gate is load-bearing, not a shortcut: see the module
    docstring for the real company names that match the name patterns and are
    excluded only by it. `bucket_of` is reused from services/asset_class.py so
    this predicate and the scanner's own `asset_class=etf` filter can never
    disagree about what an ETF is.
    """
    if bucket_of(asset_class) != "etf":
        return False
    return is_leveraged_name(name)


__all__ = ["is_leveraged_fund", "is_leveraged_name"]
