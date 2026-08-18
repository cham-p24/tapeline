"""Free watchlist cap — RESTORED 2026-08-19 (the 2026-08-02 Pro+ cutover was reversed).

The saved watchlist is a FREE-tier feature again: free_watchlist_cap() returns
FREE_WATCHLIST_TICKERS on every date (the date gate is no longer consulted), and
limit() delegates to it. The reversal un-orphaned the free web-push alert on-ramp
(ArmAlerts seeds from the watchlist) and stopped tightening the free tier while
arrivals + activation — not gating a feature with no paying cohort to protect —
are the priority.
"""
from datetime import date

from app.services.tier import (
    FREE_WATCHLIST_TICKERS,
    Tier,
    free_has_watchlist,
    free_watchlist_cap,
    limit,
)


def test_free_watchlist_cap_is_restored_on_every_date():
    # No longer date-gated: the cap is the same before, on, and long after the
    # old cutover date.
    assert free_watchlist_cap(date(2026, 8, 1)) == FREE_WATCHLIST_TICKERS
    assert free_watchlist_cap(date(2026, 8, 2)) == FREE_WATCHLIST_TICKERS
    assert free_watchlist_cap(date(2027, 1, 1)) == FREE_WATCHLIST_TICKERS
    assert free_watchlist_cap() == FREE_WATCHLIST_TICKERS
    assert FREE_WATCHLIST_TICKERS == 5


def test_free_still_has_a_watchlist():
    assert free_has_watchlist() is True
    assert free_has_watchlist(date(2026, 8, 2)) is True


def test_limit_delegates_to_the_free_cap():
    # FREE/watchlist_tickers must still read free_watchlist_cap() (single source
    # of truth), which now returns the restored non-zero cap.
    assert limit(Tier.FREE, "watchlist_tickers") == free_watchlist_cap()
    assert limit(Tier.FREE, "watchlist_tickers") == FREE_WATCHLIST_TICKERS


def test_paid_tiers_are_unaffected():
    assert limit(Tier.PRO, "watchlist_tickers") == 50
    assert limit(Tier.PREMIUM, "watchlist_tickers") == 200
