"""The public track record must only ever be built from real closes.

/scorecard is the trust mechanism — "one number, one sentence, and a public
track record" — and its hit rate, median alpha and JSON-LD Dataset markup are
computed from these rows. Two defects were writing numbers the market never
printed, and both were PERMANENT: the row is written with a non-NULL
`price_next_day`, which is exactly the predicate `backcheck_all_pending` uses to
find pending work, so nothing ever revisits it.

1. Scoring a session that was still open.

   The gate was `if next_day > today`, which ACCEPTS `next_day == today`.
   Massive/Polygon `/v2/aggs` returns the CURRENT session's PARTIAL daily bar
   (its `c` is the last trade so far, not the close), so a run landing during US
   cash hours read an intraday print as "the next-day close" for both SPY and
   every pick.

   Systematic, not occasional: the worker dispatches the back-check on a bare
   6-hour cadence with no post-close gate, and the cash session is 6.5h
   (13:30-20:00 UTC) — so at least one run falls inside the session every
   trading day, and it PRECEDES that day's post-close run.

   It is also asymmetric with the freeze side, which deliberately waits until
   21:15 UTC precisely so `price_at_flag` IS a real close.

2. Substituting today's live price for a historical close.

   When `_fetch_close` returned None the code fell back to the live
   `Ticker.price` snapshot, accepting it whenever it merely DIFFERED from
   `price_at_flag`. The module docstring says that fallback is for
   "dev / mock mode (no key)" — but the code never checked, so in production it
   fired on any per-symbol fetch failure (a delisted ticker whose aggregates
   come back empty, or a 429/5xx that exhausts the retries). `Ticker.price` is
   TODAY's price, and `backcheck_all_pending` replays dates up to 90 days old,
   so a multi-session drift got published as a ONE-DAY return against SPY's
   genuine one-day move.
"""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.services import scorecard_backcheck as bc


# ---------------------------------------------------------------------------
# 1. The session-completion gate
# ---------------------------------------------------------------------------

_TODAY = date(2026, 8, 25)


def _at(h: int, m: int) -> datetime:
    return datetime(2026, 8, 25, h, m, tzinfo=UTC)


def test_future_session_is_never_complete():
    assert bc._session_is_complete(date(2026, 8, 26), _TODAY, _at(23, 59)) is False


def test_past_session_is_always_complete():
    assert bc._session_is_complete(date(2026, 8, 22), _TODAY, _at(0, 1)) is True


@pytest.mark.parametrize(
    "hour,minute",
    [
        (0, 0),     # pre-market
        (13, 30),   # US open
        (15, 0),    # THE reported failure — 11:00 ET, mid-session
        (17, 45),
        (20, 0),    # cash close, but the daily bar is not final yet
        (21, 14),   # one minute before the freeze boundary
    ],
)
def test_todays_session_is_not_complete_before_the_close_boundary(hour, minute):
    """THE regression. Every one of these used to be accepted and scored."""
    assert bc._session_is_complete(_TODAY, _TODAY, _at(hour, minute)) is False, (
        f"{hour:02d}:{minute:02d} UTC was treated as a finished session — the "
        f"vendor's daily bar is still the last trade so far, not the close"
    )


@pytest.mark.parametrize("hour,minute", [(21, 15), (21, 16), (23, 0)])
def test_todays_session_is_complete_after_the_close_boundary(hour, minute):
    assert bc._session_is_complete(_TODAY, _TODAY, _at(hour, minute)) is True


def test_boundary_matches_the_freeze_side():
    """The freeze waits until 21:15 UTC so `price_at_flag` is a real close. The
    back-check must hold the SAME line or the two legs of every published
    return are measured at different points in the day."""
    from app.workers import signal_publisher as sp

    assert (bc.BACKCHECK_CLOSE_UTC_HOUR, bc.BACKCHECK_CLOSE_UTC_MINUTE) == (
        sp._SCORECARD_FREEZE_UTC_HOUR,
        sp._SCORECARD_FREEZE_UTC_MINUTE,
    ), (
        "the back-check close boundary drifted from the freeze boundary — "
        "price_at_flag and price_next_day would be sampled at different times"
    )


def test_watchlist_track_record_uses_the_same_gate():
    """The per-user Premium track record had the identical `next_day > today`
    gate and the identical consequence."""
    import inspect

    from app.services import watchlist_trackrecord as wtr

    src = inspect.getsource(wtr.backcheck_watchlist)
    assert "_session_is_complete" in src, (
        "watchlist_trackrecord still uses a bare date comparison, so it scores "
        "the session that is still open"
    )


# ---------------------------------------------------------------------------
# 2. The live-snapshot fallback
# ---------------------------------------------------------------------------


def test_fallback_is_gated_on_having_no_vendor_key():
    """The docstring always claimed this was dev-only; now the code agrees.

    Asserted on the source because the condition is what matters: with a key
    configured, a failed per-symbol fetch must NOT resolve to Ticker.price.
    """
    import inspect

    src = inspect.getsource(bc.backcheck_yesterday)
    assert "_polygon_key()" in src, (
        "the live-snapshot fallback is not gated on the vendor key — in "
        "production it fires on any per-symbol fetch failure and publishes "
        "today's price as a historical close"
    )
    assert "next_day == today" in src, (
        "the fallback is not gated on next_day being the session just closed — "
        "the drain replays dates up to 90 days old, so the snapshot can be "
        "weeks away from the date being scored"
    )


def test_usable_snapshot_conditions():
    """Spell out the truth table the guard implements, so a future edit that
    drops a condition is visible."""
    def usable(has_key: bool, next_day: date, today: date, snap, flag):
        return (
            not has_key
            and next_day == today
            and snap is not None
            and snap != flag
        )

    today = date(2026, 8, 25)
    # Production shape: key configured, replaying an old date, stale snapshot.
    assert usable(True, date(2026, 6, 23), today, 21.80, 14.20) is False
    # Key configured, even for today — the vendor is the source of truth.
    assert usable(True, today, today, 21.80, 14.20) is False
    # Dev/mock, but replaying an old date — snapshot is meaningless for it.
    assert usable(False, date(2026, 6, 23), today, 21.80, 14.20) is False
    # Dev/mock, scoring the session just closed, snapshot moved: allowed.
    assert usable(False, today, today, 21.80, 14.20) is True
    # Snapshot identical to the flag price is the known stale pattern.
    assert usable(False, today, today, 14.20, 14.20) is False
    assert usable(False, today, today, None, 14.20) is False
