"""Embed impression recording + roll-up.

Two jobs:

  1. `record_embed_impression(...)` — increment one (day, host, symbol, surface)
     bucket. Fire-and-forget: it NEVER raises, and it never blocks the render it
     rides along with (the caller is a detached background task).
  2. `summarize_embed_impressions(...)` — the admin readout: top embedding
     hosts, top embedded symbols, per-day totals over the last N days.

PRIVACY CONTRACT (see also models/embed_impression.py)
------------------------------------------------------
The only third-party string that ever lands in the database is a HOSTNAME.
`normalize_embed_host` is the single chokepoint that enforces it, and it is
applied on BOTH sides of the wire: the frontend derives the hostname from the
browser's Referer before it ever leaves the Next server, and this function
re-derives + re-validates it here. A referring URL's path or query can carry a
search phrase, a document title, a session token, or an account handle from
someone else's site — none of that may be persisted, so we throw the whole URL
away and keep the host label.

Skipped (recorded as "not an external embed", never stored):
  - a missing / empty / unparseable Referer
  - our own domain (tapeline.io + subdomains + the configured app_url host) —
    an internal page previewing the badge is not a distribution signal
  - localhost / loopback / *.local — dev renders

WHY AGGREGATE, NOT LOG
----------------------
Badges are hotlinked images: one popular README can fire thousands of requests a
day. Rows are therefore bounded by the number of distinct embedding sites, not
by traffic volume. See the model docstring for why the resulting counts are
directional (CDN caching) and must not be "reconciled".
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.embed_impression import EMBED_SURFACES, MAX_HOST_LEN, EmbedImpression

logger = logging.getLogger(__name__)
settings = get_settings()

# A hostname after lowercasing: letters, digits, dots and hyphens, starting and
# ending alphanumeric. Anything else (spaces, slashes, `?`, `@`, credentials,
# control characters) is junk or an attempt to smuggle a non-host string into
# the column — dropped rather than stored.
_HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$")

# Ticker shape, mirroring the badge route's own client-side guard.
_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")

# Loopback / dev hosts. A developer rendering the badge locally is not a
# distribution signal.
_LOCAL_HOSTS: frozenset[str] = frozenset(
    {"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"}
)


def _self_hosts() -> set[str]:
    """Hostnames that count as "us" — never recorded as an embedding site.

    Always includes the production apex; also picks up whatever `app_url` is
    configured to, so a preview/staging origin doesn't pollute the readout.
    """
    hosts = {"tapeline.io"}
    try:
        configured = (urlsplit(settings.app_url or "").hostname or "").strip().lower()
        if configured.startswith("www."):
            configured = configured[4:]
        if configured:
            hosts.add(configured)
    except Exception:
        pass
    return hosts


def normalize_embed_host(referer: str | None) -> str | None:
    """Reduce a Referer (or a bare hostname) to a storable host label.

    Returns None whenever the value must NOT be recorded — missing, junk,
    our own domain, or a local/dev host. Accepts both a full URL (what a
    browser sends) and an already-extracted hostname (what the frontend
    forwards), so the same rules apply on both sides of the wire.

    ONLY the hostname survives. A URL's path and query are discarded here and
    are never returned, logged, or stored.
    """
    if not referer:
        return None
    raw = referer.strip()
    if not raw:
        return None
    try:
        # urlsplit only populates `hostname` when there's an authority section,
        # so a bare "blog.example.com" needs the scheme-relative prefix.
        if "://" not in raw:
            raw = "//" + raw.lstrip("/")
        host = (urlsplit(raw).hostname or "").strip().lower().rstrip(".")
    except Exception:
        # A malformed Referer is the remote site's problem, never ours.
        return None
    if not host:
        return None

    # Treat www.example.com and example.com as one site.
    if host.startswith("www."):
        host = host[4:]

    if host in _LOCAL_HOSTS or host.endswith((".local", ".localhost")):
        return None
    if host in _self_hosts() or host.endswith(".tapeline.io"):
        return None

    # Cap BEFORE validating so an absurdly long value can neither reach the
    # column nor pass as a plausible host once truncated.
    host = host[:MAX_HOST_LEN]
    if not _HOST_RE.match(host):
        return None
    # A host with no dot is either a bare intranet name or junk — not a public
    # site we could ever do outreach to.
    if "." not in host:
        return None
    return host


def normalize_symbol(symbol: str | None) -> str | None:
    """Uppercase + shape-check a ticker. None when it isn't a plausible symbol."""
    if not symbol:
        return None
    sym = symbol.strip().upper()
    # `/badge/NVDA.svg` is a supported URL form; the extension isn't part of
    # the ticker.
    if sym.endswith(".SVG"):
        sym = sym[:-4]
    return sym if _SYMBOL_RE.match(sym) else None


def normalize_surface(surface: str | None) -> str | None:
    """One of EMBED_SURFACES, else None."""
    if not surface:
        return None
    s = surface.strip().lower()
    return s if s in EMBED_SURFACES else None


async def record_embed_impression(
    session: AsyncSession,
    *,
    referer: str | None,
    symbol: str,
    surface: str,
    day: date | None = None,
) -> bool:
    """Increment one impression bucket. Never raises; returns whether it stored.

    False means "deliberately skipped or safely failed" — a self/dev/missing
    referer, a junk symbol, an unknown surface, or a write error. The caller is
    an embed render that has already been (or is about to be) served, so there
    is nothing to fail: a lost impression is strictly cheaper than a broken
    badge.

    The write is UPDATE-first so the common case (an established embed being
    re-rendered) is a single indexed statement with no read. Only a bucket's
    FIRST impression of the day pays for an INSERT, and a race on that INSERT
    is resolved by falling back to the increment.
    """
    try:
        host = normalize_embed_host(referer)
        sym = normalize_symbol(symbol)
        surf = normalize_surface(surface)
        if host is None or sym is None or surf is None:
            return False

        bucket_day = day or datetime.now(UTC).date()
        now = datetime.now(UTC)

        def _increment():
            return (
                update(EmbedImpression)
                .where(
                    EmbedImpression.day == bucket_day,
                    EmbedImpression.host == host,
                    EmbedImpression.symbol == sym,
                    EmbedImpression.surface == surf,
                )
                .values(
                    impressions=EmbedImpression.impressions + 1,
                    last_seen_at=now,
                )
            )

        # getattr: an UPDATE always yields a CursorResult (which has rowcount),
        # but the annotated return type is the base Result — read it defensively
        # so a driver that doesn't report rowcount degrades to the INSERT path
        # instead of raising.
        result = await session.execute(_increment())
        if getattr(result, "rowcount", 0):
            await session.commit()
            return True

        # First impression for this bucket today.
        try:
            session.add(
                EmbedImpression(
                    day=bucket_day,
                    host=host,
                    symbol=sym,
                    surface=surf,
                    impressions=1,
                    first_seen_at=now,
                    last_seen_at=now,
                )
            )
            await session.commit()
            return True
        except IntegrityError:
            # A concurrent request created the same bucket between our UPDATE
            # and our INSERT. The unique constraint caught it; increment the
            # row that won instead of writing a duplicate.
            await session.rollback()
            retry = await session.execute(_increment())
            await session.commit()
            return bool(getattr(retry, "rowcount", 0))
    except Exception:
        logger.warning(
            "embed_impression.record_failed symbol=%s surface=%s", symbol, surface
        )
        try:
            await session.rollback()
        except Exception:
            pass
        return False


async def summarize_embed_impressions(
    session: AsyncSession,
    *,
    days: int = 30,
    top: int = 20,
) -> dict:
    """Roll up the last `days` days of embed impressions for the admin readout.

    Returns top embedding hosts, top embedded symbols, per-surface totals and a
    per-day series — i.e. "is the distribution loop working, who is carrying us,
    and which tickers get embedded". Every failure degrades to an empty summary:
    this rides inside the revenue dashboard and must never take it down.
    """
    window_days = max(1, min(int(days), 365))
    top_n = max(1, min(int(top), 100))
    empty: dict = {
        "window_days": window_days,
        "impressions_total": 0,
        "distinct_hosts": 0,
        "by_surface": {},
        "top_hosts": [],
        "top_symbols": [],
        "by_day": [],
    }
    try:
        # Inclusive window: `days=1` means today only.
        cutoff = datetime.now(UTC).date() - timedelta(days=window_days - 1)
        in_window = EmbedImpression.day >= cutoff
        total_col = func.coalesce(func.sum(EmbedImpression.impressions), 0)

        impressions_total = (
            await session.execute(
                select(total_col).where(in_window)
            )
        ).scalar() or 0

        distinct_hosts = (
            await session.execute(
                select(func.count(func.distinct(EmbedImpression.host))).where(in_window)
            )
        ).scalar() or 0

        surface_rows = (
            await session.execute(
                select(EmbedImpression.surface, total_col.label("n"))
                .where(in_window)
                .group_by(EmbedImpression.surface)
            )
        ).all()

        host_rows = (
            await session.execute(
                select(
                    EmbedImpression.host,
                    total_col.label("impressions"),
                    func.count(func.distinct(EmbedImpression.symbol)).label("symbols"),
                )
                .where(in_window)
                .group_by(EmbedImpression.host)
                .order_by(total_col.desc())
                .limit(top_n)
            )
        ).all()

        symbol_rows = (
            await session.execute(
                select(
                    EmbedImpression.symbol,
                    total_col.label("impressions"),
                    func.count(func.distinct(EmbedImpression.host)).label("hosts"),
                )
                .where(in_window)
                .group_by(EmbedImpression.symbol)
                .order_by(total_col.desc())
                .limit(top_n)
            )
        ).all()

        day_rows = (
            await session.execute(
                select(EmbedImpression.day, total_col.label("impressions"))
                .where(in_window)
                .group_by(EmbedImpression.day)
                .order_by(EmbedImpression.day)
            )
        ).all()

        return {
            "window_days": window_days,
            "impressions_total": int(impressions_total),
            "distinct_hosts": int(distinct_hosts),
            "by_surface": {row[0]: int(row[1]) for row in surface_rows},
            "top_hosts": [
                {
                    "host": row.host,
                    "impressions": int(row.impressions),
                    "symbols": int(row.symbols),
                }
                for row in host_rows
            ],
            "top_symbols": [
                {
                    "symbol": row.symbol,
                    "impressions": int(row.impressions),
                    "hosts": int(row.hosts),
                }
                for row in symbol_rows
            ],
            "by_day": [
                {"day": str(row[0]), "impressions": int(row[1])} for row in day_rows
            ],
        }
    except Exception:
        logger.warning("embed_impression.summary_failed days=%s", days)
        return empty
