"""The referral page's `converted` count.

THE BUG
-------
    converted = u.tier in ("pro", "premium") and not u.trial_ends_at

`trial_ends_at` is written once when a trial starts and is never cleared. So a
friend who took the 14-day trial and then CONVERTED — the outcome the whole
referral mechanic exists to produce — kept a non-null value forever and showed
as "pending" on the referrer's page for the rest of time.

Since the card-required trial is the normal path to paid, that meant the
success case was the one case the counter could never register.

The fix asks whether they are STILL INSIDE a trial, not whether they ever had
one. Both directions matter, so both are asserted here:
  * a FUTURE trial_ends_at is mid-trial — Stripe has a card but has charged
    $0, so counting it as converted would be the opposite error;
  * a PAST one means the trial ended and they are still on a paid tier, which
    is conversion.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.models import User
from app.routers.referrals import _has_converted

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def _friend(tier: str, trial_ends_at: datetime | None) -> User:
    return User(
        id="u_friend",
        email="friend@example.com",
        tier=tier,
        trial_ends_at=trial_ends_at,
    )


def test_trial_converted_subscriber_counts_as_converted():
    """The regression. Paid tier, trial ended two days ago."""
    u = _friend("premium", NOW - timedelta(days=2))
    assert _has_converted(u, NOW) is True


def test_mid_trial_friend_does_not_count_yet():
    """$0 has been charged. Counting this as converted would be the opposite
    error, and it is what a naive `trial_ends_at is not None` fix would do."""
    u = _friend("premium", NOW + timedelta(days=5))
    assert _has_converted(u, NOW) is False


def test_direct_subscriber_with_no_trial_counts():
    u = _friend("pro", None)
    assert _has_converted(u, NOW) is True


def test_free_friend_never_counts():
    # Both shapes: never trialled, and lapsed-then-downgraded.
    assert _has_converted(_friend("free", None), NOW) is False
    assert _has_converted(_friend("free", NOW - timedelta(days=30)), NOW) is False


def test_naive_timestamp_does_not_raise():
    """Postgres can hand back a naive datetime depending on the column and the
    driver. A TypeError here would 500 the whole referrals page."""
    u = _friend("premium", (NOW - timedelta(days=2)).replace(tzinfo=None))
    assert _has_converted(u, NOW) is True


def test_the_old_predicate_would_fail_the_regression_case():
    """Pins WHY the fix is shaped this way.

    If someone 'simplifies' `_has_converted` back to the old form, the first
    test above goes red — but this one states the reason in the same file, so
    the next reader does not have to reconstruct it from a diff.
    """
    u = _friend("premium", NOW - timedelta(days=2))
    old_predicate = u.tier in ("pro", "premium") and not u.trial_ends_at
    assert old_predicate is False, "the old predicate is the bug"
    assert _has_converted(u, NOW) is True, "the new one must disagree with it"


@pytest.mark.parametrize("tier", ["pro", "premium"])
def test_both_paid_tiers_count(tier):
    assert _has_converted(_friend(tier, NOW - timedelta(days=1)), NOW) is True
