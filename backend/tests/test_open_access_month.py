"""Open-access month (founder experiment 2026-08-08).

Time-boxed: the FREE tier's scanner ROW cap lifts to Pro level (top-10 → the
full ~2,500-row universe — the single biggest, most visible Free wall) until
PROMO_OPEN_ACCESS_UNTIL, then auto-reverts. Deliberately NARROW so it opens the
core product without collateral:
  - daily_lookups is NOT lifted — lifting it defeats the look-up meter's
    cap-hit + stale-read guards (those tests assume Free hits its 12/day wall),
  - web_push_alerts is NOT lifted (kept simple; not a wall anyone reports),
  - watchlist_tickers is NOT lifted (kept removed per the Aug-2 cutover), and
  - Pro FEATURES are NOT unlocked (has_feature unchanged — premium tools stay
    the paid moat).
"""
from datetime import timedelta

from app.services.tier import (
    PROMO_OPEN_ACCESS_UNTIL,
    TIER_LIMITS,
    Tier,
    free_open_access,
    free_watchlist_cap,
    has_feature,
    limit,
)


def test_open_access_window_boundary():
    assert free_open_access(PROMO_OPEN_ACCESS_UNTIL - timedelta(days=1)) is True
    assert free_open_access(PROMO_OPEN_ACCESS_UNTIL) is False  # revert day
    assert free_open_access(PROMO_OPEN_ACCESS_UNTIL + timedelta(days=1)) is False


def test_during_window_free_scanner_rows_lift_to_pro():
    # Guarded so the test is correct whether CI runs inside or after the window.
    if not free_open_access():
        return
    assert limit(Tier.FREE, "scanner_rows") == TIER_LIMITS[Tier.PRO]["scanner_rows"]


def test_lookup_meter_is_NOT_lifted_by_open_access():
    # daily_lookups must stay Free's finite cap so the look-up meter + its
    # cap-hit/stale-read guards keep enforcing. During the window this is
    # UNCHANGED from the static table.
    if not free_open_access():
        return
    assert limit(Tier.FREE, "daily_lookups") == TIER_LIMITS[Tier.FREE]["daily_lookups"]


def test_web_push_is_NOT_lifted_by_open_access():
    if not free_open_access():
        return
    assert limit(Tier.FREE, "web_push_alerts") == TIER_LIMITS[Tier.FREE]["web_push_alerts"]


def test_watchlist_is_NOT_lifted_by_open_access():
    # The just-removed watchlist must stay removed — no yo-yo for users.
    assert limit(Tier.FREE, "watchlist_tickers") == free_watchlist_cap()


def test_pro_features_stay_gated_during_window():
    # Numeric-cap lift only — the premium tools remain the paid moat.
    for feat in ("export.csv", "squeeze.full", "heatmap", "congress.feed", "api.access"):
        assert has_feature(Tier.FREE, feat) is False, feat


def test_paid_tiers_unaffected():
    assert limit(Tier.PRO, "scanner_rows") == TIER_LIMITS[Tier.PRO]["scanner_rows"]
    assert limit(Tier.PREMIUM, "watchlist_tickers") == 200
    assert has_feature(Tier.PREMIUM, "congress.feed") is True


def test_anonymous_callers_do_NOT_get_the_open_access_lift():
    """The lift is the reward for having an account, not for showing up.

    Anonymous requests are scored against the FREE table (scanner.py:
    `tier = Tier(user.tier) if user else Tier.FREE`), so without an explicit
    guard the promo would hand the full universe to logged-out visitors — during
    the exact month the promo exists to drive signups, and re-opening the
    offset-walk that the scanner's anonymous pagination guard closes.
    """
    if not free_open_access():
        return
    assert limit(Tier.FREE, "scanner_rows", authenticated=False) == (
        TIER_LIMITS[Tier.FREE]["scanner_rows"]
    )
    # ...while a signed-in free user in the same window does get it.
    assert limit(Tier.FREE, "scanner_rows", authenticated=True) == (
        TIER_LIMITS[Tier.PRO]["scanner_rows"]
    )
