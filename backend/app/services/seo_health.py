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

This module owns both. Neither runs in the worker: a full-sitemap crawl in
the tick's process wedged production for ~3h on 2026-08-24. The daily audit
runs from .github/workflows/stale-link-audit.yml and the weekly digest from
.github/workflows/seo-weekly-digest.yml, each on the Fly machine over
`flyctl ssh`.

NEVER HOLD A DATABASE SESSION ACROSS THE CRAWL. Production Postgres has
idle_in_transaction_session_timeout = 5min and the crawl takes longer (4 to
14 minutes, 2026-09-06 to 09-12). A session that has run a query and then
waits on the crawl is killed, and its next statement fails. That is why the
daily audit failed on every run from 2026-09-07 to 09-12, each ending in
"received 2 results from command 'COMMIT'".

DELIVERY: results go to the founder's Telegram chat (via the existing
services/telegram.py send_message). The chat_id is sourced from the
owner User record (owner@tapeline.io); if not configured, the digest
is logged at INFO level and otherwise discarded.

NO EXTERNAL CREDENTIALS: stale-link audit just fetches our own URLs
over HTTPS — no GCP, no Search Console API, no Microsoft Webmaster
Tools. The weekly digest pulls from internal DB + sitemap fetch.
"""
from __future__ import annotations

import asyncio
import enum
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from xml.etree import ElementTree as ET

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import session_scope
from app.models import Ticker, User
from app.services.job_claims import (
    Claim,
    ClaimStatus,
    claim_period,
    complete_period,
    release_period,
)
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
# Re-check tuning. The backend's per-IP bucket refills at 2 tokens/sec, so a
# 30s pause is many times what a self-inflicted 429 needs to clear, while
# still finishing a re-check of a realistic broken list well inside one run.
RECHECK_PAUSE_SECONDS = 30
RECHECK_SPACING_SECONDS = 0.25

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

        # Re-check pass. The first sweep's "broken" list is NOT trustworthy on
        # its own: crawling the sitemap is itself a load spike, and every SSR
        # page render funnels through one Fly egress IP that shares the
        # backend's per-IP limit_api bucket. Sustained crawling therefore makes
        # the backend 429 its own frontend, which the ticker page turns into a
        # 500 — so the audit reports URLs *it* broke. That is exactly what
        # produced the "1,534 URLs returning non-2xx/3xx" alert while every one
        # of those pages served fine to a normal visitor moments later.
        #
        # A single serial re-check after a pause separates the two cases: a
        # genuinely broken URL fails again, a self-inflicted 429/timeout
        # recovers. Serial (not concurrent) and rate-limited so the re-check
        # cannot re-trigger the very condition it is measuring.
        if broken:
            await asyncio.sleep(RECHECK_PAUSE_SECONDS)
            confirmed: list[dict] = []
            for item in broken:
                u, status, err = await audit_one(item["url"], client)
                if status in HEALTHY_STATUSES:
                    healthy_count += 1          # recovered — was transient
                else:
                    confirmed.append({"url": u, "status": status, "error": err})
                await asyncio.sleep(RECHECK_SPACING_SECONDS)
            transient = len(broken) - len(confirmed)
            broken = confirmed
        else:
            transient = 0

    return {
        "checked": len(urls),
        "healthy": healthy_count,
        "broken": broken,
        # How many first-pass failures cleared on re-check. A large number here
        # means the sweep is load-limiting itself, not that the site is broken.
        "transient": transient,
        "ran_at": datetime.now(UTC).isoformat(),
    }


# --------------------------------------------------------------------------
# Weekly SEO digest
# --------------------------------------------------------------------------


async def _owner_chat_id(session: AsyncSession) -> str | None:
    """Return the founder's Telegram chat_id, or None if not configured.

    The owner user is seeded by scripts/seed_owner.py with email
    settings.owner_email (defaults to owner@tapeline.io), and the
    destination is that row's `telegram_chat_id` column. No endpoint
    writes that column any more — the customer-facing Telegram alert
    channel was retired 2026-08-11 — so it has to be set on the owner
    row directly. This is founder-facing plumbing only.
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
    transient_count = int(stale_audit.get("transient", 0) or 0)

    iso_year, iso_week, _ = now.isocalendar()
    lines = [
        f"📊 *Tapeline weekly SEO digest* — week {iso_year}-W{iso_week:02d}",
        "",
        "*Sitemap*",
        f"  • {sitemap_total} URLs in sitemap.xml",
        f"  • {healthy} returning 2xx/3xx",
        f"  • {broken_count} broken {'⚠️' if broken_count else '✅'}"
        + (
            # Confirmed on a second pass, so this is a real defect list rather
            # than the crawl tripping the SSR rate limit and reporting itself.
            f" (confirmed on re-check; {transient_count} first-pass "
            f"failures cleared and were self-inflicted)"
            if transient_count
            else ""
        ),
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
    lines.append("_Sent once a week, from Monday 09:00 UTC._")

    return "\n".join(lines)


#: The durable claim key for the weekly digest (services/job_claims).
DIGEST_JOB = "seo_weekly_digest"

#: A run that has not rendered its digest within this long of claiming the week
#: sends nothing. It sits well inside job_claims.STALE_CLAIM_AFTER, so by the
#: time a run sends, no other run can have taken the week over.
DIGEST_BUDGET = timedelta(minutes=45)

#: Attempts at recording a sent digest before giving up. After a send, the claim
#: is never released: a failure to record it risks one duplicate a day later,
#: while releasing it would re-send on the next run.
COMPLETE_ATTEMPTS = 3
COMPLETE_RETRY_SECONDS = 2.0

#: The first ISO week the claim governs. Until this change the worker sent the
#: digest from a process-memory latch, which leaves no record. The first Actions
#: run after the merge must not send a week the worker may already have sent.
FIRST_CLAIMED_WEEK = (2026, 39)


class DigestOutcome(enum.Enum):
    NOT_YET = "not_yet"                  # before Monday 09:00 UTC of this ISO week
    NO_RECIPIENT = "no_recipient"        # no bot token, or no owner chat id
    ALREADY_SENT = "already_sent"
    IN_FLIGHT = "in_flight"              # another run holds a fresh claim
    SENT = "sent"
    SENT_UNRECORDED = "sent_unrecorded"  # sent, but the claim could not be completed
    FAILED = "failed"                    # nothing sent; the week is released to retry


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _release(claim: Claim) -> None:
    try:
        await release_period(claim)
    except Exception:
        # The claim goes stale after job_claims.STALE_CLAIM_AFTER and is taken
        # over then, so a failed release delays the retry but does not lose it.
        logger.exception("seo_digest.release_failed period=%s", claim.period)


async def run_weekly_digest(*, clock: Callable[[], datetime] = _utcnow) -> DigestOutcome:
    """Send the weekly SEO digest at most once per ISO week.

    Run daily by .github/workflows/seo-weekly-digest.yml. Any run from Monday
    09:00 UTC to the end of the ISO week sends the week's digest if no earlier
    run has, so a run lost to a deploy or to Actions' late schedule is retried
    the next day. The week is claimed in job_period_claims before the crawl:

      DONE      the week was sent; nothing else happens, and nothing is crawled.
      BUSY      another run holds a fresh claim; this one stops.
      CLAIMED   crawl, render, send, then record the week as done.

    Nothing sent (a crawl error, a render that misses DIGEST_BUDGET, Telegram
    refusing the message) releases the week to the next run. A sent digest is
    never released; see COMPLETE_ATTEMPTS.
    """
    started = clock()
    iso_year, iso_week, iso_dow = started.isocalendar()
    if (iso_year, iso_week) < FIRST_CLAIMED_WEEK or (iso_dow, started.hour) < (1, 9):
        logger.info("seo_digest.not_yet at=%s", started.isoformat())
        return DigestOutcome.NOT_YET

    if not settings.telegram_bot_token:
        logger.info("seo_digest.skipped no_bot_token")
        return DigestOutcome.NO_RECIPIENT
    async with session_scope() as session:
        chat_id = await _owner_chat_id(session)
    if not chat_id:
        logger.info("seo_digest.skipped no_owner_chat_id")
        return DigestOutcome.NO_RECIPIENT

    period = f"{iso_year}W{iso_week:02d}"
    claim = await claim_period(DIGEST_JOB, period, now=started)
    if claim.status is ClaimStatus.DONE:
        logger.info("seo_digest.already_sent period=%s", period)
        return DigestOutcome.ALREADY_SENT
    if claim.status is ClaimStatus.BUSY:
        logger.info("seo_digest.in_flight_elsewhere period=%s", period)
        return DigestOutcome.IN_FLIGHT

    deadline = started + DIGEST_BUDGET
    try:
        # No session is open across the crawl; see the module docstring.
        stale = await asyncio.wait_for(
            run_stale_link_audit(),
            timeout=max((deadline - clock()).total_seconds(), 0.0),
        )
        async with session_scope() as session:
            text = await render_weekly_digest(session, stale_audit=stale)
        if clock() >= deadline:
            raise TimeoutError(f"digest rendered after its {DIGEST_BUDGET} budget")
        sent = await send_message(chat_id, text)
    except Exception:
        logger.exception("seo_digest.failed period=%s", period)
        await _release(claim)
        return DigestOutcome.FAILED

    if not sent:
        # send_message returns False on a Telegram non-200. The bot token was
        # checked above, so this is a refusal, not a missing configuration.
        logger.warning("seo_digest.send_refused period=%s", period)
        await _release(claim)
        return DigestOutcome.FAILED

    logger.info(
        "seo_digest.sent period=%s broken=%d healthy=%d",
        period, len(stale.get("broken", []) or []), stale.get("healthy", 0),
    )
    for attempt in range(1, COMPLETE_ATTEMPTS + 1):
        try:
            if await complete_period(claim):
                return DigestOutcome.SENT
            logger.error("seo_digest.claim_lost_after_send period=%s", period)
            return DigestOutcome.SENT_UNRECORDED
        except Exception:
            logger.exception("seo_digest.complete_failed period=%s attempt=%d", period, attempt)
            if attempt < COMPLETE_ATTEMPTS:
                await asyncio.sleep(COMPLETE_RETRY_SECONDS * attempt)
    return DigestOutcome.SENT_UNRECORDED


async def run_stale_audit_alert(session: AsyncSession) -> bool:
    """Run a stale-link audit and alert the founder ONLY if broken
    URLs are present. Intended for daily/weekly cron use as a
    lightweight pager — no broken links = no Telegram noise.
    """
    chat_id = await _owner_chat_id(session)
    # End the read before the crawl. Left open, the transaction sat idle for the
    # whole crawl, Postgres killed it at 5 minutes, and the caller's commit
    # failed after every crawl from 2026-09-07 to 09-12.
    await session.commit()
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
