"""Free-tier cap-hit event — one append-only row each time a FREE user is
refused MORE of a metered resource at a server-side enforcement point.

WHY THIS TABLE EXISTS
---------------------
The free→paid decision (should we tighten a cap, and which one?) has been a
gut call because there was no durable record of WHERE free users actually hit
a wall. `grep cap_hit` used to return only a research doc — zero implementation.
This table is that implementation: the ground truth for the micro-funnel

    cap_hit → upgrade_prompt_shown → upgrade_prompt_clicked → begin_checkout

Each row is written fire-and-forget by `services/cap_events.record_cap_hit`
at the exact 403 / 402 / limit branch that tells a free user "no more":

  - scanner_rows     — routers/scanner.py     (free row cap filled the page)
  - daily_lookups    — routers/ticker.py      (402 free_lookup_limit)
  - watchlist_tickers— routers/watchlist.py   (403 watchlist full)
  - web_push_alerts  — routers/alerts.py      (403 free web-push allowance used)
  - squeeze_preview  — routers/squeeze.py     (free preview shows N of many)

DESIGN
------
Append-only, never updated or deleted in the request path — a pure event log
that low-N aggregate queries roll up off-line. `tier` is denormalised at
write time (always "free" today; the helper refuses to log paid tiers) so an
analyst never has to join back to a mutable users row whose tier may have
changed since. No FK to users: this is an audit/analytics trail and must
survive a user-row deletion the same way inbox_classification_log does.

NO cap VALUES change with this table — it is pure instrumentation. It also
does NOT drive any user-facing "X of Y left" nag; the pre-cap look-up meter
already covers that. This only records.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# The five metered free-tier caps, matching the tier.TIER_LIMITS keys plus the
# squeeze "taste". Kept here as the single source of truth the helper validates
# against so a typo at a call site can never silently poison the dataset.
CAP_NAMES: frozenset[str] = frozenset(
    {
        "scanner_rows",
        "daily_lookups",
        "watchlist_tickers",
        "web_push_alerts",
        "squeeze_preview",
    }
)


class CapEvent(Base):
    __tablename__ = "cap_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    # No FK — this is an append-only analytics trail that must outlive a
    # deleted user (same posture as inbox_classification_log.inbound_message_id).
    # Indexed so per-user funnel roll-ups stay cheap.
    user_id: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    # One of CAP_NAMES. Indexed because the primary query is "hits per cap".
    cap: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Denormalised tier at hit-time. Always "free" today (record_cap_hit refuses
    # paid tiers), but stored so a future policy change is self-describing.
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
