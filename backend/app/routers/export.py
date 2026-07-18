"""GET /api/export/* — Pro+ CSV downloads (PRICING.md's "CSV export").

CSV export has been sold on every pricing surface as a Pro feature since
launch, but until 2026-07-18 there was no endpoint and no button — this
router is the minimal delivery of exactly what those surfaces promise:

  GET /api/export/scanner.csv    — the current scanner result set (same
                                   filters/sort as GET /api/scanner)
  GET /api/export/watchlist.csv  — the caller's watchlist with current scores

Both are gated on tier.FEATURES["export.csv"] (Tier.PRO) using the same
has_feature() → 403 pattern as the other Pro routes (heatmap, squeeze,
regime), so the frontend's TierGateError → PaywallModal path works
unchanged. Free users KEEP the visible button client-side (shown-locked
feature) — the 403 here is the server-authoritative backstop.

Row cap: EXPORT_ROW_CAP (2500) — comfortably the whole scored universe
(~2,500 names) while bounding worst-case response size.
"""
from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import desc, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, is_sqlite
from app.models import Ticker, User, WatchlistItem
from app.routers.scanner import SCANNER_MIN_DOLLAR_VOLUME, SCANNER_QUERY_TIMEOUT_MS
from app.services.auth import current_user_required
from app.services.ticker_freshness import live_clauses
from app.services.tier import Tier, has_feature

router = APIRouter()

# Hard row ceiling for any single CSV export. The scored universe is ~2,500
# names, so Pro users get the whole thing; the cap exists to bound the
# response size, not to meter the feature.
EXPORT_ROW_CAP = 2500

# Standard tier-gate message — same phrase shape as the other Pro routes
# ("Heatmap is a Pro feature") so frontend TierGateError parses the required
# tier ("Pro") out of it.
_GATE_DETAIL = "CSV export is a Pro feature"

_SCANNER_HEADERS = [
    "symbol", "name", "sector", "asset_class", "score", "signal", "price",
    "change_pct_1d", "change_pct_5d", "change_pct_1m", "volume",
    "confidence_pct", "sub_trend", "sub_rs", "sub_fundamentals",
    "sub_momentum", "sub_macro", "sub_smart_money", "reason", "updated_at",
]

_WATCHLIST_HEADERS = [
    "symbol", "note", "added_at", "baseline_score", "current_score",
    "score_delta", "signal", "price", "change_pct_1d",
    "alert_threshold_delta", "reason",
]


def _require_csv_export(user: User) -> None:
    """403 with the standard Pro-feature detail unless the tier includes it."""
    if not has_feature(Tier(user.tier), "export.csv"):
        raise HTTPException(403, _GATE_DETAIL)


def _sanitize_cell(value: object) -> object:
    """Neutralise spreadsheet formula injection in string cells.

    A cell beginning with = + - @ (or a tab/CR) is executed as a formula by
    Excel / Sheets on open. Watchlist notes are user-authored and ticker
    name/reason come from external feeds, so prefix any such string with a
    literal apostrophe (the standard mitigation — renders as text, executes
    nothing). Numbers pass through untouched; None becomes an empty cell
    (csv.writer would otherwise emit the literal string "None").
    """
    if value is None:
        return ""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _csv_response(headers: list[str], rows: list[list[object]], kind: str) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_sanitize_cell(v) for v in row])
    filename = f"tapeline-{kind}-{datetime.now(UTC).strftime('%Y-%m-%d')}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            # User-specific data — never let a shared cache hold it.
            "Cache-Control": "no-store",
        },
    )


@router.get("/scanner.csv")
async def export_scanner_csv(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user_required),
    # Same filter surface as GET /api/scanner (routers/scanner.py) so the
    # export matches what the user is looking at. Kept in sync by hand —
    # both places validate with identical Query() constraints.
    min_score: float = Query(0, ge=0, le=100),
    max_score: float = Query(100, ge=0, le=100),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    min_dollar_volume: float = Query(SCANNER_MIN_DOLLAR_VOLUME, ge=0),
    signal: str | None = None,
    sector: str | None = None,
    q: str | None = Query(None, max_length=20),
    sort: str = Query("score", pattern="^(score|change_pct_1d|change_pct_5d|change_pct_1m|volume|symbol)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(EXPORT_ROW_CAP, ge=1, le=EXPORT_ROW_CAP),
) -> Response:
    """Current scanner result set as CSV — Pro+, capped at EXPORT_ROW_CAP rows.

    Mirrors the /api/scanner query exactly (filters, freshness/data-quality
    floor, liquidity floor, sort) with the export row cap instead of the
    pagination cap, so what downloads is what the scanner ranks.
    """
    _require_csv_export(user)

    # Ticker.score IS NOT NULL is enforced by live_clauses() below.
    stmt = select(Ticker).where(
        Ticker.score >= min_score,
        Ticker.score <= max_score,
    )
    if min_price is not None:
        stmt = stmt.where(Ticker.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Ticker.price <= max_price)
    if signal:
        stmt = stmt.where(Ticker.signal == signal)
    if sector:
        stmt = stmt.where(Ticker.sector == sector)
    if q:
        needle = q.strip().upper()
        if needle:
            stmt = stmt.where(Ticker.symbol.like(f"%{needle}%"))

    # Same freshness + data-quality floor as the scanner — the export must
    # never contain ghost/corrupt rows the in-app view hides.
    for clause in await live_clauses(session):
        stmt = stmt.where(clause)

    # Same liquidity floor semantics as the scanner: drop rows whose KNOWN
    # dollar-volume is under the floor; keep rows missing price/volume.
    if min_dollar_volume > 0:
        stmt = stmt.where(
            or_(
                Ticker.price.is_(None),
                Ticker.volume.is_(None),
                Ticker.price * Ticker.volume >= min_dollar_volume,
            )
        )

    col = getattr(Ticker, sort)
    stmt = stmt.order_by(desc(col) if order == "desc" else col)
    stmt = stmt.limit(limit)

    # Server-side statement cap (Postgres only — no-op on SQLite), mirroring
    # routers/scanner.py's pool-exhaustion guard for pathological filters.
    if not is_sqlite():
        await session.execute(
            text(f"SET LOCAL statement_timeout = '{SCANNER_QUERY_TIMEOUT_MS}ms'")
        )

    rows = (await session.execute(stmt)).scalars().all()

    csv_rows: list[list[object]] = [
        [
            r.symbol, r.name, r.sector, r.asset_class, r.score, r.signal,
            r.price, r.change_pct_1d, r.change_pct_5d, r.change_pct_1m,
            r.volume, r.confidence_pct, r.sub_trend, r.sub_rs,
            r.sub_fundamentals, r.sub_momentum, r.sub_macro,
            r.sub_smart_money, r.reason,
            r.updated_at.isoformat() if r.updated_at else None,
        ]
        for r in rows
    ]
    return _csv_response(_SCANNER_HEADERS, csv_rows, "scanner")


@router.get("/watchlist.csv")
async def export_watchlist_csv(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user_required),
    # Optional single-list narrowing, same param as GET /api/watchlist.
    list_id: int | None = None,
) -> Response:
    """The caller's watchlist (all lists, or one via list_id) with current
    scores, as CSV. Pro+ only. Cross-user access is impossible — the WHERE
    clause always pins WatchlistItem.user_id to the caller."""
    _require_csv_export(user)

    stmt = (
        select(WatchlistItem, Ticker)
        .outerjoin(Ticker, Ticker.symbol == WatchlistItem.symbol)
        .where(WatchlistItem.user_id == user.id)
        .order_by(desc(WatchlistItem.added_at))
        .limit(EXPORT_ROW_CAP)
    )
    if list_id is not None:
        stmt = stmt.where(WatchlistItem.watchlist_id == list_id)
    rows = (await session.execute(stmt)).all()

    csv_rows: list[list[object]] = []
    for w, t in rows:
        current_score = t.score if t else None
        delta = (
            (current_score - w.baseline_score)
            if (current_score is not None and w.baseline_score is not None)
            else None
        )
        csv_rows.append([
            w.symbol,
            w.note,
            w.added_at.isoformat() if w.added_at else None,
            w.baseline_score,
            current_score,
            delta,
            t.signal if t else None,
            t.price if t else None,
            t.change_pct_1d if t else None,
            w.alert_threshold_delta,
            t.reason if t else None,
        ])
    return _csv_response(_WATCHLIST_HEADERS, csv_rows, "watchlist")
