"""
Finnhub adapter — fundamentals, earnings calendar, IPO calendar, insider data.

Used to enrich Tapeline's `sub_fundamentals` factor with real financial metrics
and to replace mock earnings + IPO calendars with real upcoming events.

Auth:
    - Requires FINNHUB_API_KEY env var (free tier from https://finnhub.io/dashboard).
    - Without a key, every fetch returns None (caller falls back to mock).

Rate limits:
    - Free tier: 60 calls/minute. Plenty for Tapeline at expected volumes:
      870 tickers × weekly fundamentals refresh = ~125 calls/day = ~5/hour.
      Earnings + IPO calendars are 1 call each per refresh.

Cache:
    - 24h for fundamentals + insider (slow-moving data)
    - 12h for calendars (new earnings dates appear daily)
    - Written to backend/.cache/finnhub_*.json
"""
from __future__ import annotations

import contextlib
import json
import logging
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.services.vendor_errors import VendorThrottledError, VendorUnavailableError

logger = logging.getLogger(__name__)
settings = get_settings()

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache"
BASE_URL = "https://finnhub.io/api/v1"

CACHE_TTL_FUNDAMENTALS_HOURS = 24 * 7   # Fundamentals refresh weekly
CACHE_TTL_CALENDAR_HOURS = 12           # Calendars refresh twice a day
CACHE_TTL_INSIDER_HOURS = 24            # Insider Form 4 refresh daily

#: Statuses that mean Finnhub refused the KEY rather than answering about the
#: symbol: 429 is the per-minute throttle, 401 a rejected key. Both say nothing
#: about the symbol that was asked about, and both apply to every symbol asked
#: next.
THROTTLED_STATUSES = frozenset({401, 429})


class FinnhubThrottledError(VendorThrottledError):
    """Finnhub refused the key (429 throttle or 401), not the symbol.

    Raised only when a caller passes `raise_failures=True`, which only the
    worker's two factor passes do. Everywhere else a throttled call keeps
    returning the same None it always has, so the API's ticker pages degrade to
    "no data" exactly as before.

    Why the passes need the difference: they stamp every symbol they ATTEMPT,
    because "Finnhub has no fundamentals for this ETF" is a settled answer that
    must not be asked again tomorrow. A 429 is not an answer, but it came back
    as that same None, so it was stamped as settled too and the symbol sat out
    a whole refresh horizon with nothing learned.
    """

    def __init__(self, endpoint: str, status: int) -> None:
        super().__init__(f"finnhub {endpoint} throttled status={status}")
        self.endpoint = endpoint
        self.status = status


class FinnhubUnavailableError(VendorUnavailableError):
    """Finnhub did not answer: any non-200 other than a throttle, a transport
    error or timeout, or a 200 whose body is not the JSON object it sends.

    Raised under the same `raise_failures=True`, and deliberately a different
    type from FinnhubThrottledError, because the passes treat it differently.
    These can repeat for ONE symbol on every call, and a symbol that is never
    stamped stays at the head of every future selection, so a handful of them
    would stall the refresh for the whole universe. They are therefore still
    stamped. What the passes need to SEE is a run of them: that is an outage,
    and stamping through it at full pace would push every due row out a whole
    horizon having learned nothing.
    """

    def __init__(self, endpoint: str, detail: str) -> None:
        super().__init__(f"finnhub {endpoint} unavailable: {detail}")
        self.endpoint = endpoint


def _raise_if_failure(endpoint: str, status: int, raise_failures: bool) -> None:
    """Raise for a non-200 response: none of them is an answer about the symbol.

    401/429 refused the KEY and raise FinnhubThrottledError. Every other status
    raises FinnhubUnavailableError. Finnhub reports "nothing for this symbol" as
    a 200 with an empty body, which the callers already read as no coverage, so
    for this universe of US listings a 403, 404, 408 or 3xx is a plan, endpoint
    or edge refusal rather than a verdict on one symbol. Review found that
    treating those as answers would stamp the whole due universe without a word
    in the logs. A symbol that really is refused on its own is still stamped by
    the passes, so it cannot block the queue.
    """
    if not raise_failures:
        return
    if status in THROTTLED_STATUSES:
        raise FinnhubThrottledError(endpoint, status)
    raise FinnhubUnavailableError(endpoint, f"status={status}")


def _cache_path(name: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / f"finnhub_{name}.json"


def _load_cache(name: str, ttl_hours: float) -> Any | None:
    p = _cache_path(name)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        if (time.time() - data.get("_ts", 0)) > ttl_hours * 3600:
            return None
        return data.get("payload")
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(name: str, payload: Any) -> None:
    try:
        _cache_path(name).write_text(json.dumps({"payload": payload, "_ts": time.time()}))
    except (OSError, TypeError):
        logger.warning("finnhub.cache_write_failed name=%s", name)


def _api_key() -> str:
    return getattr(settings, "finnhub_api_key", "") or ""


def auth_headers() -> dict[str, str]:
    """Finnhub auth as a HEADER, never a query parameter.

    Finnhub accepts either `?token=` or the `X-Finnhub-Token` header. Only the
    header is safe here: httpx logs the full request URL at INFO, main.py and
    signal_publisher.py both call logging.basicConfig(level=INFO) with no httpx
    suppression, and HTTPStatusError embeds the URL — so a query-param key
    reaches the application log, every stack trace and Sentry on every call.

    This is the same mistake `polygon_feed.auth_headers()` exists to prevent,
    and `tests/test_vendor_key_never_in_urls.py` already says in as many words
    that the failure mode is not "polygon_feed regressed" but "a new outbound
    integration copies the identical mistake". Finnhub was that integration:
    eight call sites, never added to the guard's VENDOR_MODULES. It is now.
    """
    k = _api_key()
    return {"X-Finnhub-Token": k} if k else {}


def configured() -> bool:
    return bool(_api_key())


# ---- In-memory fundamentals score cache --------------------------------
# Populated by the worker's daily _refresh_fundamentals task. Keyed by
# uppercase symbol; value is the 0-100 sub_fundamentals score (or None
# if Finnhub returned no data — typical for ETFs without P/E).
# polygon_feed.fetch_snapshots reads from this cache per tick — the
# expensive Finnhub fetches happen once per day, the cheap dict lookup
# happens 60×/min during market hours.
_FUND_SCORE_CACHE: dict[str, float] = {}


def get_cached_score(symbol: str) -> float | None:
    """Per-tick lookup. Returns None if the symbol hasn't been refreshed yet
    or had no Finnhub fundamentals (e.g. ETFs, foreign ADRs)."""
    return _FUND_SCORE_CACHE.get(symbol.upper())


def set_cached_score(symbol: str, score: float | None) -> None:
    """Worker-side setter — call after each fetch_basic_financials + compute."""
    if score is not None:
        _FUND_SCORE_CACHE[symbol.upper()] = score


def fund_cache_size() -> int:
    """For diagnostics."""
    return len(_FUND_SCORE_CACHE)


# ---- In-memory market-cap cache (absolute dollars) ---------------------
# Same pattern as _FUND_SCORE_CACHE — populated when the worker fetches a
# company profile (daily sector backfill), read per-tick by
# polygon_feed.fetch_snapshots so the cheap dict lookup — not an HTTP call —
# runs 60×/min. Values are ABSOLUTE DOLLARS (Finnhub reports market cap in
# MILLIONS; the populator multiplies by 1e6 before storing here).
_MARKET_CAP_CACHE: dict[str, float] = {}


def get_cached_market_cap(symbol: str) -> float | None:
    """Per-tick lookup. Returns None if the symbol has no profile yet."""
    return _MARKET_CAP_CACHE.get(symbol.upper())


def set_cached_market_cap(symbol: str, market_cap: float | None) -> None:
    """Worker-side setter — call with ABSOLUTE DOLLARS (already ×1e6)."""
    if market_cap is not None:
        _MARKET_CAP_CACHE[symbol.upper()] = market_cap


def market_cap_cache_size() -> int:
    return len(_MARKET_CAP_CACHE)


# ---- In-memory smart-money score cache (insider Form 4) ----------------
# Same pattern as _FUND_SCORE_CACHE — populated daily by the worker,
# read per-tick by polygon_feed.fetch_snapshots.
_SMART_MONEY_SCORE_CACHE: dict[str, float] = {}

#: Symbols whose last insider answer was EMPTY, until a tick has written that.
#:
#: A cache miss means "not measured yet", so the tick's `_merged_factor_set`
#: keeps the row's previous value. An empty answer means "measured, no Form 4
#: filings in 90 days", and the previous value is exactly what must go. The
#: insider pass clears the row itself, but a tick that read the old value before
#: that commit writes it straight back. This set tells the tick to write NULL
#: instead. The tick removes the symbols it wrote; a new reading removes its own.
_SMART_MONEY_CLEARED: set[str] = set()


def get_cached_smart_money_score(symbol: str) -> float | None:
    return _SMART_MONEY_SCORE_CACHE.get(symbol.upper())


def set_cached_smart_money_score(symbol: str, score: float | None) -> None:
    if score is not None:
        sym = symbol.upper()
        _SMART_MONEY_SCORE_CACHE[sym] = score
        _SMART_MONEY_CLEARED.discard(sym)


def clear_cached_smart_money_score(symbol: str) -> None:
    """Forget this process's reading because the vendor answered with nothing.

    Not the same as never having a reading; see `_SMART_MONEY_CLEARED`."""
    sym = symbol.upper()
    _SMART_MONEY_SCORE_CACHE.pop(sym, None)
    _SMART_MONEY_CLEARED.add(sym)


def smart_money_cleared_symbols() -> frozenset[str]:
    """A copy: the tick reads it once, then releases exactly what it wrote."""
    return frozenset(_SMART_MONEY_CLEARED)


def release_smart_money_cleared(symbols: frozenset[str] | set[str]) -> None:
    _SMART_MONEY_CLEARED.difference_update(symbols)


def smart_money_cache_size() -> int:
    return len(_SMART_MONEY_SCORE_CACHE)


#: When the worker's insider pass scores a symbol it writes the Form 4 rows it
#: fetched to insider_transactions (one delete-then-insert, fetched_at = insert
#: time) and then stamps last_smart_money_at in a batch flushed every 20
#: symbols. So a symbol's stored rows ARE the fetch its stamp records exactly
#: when they came from one insert that landed shortly before the stamp.
#:
#: Same rule and same numbers as app/scripts/backfill_smart_money.py (#812), so
#: the boot-time rebuild below and that one-off repair cannot disagree about
#: what counts as a lost reading. tests/test_factor_refresh_what_is_due.py
#: asserts the two agree.
INSIDER_STAMP_LAG = timedelta(minutes=15)
INSIDER_CLOCK_SKEW = timedelta(minutes=2)


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)


def insider_rows_are_the_stamped_fetch(
    stamp: datetime, first_fetch: datetime, last_fetch: datetime,
) -> bool:
    """True when a symbol's stored Form 4 rows are the fetch its stamp recorded."""
    stamp, first_fetch, last_fetch = _aware(stamp), _aware(first_fetch), _aware(last_fetch)
    if first_fetch != last_fetch:
        return False
    lag = stamp - first_fetch
    return -INSIDER_CLOCK_SKEW <= lag <= INSIDER_STAMP_LAG


async def _rebuild_unsaved_smart_money_scores() -> int:
    """Put back smart-money readings the insider pass computed but nothing saved.

    THE LOSS. The insider pass used to put its score only into this process's
    `_SMART_MONEY_SCORE_CACHE`. The Ticker row received it later: from the tick
    for rows the sheet does not own, and from the sheet upsert - which runs only
    when the sheet changes - for rows it does. A restart in between lost the
    reading, and the pass's stamp then hid the symbol from the refresh. On
    2026-09-13 production held 3,231 such rows, NVDA, AAPL, MSFT, GOOGL, AMZN
    and META among them, each with its Form 4 rows on file. #812's script
    repaired them once. This repeats that repair at every boot, so the next
    restart cannot lose them again.

    The pass now writes each reading onto its row with its stamp
    (`signal_publisher._flush_insider_attempts`), because this repair cannot
    see a reading that replaced an OLDER stored value: it only looks at NULL
    rows. What is left for it here is a reading the pass stamped without
    writing - a row another writer kept changing - and rows from before that.

    Rebuilt only for rows whose sub_smart_money is NULL, never for an X: crypto
    pair, and only where the stored rows are the stamped fetch
    (`insider_rows_are_the_stamped_fetch`). Scored over ALL of those rows, the
    same input #812's repair uses. Stored rows are deduplicated on their natural
    key, so for a symbol with colliding Form 4 lines the value can differ a
    little from the one the pass computed from the raw list. No vendor call.

    It fills the CACHE, not the row. The existing writers then put the value on
    the row together with a composite recomputed from it, so a factor never
    lands beside a score that ignored it.

    Returns the number of readings rebuilt. Never raises.
    """
    from sqlalchemy import func, select

    from app.db import session_scope
    from app.models import InsiderTransaction, Ticker

    try:
        async with session_scope() as session:
            groups = (await session.execute(
                select(
                    Ticker.symbol,
                    Ticker.last_smart_money_at,
                    func.min(InsiderTransaction.fetched_at),
                    func.max(InsiderTransaction.fetched_at),
                )
                .join(InsiderTransaction, InsiderTransaction.symbol == Ticker.symbol)
                .where(
                    Ticker.sub_smart_money.is_(None),
                    Ticker.last_smart_money_at.is_not(None),
                    Ticker.symbol.not_like("X:%"),
                )
                .group_by(Ticker.symbol, Ticker.last_smart_money_at)
            )).all()
            eligible = [
                sym for sym, stamp, first, last in groups
                if insider_rows_are_the_stamped_fetch(stamp, first, last)
            ]
            if not eligible:
                return 0
            rows = (await session.execute(
                select(
                    InsiderTransaction.symbol,
                    InsiderTransaction.share_change,
                    InsiderTransaction.transaction_price,
                ).where(InsiderTransaction.symbol.in_(eligible))
            )).all()

        by_symbol: dict[str, list[dict[str, Any]]] = {sym: [] for sym in eligible}
        for sym, change, price in rows:
            by_symbol[sym].append({"share_change": change, "transaction_price": price})
        rebuilt = 0
        for sym, txns in by_symbol.items():
            score = compute_smart_money_score(txns)
            if score is not None and get_cached_smart_money_score(sym) is None:
                set_cached_smart_money_score(sym, score)
                rebuilt += 1
    except Exception:
        # Guards the WHOLE rebuild, scoring included: the warm is awaited
        # unguarded at worker boot and on the API's sheet-changed webhook.
        logger.exception("factor_cache.smart_money_rebuild_failed")
        return 0
    return rebuilt


async def warm_factor_caches_from_db() -> tuple[int, int]:
    """Refill `_FUND_SCORE_CACHE` and `_SMART_MONEY_SCORE_CACHE` from the values
    already stored on the Ticker rows.

    Both dicts are process-local and both are filled ONLY by the worker's daily
    Finnhub chain, so every process starts with no reading for either of the two
    factors they back — and `app.services.score` treats a cache miss as NEUTRAL
    50 by design. The Ticker table has persisted both sub-scores all along;
    nothing ever read them back. This is that read.

    "We measured this yesterday and then forgot" is not the same claim as "we
    have never measured this", and only the second is honestly NEUTRAL.

    WHO ACTUALLY NEEDS THIS — the two composite write paths differ, so be
    precise before deleting either caller:

    * The WORKER's tick is already half-protected. `_merged_factor_set` merges
      each incoming factor against the value on the row (incoming-or-previous)
      and recomputes the composite from the merged set, so a cold cache there
      preserves a stored sub-score rather than erasing it. What it does NOT do
      is help a row the tick has never seen before, and it does nothing at all
      for sheet-governed symbols, whose factors the tick deliberately leaves
      alone.
    * The SHEET path has no such protection, on purpose. `sheet_feed`'s
      `upsert_tickers` writes all six sub-scores unconditionally INCLUDING None
      — because writing only non-None values would leave a stale 70 printed
      beside a composite computed as if that factor were 50, and the displayed
      numbers would not add up (PRs #225/#226). Correct, and it means a cold
      cache blanks both factors for every sheet-governed row and recomputes
      those composites with NEUTRAL twice over. The cache is therefore the only
      place this can be fixed.

    That second path runs in the API process (`routers/internal.py`'s
    sheet-changed webhook), where the daily Finnhub chain never runs at all, so
    there the caches are not merely cold after a deploy — they are empty for the
    life of the process.

    Smart money gets one more source: a reading the insider pass computed but
    no writer ever put on the row is rebuilt from its stored Form 4 rows. See
    `_rebuild_unsaved_smart_money_scores`.

    And one removal. The API process warms on every sheet-changed webhook, so
    its cache holds whatever the rows said the LAST time. When the insider pass
    has since cleared a reading - an empty answer: row NULL, Form 4 rows
    deleted - the stale entry would be written back onto the sheet-owned row by
    the refresh that follows. So an entry whose row is NULL and which has no
    Form 4 rows on file is dropped. Nothing is lost by that: there is no reading
    on the row and nothing to rebuild one from. The worker warms only at boot,
    when its cache is empty and this removes nothing.

    Returns (fundamentals_loaded, smart_money_loaded), the second including
    rebuilt readings. Never raises: a warm that fails leaves the caches exactly
    as cold as they were, which is the pre-existing behaviour.
    """
    from sqlalchemy import select

    from app.db import session_scope
    from app.models import InsiderTransaction, Ticker

    funds = 0
    smart = 0
    dropped = 0
    try:
        async with session_scope() as session:
            rows = (await session.execute(
                select(
                    Ticker.symbol, Ticker.sub_fundamentals, Ticker.sub_smart_money,
                ).where(
                    Ticker.sub_fundamentals.is_not(None)
                    | Ticker.sub_smart_money.is_not(None)
                )
            )).all()
            on_row = {sym for sym, _, sm in rows if sm is not None}
            unbacked = [s for s in _SMART_MONEY_SCORE_CACHE if s not in on_row]
            with_form4: set[str] = set()
            if unbacked:
                with_form4 = set((await session.execute(
                    select(InsiderTransaction.symbol)
                    .where(InsiderTransaction.symbol.in_(unbacked))
                    .distinct()
                )).scalars().all())
        for sym, fund, sm in rows:
            if fund is not None:
                set_cached_score(sym, float(fund))
                funds += 1
            if sm is not None:
                set_cached_smart_money_score(sym, float(sm))
                smart += 1
        for sym in unbacked:
            if sym not in with_form4:
                _SMART_MONEY_SCORE_CACHE.pop(sym, None)
                dropped += 1
    except Exception:
        logger.exception("factor_cache.warm_failed")
        return funds, smart

    rebuilt = await _rebuild_unsaved_smart_money_scores()
    logger.info(
        "factor_cache.warmed fundamentals=%d smart_money=%d smart_money_rebuilt=%d "
        "smart_money_dropped=%d",
        funds, smart, rebuilt, dropped,
    )
    return funds, smart + rebuilt


# ---- Recent insider transactions — DB-backed, cross-process ---------------
# Powers /app/holdings ("Recent Insider Buys") and the per-ticker InsiderTab.
# Before 2026-05-16 this was an in-process `_INSIDER_FEED` list — the worker
# wrote to its own list, the API read from its own list, and on Fly (where
# api + worker run on separate machines) the API ALWAYS saw an empty list.
# Now writes go to the `insider_transactions` table; reads query it directly.
#
# The setter/getter API is preserved bit-for-bit so callers (worker, router,
# tests) don't need to change. Synchronous wrappers around the async DB calls
# would have required threadlocal sessions; instead both functions are now
# async, with a single sync wrapper kept for legacy compute paths that don't
# have an event loop handy.


async def set_recent_insider_transactions_db(
    symbol: str, txns: list[dict[str, Any]], *, source: str = "edgar",
) -> None:
    """Bulk-replace this symbol's insider transactions in the DB.

    Pattern:
      DELETE FROM insider_transactions WHERE symbol = :sym
      INSERT INTO insider_transactions (...) VALUES (...) -- N rows

    Idempotent — running the daily refresh twice in a row produces the same
    end state because we delete-then-insert. The UniqueConstraint is a
    belt-and-braces guard in case a future bug duplicates inserts.
    """
    from sqlalchemy import delete
    from sqlalchemy.exc import IntegrityError

    from app.db import session_scope
    from app.models import InsiderTransaction

    sym = symbol.upper()

    # Dedupe on the NATURAL KEY before touching the DB.
    #
    # InsiderTransaction carries
    #   UniqueConstraint(symbol, transaction_date, insider_name, share_change)
    # which deliberately excludes transaction_price and code — but
    # fetch_insider_transactions maps Finnhub's payload ONE ROW PER LINE ITEM
    # with no dedupe, and share_change falls back to 0 when `change` is absent.
    # Two Form 4 lines therefore collide routinely.
    #
    # When they did, the single commit raised IntegrityError and the handler
    # below rolled back — which also rolled back the DELETE. The symbol kept its
    # OLD rows, and because the trigger is deterministic VENDOR DATA rather than
    # a race, the next run failed identically. fetch_insider_transactions
    # re-requests the same rolling 90-day window daily, so the offending pair
    # kept reappearing until it aged out: a Premium feature's data frozen for up
    # to three months.
    #
    # It was invisible too — only a warning fired, the worker still counted
    # `refreshed += 1`, and compute_smart_money_score cached the FRESH score, so
    # the displayed transactions and the sub_smart_money factor disagreed.
    #
    # By the schema's own definition two rows sharing the 4-tuple ARE the same
    # transaction, so collapsing them is consistent with it. First occurrence
    # wins (vendor order, deterministic) and the collapse is logged so the
    # narrowness of the key stays visible rather than silently losing lines.
    rows: list[InsiderTransaction] = []
    seen: set[tuple[str, str, int]] = set()
    collapsed = 0
    for t in txns or []:
        share_change = int(t.get("share_change") or 0)
        price = float(t.get("transaction_price") or 0)
        insider_name = (t.get("filer_name") or "")[:120]
        transaction_date = (t.get("transaction_date") or "")[:10]
        key = (transaction_date, insider_name, share_change)
        if key in seen:
            collapsed += 1
            continue
        seen.add(key)
        rows.append(
            InsiderTransaction(
                symbol=sym,
                insider_name=insider_name,
                transaction_date=transaction_date,
                share_change=share_change,
                transaction_price=round(price, 4),
                transaction_value=round(abs(share_change * price), 2),
                code=(t.get("code") or "")[:4],
                source=source,
            )
        )
    if collapsed:
        logger.info(
            "insider.collapsed_duplicate_natural_key symbol=%s dropped=%d kept=%d "
            "(uq_insider_natural excludes price+code)",
            sym, collapsed, len(rows),
        )

    async with session_scope() as session:
        await session.execute(delete(InsiderTransaction).where(InsiderTransaction.symbol == sym))
        for row in rows:
            session.add(row)
        try:
            await session.commit()
        except IntegrityError:
            # With the payload deduped above, this can only be a genuine race
            # against another concurrent refresh of the SAME symbol. Roll back
            # and let the next refresh re-run cleanly — that really is transient.
            # Logged at ERROR, not warning: it should now be rare, and if it
            # starts recurring for one symbol the dedupe above has a hole.
            await session.rollback()
            logger.error("insider.write_race symbol=%s rows=%d", sym, len(rows))


# Legacy alias for the worker, which still calls the sync-named helper.
def set_recent_insider_transactions(symbol: str, txns: list[dict[str, Any]]) -> None:
    """Sync facade — schedules the async DB write without blocking the worker.

    The worker loop is inside asyncio.run, so we can grab the running loop
    and create_task. If somehow there's no loop (sync test), we fall back to
    asyncio.run on a one-shot loop.
    """
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(set_recent_insider_transactions_db(symbol, txns))
    except RuntimeError:
        # No running loop — sync caller, e.g. a test. Run inline.
        asyncio.run(set_recent_insider_transactions_db(symbol, txns))


async def get_recent_insider_transactions_db(
    days: int = 30,
    limit: int = 100,
    symbol: str | None = None,
    buys_only: bool = False,
) -> list[dict[str, Any]]:
    """Query the DB-backed feed.

    days        — only entries whose transaction_date is within this many days
    limit       — max rows to return (post-filter)
    symbol      — optional ticker filter (case-insensitive)
    buys_only   — if True, return only net positive share_change rows

    Same shape and ordering as the prior in-memory implementation so the
    router/UI don't see any contract change.
    """
    from sqlalchemy import desc, select

    from app.db import session_scope
    from app.models import InsiderTransaction

    cutoff = (date.today() - timedelta(days=max(1, days))).isoformat()
    sym = symbol.upper() if symbol else None

    stmt = (
        select(InsiderTransaction)
        .where(InsiderTransaction.transaction_date >= cutoff)
        .order_by(desc(InsiderTransaction.transaction_date))
        .limit(limit)
    )
    if sym:
        stmt = stmt.where(InsiderTransaction.symbol == sym)
    if buys_only:
        stmt = stmt.where(InsiderTransaction.share_change > 0)

    async with session_scope() as session:
        result = await session.execute(stmt)
        rows = result.scalars().all()

    return [
        {
            "symbol":            r.symbol,
            "insider_name":      r.insider_name,
            "transaction_date":  r.transaction_date,
            "share_change":      r.share_change,
            "transaction_price": r.transaction_price,
            "transaction_value": r.transaction_value,
            "code":              r.code,
        }
        for r in rows
    ]


def get_recent_insider_transactions(
    days: int = 30,
    limit: int = 100,
    symbol: str | None = None,
    buys_only: bool = False,
) -> list[dict[str, Any]]:
    """Sync facade for legacy callers (none expected — router is async).

    Kept so existing tests that imported the old sync API continue to work.
    Returns [] if called from inside an async context (use the _db variant
    directly there).
    """
    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            get_recent_insider_transactions_db(days, limit, symbol, buys_only)
        )
    # Inside an event loop — can't run another. Caller should use the async
    # variant. Return empty as a defensive default.
    logger.warning("insider.sync_facade_called_in_async_context")
    return []


async def insider_feed_size_db() -> int:
    """Total rows in the DB-backed feed. Cheap COUNT(*) — runs against an
    index'd column so it's sub-millisecond even with the full universe."""
    from sqlalchemy import func as sa_func
    from sqlalchemy import select as sa_select

    from app.db import session_scope
    from app.models import InsiderTransaction

    async with session_scope() as session:
        result = await session.execute(sa_select(sa_func.count(InsiderTransaction.id)))
        return int(result.scalar_one() or 0)


def insider_feed_size() -> int:
    """Sync facade — kept for callers that show the count without an async
    context. Returns 0 if inside an event loop (use *_db variant)."""
    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(insider_feed_size_db())
    return 0


def compute_smart_money_score(transactions: list[dict[str, Any]] | None) -> float | None:
    """
    0-100 score from insider Form 4 transactions.

    Net buying (insiders adding to their position) → score above 50.
    Net selling (insiders dumping) → score below 50.
    Magnitude scales with the dollar value of the net position change relative
    to total transaction volume — so a $50M buy by one insider weighs more than
    50 separate $1M sells, but only if it's net of the activity.

    Returns None for tickers with no transactions in the window — caller falls
    back to mock or keeps existing value.
    """
    if not transactions:
        return None

    net_value = 0.0
    total_value = 0.0
    for t in transactions:
        change = t.get("share_change") or 0
        price = t.get("transaction_price") or 0
        signed = change * price
        net_value += signed
        total_value += abs(signed)

    if total_value == 0:
        return 50.0

    # Net buy ratio: -1 (all selling) to +1 (all buying)
    ratio = net_value / total_value
    # Map to 10–90 score band — leave headroom at the extremes for stronger signals
    score = 50 + (ratio * 40)
    return round(max(0, min(100, score)), 1)


# ---- Earnings calendar -----------------------------------------------------

# One /calendar/earnings request is capped by the vendor at ~1,500 rows, and an
# over-long range returns the tail of the window rather than the head. 30 days
# of US earnings sits well under that even in peak reporting season.
_EARNINGS_CHUNK_DAYS = 30
_EARNINGS_ROWS_CAP = 1500


async def fetch_earnings_calendar(days_ahead: int = 14) -> list[dict[str, Any]] | None:
    """
    Returns earnings events scheduled in the next `days_ahead` days.
    Shape matches mock_upcoming_earnings() so it's a drop-in replacement.

    Returns None if no API key OR fetch failed (caller falls back to mock).
    """
    if not configured():
        logger.info("finnhub.earnings_skipped reason=no_api_key")
        return None

    cache_key = f"earnings_{days_ahead}d"
    cached = _load_cache(cache_key, CACHE_TTL_CALENDAR_HOURS)
    if cached is not None:
        logger.info("finnhub.earnings_cache_hit count=%d", len(cached))
        return cached

    today = date.today()

    # Fetch in CHUNKS, and merge. Finnhub caps a single /calendar/earnings
    # response at roughly 1,500 rows, and when the requested range overflows
    # that cap the rows we get back are the FAR END of it. Asking for 90 days in
    # one call produced exactly 1500 rows dated 2026-11-05..11-20 with NOTHING
    # in the intervening ten weeks — so "next earnings" was silently wrong for
    # every company reporting sooner, which is the only case the field exists to
    # answer. Chunking keeps each request comfortably under the cap, so the
    # near-term dates (the ones that matter) are always present.
    #
    # Cost is 1 request per chunk instead of 1 total, on a 12h cache — a
    # rounding error against the per-tick symbol calls this module already makes.
    chunks: list[tuple[date, date]] = []
    cursor = today
    end = today + timedelta(days=days_ahead)
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=_EARNINGS_CHUNK_DAYS - 1), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)

    raw_rows: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            for chunk_from, chunk_to in chunks:
                # `resp`, not `r`: the row loop further down binds `r` to each
                # calendar entry, and reusing the name makes the response type
                # leak into it.
                resp = await c.get(
                    f"{BASE_URL}/calendar/earnings",
                    params={
                        "from": chunk_from.isoformat(),
                        "to": chunk_to.isoformat(),
                    },
                    headers=auth_headers(),
                )
                if resp.status_code != 200:
                    logger.warning(
                        "finnhub.earnings_failed status=%s from=%s to=%s body=%s",
                        resp.status_code, chunk_from, chunk_to, resp.text[:200],
                    )
                    # A partial calendar beats no calendar: keep what we have.
                    continue
                part = (resp.json() or {}).get("earningsCalendar", []) or []
                if len(part) >= _EARNINGS_ROWS_CAP:
                    # Still truncating. Say so loudly rather than shipping a
                    # window that silently starts late again.
                    logger.warning(
                        "finnhub.earnings_chunk_at_cap rows=%d from=%s to=%s "
                        "— shrink _EARNINGS_CHUNK_DAYS",
                        len(part), chunk_from, chunk_to,
                    )
                raw_rows.extend(part)
    except Exception:
        logger.exception("finnhub.earnings_exception")
        return None

    if not raw_rows:
        return None

    rows: list[dict[str, Any]] = []
    for r in raw_rows:
        sym = r.get("symbol", "")
        report_date_str = r.get("date")
        if not sym or not report_date_str:
            continue
        try:
            report_d = date.fromisoformat(report_date_str)
        except ValueError:
            continue
        # Finnhub `hour` field: bmo / amc / dmh (before/after/during market hours)
        report_time = (r.get("hour") or "").upper() or "BMO"
        if report_time not in ("BMO", "AMC", "DMH"):
            report_time = "BMO"
        quarter = r.get("quarter")
        year = r.get("year")
        fiscal_quarter = f"Q{quarter} {year}" if quarter and year else f"Q{((report_d.month - 1) // 3) + 1} {report_d.year}"

        eps_est = r.get("epsEstimate")
        eps_act = r.get("epsActual")
        rev_est = r.get("revenueEstimate")
        rev_act = r.get("revenueActual")
        # Surprise pct vs estimate, only if both actual and estimate are populated
        surprise_pct = None
        if eps_act is not None and eps_est is not None and eps_est != 0:
            surprise_pct = round(((eps_act - eps_est) / abs(eps_est)) * 100, 2)

        rows.append({
            "symbol": sym.upper(),
            "report_date": report_d,
            "report_time": report_time,
            "fiscal_quarter": fiscal_quarter,
            "eps_estimate": float(eps_est) if eps_est is not None else None,
            "eps_actual": float(eps_act) if eps_act is not None else None,
            "revenue_estimate_m": round(float(rev_est) / 1_000_000, 0) if rev_est else None,
            "revenue_actual_m": round(float(rev_act) / 1_000_000, 0) if rev_act else None,
            "surprise_pct": surprise_pct,
        })

    rows.sort(key=lambda r: r["report_date"])
    # Date isn't JSON-serialisable directly — store as ISO string in cache
    _save_cache(cache_key, [{**r, "report_date": r["report_date"].isoformat()} for r in rows])
    logger.info("finnhub.earnings_fetched count=%d days=%d", len(rows), days_ahead)
    return rows


# ---- IPO calendar ----------------------------------------------------------

async def fetch_ipo_calendar(days_ahead: int = 90) -> list[dict[str, Any]] | None:
    """
    Returns upcoming IPOs scheduled in the next `days_ahead` days.
    Shape matches mock_upcoming_ipos().
    """
    if not configured():
        logger.info("finnhub.ipo_skipped reason=no_api_key")
        return None

    cache_key = f"ipo_{days_ahead}d"
    cached = _load_cache(cache_key, CACHE_TTL_CALENDAR_HOURS)
    if cached is not None:
        logger.info("finnhub.ipo_cache_hit count=%d", len(cached))
        return cached

    today = date.today()
    end = today + timedelta(days=days_ahead)
    params = {"from": today.isoformat(), "to": end.isoformat()}
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{BASE_URL}/calendar/ipo", params=params, headers=auth_headers())
            if r.status_code != 200:
                logger.warning("finnhub.ipo_failed status=%s body=%s", r.status_code, r.text[:200])
                return None
            data = r.json()
    except Exception:
        logger.exception("finnhub.ipo_exception")
        return None

    raw_rows = data.get("ipoCalendar", []) or []
    rows: list[dict[str, Any]] = []
    for r in raw_rows:
        sym = (r.get("symbol") or "").upper()
        if not sym:
            continue
        ipo_date_str = r.get("date")
        try:
            ipo_d = date.fromisoformat(ipo_date_str) if ipo_date_str else None
        except ValueError:
            ipo_d = None
        if ipo_d is None:
            continue
        # Finnhub price field is a string like "30-35" or single price
        price_low, price_high = None, None
        price_str = r.get("price") or ""
        if "-" in price_str:
            try:
                lo, hi = price_str.split("-", 1)
                price_low, price_high = float(lo), float(hi)
            except ValueError:
                pass
        elif price_str:
            with contextlib.suppress(ValueError):
                price_low = price_high = float(price_str)

        status_raw = (r.get("status") or "").lower()
        status = {
            "expected": "upcoming",
            "filed": "upcoming",
            "priced": "priced",
            "withdrawn": "withdrawn",
            "postponed": "postponed",
        }.get(status_raw, "upcoming")

        rows.append({
            "symbol": sym,
            "company_name": r.get("name") or sym,
            "sector": "Unknown",  # Finnhub IPO endpoint doesn't provide sector
            "exchange": r.get("exchange") or "NASDAQ",
            "expected_date": ipo_d,
            "price_low": price_low,
            "price_high": price_high,
            "shares_offered": int(r.get("numberOfShares") or 0),
            "status": status,
            "lead_underwriter": "—",  # Finnhub free tier doesn't include underwriter
            "description": f"{r.get('name') or sym} listing on {r.get('exchange') or 'a US exchange'}.",
        })

    rows.sort(key=lambda r: r["expected_date"])
    _save_cache(cache_key, [{**r, "expected_date": r["expected_date"].isoformat()} for r in rows])
    logger.info("finnhub.ipo_fetched count=%d days=%d", len(rows), days_ahead)
    return rows


# ---- Fundamentals ----------------------------------------------------------

async def _fetch_metric_all(
    symbol: str, *, raise_failures: bool = False,
) -> dict[str, Any] | None:
    """
    One cached GET of /stock/metric?metric=all — the single upstream call
    behind BOTH fetch_basic_financials and fetch_key_statistics.

    What's cached is the RAW `metric` object, not a projection of it. Until
    2026-08-22 the six-key fundamentals dict was the cached thing, so ~110
    other data points in a payload we had already fetched and paid for were
    discarded at parse time, and a second consumer would have needed a second
    API call. Caching the blob makes the key-statistics columns cost ZERO
    extra calls against the 60/min free tier.

    Returns None for "no coverage". `{}` is the on-disk sentinel for that
    (same as fetch_company_profile) — it has to be a NON-None value because
    _load_cache can't tell a cached None from a genuine miss, and caching
    None made the 7-day negative cache dead code so every ETF/ADR re-polled
    on every call.

    The cache key moved from `fund_` to `metric_` with the shape change, so
    any `finnhub_fund_*.json` left on disk is simply orphaned and ignored
    (nothing reads it, and it ages out) rather than being misread as a blob.
    """
    if not configured():
        return None

    sym = symbol.upper()
    cache_key = f"metric_{sym}"
    cached = _load_cache(cache_key, CACHE_TTL_FUNDAMENTALS_HOURS)
    if cached is not None:
        return cached or None  # {} = cached negative

    params = {"symbol": sym, "metric": "all"}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{BASE_URL}/stock/metric", params=params, headers=auth_headers())
            if r.status_code != 200:
                # Neither a throttle nor an outage is "no coverage" - see the two
                # error types. Never negative-cached either way: that happens
                # only on a 200.
                _raise_if_failure("stock/metric", r.status_code, raise_failures)
                return None
            data = r.json()
            if not isinstance(data, dict):
                raise ValueError(f"expected a JSON object, got {type(data).__name__}")
    except (FinnhubThrottledError, FinnhubUnavailableError):
        raise
    except Exception as exc:
        if raise_failures:
            raise FinnhubUnavailableError("stock/metric", type(exc).__name__) from exc
        return None

    metric = data.get("metric") or {}
    # ETFs / funds sometimes return empty here — cache the negative so we
    # don't re-poll for 7 days, then let the caller fall back.
    _save_cache(cache_key, metric)
    return metric or None


async def fetch_basic_financials(
    symbol: str, *, raise_failures: bool = False,
) -> dict[str, float] | None:
    """
    Per-ticker financial metrics: P/E, margin, ROE, EPS growth, revenue growth.
    Cached 7 days per symbol — fundamentals don't change tick-to-tick.

    Returns None if no API key OR ticker has no data (e.g. ETFs without fundamentals).
    With `raise_failures=True` a throttled key or a failed call raises
    (FinnhubThrottledError / FinnhubUnavailableError) instead of returning that
    same None.
    """
    metric = await _fetch_metric_all(symbol, raise_failures=raise_failures)
    if not metric:
        return None

    out = {
        "pe":             _f(metric.get("peNormalizedAnnual") or metric.get("peTTM")),
        "margin":         _f(metric.get("netProfitMarginAnnual") or metric.get("netProfitMarginTTM")),
        "roe":            _f(metric.get("roeRfy") or metric.get("roeTTM")),
        "eps_growth":     _f(metric.get("epsGrowth5Y") or metric.get("epsGrowthTTMYoy")),
        "revenue_growth": _f(metric.get("revenueGrowth5Y") or metric.get("revenueGrowthTTMYoy")),
        "debt_to_equity": _f(metric.get("totalDebt/totalEquityAnnual")),
    }
    # ETFs and funds: Finnhub returns a non-empty `metric` object (price/return
    # stats) but NONE of the stock-fundamentals fields we look for. Without
    # this check the router reports available=true, which makes the frontend
    # render 6 cards full of "—" dashes — exactly what the user reported on
    # /app/ticker/BBP. Treat all-null as no coverage.
    #
    # This guard stays scoped to the SIX SCORING KEYS above, deliberately. The
    # blob those ETFs return usually DOES carry a real beta and 52-week range,
    # which fetch_key_statistics now reads — but a beta is not fundamentals
    # coverage, and widening this `out` dict to include it would flip
    # available=true and bring the six-dashes bug straight back.
    if all(v is None for v in out.values()):
        return None
    return out


async def fetch_key_statistics(symbol: str) -> dict[str, Any] | None:
    """
    The Finnhub-sourced half of the per-ticker key-statistics block: beta,
    EPS (TTM), P/E (TTM), dividend yield, ex-dividend date. Keys match the
    Ticker column names so the caller can splat them into an UPDATE.

    Costs ZERO extra API calls — reads the same 7-day-cached
    /stock/metric?metric=all blob fetch_basic_financials reads.

    Returns None only when every field is absent, so a caller can skip the
    row entirely rather than writing five NULLs over five NULLs. Unlike
    fetch_basic_financials this does NOT require stock-fundamentals coverage:
    an ETF with nothing but a beta still has a real beta worth showing.

    Units, because they are not self-evident and a mislabelled number is
    worse than a blank:
      beta            — raw ratio vs the market (1.0 = moves with it)
      eps_ttm         — currency per share
      pe_ttm          — raw ratio
      dividend_yield  — PERCENT, as Finnhub reports it (2.5 means 2.5%), the
                        same convention as `margin`/`roe` above
    """
    metric = await _fetch_metric_all(symbol)
    if not metric:
        return None

    out: dict[str, Any] = {
        "beta": _f(metric.get("beta")),
        # TTM-only fallback chains. Finnhub ships several spellings of the
        # same figure depending on coverage, but every candidate here is a
        # trailing-twelve-month series: falling back to an *Annual* field
        # under a column named `_ttm` would mislabel the period, which is its
        # own kind of invented number.
        "eps_ttm": _f(_first(
            metric,
            "epsTTM", "epsBasicExclExtraItemsTTM",
            "epsExclExtraItemsTTM", "epsInclExtraItemsTTM",
        )),
        "pe_ttm": _f(_first(
            metric,
            "peTTM", "peBasicExclExtraTTM",
            "peExclExtraTTM", "peInclExtraTTM",
        )),
        # Indicated-annual first (the forward figure Yahoo shows), TTM second.
        "dividend_yield": _f(_first(
            metric, "dividendYieldIndicatedAnnual", "currentDividendYieldTTM",
        )),
        # Verified 2026-08-22: the metric blob carries NO ex-dividend date on
        # our plan — it lives on /stock/dividend, which is Premium-gated and
        # not entitled. The chain is here so the column fills by itself if
        # that ever changes; until then it stays null and renders an em-dash.
        # It is NOT worth a second endpoint, and it is certainly not worth
        # deriving from a dividend-frequency guess.
        "ex_dividend_date": _d(_first(
            metric, "exDividendDate", "lastDividendDate",
        )),
    }
    if all(v is None for v in out.values()):
        return None
    return out


def _f(v: Any) -> float | None:
    """Coerce to float or None — Finnhub sometimes returns null/empty/strings."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _d(v: Any) -> date | None:
    """Coerce a Finnhub "YYYY-MM-DD" string to a date, or None. Sibling of _f."""
    if v is None or v == "":
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _first(metric: dict[str, Any], *keys: str) -> Any:
    """First of `keys` that is PRESENT with a non-null value.

    Deliberately not the `a or b` chain the six scoring keys use above: `or`
    treats a legitimate 0.0 as missing, and 0.0 is the right answer for a
    break-even EPS or a company that pays no dividend. Falling through it
    would publish the NEXT field's number under this field's name — a
    fabricated statistic rather than an honest blank.
    """
    for k in keys:
        v = metric.get(k)
        if v is not None and v != "":
            return v
    return None


def compute_fundamentals_score(metrics: dict[str, float | None] | None) -> float | None:
    """
    Convert raw Finnhub fundamentals into a 0-100 sub-score.
    Returns None for tickers with no fundamentals (ETFs, funds) — caller
    should fall back to a neutral 50 or skip the factor entirely.

    Algorithm: weighted blend of (margin, ROE, EPS growth, revenue growth)
    bucketed against rough industry-typical ranges. Not academically rigorous
    but signals direction: high-margin / growing / profitable tickers score
    higher, money-losing / shrinking tickers score lower.
    """
    if not metrics:
        return None

    components: list[float] = []

    margin = metrics.get("margin")
    if margin is not None:
        # 0% margin = 30; 20% margin = 80; >40% margin = 100
        components.append(max(0, min(100, 30 + margin * 2.5)))

    roe = metrics.get("roe")
    if roe is not None:
        # 0% ROE = 30; 15% = 75; >30% = 100
        components.append(max(0, min(100, 30 + roe * 2.3)))

    eps_g = metrics.get("eps_growth")
    if eps_g is not None:
        # -10% = 20; 0% = 50; 15% = 80; >30% = 100
        components.append(max(0, min(100, 50 + eps_g * 2)))

    rev_g = metrics.get("revenue_growth")
    if rev_g is not None:
        # Same scale as EPS growth
        components.append(max(0, min(100, 50 + rev_g * 2)))

    pe = metrics.get("pe")
    if pe is not None and pe > 0:
        # Inverse: P/E 15 = 70 (cheap-ish), 25 = 55, 40 = 35 (expensive)
        components.append(max(0, min(100, 100 - pe * 1.5)))

    if not components:
        return None
    return round(sum(components) / len(components), 1)


async def fetch_company_profile(symbol: str) -> dict[str, Any] | None:
    """
    Sector + industry + name + market cap for a ticker. Used to backfill
    Ticker.sector="Unknown" rows after universe auto-discovery.

    Cached 7 days per symbol — sectors don't change.
    """
    if not configured():
        return None

    sym = symbol.upper()
    cache_key = f"profile_{sym}"
    cached = _load_cache(cache_key, CACHE_TTL_FUNDAMENTALS_HOURS)
    if cached is not None:
        # Seed the per-tick cap cache on the CACHED path too. It used to be
        # populated only on a live fetch (below), so once a symbol's profile
        # was on disk this early return skipped it — and since _MARKET_CAP_CACHE
        # is in-process, every worker restart started from empty and warm-cache
        # symbols never re-seeded it. Half of why market_cap was NULL for the
        # whole universe; the other half was the caller (see
        # signal_publisher._backfill_market_cap).
        _seed_market_cap_from_profile(sym, cached)
        return cached if cached else None  # may be {} for unknown tickers

    params = {"symbol": sym}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{BASE_URL}/stock/profile2", params=params, headers=auth_headers())
            if r.status_code != 200:
                return None
            data = r.json()
    except Exception:
        return None

    if not data:
        _save_cache(cache_key, {})  # cache the empty so we don't re-poll
        return None

    profile = {
        "sector":      data.get("finnhubIndustry") or "Unknown",
        "industry":    data.get("finnhubIndustry") or "",
        "name":        data.get("name") or sym,
        "market_cap":  _f(data.get("marketCapitalization")),
        "country":     data.get("country") or "",
        "exchange":    data.get("exchange") or "",
        "ipo":         data.get("ipo") or "",
    }
    _save_cache(cache_key, profile)
    _seed_market_cap_from_profile(sym, profile)
    return profile


def _seed_market_cap_from_profile(symbol: str, profile: dict[str, Any] | None) -> None:
    """Populate the per-tick market-cap cache from a profile dict.

    `profile["market_cap"]` is Finnhub's `marketCapitalization`, which is
    reported in MILLIONS. The cache — and Ticker.market_cap, and the scanner's
    "Mkt Cap" column — hold ABSOLUTE DOLLARS. The ×1e6 conversion lives here
    and nowhere else, so the live path and the cache-hit path can't drift by
    six orders of magnitude.
    """
    mc_millions = _f((profile or {}).get("market_cap"))
    if mc_millions is not None:
        set_cached_market_cap(symbol.upper(), mc_millions * 1e6)


async def fetch_insider_transactions(
    symbol: str, days_back: int = 90, *, raise_failures: bool = False,
) -> list[dict[str, Any]] | None:
    """
    Recent insider Form 4 filings for a ticker. Used to enrich sub_smart_money.
    Returns list of {filer_name, transaction_date, share_change, transaction_value}.
    With `raise_failures=True` a throttled key or a failed call raises
    (FinnhubThrottledError / FinnhubUnavailableError) instead of returning None.
    """
    if not configured():
        return None

    sym = symbol.upper()
    cache_key = f"insider_{sym}_{days_back}d"
    cached = _load_cache(cache_key, CACHE_TTL_INSIDER_HOURS)
    if cached is not None:
        return cached

    today = date.today()
    start = today - timedelta(days=days_back)
    params = {
        "symbol": sym,
        "from": start.isoformat(),
        "to": today.isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{BASE_URL}/stock/insider-transactions", params=params, headers=auth_headers())
            if r.status_code != 200:
                _raise_if_failure("stock/insider-transactions", r.status_code, raise_failures)
                return None
            data = r.json()
            if not isinstance(data, dict):
                raise ValueError(f"expected a JSON object, got {type(data).__name__}")
    except (FinnhubThrottledError, FinnhubUnavailableError):
        raise
    except Exception as exc:
        if raise_failures:
            raise FinnhubUnavailableError(
                "stock/insider-transactions", type(exc).__name__,
            ) from exc
        return None

    raw = data.get("data") or []
    rows: list[dict[str, Any]] = []
    for it in raw:
        rows.append({
            "filer_name": it.get("name", ""),
            "transaction_date": it.get("transactionDate", ""),
            "share_change": int(it.get("change") or 0),
            "transaction_price": float(it.get("transactionPrice") or 0),
            # SEC Form 4 transaction code (P/S/A/M/G/F/etc) — exposed so the
            # /app/holdings UI can filter open-market buys ("P") from grants ("A").
            "code": it.get("transactionCode", "") or "",
        })
    _save_cache(cache_key, rows)
    return rows


# ---------------------------------------------------------------------------
# News + analyst coverage
# ---------------------------------------------------------------------------
# Finnhub has broad coverage including international / UK-listed names (BUR,
# RIO ADR, etc.) because they aggregate from a wide wire net. Used as the
# secondary news source in news_feed (alongside Massive) and as the source
# for the per-ticker analyst-ratings widget.

CACHE_TTL_NEWS_HOURS = 0.25  # 15 min — news is the most time-sensitive
CACHE_TTL_RECS_HOURS = 12    # Analyst recs aggregate is monthly; 12h is plenty


async def fetch_news_for_ticker(
    symbol: str, days_back: int = 14, limit: int = 10,
) -> list[dict[str, Any]]:
    """Per-ticker news from Finnhub /company-news.

    One of the parallel sources in news_feed (alongside Massive), with
    broad coverage of UK-listed names, smaller US ADRs, etc. Returns the
    canonical news-row shape so consumers don't care which source served it.
    """
    from datetime import datetime

    if not configured():
        return []

    sym = symbol.upper()
    cache_key = f"news_{sym}_{days_back}d_{limit}"
    cached = _load_cache(cache_key, CACHE_TTL_NEWS_HOURS)
    if cached is not None:
        # The on-disk cache stores published_at as an ISO string (a datetime
        # isn't JSON-serializable). Re-hydrate to a tz-aware datetime so this
        # function returns the SAME type on a cache hit as on a cache miss —
        # and the same type as edgar/massive. news_feed.merge sorts
        # the combined list by published_at and raises TypeError if some rows
        # are str and others datetime.
        for r in cached:
            pa = r.get("published_at")
            if isinstance(pa, str):
                try:
                    r["published_at"] = datetime.fromisoformat(pa)
                except ValueError:
                    r["published_at"] = datetime.now(UTC)
        return cached

    today = date.today()
    start = today - timedelta(days=days_back)
    params = {
        "symbol": sym,
        "from": start.isoformat(),
        "to": today.isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{BASE_URL}/company-news", params=params, headers=auth_headers())
            if r.status_code != 200:
                return []
            data = r.json() if isinstance(r.json(), list) else []
    except Exception:
        logger.exception("finnhub.news_fetch_failed symbol=%s", sym)
        return []

    rows: list[dict[str, Any]] = []
    for a in data[:limit]:
        # Finnhub's `datetime` is a unix timestamp (seconds).
        try:
            ts = int(a.get("datetime") or 0)
            published = datetime.fromtimestamp(ts, tz=UTC)
        except Exception:
            published = datetime.now(UTC)
        article_id = f"fh-{a.get('id') or ts}"
        # clip_news_row caps every column to its DB length so a Finnhub
        # tracking-URL >500 chars can't poison the session.
        from app.services.news_feed import clip_news_row
        rows.append(clip_news_row({
            "id": article_id,
            "title": str(a.get("headline") or "").strip()[:300],
            "publisher": (a.get("source") or "Finnhub").strip(),
            "author": None,
            "published_at": published,
            "url": a.get("url") or "",
            "description": (a.get("summary") or "").strip()[:300] or None,
            "tickers": sym,
            "sentiment": None,
        }))
    # published_at is a datetime, which json.dumps can't serialize — so
    # _save_cache was silently TypeError-ing (logged as cache_write_failed)
    # and news was NEVER cached. Every /api/ticker render then re-hit Finnhub
    # (httpx 15s, 60/min rate-limited) while holding a DB connection, the core
    # driver of the QueuePool-exhaustion latency. Serialize published_at to ISO
    # for the on-disk copy only; the returned `rows` keep their datetimes and
    # the cache-hit path above re-hydrates.
    _save_cache(cache_key, [
        {
            **r,
            "published_at": r["published_at"].isoformat()
            if hasattr(r.get("published_at"), "isoformat")
            else r.get("published_at"),
        }
        for r in rows
    ])
    return rows


async def fetch_market_news(limit: int = 40) -> list[dict[str, Any]]:
    """Market-wide latest headlines from Finnhub /news?category=general.

    Added as a parallel source to news_feed.fetch_latest_news so universe-level
    freshness no longer depends solely on Massive's reference/news feed (which
    lags); the old real-time wire (Benzinga) was removed 2026-06-24. Returns the
    canonical news-row shape so callers don't care which source served it.

    Deliberately NOT cached: freshness is the whole point here, and it's a single
    cheap request per ~5-min worker refresh (well inside Finnhub's 60/min free
    tier). Mirrors the row-building of fetch_news_for_ticker.
    """
    from datetime import datetime

    if not configured():
        return []

    params = {"category": "general"}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{BASE_URL}/news", params=params, headers=auth_headers())
            if r.status_code != 200:
                return []
            payload = r.json()
            data = payload if isinstance(payload, list) else []
    except Exception:
        logger.exception("finnhub.market_news_fetch_failed")
        return []

    # Local import avoids a circular import at module load (news_feed imports
    # this module lazily too).
    from app.services.news_feed import clip_news_row

    rows: list[dict[str, Any]] = []
    for a in data[:limit]:
        # Finnhub's `datetime` is a unix timestamp (seconds).
        try:
            ts = int(a.get("datetime") or 0)
            published = datetime.fromtimestamp(ts, tz=UTC)
        except Exception:
            published = datetime.now(UTC)
        rows.append(clip_news_row({
            "id": f"fh-{a.get('id') or ts}",
            "title": str(a.get("headline") or "").strip()[:300],
            "publisher": (a.get("source") or "Finnhub").strip(),
            "author": None,
            "published_at": published,
            "url": a.get("url") or "",
            "description": (a.get("summary") or "").strip()[:300] or None,
            # General news often carries a comma-separated `related` ticker list
            # (frequently empty for macro headlines).
            "tickers": (a.get("related") or "").strip(),
            "sentiment": None,
        }))
    return rows


async def fetch_analyst_recommendations(symbol: str) -> dict[str, Any] | None:
    """Aggregate analyst tally from Finnhub /stock/recommendation.

    Returns the latest-period buy/hold/sell consensus in the canonical
    ratings shape the frontend's Analyst Ratings widget renders. Covers
    US, UK-listed, and international names.

    Note: Finnhub's free tier only exposes the AGGREGATE — individual
    rating events (firm-by-firm with prior/current + price targets) are
    a paid endpoint. So `events: []` and `avg_pt: null` here. The
    frontend handles the empty events list gracefully.
    """
    if not configured():
        return None

    sym = symbol.upper()
    cache_key = f"recs_{sym}"
    cached = _load_cache(cache_key, CACHE_TTL_RECS_HOURS)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                f"{BASE_URL}/stock/recommendation",
                params={"symbol": sym}, headers=auth_headers(),
            )
            if r.status_code != 200:
                return None
            data = r.json() if isinstance(r.json(), list) else []
    except Exception:
        logger.exception("finnhub.recs_fetch_failed symbol=%s", sym)
        return None

    if not data:
        return None

    # Pick the latest period. Finnhub returns desc by period.
    latest = data[0]
    bull = int(latest.get("strongBuy") or 0) + int(latest.get("buy") or 0)
    bear = int(latest.get("strongSell") or 0) + int(latest.get("sell") or 0)
    neutral = int(latest.get("hold") or 0)
    total = bull + bear + neutral
    if total == 0:
        return None

    result = {
        "symbol": sym,
        "consensus": {"bull": bull, "bear": bear, "neutral": neutral, "total": total},
        "avg_pt": None,
        "events": [],  # Finnhub free tier doesn't expose per-firm events.
        "source": "finnhub",
        "as_of_period": str(latest.get("period") or ""),
    }
    _save_cache(cache_key, result)
    return result


def _empty_ratings(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "consensus": {"bull": 0, "bear": 0, "neutral": 0, "total": 0},
        "avg_pt": None,
        "events": [],
        "source": "empty",
    }


async def fetch_analyst_ratings(symbol: str) -> dict[str, Any]:
    """Recent analyst ratings + consensus for a ticker — backs the per-ticker
    Analyst Ratings widget (GET /api/ticker/{symbol}/ratings).

    Returns the canonical ratings shape:

        {
          "symbol": "AAPL",
          "consensus": {"bull": int, "bear": int, "neutral": int, "total": int},
          "avg_pt": float | None,
          "events": [...],          # per-firm events (empty on Finnhub free tier)
          "source": "finnhub" | "empty",
        }

    When there's no analyst coverage for the ticker (common for thinly-covered
    long-tail names), returns the empty shape so the frontend renders a clean
    "no consensus tracked" state.
    """
    symbol = (symbol or "").upper()
    if not symbol:
        return _empty_ratings(symbol)
    try:
        data = await fetch_analyst_recommendations(symbol)
    except Exception:
        logger.exception("finnhub.ratings_fetch_failed symbol=%s", symbol)
        return _empty_ratings(symbol)
    if data and data.get("consensus", {}).get("total", 0) > 0:
        return data
    return _empty_ratings(symbol)
