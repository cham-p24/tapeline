"""Trial-state throttling — Premium during trial gets reduced api/telegram caps."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.services.tier import Tier, effective_limit, is_on_trial, limit


def _user(tier: str, trial_ends_at: datetime | None, stripe_customer_id: str | None) -> SimpleNamespace:
    """Mimic just enough of the User model for the helpers under test."""
    return SimpleNamespace(
        tier=tier,
        trial_ends_at=trial_ends_at,
        stripe_customer_id=stripe_customer_id,
    )


def test_is_on_trial_true_for_active_premium_no_card():
    future = datetime.now(UTC) + timedelta(days=7)
    assert is_on_trial("premium", future, None) is True


def test_is_on_trial_false_for_paid_premium():
    future = datetime.now(UTC) + timedelta(days=7)
    # Has a Stripe customer id => on a paid plan, not a trial
    assert is_on_trial("premium", future, "cus_123") is False


def test_is_on_trial_false_for_free_or_pro():
    future = datetime.now(UTC) + timedelta(days=7)
    assert is_on_trial("free", future, None) is False
    assert is_on_trial("pro", future, None) is False


def test_is_on_trial_false_when_trial_ended():
    past = datetime.now(UTC) - timedelta(days=1)
    assert is_on_trial("premium", past, None) is False


def test_is_on_trial_false_when_no_trial_set():
    assert is_on_trial("premium", None, None) is False


def test_effective_limit_throttles_api_during_trial():
    future = datetime.now(UTC) + timedelta(days=7)
    user = _user("premium", future, None)
    # Paid Premium gets 1000; trial gets 100.
    assert limit(Tier.PREMIUM, "api_requests_per_day") == 1000
    assert effective_limit(user, "api_requests_per_day") == 100


def test_effective_limit_throttles_telegram_during_trial():
    future = datetime.now(UTC) + timedelta(days=7)
    user = _user("premium", future, None)
    assert limit(Tier.PREMIUM, "telegram_alerts_per_day") == 10_000
    assert effective_limit(user, "telegram_alerts_per_day") == 100


def test_effective_limit_does_not_throttle_paid_premium():
    future = datetime.now(UTC) + timedelta(days=30)
    user = _user("premium", future, "cus_paid_123")
    assert effective_limit(user, "api_requests_per_day") == 1000
    assert effective_limit(user, "telegram_alerts_per_day") == 10_000


def test_effective_limit_unaffected_keys_unchanged_during_trial():
    """Conversion-test caps stay at full Premium during trial."""
    future = datetime.now(UTC) + timedelta(days=7)
    user = _user("premium", future, None)
    # Watchlist + scanner + email_alerts are NOT in the throttle dict — full Premium
    assert effective_limit(user, "watchlist_tickers") == 200
    assert effective_limit(user, "scanner_rows") == 1000
    assert effective_limit(user, "email_alerts_per_day") == 10_000


def test_effective_limit_free_user_unchanged():
    user = _user("free", None, None)
    assert effective_limit(user, "api_requests_per_day") == 0
    # Post-freemium-retune (2026-06-20): Free watchlist cap is 3 (was 5).
    assert effective_limit(user, "watchlist_tickers") == 3
