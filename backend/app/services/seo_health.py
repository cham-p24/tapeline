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
from app.services.telegram import SendStatus, send_message, send_message_status

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


class SitemapUnavailableError(RuntimeError):
    """The audit could not read the sitemap, so it checked nothing.

    run_stale_link_audit reports that as {"checked": 0, "broken": []}, which a
    caller counting broken URLs reads as a clean site. Both founder reports
    raise this instead of saying the site is healthy.
    """


def _require_sitemap(stale: dict) -> None:
    if stale.get("note") == "sitemap_unavailable" or not stale.get("checked"):
        raise SitemapUnavailableError(
            f"the audit checked {stale.get('checked', 0)} URLs "
            f"(note={stale.get('note', 'none')}); {SITEMAP_URL} could not be read"
        )


def _log_broken(prefix: str, broken: list[dict]) -> None:
    """The full broken list, into the run log the Telegram message points to."""
    for entry in broken:
        logger.warning(
            "%s.broken status=%s error=%s url=%s",
            prefix, entry.get("status") or 0, entry.get("error") or "-", entry.get("url", ""),
        )


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
    *,
    week: tuple[int, int] | None = None,
) -> str:
    """Build the weekly SEO digest Markdown string.

    Pulls from internal DB + the most recent stale-link audit (passed
    in to avoid double-fetching). If no audit is provided, runs one
    inline (slower but self-contained for ad-hoc CLI use).

    `week` is the (ISO year, ISO week) the digest is recorded under. The header
    must name that week, not the week the render happens to finish in: a run
    claimed late on a Sunday can render after midnight UTC.
    """
    if week is None:
        iso_year, iso_week, _ = datetime.now(UTC).isocalendar()
    else:
        iso_year, iso_week = week
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
            lines.append(f"  • _… {broken_count - 8} more — full list in the GitHub Actions run log_")
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
#: An (ISO year, ISO week) pair, compared as a tuple so that 2027-W01 comes after
#: 2026-W39. Comparing the week number alone would hold back 2027-W01 to W38.
FIRST_CLAIMED_WEEK: tuple[int, int] = (2026, 39)

#: Send errors that prove Telegram never received the request: no connection
#: was made. Anything else raised by the send (a read or write timeout, a
#: dropped connection, a protocol error) can happen after Telegram delivered.
_NOTHING_DELIVERED = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)


class DigestOutcome(enum.Enum):
    NOT_YET = "not_yet"                  # before Monday 09:00 UTC of this ISO week
    NO_RECIPIENT = "no_recipient"        # no bot token, or no owner chat id
    ALREADY_SENT = "already_sent"
    IN_FLIGHT = "in_flight"              # another run holds a fresh claim
    SENT = "sent"
    SENT_UNRECORDED = "sent_unrecorded"  # sent, but the claim could not be completed
    SEND_UNKNOWN = "send_unknown"        # the send may have delivered; the week is kept
    SITEMAP_UNAVAILABLE = "sitemap_unavailable"  # nothing checked, nothing sent; released
    FAILED = "failed"                    # nothing sent; the week is released to retry


def _utcnow() -> datetime:
    return datetime.now(UTC)


def iso_week(at: datetime) -> tuple[int, int]:
    """The (ISO year, ISO week) `at` falls in. Not the calendar year: 2027-01-01
    is in 2026-W53, and 2029-12-31 is in 2030-W01."""
    iso_year, week, _ = at.isocalendar()
    return (iso_year, week)


def period_key(week: tuple[int, int]) -> str:
    return f"{week[0]}W{week[1]:02d}"


async def _record_sent(claim: Claim) -> bool:
    """Complete the claim of a digest that was, or may have been, delivered.

    Never releases: a failure to record risks one duplicate a day later, while
    releasing would re-send on the next run.
    """
    for attempt in range(1, COMPLETE_ATTEMPTS + 1):
        try:
            if await complete_period(claim):
                return True
            logger.error("seo_digest.claim_lost_after_send period=%s", claim.period)
            return False
        except Exception:
            logger.exception(
                "seo_digest.complete_failed period=%s attempt=%d", claim.period, attempt,
            )
            if attempt < COMPLETE_ATTEMPTS:
                await asyncio.sleep(COMPLETE_RETRY_SECONDS * attempt)
    return False


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

    Nothing sent (a crawl error, an unreadable sitemap, a render that misses
    DIGEST_BUDGET, a connection that never opened, Telegram refusing the message
    with a 4xx) releases the week to the next run. A sent digest is never
    released; see COMPLETE_ATTEMPTS. Neither is a send whose delivery is
    unknown (a read timeout, a dropped connection, a Telegram 5xx): the week is
    recorded as sent and the run goes red, so a person checks Telegram rather
    than the next run sending it a second time.
    """
    started = clock()
    week = iso_week(started)
    if week < FIRST_CLAIMED_WEEK or (started.isoweekday(), started.hour) < (1, 9):
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

    period = period_key(week)
    claim = await claim_period(DIGEST_JOB, period, now=started)
    if claim.status is ClaimStatus.DONE:
        logger.info("seo_digest.already_sent period=%s", period)
        return DigestOutcome.ALREADY_SENT
    if claim.status is ClaimStatus.BUSY:
        # A run killed by a deploy leaves a claim that looks in flight for
        # STALE_CLAIM_AFTER. Say whose it is and when a re-dispatch takes over.
        held_since, retry_at = claim.held_since, claim.retryable_after()
        logger.warning(
            "seo_digest.in_flight_elsewhere period=%s owner=%s claimed_at=%s age=%s "
            "retryable_after=%s",
            period,
            f"{claim.held_by[:8]}..." if claim.held_by else "unknown",
            held_since.isoformat() if held_since else "unknown",
            f"{int((started - held_since).total_seconds() // 60)}m" if held_since else "unknown",
            retry_at.isoformat() if retry_at else "now",
        )
        return DigestOutcome.IN_FLIGHT

    deadline = started + DIGEST_BUDGET
    try:
        # No session is open across the crawl; see the module docstring.
        stale = await asyncio.wait_for(
            run_stale_link_audit(),
            timeout=max((deadline - clock()).total_seconds(), 0.0),
        )
        _require_sitemap(stale)
        async with session_scope() as session:
            text = await render_weekly_digest(session, stale_audit=stale, week=week)
        if clock() >= deadline:
            raise TimeoutError(f"digest rendered after its {DIGEST_BUDGET} budget")
    except SitemapUnavailableError:
        # "0 URLs, 0 broken" would be a healthy report about a site nobody checked.
        logger.exception("seo_digest.sitemap_unavailable period=%s released=yes", period)
        await _release(claim)
        return DigestOutcome.SITEMAP_UNAVAILABLE
    except Exception:
        logger.exception("seo_digest.failed period=%s", period)
        await _release(claim)
        return DigestOutcome.FAILED

    # Only the send is classified: from here an exception may follow delivery.
    try:
        status = await send_message_status(chat_id, text)
    except _NOTHING_DELIVERED:
        logger.exception("seo_digest.send_not_connected period=%s released=yes", period)
        await _release(claim)
        return DigestOutcome.FAILED
    except Exception:
        logger.exception("seo_digest.send_raised period=%s delivery=unknown", period)
        status = SendStatus.UNCERTAIN

    if status is SendStatus.UNCERTAIN:
        recorded = await _record_sent(claim)
        logger.error(
            "seo_digest.send_unknown period=%s recorded_as_sent=%s. Telegram may have "
            "delivered this digest. Check the founder's Telegram before re-dispatching: "
            "if it did not arrive, delete job_period_claims row (job=%s, period=%s) first.",
            period, "yes" if recorded else "no", DIGEST_JOB, period,
        )
        return DigestOutcome.SEND_UNKNOWN
    if status is not SendStatus.DELIVERED:
        # REFUSED is a Telegram 4xx: nothing delivered. SKIPPED cannot happen,
        # the bot token was checked above, but it too is nothing sent.
        logger.warning("seo_digest.send_refused period=%s status=%s", period, status.value)
        await _release(claim)
        return DigestOutcome.FAILED

    broken = stale.get("broken", []) or []
    logger.info(
        "seo_digest.sent period=%s broken=%d healthy=%d",
        period, len(broken), stale.get("healthy", 0),
    )
    _log_broken("seo_digest", broken)
    if await _record_sent(claim):
        return DigestOutcome.SENT
    return DigestOutcome.SENT_UNRECORDED


async def run_stale_audit_alert(session: AsyncSession) -> bool:
    """Run a stale-link audit and alert the founder ONLY if broken
    URLs are present. Intended for daily/weekly cron use as a
    lightweight pager — no broken links = no Telegram noise.

    Raises SitemapUnavailableError when the audit could not read the sitemap. That
    crawl checked nothing, and returning False would make the run look clean.
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
    _require_sitemap(stale)
    broken = stale.get("broken", []) or []
    _log_broken("stale_audit", broken)
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
        lines.append(f"  • _… {len(broken) - 12} more — full list in the GitHub Actions run log_")
    lines.append("")
    lines.append("Fix or 301-redirect ASAP — Google downranks the cluster otherwise.")

    sent = await send_message(chat_id, "\n".join(lines))
    if sent:
        logger.warning("stale_audit.alerted broken=%d", len(broken))
    return sent
