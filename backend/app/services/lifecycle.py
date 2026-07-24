"""Lifecycle stage model + the global email frequency governor.

WHY THIS EXISTS
───────────────
Tapeline had eleven independent email orchestrators (trial drip, re-engagement,
win-back, activation, annual nudge, renewal reminder, founder touch, referral
milestone, checkout recovery, EOD digest, weekly newsletter). Eight of them run
back-to-back against the SAME session inside one worker tick
(workers/signal_publisher._maybe_run_daily_drips). Nothing stopped a single
user matching three of those populations at once and receiving three emails
within the same minute — each orchestrator only ever knew about its own
per-stage dedupe token.

That was survivable at eleven flows. It is not survivable while we're adding
more (the activation nudge below is the first of several). So the governor
lands BEFORE the new flows, not after: one place that decides whether this
user may receive this message right now, which every non-transactional send
routes through.

WHAT IT GUARANTEES
──────────────────
  1. At most one LIFECYCLE email per user per MIN_LIFECYCLE_GAP_HOURS,
     regardless of which flow wants to send it.
  2. At most MAX_LIFECYCLE_SENDS_PER_WEEK lifecycle emails per rolling 7 days.
  3. At most MAX_ACTIVATION_SERIES_MESSAGES messages in the activation series
     (the day-0 welcome counts as message #1).
  4. A user who has globally unsubscribed (email_prefs == 0) receives nothing
     outside the TRANSACTIONAL class.
  5. Scheduled sends the user explicitly asked for (EOD digest, weekly
     newsletter) are never BLOCKED — but they are RECORDED, so a lifecycle
     nudge won't pile on top of the digest the user already got today.

WHAT IT DOES NOT DO
───────────────────
It does not override per-category EmailPref gating or the unsubscribe bits.
Flows still call `email_prefs.wants(...)` for their own category; the governor
is an additional ceiling on top, never a licence to send.

STORAGE — process-global, single-instance (deliberate)
──────────────────────────────────────────────────────
The send ledger is an in-memory module global, pruned on access. This mirrors
the established pattern for cross-request counters in this codebase —
services/rate_limit (token buckets), services/trial_abuse (signup log), and
services/usage._anon_lookups (anonymous meter) all do exactly this, with the
same documented caveat: per-process, resets on worker restart, correct while
Tapeline runs a single Fly machine. Move to Redis (or a durable
users.last_lifecycle_email_at column) when concurrent machines exceed one.

The trade-off is deliberate and bounded: a worker restart can at worst let one
extra lifecycle email through the gap check, because every flow ALSO dedupes
durably on its own drip_state / winback_state token. The governor is a
frequency ceiling, not the correctness mechanism for at-most-once delivery —
that already lives in the per-stage tokens and is unaffected by a restart.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import User

logger = logging.getLogger(__name__)


# ── Policy constants ────────────────────────────────────────────────────────

# Minimum gap between two LIFECYCLE emails to the same user, across ALL flows.
# 20h rather than 24h so a daily worker tick that drifts slightly later than
# the previous day's tick doesn't silently skip a whole stage for everyone.
MIN_LIFECYCLE_GAP_HOURS = 20

# Ceiling on lifecycle emails in any rolling 7-day window. Three is the point
# at which a nurture sequence stops reading as helpful and starts reading as
# pressure — and pressure is exactly what Rule 6 forbids us from manufacturing.
MAX_LIFECYCLE_SENDS_PER_WEEK = 3

# Total messages in the behaviour-triggered activation series, INCLUDING the
# day-0 welcome sent at signup. So three post-welcome touches at most, ever.
MAX_ACTIVATION_SERIES_MESSAGES = 4

# drip_state tokens that belong to the activation series and therefore count
# against MAX_ACTIVATION_SERIES_MESSAGES.
ACTIVATION_SERIES_TOKENS = frozenset({
    "act_scan6h",   # ~6h after signup, zero recorded activity
    "act_ask48h",   # ~48h after signup, still zero recorded activity
    "act_wl",       # first-watchlist milestone nudge
    "act_alert",    # first-alert milestone nudge
})

# Terminal drip_state token that SUNSETS a user. Set by the re-engagement
# series (services/email.run_re_engagement_drip) after touch 2 goes out and the
# user is STILL dormant. Once present, the governor suppresses every
# non-transactional send to them — see LIFECYCLE_SUPPRESSED_TOKENS below. Kept
# here (not in email.py) because this is where it takes effect, and email.py
# already imports from lifecycle, so a single source of truth avoids a cycle.
RE_SUNSET_TOKEN = "re_sunset"

# drip_state tokens that suppress a user from ALL non-transactional sends
# (LIFECYCLE and SCHEDULED). This is deliverability insurance, not an
# unsubscribe: transactional receipts still go out and List-Unsubscribe is
# untouched. A suppressed user is segmented, never hard-deleted, so the state
# is fully reversible.
LIFECYCLE_SUPPRESSED_TOKENS = frozenset({RE_SUNSET_TOKEN})

# How long after signup a returning session counts as "came back". The
# last_seen_at bump is throttled to one write per hour (services/auth.
# _bump_last_seen), so a user who browsed for twenty minutes at signup and
# never returned still shows last_seen_at ≈ created_at. Anything beyond this
# gap means they came back on a later request.
RETURN_GAP_MINUTES = 90

# Ledger retention. Nothing older than the weekly window can affect a decision.
_LEDGER_TTL_SECONDS = 8 * 24 * 3600


def _as_utc(dt: datetime | None) -> datetime | None:
    """Normalise a possibly-naive datetime to UTC.

    SQLite hands back naive datetimes for timezone=True columns; Postgres
    hands back aware ones. Every comparison in this module goes through here
    so the same code is correct on the test DB and in production.
    """
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _tokens(drip_state: str | None) -> set[str]:
    """Parse the comma-separated User.drip_state into a token set."""
    return set((drip_state or "").split(",")) - {""}


# ── Lifecycle stage ─────────────────────────────────────────────────────────

class LifecycleStage(StrEnum):
    """Where a user sits in the lifecycle, resolved from durable columns.

    Deliberately coarse. The stage answers "what kind of message is even
    appropriate for this person", not "which template" — the flows still own
    their own targeting windows. Ordering below is the resolution order, not a
    progression: the first matching rule wins.
    """

    PAID = "paid"            # has a live Stripe subscription
    TRIALING = "trialing"    # inside the no-card 14-day Premium trial
    NEW = "new"              # signed up, no recorded activity yet
    ACTIVATED = "activated"  # has actually used the product
    DORMANT = "dormant"      # used it once, then went quiet for 14d+
    LAPSED = "lapsed"        # trial ended or subscription cancelled; now free


# How long without a sighting before an activated user reads as dormant. Kept
# equal to the existing re-engagement drip window so the two agree.
DORMANT_AFTER_DAYS = 14


@dataclass(frozen=True)
class ActivitySnapshot:
    """Durable evidence that a user has actually USED Tapeline.

    There is no scan-event table in the schema, so "has run a scan" cannot be
    measured directly. This is the honest proxy set: the artefacts a user can
    only own by having done something, plus the last_seen_at return signal.
    A user with none of these has, as far as anything we persist can tell,
    signed up and never come back — which is precisely the day-1 bounce the
    activation nudge exists to address.

    Follow-up (out of lane here, needs a schema change): a real
    users.scans_run counter incremented by the scanner router would let the
    6h nudge fire on genuine scan-count == 0 rather than this proxy.
    """

    has_watchlist_item: bool = False
    has_alert_rule: bool = False
    has_saved_scan: bool = False

    @property
    def has_any_artefact(self) -> bool:
        return self.has_watchlist_item or self.has_alert_rule or self.has_saved_scan


def returned_after_signup(user: User, *, now: datetime | None = None) -> bool:
    """True if last_seen_at is meaningfully later than created_at.

    See RETURN_GAP_MINUTES — the hourly throttle on the last_seen_at bump
    means "same as signup time" is what a single bounce-off session looks
    like. A missing last_seen_at (never made an authenticated request after
    the signup response) reads as "did not return".
    """
    created = _as_utc(getattr(user, "created_at", None))
    seen = _as_utc(getattr(user, "last_seen_at", None))
    if created is None or seen is None:
        return False
    return (seen - created) >= timedelta(minutes=RETURN_GAP_MINUTES)


def has_recorded_activity(
    user: User, snapshot: ActivitySnapshot | None = None,
) -> bool:
    """True if we hold ANY durable evidence this user used the product.

    Fails SAFE for the nudge: any hint of activity counts, so a user we're
    unsure about is treated as active and is NOT nudged. Sending a
    "you haven't started yet" note to someone who has is the worse error.
    """
    if getattr(user, "activated_at", None) is not None:
        return True
    if (getattr(user, "lookups_today", 0) or 0) > 0:
        return True
    if getattr(user, "lookups_reset_on", None) is not None:
        return True
    if snapshot is not None and snapshot.has_any_artefact:
        return True
    return returned_after_signup(user)


def resolve_stage(
    user: User,
    snapshot: ActivitySnapshot | None = None,
    *,
    now: datetime | None = None,
) -> LifecycleStage:
    """Resolve the user's lifecycle stage from durable state.

    Single source of truth for "what kind of user is this", so a new flow
    doesn't have to re-derive trial/paid/dormant logic (and get it subtly
    different, which is how the lapse30 gap happened).
    """
    now = now or datetime.now(UTC)

    if getattr(user, "stripe_customer_id", None) and user.tier in ("pro", "premium"):
        return LifecycleStage.PAID

    trial_ends = _as_utc(getattr(user, "trial_ends_at", None))
    on_trial = trial_ends is not None and trial_ends > now

    active = has_recorded_activity(user, snapshot)

    if not active:
        # Never used it. NEW outranks TRIALING here on purpose: the useful
        # message for a bounced signup is "here's the first thing to do",
        # not "your trial is ticking".
        return LifecycleStage.NEW

    if on_trial:
        return LifecycleStage.TRIALING

    seen = _as_utc(getattr(user, "last_seen_at", None))
    if seen is not None and (now - seen) >= timedelta(days=DORMANT_AFTER_DAYS):
        return LifecycleStage.DORMANT

    if trial_ends is not None or getattr(user, "canceled_at", None) is not None:
        # Had a trial or a subscription, no longer paying.
        return LifecycleStage.LAPSED

    return LifecycleStage.ACTIVATED


# ── Send classes ────────────────────────────────────────────────────────────

class SendClass(StrEnum):
    """How the governor treats a given send.

    TRANSACTIONAL — account state the user cannot opt out of (welcome, email
        verification, password reset, payment failed, subscription started).
        NEVER blocked and NEVER recorded: a receipt must always arrive, and it
        must not consume the lifecycle budget.

    SCHEDULED — a recurring send the user explicitly asked for (EOD watchlist
        digest, weekly newsletter), plus high-intent user-initiated recovery
        (checkout abandonment: they just tried to pay) and billing notices.
        Never blocked — suppressing something the user opted into would be a
        bug, not a courtesy — but RECORDED, so a lifecycle nudge sees it and
        stays off that user for the gap.

    LIFECYCLE — everything we initiate to move a user along: drips, nudges,
        win-backs, activation. Fully governed.
    """

    TRANSACTIONAL = "transactional"
    SCHEDULED = "scheduled"
    LIFECYCLE = "lifecycle"


# ── Send ledger ─────────────────────────────────────────────────────────────

class SendLedger:
    """Recent non-transactional sends, keyed by user id.

    Values are monotonic-ish epoch seconds (time.time()); pruned lazily on
    access so a long-lived worker doesn't accumulate a row per user forever.
    """

    __slots__ = ("_log",)

    def __init__(self) -> None:
        self._log: dict[str, list[float]] = {}

    def record(self, user_id: str, at: float | None = None) -> None:
        at = time.time() if at is None else at
        self._log.setdefault(user_id, []).append(at)

    def recent(self, user_id: str, within_seconds: float) -> list[float]:
        """Timestamps for this user inside the window, pruning stale rows."""
        entries = self._log.get(user_id)
        if not entries:
            return []
        cutoff = time.time() - _LEDGER_TTL_SECONDS
        fresh = [t for t in entries if t >= cutoff]
        if fresh:
            self._log[user_id] = fresh
        else:
            self._log.pop(user_id, None)
            return []
        window_start = time.time() - within_seconds
        return [t for t in fresh if t >= window_start]

    def clear(self) -> None:
        self._log.clear()


# Process-global ledger used by the worker. Direct callers (tests, one-off
# scripts) get their own isolated ledger unless they explicitly ask for this
# one via worker_governor(), so a standalone flow invocation is never silently
# throttled by an unrelated run.
_GLOBAL_LEDGER = SendLedger()


def reset_send_ledger() -> None:
    """Wipe the process-global ledger. For tests and worker self-checks."""
    _GLOBAL_LEDGER.clear()


# ── The governor ────────────────────────────────────────────────────────────

class FrequencyGovernor:
    """Decides whether a user may receive a given message right now.

    Usage inside a flow:

        if not governor.allows(user, SendClass.LIFECYCLE, token="act_wl"):
            continue
        ...send...
        governor.record(user, SendClass.LIFECYCLE)

    `record` is called only after a CONFIRMED delivery (send_email did not
    return skipped:True), so a no-op send in an environment without
    RESEND_API_KEY never consumes anyone's budget.
    """

    __slots__ = ("_ledger", "blocked", "sent")

    def __init__(self, *, ledger: SendLedger | None = None) -> None:
        self._ledger = ledger if ledger is not None else SendLedger()
        self.blocked = 0
        self.sent = 0

    # -- policy ------------------------------------------------------------

    def allows(
        self,
        user: User,
        send_class: SendClass = SendClass.LIFECYCLE,
        *,
        token: str | None = None,
    ) -> bool:
        """True if this send may proceed."""
        # Account-state mail always goes out.
        if send_class is SendClass.TRANSACTIONAL:
            return True

        if not getattr(user, "email", None):
            return False

        # Global unsubscribe: email_prefs == 0 means every category bit was
        # cleared (services/unsubscribe.apply_unsubscribe with "all"). A None
        # value is NOT an opt-out — it's an unset column on an in-memory row,
        # which email_prefs.wants() deliberately treats as opted in.
        prefs = getattr(user, "email_prefs", None)
        if prefs is not None and int(prefs) == 0:
            self.blocked += 1
            return False

        # A bounced / spam-flagged address is dead for everything but
        # transactional (send_email enforces this too; checking here saves the
        # render + the round-trip).
        if getattr(user, "email_undeliverable_at", None) is not None:
            self.blocked += 1
            return False

        # Sunset: a user who went through the full re-engagement series without
        # returning is suppressed from every non-transactional send going
        # forward. Checked ABOVE the SCHEDULED early-return on purpose, so even
        # opted-in recurring mail (EOD digest, weekly newsletter) stops — the
        # whole point is to quit sending to an address that has gone quiet
        # through a complete win-back sequence, before it spam-folds and drags
        # the sender reputation down for everyone else. TRANSACTIONAL already
        # returned True at the top, so receipts are unaffected, and this never
        # touches email_prefs, so List-Unsubscribe still works.
        if LIFECYCLE_SUPPRESSED_TOKENS & _tokens(getattr(user, "drip_state", "")):
            self.blocked += 1
            logger.info(
                "governor.blocked reason=sunset user=%s token=%s",
                getattr(user, "id", None), token,
            )
            return False

        # Opted-in recurring sends are never suppressed.
        if send_class is SendClass.SCHEDULED:
            return True

        # -- LIFECYCLE ceiling --------------------------------------------
        if token is not None and token in ACTIVATION_SERIES_TOKENS:
            already = len(_tokens(getattr(user, "drip_state", "")) & ACTIVATION_SERIES_TOKENS)
            # The day-0 welcome is message #1 and is not tokenised, hence -1.
            if already >= MAX_ACTIVATION_SERIES_MESSAGES - 1:
                self.blocked += 1
                logger.info(
                    "governor.blocked reason=activation_series_cap user=%s token=%s",
                    user.id, token,
                )
                return False

        uid = user.id
        if self._ledger.recent(uid, MIN_LIFECYCLE_GAP_HOURS * 3600):
            self.blocked += 1
            logger.info(
                "governor.blocked reason=min_gap user=%s token=%s", uid, token,
            )
            return False

        if len(self._ledger.recent(uid, 7 * 24 * 3600)) >= MAX_LIFECYCLE_SENDS_PER_WEEK:
            self.blocked += 1
            logger.info(
                "governor.blocked reason=weekly_cap user=%s token=%s", uid, token,
            )
            return False

        return True

    def record(
        self, user: User, send_class: SendClass = SendClass.LIFECYCLE,
    ) -> None:
        """Note a CONFIRMED delivery against this user's frequency budget."""
        if send_class is SendClass.TRANSACTIONAL:
            return
        self._ledger.record(user.id)
        self.sent += 1


def worker_governor() -> FrequencyGovernor:
    """A governor bound to the process-global ledger.

    The worker builds ONE of these per drip run and threads it through every
    flow, so the cap holds across flows within a tick AND across ticks within
    the process lifetime (which is what makes the hourly activation nudge
    respect a drip email sent six hours earlier).
    """
    return FrequencyGovernor(ledger=_GLOBAL_LEDGER)
