"""Free watchlist → Pro+ cutover (announced to free users by email 2026-07-26).

The saved watchlist becomes a Pro-and-up feature on FREE_WATCHLIST_REMOVAL_DATE;
the FREE cap date-gates to 0 from then on. These tests pin the boundary (the
cutover day itself counts as removed, matching the "on August 2" the email
promised) and confirm `limit()` reads the live date-gated cap, not the static
TIER_LIMITS value, so enforcement flips with no deploy on the day.
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


def test_cutover_date_is_august_2_2026():
    # The date announced to every free user by email — do not move it without
    # re-notifying them.
    assert FREE_WATCHLIST_REMOVAL_DATE == date(2026, 8, 2)


def test_before_cutover_free_keeps_watchlist():
    day_before = FREE_WATCHLIST_REMOVAL_DATE - timedelta(days=1)
    assert free_watchlist_cap(day_before) == FREE_WATCHLIST_TICKERS
    assert free_watchlist_cap(day_before) == 5
    assert free_has_watchlist(day_before) is True


def test_on_and_after_cutover_free_watchlist_is_gone():
    # The cutover day itself = removed (email said "on August 2").
    assert free_watchlist_cap(FREE_WATCHLIST_REMOVAL_DATE) == 0
    assert free_watchlist_cap(FREE_WATCHLIST_REMOVAL_DATE + timedelta(days=1)) == 0
    assert free_watchlist_cap(date(2027, 1, 1)) == 0
    assert free_has_watchlist(FREE_WATCHLIST_REMOVAL_DATE) is False


def test_limit_reads_the_date_gated_cap_not_the_static_table():
    # FREE/watchlist_tickers must delegate to free_watchlist_cap() so the
    # cutover needs no restart/redeploy. The open-access month deliberately
    # EXCLUDES watchlist_tickers, so this holds during the window too.
    assert limit(Tier.FREE, "watchlist_tickers") == free_watchlist_cap()


def test_paid_tiers_are_unaffected_by_the_cutover():
    assert limit(Tier.PRO, "watchlist_tickers") == 50
    assert limit(Tier.PREMIUM, "watchlist_tickers") == 200
