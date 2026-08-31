"""record_funnel_event — append-only activation logging with the wall counterfactual.

Same two hard guarantees as services/cap_events.record_cap_hit, for the same
reason: this runs on the hot path of ordinary successful requests, and a
logging hiccup must never turn a working page into a 500.

  1. IT NEVER BREAKS THE REQUEST. Every failure — unknown event name, write
     error, a session already in trouble, a duplicate — is swallowed and logged.
  2. IT NEVER DOUBLE-WRITES. One row per user per event per UTC day, enforced
     by a unique index rather than by SELECT-then-INSERT, so two concurrent
     requests race into the constraint instead of into two rows.

Unlike cap_events this records PAID tiers too. A cap hit is a free→paid signal
and a paid ceiling would pollute it; activation is not — knowing whether
subscribers actually run scans is exactly as useful as knowing whether free
users do, and more so if one day nobody renews.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.models.funnel_events import FUNNEL_EVENTS, FunnelEvent

logger = logging.getLogger(__name__)


async def record_funnel_event(user, event: str) -> None:
    """Record that `user` did `event` today. Fire-and-forget: never raises.

    OPENS ITS OWN SESSION, and does not take the caller's.

    That is the difference between this and services/cap_events.record_cap_hit,
    and it is not stylistic. record_cap_hit runs on a REFUSAL branch whose
    caller is about to raise a 402/403, so committing and rolling back inside
    the request's session is harmless — nothing uses it afterwards.

    This runs on the SUCCESS path of an ordinary request. The daily-dedup
    unique index means the second scan of the day RAISES IntegrityError by
    design, and rolling that back inside the caller's session left it poisoned:
    the scanner endpoint then died with PendingRollbackError on its very next
    statement. A second scan is the normal case, so this would have broken the
    scanner for anyone who used it twice.

    Its own short-lived session makes the logging genuinely independent of the
    request: the duplicate is swallowed, the caller's transaction is untouched,
    and no failure here can reach the user.

    `user` is the ORM User (not an id) because the counterfactual needs the
    whole row: `must_add_card` reads the tier, the creation date, the card on
    file and the trial history.
    """
    try:
        if event not in FUNNEL_EVENTS:
            logger.warning("funnel.unknown_event event=%s", event)
            return

        # THE COUNTERFACTUAL. must_add_card is the exact predicate the removed
        # wall used, and it is still computed for the upgrade prompts and the
        # trial page — so this stays a faithful "would the wall have stopped
        # this" long after the wall itself is gone.
        from app.services.tier import must_add_card

        try:
            walled = bool(must_add_card(user))
        except Exception:
            logger.exception("funnel.counterfactual_failed user=%s", user.id)
            walled = False

        from app.db import session_scope

        async with session_scope() as own:
            own.add(
                FunnelEvent(
                    user_id=user.id,
                    event=event,
                    tier=str(user.tier),
                    day=datetime.now(UTC).date(),
                    would_have_been_walled=walled,
                )
            )
            await own.commit()
    except Exception:
        # The overwhelmingly common case is the unique index rejecting the
        # second event of the same kind on the same day, which is the dedup
        # working rather than a fault. Debug level so a genuine write failure
        # is still visible above the noise. Nothing to roll back here — the
        # session that failed was this function's own and is already closing.
        logger.debug(
            "funnel.write_skipped event=%s user=%s", event, getattr(user, "id", "?")
        )
