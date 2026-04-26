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


def universe() -> list[dict[str, str]]:
    """Return the master ticker list for initial DB seed."""
    return [
        {"symbol": sym, "name": name, "sector": sector, "asset_class": "etf" if sector == "ETF" else "equity"}
        for sym, name, sector in TICKER_UNIVERSE
    ]


def fetch_snapshots() -> list[dict[str, Any]]:
    """
    Generate a batch of fresh mock snapshots with full score breakdown.
    Sub-scores are what make Tapeline's 'synthesis moat' visible to users.
    """
    now = datetime.now(UTC)
    rows = []
    for sym, _name, sector in TICKER_UNIVERSE:
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
            "sub_trend": round(sub_trend, 1),
            "sub_rs": round(sub_rs, 1),
            "sub_fundamentals": round(sub_fund, 1),
            "sub_momentum": round(sub_mom, 1),
            "sub_macro": round(sub_macro, 1),
            "sub_smart_money": round(sub_smart, 1),
            "reason": reason,
            "last_timestamp": now.isoformat(),
        })
    return rows


def _signal_from_score(score: float) -> str:
    """
    Descriptive (not prescriptive) labels describing the STATE of the factor data.
    Legal posture: never tells the user what to do. See LEGAL_CHECKLIST.md.
    """
    if score >= 85: return "HIGH CONVICTION"     # score 85-100
    if score >= 70: return "STRONG SETUP"        # score 70-84
    if score >= 55: return "CONSTRUCTIVE"        # score 55-69
    if score >= 40: return "NEUTRAL"             # score 40-54
    if score >= 25: return "CAUTION"             # score 25-39
    return "WEAK"                                 # score 0-24


def _render_reason(symbol: str, sector: str, trend: float, rs: float, fund: float, mom: float, macro: float, smart: float) -> str:
    """
    Per-ticker plain-English reason string. Designed (April 2026, post-AI-Why-
    commodity-shift) to read like a human analyst, not a template:

    - ~100 phrase variants across factor states (vs the previous 7 fixed phrases)
    - Sector-aware relative-strength clauses ("leading tech peers", "outperforming
      the oil patch", etc.)
    - Top-3 strongest factors selected, then woven with varied sentence structure
    - Same composite score will render different sentences each tick — feels
      generative without actually being LLM-generated

    Real polygon_feed should pass deterministic seeds for stability across reads;
    mock here uses fresh randomness each tick which is fine for dev.
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

_TREND_STRONG_UP = [
    "primary trend decisively up across all timeframes",
    "leadership uptrend with steepening slope",
    "breakout from multi-month base, holding gains",
    "above all major moving averages and accelerating",
    "trend strength at a fresh cycle high",
]
_TREND_UP = [
    "uptrend intact above the 50DMA",
    "higher-highs structure holding",
    "trend persistent on the daily and weekly",
    "above the 200DMA with positive slope",
    "constructive trend pattern, no breakdown signal",
]
_TREND_DOWN = [
    "trend rolling under the 50DMA",
    "primary trend under pressure",
    "lower-highs forming on the daily",
    "below 50DMA with the 200DMA flattening",
]
_TREND_STRONG_DOWN = [
    "trend broken across all timeframes",
    "below the 200DMA with negative slope",
    "structural downtrend confirmed",
    "lower-lows compounding",
    "breakdown from prior support, no reclaim",
]

_RS_STRONG_UP = [
    "leading {peer} by a wide margin",
    "outperforming {peer} on every timeframe",
    "relative strength near 12-month highs vs {peer}",
    "among the strongest names in {peer} this quarter",
]
_RS_UP = [
    "outperforming {peer}",
    "ahead of {peer} on the 1M and 3M view",
    "relative strength tilting up vs {peer}",
    "above the {peer} average",
]
_RS_DOWN = [
    "underperforming {peer}",
    "lagging {peer} on the 1M view",
    "RS line trending down vs {peer}",
]
_RS_STRONG_DOWN = [
    "lagging {peer} badly",
    "among the weakest in {peer}",
    "relative strength near 12-month lows",
    "underperforming {peer} on every timeframe",
]

_FUND_STRONG = [
    "fundamentals exceptional — margin expansion, growth accelerating",
    "fundamentals top decile (revenue + margin trend + ROE)",
    "best-in-class fundamentals on every metric we track",
    "growth and profitability both above sector median",
]
_FUND_GOOD = [
    "solid fundamentals (revenue trend, margins, balance sheet)",
    "fundamentals supportive — clean balance sheet, healthy margins",
    "fundamentals trend up — margin and growth both improving",
    "fundamentals score above sector median",
]
_FUND_WEAK = [
    "fundamentals deteriorating — margin compression visible",
    "weak fundamentals — debt high, growth slowing",
    "fundamentals below sector median",
    "EPS revisions trending down",
]

_MOM_STRONG = [
    "momentum accelerating into the move",
    "RSI on a fresh leg up, volume confirming",
    "momentum reading at a 6-month high",
    "thrust signal triggered, breadth widening",
]
_MOM_WEAK = [
    "momentum stalling — bearish RSI divergence forming",
    "thrust fading on lighter volume",
    "momentum below the 6-month average",
    "negative momentum divergence on the daily",
]

_SMART_BUYING = [
    "elite institutions adding (recent 13F filings)",
    "insider net buying over the last 90 days",
    "smart-money flow positive — institutional + insider",
    "Congressional buys disclosed in the last 30 days",
    "institutional positioning bullish",
]
_SMART_SELLING = [
    "insider net selling over the last 90 days",
    "smart-money flow negative — institutional positions trimmed",
    "elite institutions reducing (recent 13F filings)",
    "Congressional sells outnumber buys recently",
]

_MACRO_TAILWIND = [
    "macro tailwind — sector aligned with the current regime",
    "favourable macro setup — rates and breadth supportive",
    "regime backdrop constructive (breadth healthy, VIX contained)",
    "macro factors aligned with the move",
]
_MACRO_HEADWIND = [
    "macro headwind — rate-sensitive in a tightening regime",
    "regime backdrop cautious — VIX elevated, breadth narrow",
    "macro factors offsetting the technical setup",
    "sector under pressure from the current macro regime",
]

_NEUTRAL = [
    "Mixed signals across factors — no decisive read.",
    "Factor data balanced; no edge in either direction.",
    "Composite reads neutral; no factor dominates.",
    "No factor extreme enough to drive a directional view.",
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
