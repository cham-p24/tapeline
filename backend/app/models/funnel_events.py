"""funnel_events — the activation funnel, and the counterfactual wall verdict.

WHY THIS EXISTS, and why it is not an A/B test.

The card wall was removed on 2026-08-30 (#683). The obvious way to know whether
that was right is to split traffic and compare. It is not available here:
Tapeline takes two to three signups a month, and detecting even a 5% versus 10%
difference needs roughly 430 people per arm. A split would take decades to
resolve and would halve the only signal there is in the meantime.

SHADOW LOGGING is available, and answers a narrower question honestly. Every
user gets the new experience. Alongside it we record what the OLD wall WOULD
have done — `would_have_been_walled`, computed from the same
`services.tier.must_add_card` the wall used and the same route list it applied.
Nobody is experimented on, no traffic is split, and the result is a direct
count of product interactions the wall would have prevented.

That does not prove the removal raised revenue. Nothing available at this
volume can. It answers the question that IS answerable: how much product use
existed on the other side of that wall.

THE GAP THIS ALSO CLOSES. Until now nothing recorded that a user ran a scan.
`users.lookups_today` counts ticker pages; `cap_events` only fires when someone
is REFUSED. A free user who ran five scans and never hit a limit left no trace
at all — and under the current design running a scan is the primary activation
event. It was invisible.

APPEND-ONLY, and deliberately coarse: one row per user per event per UTC day,
enforced by a unique index. The question is "did this person do this, and when
did they start", not "how many times". Per-request rows would be a hot-path
write and a much larger table for a worse answer.
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

#: The events worth recording. Kept small and closed for the same reason
#: CAP_NAMES is: an unknown value is dropped rather than written, so a typo
#: cannot quietly poison the dataset — and unlike CAP_NAMES, which silently
#: discarded three real events for months, this list is checked by a test
#: against the call sites.
FUNNEL_EVENTS: frozenset[str] = frozenset(
    {
        # Ran a scan on /app/scanner. THE activation event under the current
        # design, and the one that had no record of any kind before this table.
        "scan_run",
        # Opened a ticker detail page.
        "ticker_view",
        # Saved a screen (the object the card ask is about).
        "screen_saved",
        # Added a symbol to a watchlist.
        "watchlist_add",
    }
)


class FunnelEvent(Base):
    """One (user, event, day) — that this happened, and what the wall would have done."""

    __tablename__ = "funnel_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    #: Deduplication key. One row per user per event per UTC day.
    day: Mapped[date] = mapped_column(Date, nullable=False)
    user_id: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    #: One of FUNNEL_EVENTS.
    event: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    #: Tier at the time. A paid user's activity is not a free→paid signal.
    tier: Mapped[str] = mapped_column(String(20), nullable=False)

    #: THE COUNTERFACTUAL. Would the pre-2026-08-30 card wall have blocked this
    #: user from this action? True means the wall would have stopped it, so the
    #: row is one unit of product use that the wall was costing.
    #:
    #: Computed from services.tier.must_add_card, the same predicate the wall
    #: used. It stays meaningful after the wall is gone precisely because that
    #: predicate is still computed for other purposes (upgrade prompts, the
    #: /app/start trial page, the drip emails).
    would_have_been_walled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    __table_args__ = (
        # One row per user/event/day. The writer relies on this rather than a
        # SELECT-then-INSERT, so two concurrent requests cannot double-write.
        Index(
            "ux_funnel_events_user_event_day",
            "user_id",
            "event",
            "day",
            unique=True,
        ),
        # The reporting query is "events of this kind over this window".
        Index("ix_funnel_events_event_day", "event", "day"),
    )
