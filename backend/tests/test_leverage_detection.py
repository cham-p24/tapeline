"""Leveraged/inverse detection, against REAL names from the live universe.

Every string in this file was pulled from production `tickers` on 2026-09-07
(11,781 rows) — no invented fund names, no invented company names. That matters
more here than in most tests: the whole difficulty of this predicate is that
the words which mark a geared fund are ordinary words in real names, and an
invented fixture would only ever contain the cases the author already thought
of. The false-positive half of this suite is the half that would have been
useless if made up.

Detector: services/leverage.py. The rules and the trade-offs each one makes are
documented there; this file pins the behaviour those rules produce.

Measured on that snapshot with the shipping predicate: 825 of 11,781 rows flag
(415 of the 7,417 currently scored).
"""
from __future__ import annotations

import pytest

from app.services.leverage import is_leveraged_fund, is_leveraged_name

# ═══════════════════════════════════════════════════════════════════════════
# TRUE — real geared fund names, one per issuer family + one per rule
# ═══════════════════════════════════════════════════════════════════════════
GEARED_FUND_NAMES = [
    # The two that were live in the anonymous top 10 on 2026-09-07 (ranks 7
    # and 8, both labelled STRONG SETUP). These are the reason this exists.
    "Direxion Daily COIN Bull 2X ETF",
    "ProShares Ultra NASDAQ Biotechnology",
    # Explicit multipliers, every issuer family that prints one.
    "Direxion Shares ETF Trust Direxion Daily AAPL Bull 2X ETF",
    "Tradr 2X Short AAOI Daily ETF",
    "T-Rex 2X Long Apple Daily Target ETF",
    "Leverage Shares 2X Long AAL Daily ETF",
    "GraniteShares ETF Trust GraniteShares 2x Long AAPL Daily ETF",
    "Defiance Daily Target 2X Short ASTS ETF",
    "Corgi NVDA 2x Daily ETF",
    "Teucrium 2x Daily Corn ETF",
    "Volatility Shares Trust XRP 2X ETF",
    "USCF Daily Target 2X Copper Index ETF",
    "2x Bitcoin Strategy ETF",
    "Founder-Led 2X Daily ETF",
    # Fractional and negative multipliers.
    "Investment Managers Series Trust II Tradr 1.5X Short NVDA Daily ETF",
    "ETRACS Monthly Pay 1.5X Leveraged Closed-End Fund Index ETN",
    "-1x Short VIX Futures ETF",
    "MicroSectors FANG & Innovation -3x Inverse Leveraged ETN",
    "MicroSectors -3x Short Brazil ETNs",
    # A bare 1X, which is only geared because a direction word rides with it.
    "Direxion Shares ETF Trust Direxion Daily NVDA Bear 1X ETF",
    "Investment Managers Series Trust II Tradr 1X Short Innovation Daily ETF",
    # The word, including the no-space form ETRACS actually prints.
    "MAX S&P 500 4x Leveraged ETN",
    "Miller Value Partners Leverage ETF",
    "AdvisorShares MSOS Daily Leveraged ETF",
    "Defiance Leveraged Long Income MSTR ETF",
    "ETRACS Monthly Pay 2xLeveraged Preferred Stock ETN",
    "ETRACS 2xMonthly Pay Leveraged US Small Cap High Dividend ETN Series B",
    "Leverage Shares 100% TSLA AND 100% SPCX Daily ETF",
    # Gearing spelled out in words rather than digits.
    "DB Gold Double Long ETN due February 15, 2038",
    "DB Gold Double Short ETN due February 15, 2038",
    # ProShares' Ultra family — the one rule that needs the issuer.
    "ProShares Ultra S&P500",
    "ProShares Ultra Bloomberg Crude Oil",
    "ProShares UltraShort Lehman 20+ Year Treasury",
    "ProShares Trust UltraShort MSCI Japan",
    "Proshares UltraShort Technology",
    "ProShares UltraPro QQQ",
    "ProShares UltraPro Short Russell2000",
    # Un-geared inverse, which prints no multiplier at all.
    "ProShares Short S&P500",
    "ProShares Short QQQ",
    "ProShares Short High Yield",
    "ProShares Short 20+ Year Treasury ETF",
    "ProShares Short VIX Short-Term Futures ETF",
    "ProShares Trust Short MSCI Emerging Markets",
    "DB Gold Short ETN due February 15, 2038",
    "AdvisorShares Dorsey Wright Short ETF",
    "Gotham Short Strategies ETF",
    "YieldMax Short TSLA Option Income Strategy ETF",
    "YieldMax MSTR Short Option Income Strategy ETF",
    "Inverse VIX Short-Term Futures ETNs due March 22, 2045",
]

# ═══════════════════════════════════════════════════════════════════════════
# FALSE — real ETF names that carry a scary word and are NOT geared
# ═══════════════════════════════════════════════════════════════════════════
ORDINARY_FUND_NAMES = [
    # "Ultra-short" is the bond market's word for the LOWEST-volatility end of
    # fixed income. Same token as ProShares' geared brand, opposite meaning —
    # including the one-word spelling four issuers use.
    "Vanguard Ultra-Short Bond ETF",
    "Vanguard Ultra-Short Treasury ETF",
    "JPMorgan Ultra-Short Income ETF",
    "PIMCO Ultra Short Government Active ETF",
    "PGIM Ultra Short Bond ETF",
    "Goldman Sachs Ultra Short Bond ETF",
    "iShares Ultra Short Duration Bond Active ETF",
    "Angel Oak UltraShort Income ETF",
    "DoubleLine Ultrashort Income ETF",
    "Dimensional Ultrashort Fixed Income ETF",
    "Federated Hermes Ultrashort Bond ETF",
    "F/m Accumulator Ultrashort Treasury Fund",
    "abrdn Ultra Short Municipal Income Active ETF",
    "T. Rowe Price Ultra Short-Term Bond ETF",
    # "Ultra" as a plain intensifier.
    "EA Bridgeway Ultra-Small Company Market ETF",
    "Invesco S&P Ultra Dividend Revenue ETF",
    "Innovator U.S. Equity Ultra Buffer ETF - April",
    "YieldMax Ultra Option Income Strategy ETF",
    "UPAR Ultra Risk Parity ETF",
    # "Short" as a TENOR. 265 live ETFs contain the word; almost all are these.
    "Vanguard Short-Term Corporate Bond ETF",
    "Schwab Short-Term U.S. Treasury ETF",
    "Columbia Short Duration Bond ETF",
    "PIMCO Enhanced Short Maturity Active ESG ETF",
    "Twin Oak Short Horizon Absolute Return ETF",
    "Simplify Short Term Treasury Futures Strategy ETF",
    "GraniteShares Short Term Box ETF",
    "iPath VIX Short-Term",
    "ProShares VIX Short-Term Futures ETF",
    # Short-duration MUNI funds, whose prefix is textually identical to
    # ProShares' inverse "Short High Yield".
    "VanEck Short High Yield Muni ETF",
    "VanEck Short Muni ETF",
    "T. Rowe Price Short Municipal Income ETF",
    "Northern Trust Short-Term Tax-Exempt Bond ETF",
    "BondBloxx IR+M Tax Aware Short Duration ETF",
    # Long/short strategy funds — two-sided, not inverse.
    "First Trust Long/Short Equity ETF",
    "Convergence Long/Short Equity ETF",
    "Harbor Long-Short Equity ETF",
    "Even Herd Long Short ETF",
    "WisdomTree Efficient Long/Short U.S. Equity Fund",
    "ProShares Long Online/Short Stores ETF",
    # "Leveraged loan" is an asset class, not gearing.
    "State Street SPDR S&P Leveraged Loan ETF",
    # A bare 1x means exactly 1x.
    "IncomeSTKd 1x Bitcoin & 1x Gold Premium ETF",
    "IncomeSTKd 1x US Stocks & 1x Bitcoin Premium ETF",
    # Ordinary funds that merely mention a direction.
    "TrueShares Quarterly Bull Hedge ETF",
    "TrueShares Quarterly Bear Hedge ETF",
    "Simplify Bond Bull ETF",
    "JPMorgan BetaBuilders U.S. Aggregate Bond ETF",
    "SPDR S&P 500 ETF Trust",
    "Invesco QQQ Trust",
    "VanEck Biotech ETF",
    "Virtus Biotech ETF",
]

# ═══════════════════════════════════════════════════════════════════════════
# FALSE — real COMPANY names that match the name patterns.
# These are why is_leveraged_fund refuses to look outside the ETF bucket.
# ═══════════════════════════════════════════════════════════════════════════
REAL_COMPANY_NAMES = [
    "Build-A-Bear Workshop, Inc.",      # the hyphen IS a word boundary
    "BigBear.ai Holdings, Inc.",
    "Maplebear Inc. Common Stock",
    "RBC Bearings Inc",
    "Bullfrog AI Holdings, Inc. Common Stock",
    "Bullish",
    "Webull Corporation Class A Ordinary Shares",
    "Ultragenyx Pharmaceutical Inc.",
    "Ultra Clean Holdings Inc",
    "Ultrapar Participacoes SA",
    "Ultralife Corporation",
    "KPET Ultra Paceline Corporation",
    "10X Genomics Inc",                 # a bare multiplier in a company name
    "V2X, Inc.",
    "Longeveron Inc. Common Stock",
    "J-Long Group Limited Class A Ordinary Shares",
    "Julong Holding Limited Class A Ordinary Shares",
    "Elong Power Holding Limited Class A Ordinary Shares",
    "Long Table Growth Corp. Class A Ordinary Shares",
    "Trex Company Inc",
    "CEMTREX INC.",
    "Diana Shipping, Inc.",
    "Docebo Inc. Common Shares",
    "Caledonia Mining Corporation Plc",
    "Calamos Long/Short Equity & Dynamic Income Trust Common Stock",
    "PGIM Short Duration High Yield Opportunities Fund",
]


@pytest.mark.parametrize("name", GEARED_FUND_NAMES)
def test_real_geared_fund_names_are_detected(name: str) -> None:
    assert is_leveraged_name(name) is True, f"missed a geared fund: {name!r}"
    assert is_leveraged_fund(name, "etf") is True


@pytest.mark.parametrize("name", ORDINARY_FUND_NAMES)
def test_real_ordinary_fund_names_are_not_detected(name: str) -> None:
    """The expensive half. A false positive here publishes a WRONG structural
    fact on a real fund's row and hides it from the default ranked view."""
    assert is_leveraged_name(name) is False, f"false positive: {name!r}"
    assert is_leveraged_fund(name, "etf") is False


@pytest.mark.parametrize("name", REAL_COMPANY_NAMES)
def test_real_company_names_are_never_flagged_as_funds(name: str) -> None:
    for asset_class in ("equity", "stock"):
        assert is_leveraged_fund(name, asset_class) is False, (
            f"{name!r} was flagged as a leveraged fund at asset_class="
            f"{asset_class!r}"
        )


def test_the_asset_class_gate_is_what_saves_the_last_company_name() -> None:
    """The gate is not decoration — stated as an assertion so nobody
    'simplifies' is_leveraged_fund down to is_leveraged_name.

    "10X Genomics Inc" (TXG) is the ONLY equity in the 11,781-row live
    universe that the bare NAME matcher flags. It is a real listed company and
    it is caught by nothing except the ETF-bucket gate. The first assertion
    exists so that if a future rules change stops the name matcher firing
    here, this test fails loudly rather than passing while testing nothing —
    the exact way a guard silently stops guarding.
    """
    name = "10X Genomics Inc"
    assert is_leveraged_name(name) is True, (
        "this test is only meaningful while the bare NAME matcher still "
        "matches this — pick another real equity that it does match, or the "
        "gate is untested"
    )
    assert is_leveraged_fund(name, "equity") is False


def test_the_gate_uses_the_shared_asset_class_mapping() -> None:
    """'fund' is the etf bucket's synonym in services/asset_class.py. A hand
    rolled `== "etf"` check here would silently pass geared funds through on a
    vendor wording change, which is the bug asset_class.py exists to prevent."""
    name = "ProShares UltraPro QQQ"
    assert is_leveraged_fund(name, "etf") is True
    assert is_leveraged_fund(name, "fund") is True
    assert is_leveraged_fund(name, "  ETF  ") is True
    assert is_leveraged_fund(name, "future_commodity") is False
    assert is_leveraged_fund(name, "") is False


def test_empty_and_missing_names_are_not_flagged() -> None:
    for name in (None, "", "   "):
        assert is_leveraged_name(name) is False
        assert is_leveraged_fund(name, "etf") is False


def test_a_multiplier_needs_a_boundary_on_both_sides() -> None:
    """The lookarounds, stated directly.

    Left: "V2X" and the "5X" inside "1.5X" must not start a match.
    Right: a following alphanumeric must not be swallowed.
    """
    assert is_leveraged_name("V2X, Inc.") is False
    assert is_leveraged_name("Xtrackers Short Duration High Yield Bond ETF") is False
    assert is_leveraged_name("ProShares Ultra XRP ETF") is True  # via ProShares
    assert is_leveraged_name("Tradr 1.5X Short NVDA Daily ETF") is True
