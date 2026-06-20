"""Freemium daily ticker-lookup metering.

A "lookup" = one detailed single-ticker score view: GET /api/ticker/{symbol},
which powers the public /t/{symbol} page and the in-app ticker page. The
freemium model caps how many of these a non-paying caller gets per UTC day:

  - PRO / PREMIUM / active-14-day-trial users : UNLIMITED (never metered).
  - FREE (logged-in) users                    : tier.FREE_DAILY_LOOKUPS / day,
    counted durably on the users table (lookups_today / lookups_reset_on).
  - ANONYMOUS (no account)                     : tier.ANON_DAILY_LOOKUPS / day,
    counted in-memory per source IP (mirrors services/trial_abuse +
    services/rate_limit — a module dict keyed by IP, reset on the day boundary).

Both consume_* helpers are "consume on success": the router only calls them
after it has confirmed the symbol resolves to a real ticker, so a 404 / invalid
symbol never burns the caller's budget.

Single-instance caveat (same as trial_abuse / rate_limit): the anon counter is
per-process and resets on worker restart. Fine for the drive-by abuse profile;
move to Redis when concurrent Fly machines exceed one. The logged-in counter is
durable in Postgres and is therefore correct across restarts and machines.
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services.tier import (
    ANON_DAILY_LOOKUPS,
    Tier,
    is_on_trial,
    limit,
)


def _utc_today() -> date:
    return datetime.now(UTC).date()


def _is_unmetered(user: User) -> bool:
    """True for callers who are never metered: any paid tier (Pro/Premium) and
    users currently inside their no-card 14-day Premium trial.

    Free users — including a lapsed trial that dropped back to FREE — are
    metered. Active-trial users present as tier=premium with a future
    trial_ends_at and no Stripe customer; is_on_trial captures exactly that.
    """
    tier = Tier(user.tier)
    if tier in (Tier.PRO, Tier.PREMIUM):
        # Paid Pro/Premium and active-trial Premium are all uncapped. (A
        # tier=premium row IS either paid or on trial — either way, unmetered.)
        return True
    # Defensive: if a free-tier row somehow carries trial state, honour it.
    return is_on_trial(user.tier, user.trial_ends_at, user.stripe_customer_id)


async def consume_ticker_lookup(session: AsyncSession, user: User) -> dict:
    """Account for one detailed ticker lookup by a logged-in user.

    Returns dict(allowed, used, limit, remaining).

      - Pro / Premium / active-trial : always allowed, NO increment, limit=None
        (the UNLIMITED sentinel), remaining=None.
      - Free users : resets the counter when lookups_reset_on != today (UTC),
        then — only if under the cap — increments and commits. When already at
        the cap, returns allowed=False WITHOUT incrementing (the call is being
        rejected, so it mustn't cost a lookup).

    The caller (router) must invoke this only AFTER confirming the symbol is a
    real, fetchable ticker, so a 404 never burns budget.
    """
    if _is_unmetered(user):
        return {"allowed": True, "used": 0, "limit": None, "remaining": None}

    cap = limit(user.tier, "daily_lookups")
    # FREE is configured with an int cap; the UNLIMITED (None) sentinel here
    # would only appear via misconfiguration — treat it as "always allowed".
    if cap is None:
        return {"allowed": True, "used": 0, "limit": None, "remaining": None}

    today = _utc_today()
    # Roll the counter over on a new UTC day.
    if user.lookups_reset_on != today:
        user.lookups_today = 0
        user.lookups_reset_on = today

    used = user.lookups_today
    if used >= cap:
        # At/over cap — reject without consuming. Persist any rollover that
        # happened above (a same-day rollover is harmless; a day-boundary
        # rollover that lands exactly at a 0 cap is an edge we still persist).
        try:
            await session.commit()
        except Exception:
            await session.rollback()
        return {
            "allowed": False,
            "used": used,
            "limit": cap,
            "remaining": 0,
        }

    user.lookups_today = used + 1
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        # On a write failure, fail OPEN for the user-facing read — better to
        # serve the page than to 402 on an infra hiccup. The count just doesn't
        # advance this once.
        return {
            "allowed": True,
            "used": used,
            "limit": cap,
            "remaining": max(0, cap - used),
        }

    new_used = user.lookups_today
    return {
        "allowed": True,
        "used": new_used,
        "limit": cap,
        "remaining": max(0, cap - new_used),
    }


# ── Anonymous (no account) per-IP daily lookup meter ─────────────────────────
#
# In-memory, per-process. Mirrors the trial_abuse / rate_limit pattern: a module
# dict keyed by IP, holding (date, count). Reset lazily on the first hit of a new
# UTC day. Per-worker + reset-on-restart is acceptable for the anon abuse
# profile (a drive-by reading a few extra ticker pages is not the threat — the
# point is to convert anon → signup before they extract material value).
#
# Key = source IP string. Value = (utc_date, count_today).
_anon_lookups: dict[str, tuple[date, int]] = {}


def consume_anon_lookup(ip: str | None) -> dict:
    """Account for one detailed ticker lookup by an anonymous (no-account)
    caller, keyed by source IP.

    Returns dict(allowed, used, limit). Cap = tier.ANON_DAILY_LOOKUPS per UTC
    day. When already at the cap, returns allowed=False WITHOUT incrementing.

    A missing IP (couldn't read X-Forwarded-For / request.client) is bucketed
    under a shared "anon" key rather than waved through — anonymous access is the
    most abusable surface, so we'd rather over-meter a rare IP-less request than
    open an unmetered hole. (record_signup et al. fail OPEN; here we fail CLOSED
    because the downside is just an earlier sign-up prompt, not a blocked user.)
    """
    cap = ANON_DAILY_LOOKUPS
    key = ip or "anon"
    today = _utc_today()

    entry = _anon_lookups.get(key)
    if entry is None or entry[0] != today:
        used = 0
    else:
        used = entry[1]

    if used >= cap:
        # Keep the (today, used) entry as-is — don't advance past the cap.
        _anon_lookups[key] = (today, used)
        return {"allowed": False, "used": used, "limit": cap}

    used += 1
    _anon_lookups[key] = (today, used)
    return {"allowed": True, "used": used, "limit": cap}
