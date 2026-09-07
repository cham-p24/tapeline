"""Crypto pairs — a separate universe with a separate score.

WHY THIS IS ITS OWN MODULE, AND NOT A WIDER `polygon_feed`
---------------------------------------------------------

Two reasons, and both are the same reason: a coin is not a stock.

**Symbols collide.** "SOL" is Solana AND Emeren Group, a real NYSE solar
company. "EOS" is a token AND Eaton Vance Enhanced Equity Income II. On
2026-09-03 production published a token's price under each of four real
companies' tickers. The vendor namespaces pairs as `X:SOLUSD`, and this module
keeps that prefix all the way into the database, so the collapse that caused
that incident cannot be expressed. `clean_symbol(..., allow_crypto=True)` is
opt-in and only this module passes it — in particular the workbook parser,
which reads a human-typed column and is where the collision actually came
from, still refuses them.

**Scores are not comparable.** The six-factor composite needs company
fundamentals and insider filings. A token has neither: no revenue, no
directors filing with the SEC. Feeding a coin through the equity composite
means two of six factors fall back to NEUTRAL 50, which is not a measurement —
it is a placeholder that would sit in the same leaderboard as a real reading
and be indistinguishable from one. So crypto gets `CRYPTO_FACTORS`, is stored
with `asset_class="crypto"`, and every ranked equity surface already excludes
it via the existing asset-class filter.

WHAT WE CAN AND CANNOT SEE
--------------------------

Verified against the live vendor on 2026-09-07:

  * `/v2/aggs/grouped/locale/global/market/crypto/{date}` returns **380 pairs
    in ONE request** — full OHLCV. This is what the module uses.
  * The real-time crypto snapshot (`/v2/snapshot/.../crypto/tickers`) returns
    **403**, and `/v3/snapshot` on a pair returns `NOT_ENTITLED`. Live crypto
    is not on the current plan.

So crypto is DAILY while equities are sub-60s, and that difference is stated
on the surface rather than smoothed over — a stale price presented as live is
the failure this codebase keeps having.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from app.services.symbols import is_crypto_symbol

logger = logging.getLogger(__name__)

#: The benchmark a coin is measured against, the way SPY is for equities.
#: Bitcoin is the market: almost every pair is more correlated with BTC than
#: with anything else, so "beat the market" for a coin means "beat BTC".
CRYPTO_BENCHMARK = "X:BTCUSD"

#: Factors that genuinely exist for a token, and the two that do not.
#:
#: Kept as data rather than prose so the honest-gap rendering on the front end
#: can read the same list the scorer uses, instead of hardcoding its own idea
#: of which spokes to grey out.
CRYPTO_FACTORS = ("trend", "rs", "momentum", "macro")
CRYPTO_FACTORS_NOT_APPLICABLE = ("fundamentals", "smart_money")

#: How many daily bars to hold per pair. 400 covers a 1-year lookback plus
#: slack for non-trading gaps; crypto trades every day, so this is ~13 months.
CRYPTO_HISTORY_DAYS = 400

#: A pair must trade at least this much in a day to be published.
#:
#: The grouped endpoint returns every pair the vendor lists, including dead
#: ones with four-figure daily volume whose "score" would be noise dressed as
#: a signal. Measured 2026-09-07: BTC turns over ~$1.09B a day, ETH ~$370M,
#: SOL ~$162M; the tail falls away steeply below $1M.
CRYPTO_MIN_DOLLAR_VOLUME = float(1_000_000)


def _grouped_path(on: date) -> str:
    return f"/v2/aggs/grouped/locale/global/market/crypto/{on.isoformat()}"


def _row_from_bar(bar: dict[str, Any]) -> dict[str, Any] | None:
    """One grouped-bar entry -> a normalized row, or None to skip it.

    Mirrors `polygon_feed._to_scanner_row`'s contract: return None rather than
    a half-built row, so a caller can never publish a partial reading.
    """
    # MUST be the namespaced form, not merely "a valid symbol".
    #
    # `clean_symbol(..., allow_crypto=True)` widens the accepted set, it does
    # not narrow it — a bare "SOL" still passes as a perfectly good equity
    # symbol. Storing that with asset_class="crypto" is precisely the
    # 2026-09-03 incident: Solana's price written onto Emeren Group's row.
    # Caught here by a smoke test before it ever ran, which is the only reason
    # this comment is not another incident write-up.
    raw = (str(bar.get("T")) if bar.get("T") is not None else "").strip().upper()
    if not is_crypto_symbol(raw):
        return None
    symbol = raw
    close = bar.get("c")
    open_ = bar.get("o")
    volume = bar.get("v")
    if close is None or not isinstance(close, int | float) or close <= 0:
        return None

    dollar_volume = float(volume or 0) * float(close)
    change_pct_1d = None
    if isinstance(open_, int | float) and open_:
        change_pct_1d = (float(close) - float(open_)) / float(open_) * 100.0

    return {
        "symbol": symbol,
        "asset_class": "crypto",
        "price": float(close),
        "day_open": float(open_) if isinstance(open_, int | float) else None,
        "day_high": float(bar["h"]) if isinstance(bar.get("h"), int | float) else None,
        "day_low": float(bar["l"]) if isinstance(bar.get("l"), int | float) else None,
        "day_close": float(close),
        # Volume is in COINS, not shares. Stored as-is for the dollar-volume
        # maths below; the display layer must label it in units, never as a
        # share count.
        "volume": int(volume) if isinstance(volume, int | float) else None,
        "change_pct_1d": change_pct_1d,
        "dollar_volume": dollar_volume,
    }


async def fetch_crypto_universe(
    client: httpx.AsyncClient,
    *,
    on: date | None = None,
    min_dollar_volume: float | None = None,
    lookback_days: int = 5,
) -> list[dict[str, Any]]:
    """Every tradeable crypto pair for the most recent day with data.

    ONE request per day tried. Crypto trades weekends, but the vendor can lag,
    so this walks back up to `lookback_days` until a day returns rows rather
    than reporting an empty universe on a slow morning — the same "a no-read is
    not a value" rule the equity feed follows.
    """
    from app.services.polygon_feed import _request

    floor = CRYPTO_MIN_DOLLAR_VOLUME if min_dollar_volume is None else min_dollar_volume
    day = on or datetime.now(UTC).date()

    errors: list[str] = []
    for back in range(lookback_days):
        target = day - timedelta(days=back)
        try:
            body = await _request(client, _grouped_path(target), params={"adjusted": "true"})
        except Exception as exc:
            # A day with no data yet answers 403, not an empty result — the
            # vendor treats "not published" as "not entitled". Measured
            # 2026-09-07: today 403s while 2026-09-04 returns 380 pairs. So an
            # error on ONE day is a reason to try the day before, not a reason
            # to report an empty universe; only exhausting the whole lookback
            # is a real failure.
            errors.append(f"{target}: {type(exc).__name__}")
            logger.info("crypto.grouped_unavailable on=%s (%s)", target, type(exc).__name__)
            continue
        results = body.get("results") or []
        if not results:
            continue

        rows = [r for r in (_row_from_bar(b) for b in results) if r is not None]
        kept = [r for r in rows if r["dollar_volume"] >= floor]
        logger.info(
            "crypto.universe on=%s pairs=%d parsed=%d above_floor=%d floor=%s",
            target, len(results), len(rows), len(kept), f"${floor:,.0f}",
        )
        return kept

    logger.warning(
        "crypto.universe_empty — no grouped bars in the last %d days (%s); "
        "publishing nothing rather than an empty universe",
        lookback_days, "; ".join(errors) or "all empty",
    )
    return []


async def fetch_crypto_history(
    client: httpx.AsyncClient,
    symbol: str,
    *,
    days: int = CRYPTO_HISTORY_DAYS,
) -> list[dict[str, Any]] | None:
    """Daily bars for one pair, oldest first, or None if the fetch FAILED.

    None and [] are different facts and the caller must be able to tell them
    apart. Returning [] on an error made a rate-limited request
    indistinguishable from a genuinely short history — measured on the first
    dry run, where a single 429 caused Ethereum and Dogecoin to be reported as
    "too new to score". Ethereum is not too new; we simply failed to ask.
    """
    from app.services.polygon_feed import _request

    end = datetime.now(UTC).date()
    start = end - timedelta(days=days)
    path = f"/v2/aggs/ticker/{symbol}/range/1/day/{start.isoformat()}/{end.isoformat()}"
    try:
        body = await _request(client, path, params={"adjusted": "true", "limit": 50000})
    except Exception:
        logger.warning("crypto.history_failed symbol=%s — skipping this pair", symbol)
        return None
    return body.get("results") or []


def pct_change(bars: list[dict[str, Any]], days: int) -> float | None:
    """Percent change over the last `days` bars, or None if we lack the history.

    None, never 0.0. A pair listed three weeks ago has no 3-month return, and
    returning zero would score it as "flat" — a measurement — rather than as
    absent, which is what it is.
    """
    if len(bars) < days + 1:
        return None
    then = bars[-(days + 1)].get("c")
    now = bars[-1].get("c")
    if not then or not now:
        return None
    return (float(now) - float(then)) / float(then) * 100.0


#: How many pairs get a full history fetch, ranked by dollar volume.
#:
#: Trend and relative strength need months of bars, and the grouped endpoint
#: gives one DAY across all pairs — so a year of history for all 380 would be
#: ~365 requests. Per-pair it is one request each. Scoring the liquid head
#: properly beats scoring the whole tail badly: measured 2026-09-07 the tail
#: falls off a cliff below $1M/day, and a "score" on a pair nobody trades is
#: noise wearing a number.
CRYPTO_SCORED_PAIRS = 120

#: Bars needed before a factor is computed at all, mirroring the equity rule
#: that a short history yields None rather than a flattering zero.
_MIN_BARS_FOR_TREND = 95

#: Seconds between per-pair history requests.
#:
#: The same pacing discipline the Finnhub passes use, for the same reason.
#: Unpaced, the first dry run rate-limited 3 of 12 pairs — including Ethereum
#: and Dogecoin — and a rate-limited pair is simply absent from the day's
#: results. This job is detached and daily, so it has all the time it needs:
#: 120 pairs at 1.1s is about two minutes.
_PAIR_PACING_SECONDS = 1.1


async def build_crypto_rows(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """The liquid crypto universe, scored on the factors a token can have.

    Deliberately reuses `score.composite_from_factors` rather than inventing a
    crypto-specific weighting. That function's docstring explains why the
    arithmetic must exist once: on 2026-08-24 two copies drifted and CDNA
    scored 80.2 or 93.2 depending purely on which feed wrote the row.

    The consequence is real and worth stating plainly rather than engineering
    around: fundamentals and smart-money fall back to NEUTRAL 50 for a coin, so
    part of the weight is a constant and a coin's range is compressed. Measured
    against the live weights: a coin perfect on all four factors it can have
    reaches **85.0**, a strong one ~74, a weak one ~28. So coins can span the
    band but cannot reach the top of it.

    That is not a bug to be re-normalised away — it is the honest reading of a
    six-factor model applied to an instrument that has four of them, and the
    surface says so. Re-normalising would let four strong factors produce a
    number a full six-factor read never justified.
    """
    from app.services.score import composite_from_factors
    from app.services.sheet_feed import score_to_signal

    universe = await fetch_crypto_universe(client)
    if not universe:
        return []

    universe.sort(key=lambda r: -r["dollar_volume"])
    head = universe[:CRYPTO_SCORED_PAIRS]

    # The benchmark's own history, fetched once and shared by every pair.
    bench_bars = await fetch_crypto_history(client, CRYPTO_BENCHMARK)
    if bench_bars is None:
        logger.warning("crypto.benchmark_unavailable — no relative strength this run")
        bench_bars = []
    bench = {d: pct_change(bench_bars, d) for d in (63, 126, 252)}

    # The macro factor is the SAME market regime the equity path uses. Without
    # it sub_macro is None on every row and crypto silently drops to three
    # factors — which the first dry run showed as a blank macro column all the
    # way down. The regime is a property of the market, not of the instrument,
    # so a coin and a stock read the same one.
    try:
        from app.services.polygon_feed import fetch_regime

        regime_blob = await fetch_regime()
        regime = (regime_blob or {}).get("regime") if isinstance(regime_blob, dict) else None
    except Exception:
        logger.warning("crypto.regime_unavailable — macro factor absent this run")
        regime = None

    rows: list[dict[str, Any]] = []
    skipped_failed = 0
    for i, row in enumerate(head):
        if i:
            await asyncio.sleep(_PAIR_PACING_SECONDS)
        bars = await fetch_crypto_history(client, row["symbol"])
        if bars is None:
            # A failed read is not a fact about the coin. Leave whatever we
            # already hold untouched rather than overwrite it with "unscored".
            skipped_failed += 1
            continue
        if len(bars) < _MIN_BARS_FOR_TREND:
            # Too new to have a trend. Published with price and volume but no
            # score, exactly like a freshly discovered equity.
            rows.append({**row, "score": None, "signal": None})
            continue

        c3m, c6m, c1y = (pct_change(bars, d) for d in (63, 126, 252))
        factor_row = {
            "symbol": row["symbol"],
            "change_pct_3m": c3m,
            "change_pct_6m": c6m,
            "change_pct_1y": c1y,
            # Relative strength against BTC, the way equities use SPY.
            "rs_vs_spy_3m": None if c3m is None or bench[63] is None else c3m - bench[63],
            "rs_vs_spy_6m": None if c6m is None or bench[126] is None else c6m - bench[126],
            "rs_vs_spy_1y": None if c1y is None or bench[252] is None else c1y - bench[252],
            "near_52w_high_pct": _near_high_pct(bars),
            "change_pct_1m": pct_change(bars, 21),
            "market_regime": regime,
        }

        from app.services.score import sub_macro, sub_momentum, sub_rs, sub_trend

        subs: dict[str, float | None] = {
            "trend": sub_trend(factor_row),
            "rs": sub_rs(factor_row),
            "momentum": sub_momentum(factor_row),
            "macro": sub_macro(factor_row),
            # NOT measurable for a token. None, never a number — the front end
            # greys these spokes and names why.
            "fundamentals": None,
            "smart_money": None,
        }
        composite = composite_from_factors(subs)
        rows.append({
            **row,
            "score": composite,
            "signal": score_to_signal(composite) if composite is not None else None,
            "change_pct_1m": factor_row["change_pct_1m"],
            "sub_trend": subs["trend"],
            "sub_rs": subs["rs"],
            "sub_momentum": subs["momentum"],
            "sub_macro": subs["macro"],
            "sub_fundamentals": None,
            "sub_smart_money": None,
        })

    scored = sum(1 for r in rows if r.get("score") is not None)
    logger.info(
        "crypto.scored pairs=%d scored=%d too_new=%d fetch_failed=%d "
        "regime=%s benchmark=%s",
        len(rows), scored, len(rows) - scored, skipped_failed,
        regime or "unknown", CRYPTO_BENCHMARK,
    )
    return rows


def _near_high_pct(bars: list[dict[str, Any]]) -> float | None:
    """Percent below the highest close in the window, as a negative number.

    Same convention as the equity column: -3.1 means "3.1% off its high".
    """
    closes = [b.get("c") for b in bars if isinstance(b.get("c"), int | float)]
    if not closes:
        return None
    peak = max(closes)
    if not peak:
        return None
    return (closes[-1] - peak) / peak * 100.0
