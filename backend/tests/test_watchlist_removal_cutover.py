"""Free watchlist → Pro+ cutover — REVERSED 2026-08-19.

The cutover (announced to free users by email 2026-07-26) made the saved
watchlist a Pro-and-up feature: the FREE cap date-gated to 0 on
FREE_WATCHLIST_REMOVAL_DATE (2026-08-02). It was reversed — the 0-cap orphaned
the free web-push alert on-ramp and tightened the free tier while arrivals +
activation are the priority. These tests now pin the RESTORED behaviour: the
free cap is FREE_WATCHLIST_TICKERS regardless of date, `limit()` reads that
single source of truth, and the open-access month still excludes the watchlist.
The removal date is retained as a constant for history but no longer gates.
"""
from datetime import date, timedelta

from app.services.tier import (
    FREE_WATCHLIST_REMOVAL_DATE,
    FREE_WATCHLIST_TICKERS,
    Tier,
    free_has_watchlist,
    free_watchlist_cap,
    limit,
)


def test_removal_date_constant_is_retained_for_history():
    # Kept as documentation of the reversed cutover; it must no longer gate the
    # cap (see the date-independence tests below).
    assert FREE_WATCHLIST_REMOVAL_DATE == date(2026, 8, 2)


def test_free_watchlist_cap_is_restored_regardless_of_date():
    # Before, on, and long after the old cutover date: the cap is the restored
    # FREE_WATCHLIST_TICKERS everywhere — the date gate is no longer consulted.
    assert free_watchlist_cap(FREE_WATCHLIST_REMOVAL_DATE - timedelta(days=1)) == FREE_WATCHLIST_TICKERS
    assert free_watchlist_cap(FREE_WATCHLIST_REMOVAL_DATE) == FREE_WATCHLIST_TICKERS
    assert free_watchlist_cap(FREE_WATCHLIST_REMOVAL_DATE + timedelta(days=1)) == FREE_WATCHLIST_TICKERS
    assert free_watchlist_cap(date(2027, 1, 1)) == FREE_WATCHLIST_TICKERS
    assert free_watchlist_cap(date(2027, 1, 1)) == 5


def test_free_still_has_a_watchlist_on_and_after_the_old_cutover():
    assert free_has_watchlist(FREE_WATCHLIST_REMOVAL_DATE) is True
    assert free_has_watchlist(FREE_WATCHLIST_REMOVAL_DATE + timedelta(days=1)) is True
    assert free_has_watchlist(date(2027, 1, 1)) is True


def test_limit_reads_the_restored_cap_not_the_static_table():
    # FREE/watchlist_tickers must delegate to free_watchlist_cap() so enforcement
    # and copy can't drift. The open-access month deliberately EXCLUDES
    # watchlist_tickers, so this holds during that window too.
    assert limit(Tier.FREE, "watchlist_tickers") == free_watchlist_cap()
    assert limit(Tier.FREE, "watchlist_tickers") == FREE_WATCHLIST_TICKERS


def test_paid_tiers_are_unaffected():
    assert limit(Tier.PRO, "watchlist_tickers") == 50
    assert limit(Tier.PREMIUM, "watchlist_tickers") == 200
