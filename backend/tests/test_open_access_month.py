"""Open-access month (founder experiment 2026-08-08).

Time-boxed: the FREE tier's usage CAPS lift to Pro level (the walls a free user
actually hits — scanner rows, daily look-ups, web-push allowance) until
PROMO_OPEN_ACCESS_UNTIL, then auto-revert. Deliberately NARROW:
  - watchlist_tickers is NOT lifted (kept removed per the Aug-2 cutover), and
  - Pro FEATURES are NOT unlocked (has_feature unchanged — premium tools stay
    the paid moat).
"""
from datetime import date, timedelta

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


def test_during_window_free_caps_lift_to_pro():
    # Guarded so the test is correct whether CI runs inside or after the window.
    if not free_open_access():
        return
    # scanner_rows/web_push have concrete Pro ints — lifted to exactly those.
    assert limit(Tier.FREE, "scanner_rows") == TIER_LIMITS[Tier.PRO]["scanner_rows"]
    assert limit(Tier.FREE, "web_push_alerts") == TIER_LIMITS[Tier.PRO]["web_push_alerts"]
    # daily_lookups: Pro is "unlimited" (None); Free is lifted to a large int
    # (kept int so the meter/stale-read guards stay safe) — effectively no wall.
    cap = limit(Tier.FREE, "daily_lookups")
    assert isinstance(cap, int) and cap >= 1000


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
