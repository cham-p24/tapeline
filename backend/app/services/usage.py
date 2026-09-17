"""Freemium daily ticker-lookup metering.

A "lookup" = one detailed single-ticker score view: GET /api/ticker/{symbol},
which powers the public /t/{symbol} page and the in-app ticker page. The
freemium model caps how many of these a non-paying caller gets per UTC day:

  - PRO / PREMIUM / active-30-day-trial users : UNLIMITED (never metered).
  - Brand-new accounts (< tier.FREE_FIRST_SESSION_GRACE_HOURS old) : UNLIMITED
    for their first session, so a new user's first exploratory visit is never
    walled before they've found a ticker worth saving.
  - FREE (logged-in) users past the grace window : tier.FREE_DAILY_LOOKUPS / day,
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

import hashlib
import hmac
import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services.tier import (
    ANON_DAILY_LOOKUPS,
    FREE_FIRST_SESSION_GRACE_HOURS,
    Tier,
    is_on_trial,
    limit,
)

logger = logging.getLogger(__name__)


def _utc_today() -> date:
    return datetime.now(UTC).date()


def _within_first_session_grace(user: User) -> bool:
    """True while a brand-new account is inside its first-session grace window
    (tier.FREE_FIRST_SESSION_GRACE_HOURS from created_at).

    This is what makes a new user's FIRST exploratory session wall-free: they
    can click through as many ticker pages as they like on day one before any
    look-up metering kicks in. created_at is timezone-aware (server_default
    now()); older rows that are somehow naive are treated as UTC.
    """
    created = getattr(user, "created_at", None)
    if created is None:
        return False
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return datetime.now(UTC) - created < timedelta(hours=FREE_FIRST_SESSION_GRACE_HOURS)


def _is_unmetered(user: User) -> bool:
    """True for callers who are never metered: any paid tier (Pro/Premium),
    users currently inside their no-card 30-day Premium trial, AND any account
    still inside its first-session grace window (see _within_first_session_grace).

    Free users past the grace window — including a lapsed trial that dropped
    back to FREE — are metered. Active-trial users present as tier=premium with
    a future trial_ends_at and no Stripe customer; is_on_trial captures that.
    """
    tier = Tier(user.tier)
    if tier in (Tier.PRO, Tier.PREMIUM):
        # Paid Pro/Premium and active-trial Premium are all uncapped. (A
        # tier=premium row IS either paid or on trial — either way, unmetered.)
        return True
    # First-session grace: a new signup's first day is never walled.
    if _within_first_session_grace(user):
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
    # Atomic guarded increment — mirrors services/api_keys.authenticate_api_key.
    # A single UPDATE resets the counter to 1 on a UTC-day rollover, else
    # increments it via a SQL expression, and matches ONLY when the user is
    # under cap for TODAY (encoded in the WHERE). Two overlapping lookups now
    # serialise on the row write, so they can't both pass the cap and both
    # increment. The previous read-then-Python-increment (used = lookups_today;
    # if used < cap: lookups_today = used + 1) lost updates — two requests both
    # read used=N and both wrote N+1 — letting a Free user exceed the daily cap.
    new_today = case(
        (User.lookups_reset_on != today, 1),
        else_=User.lookups_today + 1,
    )
    result = await session.execute(
        update(User)
        .where(
            User.id == user.id,
            (User.lookups_reset_on != today) | (User.lookups_today < cap),
        )
        .values(lookups_today=new_today, lookups_reset_on=today)
    )
    over_cap = result.rowcount == 0  # type: ignore[attr-defined]  # CursorResult.rowcount (DML)
    try:
        await session.commit()
    except Exception:
        # Fail OPEN for the user-facing read on an infra hiccup — better to
        # serve the page than 402. The count just didn't advance this once.
        await session.rollback()

    # Reflect the committed counter for the meter (the UPDATE was raw SQL, so
    # the ORM `user` instance is stale).
    used = (await session.execute(
        select(User.lookups_today).where(User.id == user.id)
    )).scalar_one() or 0
    return {
        "allowed": not over_cap,
        "used": used,
        "limit": cap,
        "remaining": max(0, cap - used),
    }


# ── Stream refetches: served, never metered ──────────────────────────────────
#
# The in-app ticker page refetches GET /api/ticker/{symbol} each time the API's
# live bridge announces a worker pass (services/live_bridge.py, about every
# 60s in the US session). That is the SAME page the user already paid a
# look-up for, so it must not spend another, and at the cap it must not be a
# 402, a cap_events row or a founder email either.
#
# WHY A RECEIPT AND NOT A BARE MARKER. `?src=stream` on its own is a free pass
# anyone can type: a Free user could read every ticker in the universe without
# spending a look-up. The refetch therefore also carries the receipt the API
# handed back with the look-up it IS refreshing: an HMAC over
# (user id, symbol, UTC day) under the session secret. It proves "this user was
# served this symbol today" without any storage, so it holds across API
# machines and restarts, cannot be moved to another user or symbol, and expires
# at the same UTC midnight the counter resets on.
#
# WHY NOT DEDUPE EVERY LOOK-UP PER USER+SYMBOL+DAY. That would also stop a
# person's own reload from counting, which changes what the published
# allowance means ("12 detailed look-ups a day"). That is a pricing decision,
# not a bug fix; this only takes the page's background refresh off the meter.

_RECEIPT_PURPOSE = "ticker-lookup-refetch"


def _receipt_signature(user_id: str, symbol: str, day: date) -> str:
    from app.services.session import _session_secret

    msg = f"{_RECEIPT_PURPOSE}|{user_id}|{symbol.upper()}|{day.isoformat()}".encode()
    return hmac.new(_session_secret().encode(), msg, hashlib.sha256).hexdigest()


def lookup_receipt(user_id: str, symbol: str, day: date | None = None) -> str | None:
    """Proof that `user_id` was served `symbol` on `day` (default: today, UTC).

    Returned with every allowed GET /api/ticker/{symbol} for a signed-in user;
    the page echoes it on its stream refetches. Format "YYYY-MM-DD.<hex>".
    None if the signing secret is unavailable: the page then does not
    auto-refresh for a metered user, which is the safe direction.
    """
    day = day or _utc_today()
    try:
        return f"{day.isoformat()}.{_receipt_signature(user_id, symbol, day)}"
    except Exception:
        logger.exception("usage.receipt_secret_unavailable")
        return None


def verify_lookup_receipt(receipt: str | None, user_id: str, symbol: str) -> bool:
    """True only for a receipt minted TODAY (UTC) for this user and symbol.

    Never raises: any malformed input, or a missing signing secret, is False,
    and the caller then refuses the refetch (it does not fall back to metering
    it, because a background request must never spend a look-up).
    """
    if not receipt or not isinstance(receipt, str):
        return False
    day_part, sep, sig = receipt.partition(".")
    if not sep or not sig:
        return False
    today = _utc_today()
    if day_part != today.isoformat():
        return False
    try:
        expected = _receipt_signature(user_id, symbol, today)
    except Exception:
        logger.exception("usage.receipt_secret_unavailable")
        return False
    return hmac.compare_digest(sig, expected)


def is_metered(user: User) -> bool:
    """True when GET /api/ticker/{symbol} counts against this user's day."""
    if _is_unmetered(user):
        return False
    return limit(user.tier, "daily_lookups") is not None


async def peek_ticker_lookup(session: AsyncSession, user: User) -> dict:
    """The meter as consume_ticker_lookup would report it, WITHOUT consuming.

    Same dict shape (allowed is always True: nothing is being charged). Used for
    a stream refetch, so the page's "Look-up N of 12 today" stays truthful.
    """
    cap = limit(user.tier, "daily_lookups")
    if _is_unmetered(user) or cap is None:
        return {"allowed": True, "used": 0, "limit": None, "remaining": None}
    row = (
        await session.execute(
            select(User.lookups_today, User.lookups_reset_on).where(User.id == user.id)
        )
    ).one()
    used = (row.lookups_today or 0) if row.lookups_reset_on == _utc_today() else 0
    return {"allowed": True, "used": used, "limit": cap, "remaining": max(0, cap - used)}


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
    used = 0 if entry is None or entry[0] != today else entry[1]

    if used >= cap:
        # Keep the (today, used) entry as-is — don't advance past the cap.
        _anon_lookups[key] = (today, used)
        return {"allowed": False, "used": used, "limit": cap}

    used += 1
    _anon_lookups[key] = (today, used)
    return {"allowed": True, "used": used, "limit": cap}
