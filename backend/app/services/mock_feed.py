"""
Mock market data source — drop-in replacement for `polygon_feed` during
development. Generates plausible, continuously-varying ticker data so the
full pipeline (DB → API → SSE → frontend) works before a Polygon key lands.

Swap at the `main.py` import line when real data is ready:
    from app.services.mock_feed import fetch_snapshots  ->  polygon_feed
"""
from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta
from typing import Any

# ~80 liquid US tickers across sectors — enough for a meaningful scanner
TICKER_UNIVERSE: list[tuple[str, str, str]] = [
    # (symbol, name, sector)
    ("AAPL", "Apple Inc.", "Technology"),
    ("MSFT", "Microsoft Corp.", "Technology"),
    ("NVDA", "NVIDIA Corp.", "Technology"),
    ("GOOGL", "Alphabet Inc.", "Technology"),
    ("META", "Meta Platforms", "Technology"),
    ("AMZN", "Amazon.com Inc.", "Consumer Discretionary"),
    ("TSLA", "Tesla Inc.", "Consumer Discretionary"),
    ("AMD", "Advanced Micro Devices", "Technology"),
    ("AVGO", "Broadcom Inc.", "Technology"),
    ("ORCL", "Oracle Corp.", "Technology"),
    ("CRM", "Salesforce Inc.", "Technology"),
    ("ADBE", "Adobe Inc.", "Technology"),
    ("NFLX", "Netflix Inc.", "Communication Services"),
    ("DIS", "Walt Disney Co.", "Communication Services"),
    ("JPM", "JPMorgan Chase", "Financials"),
    ("BAC", "Bank of America", "Financials"),
    ("WFC", "Wells Fargo", "Financials"),
    ("GS", "Goldman Sachs", "Financials"),
    ("MS", "Morgan Stanley", "Financials"),
    ("V", "Visa Inc.", "Financials"),
    ("MA", "Mastercard Inc.", "Financials"),
    ("BRK.B", "Berkshire Hathaway", "Financials"),
    ("JNJ", "Johnson & Johnson", "Healthcare"),
    ("UNH", "UnitedHealth Group", "Healthcare"),
    ("PFE", "Pfizer Inc.", "Healthcare"),
    ("LLY", "Eli Lilly & Co.", "Healthcare"),
    ("ABBV", "AbbVie Inc.", "Healthcare"),
    ("MRK", "Merck & Co.", "Healthcare"),
    ("TMO", "Thermo Fisher", "Healthcare"),
    ("DHR", "Danaher Corp.", "Healthcare"),
    ("XOM", "ExxonMobil", "Energy"),
    ("CVX", "Chevron Corp.", "Energy"),
    ("COP", "ConocoPhillips", "Energy"),
    ("SLB", "Schlumberger", "Energy"),
    ("OXY", "Occidental Petroleum", "Energy"),
    ("MPC", "Marathon Petroleum", "Energy"),
    ("HD", "Home Depot", "Consumer Discretionary"),
    ("LOW", "Lowe's Companies", "Consumer Discretionary"),
    ("NKE", "Nike Inc.", "Consumer Discretionary"),
    ("SBUX", "Starbucks Corp.", "Consumer Discretionary"),
    ("MCD", "McDonald's Corp.", "Consumer Discretionary"),
    ("BKNG", "Booking Holdings", "Consumer Discretionary"),
    ("WMT", "Walmart Inc.", "Consumer Staples"),
    ("COST", "Costco Wholesale", "Consumer Staples"),
    ("PG", "Procter & Gamble", "Consumer Staples"),
    ("KO", "Coca-Cola Co.", "Consumer Staples"),
    ("PEP", "PepsiCo Inc.", "Consumer Staples"),
    ("BA", "Boeing Co.", "Industrials"),
    ("CAT", "Caterpillar Inc.", "Industrials"),
    ("DE", "Deere & Co.", "Industrials"),
    ("HON", "Honeywell International", "Industrials"),
    ("UPS", "United Parcel Service", "Industrials"),
    ("LMT", "Lockheed Martin", "Industrials"),
    ("RTX", "RTX Corp.", "Industrials"),
    ("GE", "GE Aerospace", "Industrials"),
    ("UNP", "Union Pacific", "Industrials"),
    ("T", "AT&T Inc.", "Communication Services"),
    ("VZ", "Verizon Communications", "Communication Services"),
    ("TMUS", "T-Mobile US", "Communication Services"),
    ("NEE", "NextEra Energy", "Utilities"),
    ("DUK", "Duke Energy", "Utilities"),
    ("SO", "Southern Co.", "Utilities"),
    ("LIN", "Linde PLC", "Materials"),
    ("FCX", "Freeport-McMoRan", "Materials"),
    ("NEM", "Newmont Corp.", "Materials"),
    ("AEM", "Agnico Eagle Mines", "Materials"),
    # ===== Commodities (ETFs only — Polygon Starter doesn't include futures) =====
    ("GLD", "SPDR Gold Shares", "Commodities"),
    ("IAU", "iShares Gold Trust", "Commodities"),
    ("SLV", "iShares Silver Trust", "Commodities"),
    ("AGQ", "ProShares Ultra Silver", "Commodities"),
    ("PALL", "abrdn Physical Palladium Shares", "Commodities"),
    ("PPLT", "abrdn Physical Platinum Shares", "Commodities"),
    ("USO", "United States Oil Fund", "Commodities"),
    ("BNO", "United States Brent Oil Fund", "Commodities"),
    ("UCO", "ProShares Ultra Bloomberg Crude Oil", "Commodities"),
    ("SCO", "ProShares UltraShort Bloomberg Crude Oil", "Commodities"),
    ("DBO", "Invesco DB Oil Fund", "Commodities"),
    ("UNG", "United States Natural Gas Fund", "Commodities"),
    ("BOIL", "ProShares Ultra Bloomberg Natural Gas", "Commodities"),
    ("KOLD", "ProShares UltraShort Bloomberg Natural Gas", "Commodities"),
    ("DBA", "Invesco DB Agriculture Fund", "Commodities"),
    ("DBC", "Invesco DB Commodity Index", "Commodities"),
    ("CORN", "Teucrium Corn Fund", "Commodities"),
    ("WEAT", "Teucrium Wheat Fund", "Commodities"),
    ("SOYB", "Teucrium Soybean Fund", "Commodities"),
    ("CANE", "Teucrium Sugar Fund", "Commodities"),
    ("MOO", "VanEck Agribusiness ETF", "Commodities"),
    ("WOOD", "iShares Global Timber & Forestry ETF", "Commodities"),
    ("CPER", "United States Copper Index Fund", "Commodities"),
    ("COPX", "Global X Copper Miners ETF", "Commodities"),
    ("GDX", "VanEck Gold Miners ETF", "Commodities"),
    ("GDXJ", "VanEck Junior Gold Miners ETF", "Commodities"),
    ("URA", "Global X Uranium ETF", "Commodities"),
    ("URNM", "Sprott Uranium Miners ETF", "Commodities"),
    ("XME", "SPDR S&P Metals & Mining ETF", "Commodities"),
    ("PICK", "iShares MSCI Global Metals & Mining Producers ETF", "Commodities"),
    ("LIT", "Global X Lithium & Battery Tech ETF", "Commodities"),
    ("REMX", "VanEck Rare Earth/Strategic Metals ETF", "Commodities"),
    ("SPY", "SPDR S&P 500 ETF", "ETF"),
    ("QQQ", "Invesco QQQ Trust", "ETF"),
    ("IWM", "iShares Russell 2000", "ETF"),
    ("DIA", "SPDR DJIA ETF", "ETF"),
    ("VTI", "Vanguard Total Market", "ETF"),
    ("ARKK", "ARK Innovation ETF", "ETF"),
    ("SMH", "VanEck Semiconductor", "ETF"),
    ("XLK", "Technology Select SPDR", "ETF"),
    ("XLF", "Financial Select SPDR", "ETF"),
    ("XLE", "Energy Select SPDR", "ETF"),
    ("XLV", "Health Care Select", "ETF"),
    ("TLT", "iShares 20+ Year Treasury", "ETF"),
    ("HYG", "iShares High Yield Corp", "ETF"),
    ("VXX", "iPath VIX Short-Term", "ETF"),
]

# Seed deterministic baseline prices so the mock isn't chaotic across restarts
random.seed(1337)
_BASELINE_PRICES: dict[str, float] = {sym: random.uniform(25, 500) for sym, _, _ in TICKER_UNIVERSE}
_DRIFT: dict[str, float] = {sym: random.uniform(-0.0002, 0.0002) for sym, _, _ in TICKER_UNIVERSE}


def _ensure_baseline(sym: str) -> None:
    """Lazy-initialise the random walk for a symbol that wasn't in the
    original hardcoded TICKER_UNIVERSE. Called when the active universe
    is sourced from the DB (services/universe.py) and includes names
    we hadn't pre-seeded. Deterministic per-symbol so reruns are stable.
    """
    if sym in _BASELINE_PRICES:
        return
    rng = random.Random(sum(ord(c) for c in sym) * 7919)
    _BASELINE_PRICES[sym] = rng.uniform(25, 500)
    _DRIFT[sym] = rng.uniform(-0.0002, 0.0002)


def universe() -> list[dict[str, str]]:
    """Return the master ticker list for initial DB seed."""
    return [
        {"symbol": sym, "name": name, "sector": sector, "asset_class": "etf" if sector == "ETF" else "equity"}
        for sym, name, sector in TICKER_UNIVERSE
    ]


def fetch_snapshots(
    universe_override: list[tuple[str, str, str]] | None = None,
) -> list[dict[str, Any]]:
    """
    Generate a batch of fresh mock snapshots with full score breakdown.
    Sub-scores are what make Tapeline's 'synthesis moat' visible to users.

    `universe_override` lets the caller (typically polygon_feed) pass a
    larger, DB-sourced active universe of (symbol, name, sector) tuples.
    Falls back to the hardcoded TICKER_UNIVERSE when None — preserves
    test + dev behaviour.
    """
    universe_list = universe_override if universe_override is not None else TICKER_UNIVERSE
    now = datetime.now(UTC)
    rows = []
    for sym, _name, sector in universe_list:
        _ensure_baseline(sym)
        shock = random.gauss(0, 0.004)
        _BASELINE_PRICES[sym] *= max(0.5, 1 + _DRIFT[sym] + shock)
        price = round(_BASELINE_PRICES[sym], 2)

        # Generate sub-scores — each 0..100, weighted into composite
        sub_trend = max(0, min(100, random.gauss(55, 22)))
        sub_rs = max(0, min(100, random.gauss(55, 20)))
        sub_fund = max(0, min(100, random.gauss(60, 18)))
        sub_mom = max(0, min(100, random.gauss(55, 25)))
        sub_macro = max(0, min(100, random.gauss(55, 15)))
        sub_smart = max(0, min(100, random.gauss(55, 20)))

        # Weights mirror the personal signal engine: trend .25 rs .20 fund .15 smart .15 macro .15 mom .10
        score = (
            sub_trend * 0.25
            + sub_rs * 0.20
            + sub_fund * 0.15
            + sub_smart * 0.15
            + sub_macro * 0.15
            + sub_mom * 0.10
        )
        score = max(0, min(100, score))

        signal = _signal_from_score(score)
        reason = _render_reason(sym, sector, sub_trend, sub_rs, sub_fund, sub_mom, sub_macro, sub_smart)

        rows.append({
            "symbol": sym,
            "score": round(score, 1),
            "signal": signal,
            "price": price,
            "change_pct_1d": round(random.gauss(0, 1.2), 2),
            "change_pct_5d": round(random.gauss(0, 3.0), 2),
            "change_pct_1m": round(random.gauss(2, 6.0), 2),
            "volume": int(random.uniform(500_000, 50_000_000)),
            # No real market-cap source on the mock path — real cap is threaded
            # in by polygon_feed from the Finnhub profile cache. Null here renders
            # as an em-dash in the scanner.
            "market_cap": None,
            "sub_trend": round(sub_trend, 1),
            "sub_rs": round(sub_rs, 1),
            "sub_fundamentals": round(sub_fund, 1),
            "sub_momentum": round(sub_mom, 1),
            "sub_macro": round(sub_macro, 1),
            "sub_smart_money": round(sub_smart, 1),
            "confidence_pct": _compute_mock_confidence(sym),
            "reason": reason,
            "last_timestamp": now.isoformat(),
        })
    return rows


def _compute_mock_confidence(symbol: str) -> float:
    """
    Per-ticker confidence — deterministic per symbol so the same ticker always
    shows the same confidence band across worker restarts. Real polygon_feed
    should compute this from actual data-feed presence (% of optional features
    that returned non-null data).

    Bands (matching the personal signal-system layout the user already validated):
    - 95%+:  full data on every signal feature (premium + Finnhub + FINRA)
    - 80-95%: most features, missing 1-3 minor data points
    - 60-80%: core scoring data + most fundamentals — typical liquid stock
    - 40-60%: only basic price/trend data (typical for ETFs without P/E)
    - <40%:  sparse data, deprioritise (rare in mock — used for plausibility)
    """
    seed = sum(ord(c) for c in symbol) * 7919  # arbitrary prime mixer
    rng = random.Random(seed)

    # Mega-caps — every data provider covers these, Finnhub fundamentals
    # fully populated, news volume high.
    if symbol in _MEGA_CAP_SET:
        return round(rng.uniform(88, 96), 1)

    # ETFs and commodity ETFs have no traditional fundamentals (no P/E, no margins).
    # Score still works (trend/rs/momentum/macro all apply) but confidence drops.
    if symbol in _ETF_SET:
        return round(rng.uniform(45, 70), 1)

    # The long tail of liquid US equities — typical band.
    return round(rng.uniform(60, 85), 1)


# Confidence-band universes — kept here to avoid recomputing per-tick
_MEGA_CAP_SET = {
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "BRK.B",
    "JPM", "V", "MA", "WMT", "COST", "UNH", "LLY", "AVGO", "ORCL",
    "JNJ", "PG", "HD", "BAC", "XOM", "CVX",
}
_ETF_SET = {
    # Index / sector ETFs
    "SPY", "QQQ", "IWM", "DIA", "VTI", "ARKK", "SMH",
    "XLK", "XLF", "XLE", "XLV", "TLT", "HYG", "VXX",
    # Commodity ETFs
    "GLD", "IAU", "SLV", "AGQ", "PALL", "PPLT",
    "USO", "BNO", "UCO", "SCO", "DBO", "UNG", "BOIL", "KOLD",
    "DBA", "DBC", "CORN", "WEAT", "SOYB", "CANE", "MOO", "WOOD",
    "CPER", "COPX", "GDX", "GDXJ", "URA", "URNM", "XME", "PICK",
    "LIT", "REMX",
}


def _signal_from_score(score: float | None) -> str | None:
    """
    Descriptive (not prescriptive) labels describing the STATE of the factor data.
    Legal posture: never tells the user what to do. See LEGAL_CHECKLIST.md.

    None in, None out: a label is a claim about a score, so with no score there
    is no label to make. polygon_feed imports THIS function (shadowing its own
    module-level copy), so this is the branch the production path runs.
    """
    if score is None:
        return None
    if score >= 85: return "HIGH CONVICTION"     # score 85-100
    if score >= 70: return "STRONG SETUP"        # score 70-84
    if score >= 55: return "CONSTRUCTIVE"        # score 55-69
    if score >= 40: return "NEUTRAL"             # score 40-54
    if score >= 25: return "CAUTION"             # score 25-39
    return "WEAK"                                 # score 0-24


def _render_reason(symbol: str, sector: str, trend: float, rs: float, fund: float, mom: float, macro: float, smart: float) -> str:
    """
    Per-ticker reason string that describes WHICH of Tapeline's six factor
    scores are driving the composite, and nothing else.

    - Selects the top-3 factors furthest from the 50 midpoint and states each
      one's score band in plain, DESCRIPTIVE language (see the phrase banks).
    - Every clause is a statement about a factor SCORE — never a claim about a
      specific external event (a filing, a Congressional trade, a particular
      RSI/DMA/VIX reading) and never an evaluative adjective on the security.
      This is a hard compliance boundary: the clauses are chosen from the
      sub-scores alone, and five of the six sub-scores are still synthesised
      rather than sourced (see polygon_feed), so anything beyond "this factor
      scores high/low" would be a fabricated claim about a real security.
    - Sentence structure varies for readability; the substance is fixed by the
      scores. (Real polygon_feed should pass deterministic seeds for stable
      wording across reads.)
    """
    parts: list[tuple[float, str]] = []  # (abs_strength, phrase)

    if trend >= 80:
        parts.append((trend - 50, _pick(_TREND_STRONG_UP)))
    elif trend >= 65:
        parts.append((trend - 50, _pick(_TREND_UP)))
    elif trend <= 20:
        parts.append((50 - trend, _pick(_TREND_STRONG_DOWN)))
    elif trend <= 35:
        parts.append((50 - trend, _pick(_TREND_DOWN)))

    if rs >= 75:
        parts.append((rs - 50, _pick_sector(_RS_STRONG_UP, sector)))
    elif rs >= 60:
        parts.append((rs - 50, _pick_sector(_RS_UP, sector)))
    elif rs <= 25:
        parts.append((50 - rs, _pick_sector(_RS_STRONG_DOWN, sector)))
    elif rs <= 40:
        parts.append((50 - rs, _pick_sector(_RS_DOWN, sector)))

    if fund >= 75:
        parts.append((fund - 50, _pick(_FUND_STRONG)))
    elif fund >= 60:
        parts.append((fund - 50, _pick(_FUND_GOOD)))
    elif fund <= 25:
        parts.append((50 - fund, _pick(_FUND_WEAK)))

    if mom >= 75:
        parts.append((mom - 50, _pick(_MOM_STRONG)))
    elif mom <= 25:
        parts.append((50 - mom, _pick(_MOM_WEAK)))

    if smart >= 70:
        parts.append((smart - 50, _pick(_SMART_BUYING)))
    elif smart <= 30:
        parts.append((50 - smart, _pick(_SMART_SELLING)))

    if macro >= 70:
        parts.append((macro - 50, _pick(_MACRO_TAILWIND)))
    elif macro <= 30:
        parts.append((50 - macro, _pick(_MACRO_HEADWIND)))

    if not parts:
        return _pick(_NEUTRAL)

    # Lead with the strongest factor; take up to 3 to keep sentences readable
    parts.sort(key=lambda p: p[0], reverse=True)
    phrases = [p[1] for p in parts[:3]]

    if len(phrases) == 1:
        return phrases[0].rstrip(".") + "."
    if len(phrases) == 2:
        connector = random.choice([", with ", " — ", "; "])
        return phrases[0].rstrip(".") + connector + phrases[1].rstrip(".") + "."
    # 3 phrases — vary the structure
    structure = random.choice([
        "{0}; {1}, {2}.",
        "{0}. {1} and {2}.",
        "{0} — {1}, while {2}.",
        "{0}; {1}; {2}.",
    ])
    return structure.format(*[p.rstrip(".") for p in phrases])


def _pick(bank: list[str]) -> str:
    return random.choice(bank)


def _pick_sector(bank: list[str], sector: str) -> str:
    """Phrase banks with {peer} placeholder get the sector-appropriate peer label."""
    peer = _SECTOR_PEER.get(sector, "the sector")
    return random.choice(bank).format(peer=peer)


# ---- Phrase banks --------------------------------------------------------
# Sector-specific peer language for the relative-strength factor.
_SECTOR_PEER = {
    "Technology":             "tech peers",
    "Financials":             "the financials sector",
    "Healthcare":             "healthcare peers",
    "Energy":                 "the oil patch",
    "Consumer Discretionary": "discretionary peers",
    "Consumer Staples":       "the staples group",
    "Industrials":            "industrial peers",
    "Communication Services": "comms peers",
    "Utilities":              "utility peers",
    "Materials":              "materials peers",
    "Commodities":            "the commodities complex",
    "ETF":                    "the broader market",
}

# COMPLIANCE (2026-07): every phrase below describes Tapeline's own 0-100
# factor SCORE band and nothing else. A phrase must NOT (a) assert a specific
# external event the system has not verified — no "Form 4 filings",
# "Congressional buys", "insiders trimming", no specific RSI/DMA/VIX/12-month-
# high reading — and must NOT (b) apply an evaluative adjective to the security
# (exceptional / best-in-class / solid / weak / bullish / by a wide margin).
# Reason:  these clauses are selected purely from the factor sub-score, and
# five of the six sub-scores are still synthesised rather than sourced (see
# polygon_feed's docstring). Describing the score band is honest; asserting a
# market fact or a specific filing/technical reading is a fabricated claim
# about a real security. Keep new phrases score-descriptive only.
_TREND_STRONG_UP = [
    "trend factor in the top band of its score",
    "trend among this ticker's highest-scoring factors",
    "trend factor near the top of its range",
]
_TREND_UP = [
    "trend factor above the score midpoint",
    "trend factor on the upper side of its range",
    "positive trend factor reading",
]
_TREND_DOWN = [
    "trend factor below the score midpoint",
    "trend factor on the lower side of its range",
]
_TREND_STRONG_DOWN = [
    "trend factor in the bottom band of its score",
    "trend among this ticker's lowest-scoring factors",
    "trend factor near the bottom of its range",
]

_RS_STRONG_UP = [
    "relative-strength factor in the top band vs {peer}",
    "relative-strength among this ticker's highest-scoring factors vs {peer}",
    "relative-strength factor near the top of its range vs {peer}",
]
_RS_UP = [
    "relative-strength factor above the midpoint vs {peer}",
    "relative-strength factor on the upper side vs {peer}",
]
_RS_DOWN = [
    "relative-strength factor below the midpoint vs {peer}",
    "relative-strength factor on the lower side vs {peer}",
]
_RS_STRONG_DOWN = [
    "relative-strength factor in the bottom band vs {peer}",
    "relative-strength among this ticker's lowest-scoring factors vs {peer}",
]

_FUND_STRONG = [
    "fundamentals factor in the top band (revenue, margin, ROE inputs)",
    "fundamentals among this ticker's highest-scoring factors",
    "fundamentals factor near the top of its range",
]
_FUND_GOOD = [
    "fundamentals factor above the score midpoint",
    "fundamentals factor on the upper side of its range",
]
_FUND_WEAK = [
    "fundamentals factor below the score midpoint",
    "fundamentals factor in the lower band of its range",
]

_MOM_STRONG = [
    "momentum factor in the top band of its score",
    "momentum among this ticker's highest-scoring factors",
    "momentum factor near the top of its range",
]
_MOM_WEAK = [
    "momentum factor below the score midpoint",
    "momentum factor in the lower band of its range",
]

_SMART_BUYING = [
    "smart-money factor above the score midpoint",
    "smart-money factor on the upper side of its range",
    "smart-money factor near the top of its range",
]
_SMART_SELLING = [
    "smart-money factor below the score midpoint",
    "smart-money factor in the lower band of its range",
]

_MACRO_TAILWIND = [
    "macro factor above the midpoint for the current regime",
    "macro factor on the upper side for the current regime",
]
_MACRO_HEADWIND = [
    "macro factor below the midpoint for the current regime",
    "macro factor in the lower band for the current regime",
]

_NEUTRAL = [
    "Factor scores are balanced; no single factor drives the composite.",
    "Composite reads neutral; no factor at an extreme.",
    "Mixed factor scores; no factor stands out either way.",
]


def fetch_squeezes() -> list[dict[str, Any]]:
    """Pick ~15 random tickers and generate plausible squeeze setups."""
    random.shuffle(list(_BASELINE_PRICES.keys()))
    sample = random.sample([s for s, _, _ in TICKER_UNIVERSE], k=15)
    setups = []
    for sym in sample:
        spike = round(random.uniform(45, 95), 1)
        days = random.randint(5, 28)
        vol = round(random.uniform(1.1, 4.5), 2)
        obv = random.choice(["RISING", "FLAT", "DIVERGENT"])
        breakout = random.choice(["COIL", "SQUEEZE", "EXPANSION PENDING", "VOLATILITY CONTRACTION"])
        window = random.choice(["1-2 weeks", "1-4 weeks", "2-6 weeks", "days"])
        setups.append({
            "symbol": sym,
            "spike_score": spike,
            "squeeze_days": days,
            "volume_multiple": vol,
            "obv_trend": obv,
            "breakout_type": breakout,
            "suggested_window": window,
            "reason": f"BB squeeze {days}d, volume {vol}x avg, OBV {obv.lower()}",
        })
    return setups


def fetch_regime() -> dict[str, Any]:
    """Regime walks slowly — changes label every ~20 ticks on average."""
    vix = round(random.uniform(12, 28), 2)
    regime = (
        "BULL" if vix < 15
        else "NEUTRAL" if vix < 20
        else "CAUTIOUS" if vix < 25
        else "BEAR"
    )
    return {
        "regime": regime,
        "vix": vix,
        "dxy": round(random.uniform(100, 108), 2),
        "yield_10y": round(random.uniform(3.8, 4.8), 3),
        "rate_direction": random.choice(["RISING", "FALLING", "SIDEWAYS"]),
        "breadth_pct": round(random.uniform(35, 75), 1),
        "sector_leaders": ", ".join(random.sample(
            ["Technology", "Energy", "Financials", "Healthcare", "Industrials", "Materials"], 3
        )),
    }


def fetch_congress_trades() -> list[dict[str, Any]]:
    """Generate a few fresh plausible congress trades."""
    politicians = [
        ("Nancy Pelosi", "House", "D"),
        ("Dan Crenshaw", "House", "R"),
        ("Ro Khanna", "House", "D"),
        ("Tommy Tuberville", "Senate", "R"),
        ("Josh Gottheimer", "House", "D"),
        ("Mark Kelly", "Senate", "D"),
        ("Rick Scott", "Senate", "R"),
        ("Debbie Wasserman Schultz", "House", "D"),
    ]
    trades = []
    for _ in range(random.randint(2, 6)):
        politician = random.choice(politicians)
        sym = random.choice([s for s, _, _ in TICKER_UNIVERSE if s not in {"SPY", "QQQ", "GLD"}])
        direction = random.choices(["BUY", "SELL"], weights=[0.65, 0.35])[0]
        amount_min = random.choice([1_000, 15_000, 50_000, 100_000, 250_000, 500_000])
        trade_date = date.today() - timedelta(days=random.randint(1, 30))
        disclosed = datetime.now(UTC) - timedelta(hours=random.randint(1, 72))
        trades.append({
            "politician": politician[0],
            "chamber": politician[1],
            "party": politician[2],
            "symbol": sym,
            "direction": direction,
            "amount_min": float(amount_min),
            "amount_max": float(amount_min * 2),
            "trade_date": trade_date,
            "disclosed_at": disclosed,
        })
    return trades
