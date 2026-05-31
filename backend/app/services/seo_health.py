"""SEO health automations — stale-link audit + weekly digest renderer.

WHY: Tapeline ships new SEO surfaces faster than a human can manually
re-verify everything. Two failure modes accumulate silently:

  1. STALE LINKS — a published URL gets renamed or removed; existing
     internal links keep 404'ing; search-engine quality classifier
     downranks the whole cluster. We need to catch these within a week,
     not a month.

  2. SEO REGRESSIONS — an indexed page silently 5xx's for a day; new
     content goes uncrawled because we forgot to bump the sitemap;
     impressions drop on a query cluster we thought was working. The
     founder needs a Monday-morning summary that surfaces these
     without them having to open GSC.

This module owns both. Functions are pure async + return structured
results so they can be called from the worker (signal_publisher tick)
OR from a CLI for ad-hoc inspection.

DELIVERY: results go to the founder's Telegram chat (via the existing
services/telegram.py send_message). The chat_id is sourced from the
owner User record (owner@tapeline.io); if not configured, the digest
is logged at INFO level and otherwise discarded.

NO EXTERNAL CREDENTIALS: stale-link audit just fetches our own URLs
over HTTPS — no GCP, no Search Console API, no Microsoft Webmaster
Tools. The weekly digest pulls from internal DB + sitemap fetch.
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from xml.etree import ElementTree as ET

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Ticker, User
from app.services.telegram import send_message

logger = logging.getLogger(__name__)
settings = get_settings()

PUBLIC_BASE = "https://tapeline.io"
SITEMAP_URL = f"{PUBLIC_BASE}/sitemap.xml"

# Concurrency cap on the audit HTTP fetches. Each /t/ HEAD triggers a Next.js
# SSR render that calls /api/ticker on our own backend, so this number is also
# the burst we inflict on the API's 30-connection DB pool. Lowered 10→4 after
# the 2026-05-31 incident: even with /api/ticker no longer holding a connection
# across its news fetch, a courteous background audit has no business running
# more than a handful of concurrent origin fetches. Finishes ~1k URLs in a few
# minutes — fine for a once-daily task.
AUDIT_CONCURRENCY = 4

# We treat any HTTP status outside this set as a problem. 200-299 = OK.
# 3xx = redirect (still resolves, fine for SEO). 4xx/5xx = broken.
HEALTHY_STATUSES = set(range(200, 400))


# --------------------------------------------------------------------------
# Sitemap fetch
# --------------------------------------------------------------------------


async def fetch_sitemap_urls(sitemap_url: str = SITEMAP_URL) -> list[str]:
    """Pull the live sitemap and return the URL list.

    Handles both <urlset> (flat) and <sitemapindex> (nested) shapes,
    though Tapeline currently uses flat. Logs and returns [] on any
    fetch / parse failure — caller decides whether to bail.
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(sitemap_url)
            r.raise_for_status()
            xml = r.text
    except Exception:
        logger.exception("sitemap.fetch_failed url=%s", sitemap_url)
        return []

    try:
        # Strip XML namespace so xpath is readable. The sitemap spec
        # always uses http://www.sitemaps.org/schemas/sitemap/0.9, but
        # parsers vary on whether they require explicit namespace maps.
        xml_no_ns = re.sub(r'\sxmlns="[^"]+"', "", xml, count=1)
        root = ET.fromstring(xml_no_ns)
    except ET.ParseError:
        logger.exception("sitemap.parse_failed bytes=%d", len(xml))
        return []

    # Flat <urlset>: <url><loc>...</loc></url>
    locs = [el.text for el in root.findall(".//url/loc") if el.text]
    # Nested <sitemapindex>: <sitemap><loc>...</loc></sitemap> — we'd
    # need to recurse. Not currently used, but support added pre-emptively.
    if not locs:
        nested_sitemaps = [el.text for el in root.findall(".//sitemap/loc") if el.text]
        for nested in nested_sitemaps:
            locs.extend(await fetch_sitemap_urls(nested))

    return locs


# --------------------------------------------------------------------------
# Stale-link audit
# --------------------------------------------------------------------------


async def audit_one(url: str, client: httpx.AsyncClient) -> tuple[str, int, str]:
    """Audit a single URL — HEAD first, fall back to GET if HEAD is
    blocked (some CDN / framework configs reject HEAD). Returns
    (url, status_code, error_message).
    """
    try:
        # HEAD first — cheap, often blocked though.
        r = await client.head(url, follow_redirects=True, timeout=15)
        if r.status_code == 405 or r.status_code == 501:
            # Method not allowed / not implemented — try GET.
            r = await client.get(url, follow_redirects=True, timeout=20)
        return (url, r.status_code, "")
    except httpx.TimeoutException:
        return (url, 0, "timeout")
    except httpx.HTTPError as e:
        return (url, 0, f"http_error: {e.__class__.__name__}")
    except Exception as e:
        return (url, 0, f"exception: {e.__class__.__name__}")


async def run_stale_link_audit(
    sitemap_url: str = SITEMAP_URL,
    concurrency: int = AUDIT_CONCURRENCY,
) -> dict:
    """Crawl every URL in the sitemap; return a structured audit result.

    Result shape:
        {
            "checked": int,
            "healthy": int,
            "broken": [{"url": str, "status": int, "error": str}, ...],
            "ran_at": ISO timestamp,
        }

    Broken = status not in 200-399, or any HTTP / network exception.
    """
    urls = await fetch_sitemap_urls(sitemap_url)
    if not urls:
        return {
            "checked": 0,
            "healthy": 0,
            "broken": [],
            "ran_at": datetime.now(UTC).isoformat(),
            "note": "sitemap_unavailable",
        }

    import asyncio

    sem = asyncio.Semaphore(concurrency)
    broken: list[dict] = []
    healthy_count = 0

    async with httpx.AsyncClient(
        # User-Agent that identifies us — courteous, and lets log
        # readers on our own backend recognise audit traffic.
        headers={"User-Agent": "TapelineHealthAudit/1.0 (+https://tapeline.io)"},
    ) as client:

        async def _check(url: str) -> None:
            nonlocal healthy_count
            async with sem:
                u, status, err = await audit_one(url, client)
                if status in HEALTHY_STATUSES:
                    healthy_count += 1
                else:
                    broken.append({"url": u, "status": status, "error": err})

        await asyncio.gather(*[_check(u) for u in urls])

    return {
        "checked": len(urls),
        "healthy": healthy_count,
        "broken": broken,
        "ran_at": datetime.now(UTC).isoformat(),
    }


# --------------------------------------------------------------------------
# Weekly SEO digest
# --------------------------------------------------------------------------


async def _owner_chat_id(session: AsyncSession) -> str | None:
    """Return the founder's Telegram chat_id, or None if not configured.

    The owner user is seeded by scripts/seed_owner.py with email
    settings.owner_email (defaults to owner@tapeline.io). Telegram
    chat_id is set by the user via /app/billing → Telegram card.
    """
    owner_email = getattr(settings, "owner_email", None) or "owner@tapeline.io"
    r = await session.execute(select(User).where(User.email == owner_email))
    user = r.scalar_one_or_none()
    if user is None:
        logger.warning("seo_digest.owner_not_found email=%s", owner_email)
        return None
    return user.telegram_chat_id


async def render_weekly_digest(
    session: AsyncSession,
    stale_audit: dict | None = None,
) -> str:
    """Build the weekly SEO digest Markdown string.

    Pulls from internal DB + the most recent stale-link audit (passed
    in to avoid double-fetching). If no audit is provided, runs one
    inline (slower but self-contained for ad-hoc CLI use).
    """
    now = datetime.now(UTC)
    if stale_audit is None:
        stale_audit = await run_stale_link_audit()

    # Universe stats: how many tickers tracked, how many indexed-class
    # (score >= 40, i.e. has data we'd want crawled), how many have
    # confidence > 60.
    counts_r = await session.execute(
        select(
            func.count(Ticker.symbol).label("total"),
            func.count(Ticker.symbol).filter(Ticker.score >= 40).label("scored"),
            func.count(Ticker.symbol).filter(Ticker.confidence_pct >= 60).label("confident"),
            func.count(Ticker.symbol).filter(Ticker.sector.isnot(None)).label("sectored"),
        )
    )
    counts = counts_r.one()
    total = counts.total or 0
    scored = counts.scored or 0
    confident = counts.confident or 0
    sectored = counts.sectored or 0

    # Sitemap size from the audit
    sitemap_total = stale_audit.get("checked", 0)
    healthy = stale_audit.get("healthy", 0)
    broken_list = stale_audit.get("broken", []) or []
    broken_count = len(broken_list)

    iso_year, iso_week, _ = now.isocalendar()
    lines = [
        f"📊 *Tapeline weekly SEO digest* — week {iso_year}-W{iso_week:02d}",
        "",
        "*Sitemap*",
        f"  • {sitemap_total} URLs in sitemap.xml",
        f"  • {healthy} returning 2xx/3xx",
        f"  • {broken_count} broken {'⚠️' if broken_count else '✅'}",
        "",
        "*Ticker universe*",
        f"  • {total:,} tickers tracked",
        f"  • {scored:,} with composite ≥ 40 (eligible to surface)",
        f"  • {confident:,} with data-confidence ≥ 60%",
        f"  • {sectored:,} with known sector",
        "",
    ]

    # Per-broken-URL detail, if any. Truncate to 8 to keep the Telegram
    # message under length limits.
    if broken_list:
        lines.append("*Broken URLs (top 8)*")
        for entry in broken_list[:8]:
            status = entry.get("status") or 0
            url = entry.get("url", "")
            err = entry.get("error", "")
            tag = f"[{status}]" if status else f"[{err or 'fail'}]"
            # Trim long URLs to keep lines under Telegram's per-line wrap
            short = url.replace(PUBLIC_BASE, "")
            lines.append(f"  • `{tag}` {short or url}")
        if broken_count > 8:
            lines.append(f"  • _… {broken_count - 8} more — full list in worker logs_")
        lines.append("")

    # Action prompts
    lines.append("*Suggested next steps*")
    if broken_count > 0:
        lines.append("  • Open the broken URLs above, fix or 301-redirect")
    lines.append("  • Check GSC `Pages → Why not indexed` for new buckets")
    lines.append("  • Skim Performance → Queries for keywords newly in top 20")
    lines.append("")
    lines.append("_This digest fires every Monday around 09:00 UTC._")

    return "\n".join(lines)


async def run_weekly_digest(session: AsyncSession) -> bool:
    """Render + send the weekly SEO digest. Returns True on success."""
    chat_id = await _owner_chat_id(session)
    if not chat_id:
        logger.info("seo_digest.skipped no_owner_chat_id")
        return False

    # Run audit once, pass into digest renderer.
    stale = await run_stale_link_audit()
    text = await render_weekly_digest(session, stale_audit=stale)
    sent = await send_message(chat_id, text)
    if sent:
        logger.info(
            "seo_digest.sent broken=%d healthy=%d",
            len(stale.get("broken", [])), stale.get("healthy", 0),
        )
    return sent


async def run_stale_audit_alert(session: AsyncSession) -> bool:
    """Run a stale-link audit and alert the founder ONLY if broken
    URLs are present. Intended for daily/weekly cron use as a
    lightweight pager — no broken links = no Telegram noise.
    """
    chat_id = await _owner_chat_id(session)
    if not chat_id:
        logger.info("stale_audit.skipped no_owner_chat_id")
        return False

    stale = await run_stale_link_audit()
    broken = stale.get("broken", []) or []
    if not broken:
        logger.info("stale_audit.clean checked=%d", stale.get("checked", 0))
        return False

    now = datetime.now(UTC).strftime("%b %d %H:%M UTC")
    lines = [
        f"⚠️ *Tapeline link health alert* — {now}",
        "",
        f"{len(broken)} URL{'s' if len(broken) != 1 else ''} returning non-2xx/3xx:",
        "",
    ]
    for entry in broken[:12]:
        status = entry.get("status") or 0
        url = entry.get("url", "")
        err = entry.get("error", "")
        tag = f"[{status}]" if status else f"[{err or 'fail'}]"
        short = url.replace(PUBLIC_BASE, "")
        lines.append(f"  • `{tag}` {short or url}")
    if len(broken) > 12:
        lines.append(f"  • _… {len(broken) - 12} more — full list in worker logs_")
    lines.append("")
    lines.append("Fix or 301-redirect ASAP — Google downranks the cluster otherwise.")

    sent = await send_message(chat_id, "\n".join(lines))
    if sent:
        logger.warning("stale_audit.alerted broken=%d", len(broken))
    return sent
