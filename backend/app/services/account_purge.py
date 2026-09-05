"""Delete every row a user owns, in FK-safe order.

WHY THIS IS A SHARED SERVICE
----------------------------
Two paths destroy an account:

  * `routers/account.py` — the GDPR Art. 17 erasure endpoint, which listed all
    eleven child tables explicitly and correctly, and
  * `routers/auth.py` `_consume_verification(action="cancel")` — the
    "this wasn't me" link in every verification email, which did a bare
    `await session.delete(user)` with NO child cleanup at all.

Of the 14 FKs into `users`, only `email_verification_tokens`,
`password_reset_tokens` and `mfa_recovery_codes` carry ON DELETE CASCADE.
`watchlists`, `watchlist_items`, `alert_rules`, `alert_events`, `api_keys`,
`roadmap_votes`, `scanner_presets`, `subscriptions`, `web_push_subscriptions`
and `watchlist_track_record` are all `ondelete=None`, and there is no ORM
`relationship()` anywhere in `app/models/` — so SQLAlchemy emits a plain
`DELETE FROM users` and Postgres enforces RESTRICT.

The child rows are GUARANTEED to exist by the time anyone clicks that link:
`routers/me.py:submit_onboarding` fires on BOTH Submit and Skip and calls
`_seed_watchlist_for_new_user`, which creates a `watchlists` row and 2-4
`watchlist_items` in the first minute of every new account — before the user has
even opened the verification email.

So "this wasn't me" raised a ForeignKeyViolation, the whole commit rolled back,
and the account the user just told us was fraudulent stayed alive.

It was invisible in CI because `app/db.py` never issues
`PRAGMA foreign_keys=ON`, so SQLite silently ignores every FK, and the two
existing cancel tests use a bare signup with no watchlist rows.

Keeping the order in ONE place means a table added to one path can't be missed
by the other.
"""
from __future__ import annotations

import logging

from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AlertEvent,
    AlertRule,
    ApiKey,
    NewsletterSubscriber,
    RoadmapVote,
    ScanLog,
    ScannerPreset,
    Subscription,
    User,
    Watchlist,
    WatchlistItem,
    WatchlistTrackRecordEntry,
    WebPushSubscription,
)

logger = logging.getLogger(__name__)


async def purge_user_owned_rows(
    session: AsyncSession, user_id: str, user_email: str | None = None
) -> None:
    """Delete every child row for `user_id`. Does NOT delete the User itself.

    Ordered so each delete runs before anything that references it.

    `user_email` is optional: pass it to also purge the newsletter subscription,
    which is keyed by EMAIL and has no user_id FK — so it is not cascaded from
    `delete(User)` and would otherwise survive an erasure and keep mailing the
    person. Only the erasure path needs that; the cancel path may pass it too.
    """
    await session.execute(delete(AlertEvent).where(AlertEvent.user_id == user_id))
    await session.execute(delete(AlertRule).where(AlertRule.user_id == user_id))
    # WatchlistItem before Watchlist — items FK the parent list (ON DELETE
    # CASCADE), but both also key users.id directly, so delete the child first.
    await session.execute(delete(WatchlistItem).where(WatchlistItem.user_id == user_id))
    await session.execute(delete(Watchlist).where(Watchlist.user_id == user_id))
    await session.execute(delete(ScannerPreset).where(ScannerPreset.user_id == user_id))
    # Scan logs carry the user's OWN typed search text (the `q` filter), so an
    # erasure request plainly covers them. This is a deliberate departure from
    # cap_events and funnel_events, which are left in place as append-only
    # analytics trails that outlive a deleted user: those record only that an
    # anonymous-shaped event happened, never anything the person wrote.
    await session.execute(delete(ScanLog).where(ScanLog.user_id == user_id))
    await session.execute(
        delete(WebPushSubscription).where(WebPushSubscription.user_id == user_id)
    )
    await session.execute(delete(RoadmapVote).where(RoadmapVote.user_id == user_id))
    # watchlist_track_record (migration 0042) has a user_id FK with NO ON DELETE
    # CASCADE and is not cascaded from delete(User). Without this, delete(User)
    # raises a ForeignKeyViolation on Postgres and the whole commit rolls back —
    # the account survives a "delete me". On SQLite it would instead orphan the
    # rows (user data surviving a GDPR erasure).
    await session.execute(
        delete(WatchlistTrackRecordEntry).where(
            WatchlistTrackRecordEntry.user_id == user_id
        )
    )
    await session.execute(delete(Subscription).where(Subscription.user_id == user_id))
    await session.execute(delete(ApiKey).where(ApiKey.user_id == user_id))
    if user_email:
        await session.execute(
            delete(NewsletterSubscriber).where(
                func.lower(NewsletterSubscriber.email) == user_email.lower()
            )
        )


async def purge_user(
    session: AsyncSession, user_id: str, user_email: str | None = None
) -> None:
    """Children then the User row itself. Caller commits."""
    await purge_user_owned_rows(session, user_id, user_email)
    await session.execute(delete(User).where(User.id == user_id))
