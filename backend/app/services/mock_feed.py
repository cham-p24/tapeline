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
    ("GLD", "SPDR Gold Shares", "ETF"),
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
    for sym, _, _ in TICKER_UNIVERSE:
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
        reason = _render_reason(sub_trend, sub_rs, sub_fund, sub_mom, sub_macro, sub_smart)

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


def _render_reason(trend: float, rs: float, fund: float, mom: float, macro: float, smart: float) -> str:
    """Human-readable one-liner explaining the composite — shown in tooltips + emails."""
    parts = []
    if trend >= 70: parts.append("strong uptrend")
    elif trend <= 30: parts.append("downtrend")
    if rs >= 70: parts.append("outperforming sector")
    elif rs <= 30: parts.append("lagging sector")
    if fund >= 70: parts.append("solid fundamentals")
    elif fund <= 30: parts.append("weak fundamentals")
    if mom >= 75: parts.append("accelerating momentum")
    if smart >= 70: parts.append("insider/institutional buying")
    elif smart <= 30: parts.append("insider selling")
    if macro >= 70: parts.append("favorable macro backdrop")
    elif macro <= 30: parts.append("macro headwinds")
    return ", ".join(parts).capitalize() or "Mixed signals across factors"


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
