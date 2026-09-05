"""scan_logs — what a scan was asked for, and what it actually returned.

WHY THIS EXISTS. On 2026-09-05 the question "why did this trial user cancel
five minutes after running a scan?" turned out to be permanently unanswerable.
Two of three cancellations in the first paying cohort happened within five
minutes of a `scan_run`, and nothing anywhere recorded what that scan was for
or what came back. The investigation died there.

`funnel_events` cannot answer it and was never meant to. That table is
deliberately coarse — one row per (user, event, UTC day), enforced by a unique
index — so a user who runs ten scans produces exactly ONE row. Hanging filter
parameters off it would capture the first scan of each day and silently discard
the other nine, which is worse than not measuring: it reads like full coverage.
Worse still for this incident specifically, a cancellation follows a person's
LAST scan, and the row that survived would systematically be their first.
So this is a separate, genuinely per-execution table. `funnel_events` keeps
answering "did they activate, and when"; this answers "what did they see".

THE ABSENCE OF A UNIQUE INDEX IS THE DESIGN. Every scan gets a row. Any dedup
key — per hour, per filter-hash, per N seconds — keeps the FIRST write of its
window and drops the rest, which reintroduces exactly the defect above at finer
granularity.

`src` IS WHAT MAKES A ROW MEAN SOMETHING. The scanner page does not fetch only
when a human asks. `frontend/app/app/scanner/page.tsx` memoises `load` on the
filter state and calls it from BOTH `useEffect(() => { load(); }, [load])` and
`useLiveStream(load)` — and `lib/useLiveStream.ts` invokes that callback on
every SSE "update" the backend publishes. An idle open tab therefore refetches
on a timer, and because only `search` is debounced (min/max score are raw
state), typing "70" into a score box fires two more. Without a discriminator,
most rows would be machine traffic and "the last scan before they cancelled"
would most likely be a background refresh of a tab nobody was reading — a
confidently wrong answer, which is the failure this table exists to prevent.
The incident query is `WHERE src = 'app'`.

DENORMALISED ON PURPOSE. `top_symbols_json` stores each returned symbol
alongside the score, price and volume IT HAD AT SCAN TIME. Joining back to
`tickers` later would be a lie: those rows are rewritten on every 60-second
worker tick, so a symbol that scored 90.3 when the user saw it may score 44
tomorrow, and the reconstruction would silently describe a screen nobody ever
saw. The whole point of this table is fidelity to a moment, and a foreign key
to mutable data cannot provide that.

TEXT, NOT JSON COLUMN, AND NOT TYPED FILTER COLUMNS. Both blobs are `Text`
holding JSON, matching `scanner_presets.filters_json`, so SQLite (tests) and
Postgres (prod) use the identical column type. Typed per-filter columns were
considered and rejected: `scanner.py` declares `signal` and `sector` as bare
unbounded strings, so a String(30)/String(80) column would raise
StringDataRightTruncation on Postgres while SQLite silently accepted it — rows
vanishing in prod with CI green. Inside a length-capped Text blob they are
harmless. Nothing queries these blobs by structure; they are read whole, by a
human, when a question is being asked.

KNOWN GAP: `top_symbols_json` is a SUPERSET of what was on screen. The scanner
page filters by asset class CLIENT-SIDE on already-fetched rows, so a user who
selected "ETFs & funds" saw a subset of what is logged here. Moving that filter
server-side is the honest fix and is a separate change.

GROWTH. This table grows per REQUEST, so the bound is worth stating rather than
assuming. Only SIGNED-IN scans are recorded (see services/scan_log.py), which
keeps anonymous and SEO traffic out entirely. At the traffic that prompted this
— five users — that is on the order of 10k rows a year even counting stream
refetches. `created_at` is indexed so a delete-older-than prune stays cheap if
that stops being true. No prune is scheduled today, deliberately: unscheduled
machinery is the dead code this codebase keeps having to remove. The trigger to
revisit is pre-committed rather than left to judgment — 250k rows, or growth of
+50k in a single week.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

#: How many of the returned rows to preserve per scan. The top of the list is
#: what a user actually reads before deciding the product is or is not for
#: them; row 40 is not why anyone cancels. Ten keeps a row comfortably under
#: 1KB while covering everything visible without scrolling.
SCAN_LOG_TOP_N = 10

#: Closed set, same posture as FUNNEL_EVENTS and CAP_NAMES — an unrecognised
#: value is normalised to "unknown" rather than written through, so a typo in
#: a caller cannot quietly split the dataset into two silently-different
#: populations.
#:
#:   app     a human on /app/scanner changed filters or loaded the page
#:   stream  an automatic refetch driven by an SSE tick — NOT a user action
#:   preset  a saved screen was applied
#:   api     a programmatic caller (API key / MCP)
SCAN_SOURCES: frozenset[str] = frozenset({"app", "stream", "preset", "api"})
SCAN_SOURCE_UNKNOWN = "unknown"


class ScanLog(Base):
    """One row per executed scan by a signed-in user."""

    __tablename__ = "scan_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    #: Python-side UTC default, NOT server_default=func.now(). On SQLite the
    #: server default is CURRENT_TIMESTAMP, which is naive and whole-second:
    #: naive breaks every tz-aware comparison in tests, and whole-second cannot
    #: order two scans in the same second — and "their LAST scan before
    #: cancelling" is an ordering question. funnel_events does the same.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
    )

    #: No ForeignKey, matching cap_events and funnel_events: instrumentation
    #: must never be able to block a user row from being deleted. Unlike those
    #: two, this table IS cleared by services/account_purge — it carries the
    #: user's own typed search text, which an erasure request plainly covers.
    user_id: Mapped[str] = mapped_column(String(60), nullable=False)

    #: Tier at scan time, denormalised. `users.tier` moves (trial converts,
    #: subscription lapses), and "what could this person see THEN" is the
    #: question — a later tier cannot answer it.
    tier: Mapped[str] = mapped_column(String(20), nullable=False)

    #: One of SCAN_SOURCES, or "unknown". See the module docstring — this is
    #: what separates a human scan from a background SSE refetch.
    src: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=SCAN_SOURCE_UNKNOWN,
    )

    #: Every filter the query ACTUALLY ran with, JSON-encoded, plus the
    #: requested limit/offset alongside the applied ones — the endpoint clamps
    #: both before this is written, so the applied values alone cannot tell
    #: "asked for 200, allowed 10" apart from "asked for 10". Defaults the
    #: caller never mentioned are recorded explicitly: SCANNER_MIN_DOLLAR_VOLUME
    #: moved from 50k to 1M on 2026-08-30, so an omitted key would mean
    #: different things in a June row and a September one.
    filters_json: Mapped[str] = mapped_column(Text, nullable=False)

    #: Rows actually returned on this page — what the user saw. A real 0 is the
    #: leading hypothesis for a five-minute cancellation and must never be an
    #: absent row.
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)

    #: Size of the full matching universe behind the row cap. NULL for the
    #: paginating tiers, which are never capped and for which the endpoint does
    #: not run the COUNT — storing 0 there would invent a fact.
    total_matched: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: The row cap the tier imposed, so a short result set can be read as
    #: "the screen was empty" or "they were capped" without guessing.
    row_cap: Mapped[int] = mapped_column(Integer, nullable=False)

    #: The top SCAN_LOG_TOP_N returned rows as JSON:
    #: [{"symbol","score","price","volume"}, ...] — values AS AT SCAN TIME.
    top_symbols_json: Mapped[str] = mapped_column(Text, nullable=False)

    #: Wall time of the handler body, milliseconds. Measures OUR query, not the
    #: user's perceived latency (no network, no render), so read it as "was the
    #: backend slow" and nothing more. Nullable because a caller may not time.
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        # The query this table exists for is "this user's scans, newest first",
        # and every incident read is scoped to one user. A composite beats a
        # bare user_id index because it removes the sort.
        Index("ix_scan_logs_user_created", "user_id", "created_at"),
        # Kept separately so a delete-older-than prune is a range scan.
        Index("ix_scan_logs_created_at", "created_at"),
    )
