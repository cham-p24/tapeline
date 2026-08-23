"""The free -> trial invitation series.

The card-required trial made `run_daily_drip` unreachable for new signups (it
keys on `trial_ends_at IS NOT NULL`, and an account no longer starts with a
trial), so nobody was ever asked to try Premium. This series is the ask.

Two things are pinned here, and the second matters more than the first:

  1. **It stops at two messages.** Saturation is the demonstrated failure mode —
     the three most engaged early users received six to ten automated touches
     each and none converted. Two is the design, not a starting point.
  2. **It never claims the scanner is locked while open access is running.**
     Until PROMO_OPEN_ACCESS_UNTIL a signed-in Free user has the same 1,000
     scanner rows Pro does, so "upgrade to unlock the full scanner" is false for
     them today and true again the day after. The copy has to hold on both sides
     of that date.
"""
from __future__ import annotations

import inspect

from app.services.email import (
    render_free_trial_invite_email,
    render_free_trial_last_invite_email,
    run_free_trial_invite_drip,
)

SRC = inspect.getsource(run_free_trial_invite_drip)


def test_series_is_exactly_two_messages():
    assert SRC.count('"free_invite1"') >= 1
    assert SRC.count('"free_invite2"') >= 1
    assert "free_invite3" not in SRC, "the series must stop at two"


def test_audience_is_only_people_who_were_never_asked():
    """A trial-starter or card-holder must never be invited to do it again."""
    assert "User.trial_started_at.is_(None)" in SRC
    assert "User.stripe_customer_id.is_(None)" in SRC
    assert 'User.tier == "free"' in SRC


def test_guardrails_are_all_present():
    assert "EmailPref.TRIAL_DRIP" in SRC          # respects preferences
    assert "governor" in SRC                       # global frequency cap
    assert 'unsubscribe_category="trial_drip"' in SRC
    assert "drip_state" in SRC                     # one-shot per stage
    # Windows bounded on BOTH ends so an outage can't mail a backlog at once.
    assert SRC.count("timedelta(days=") >= 4


def test_last_note_never_arrives_without_the_first():
    assert '"free_invite1" not in sent_tokens' in SRC


def test_open_access_copy_does_not_claim_the_scanner_is_locked():
    """While the promo runs, Free already HAS the full scanner."""
    html = render_free_trial_invite_email(
        "Sam", open_access=True, open_access_until="September 8",
    )
    low = html.lower()
    assert "full scanner" in low
    assert "september 8" in low
    # It must not sell back something they already have.
    for false_claim in ("unlock the full scanner", "upgrade to see every row",
                        "top ten rows only"):
        assert false_claim not in low, f"claims a locked scanner: {false_claim!r}"


def test_non_promo_copy_describes_the_real_free_tier():
    html = render_free_trial_invite_email("Sam", open_access=False)
    low = html.lower()
    assert "top ten" in low
    assert "september" not in low, "promo wording leaked into the non-promo path"


def test_invite_states_the_trial_terms_including_the_card():
    """Someone should learn the trial takes a card from US, not at the wall."""
    html = render_free_trial_invite_email("Sam", open_access=False).lower()
    assert "takes a card" in html
    assert "$0 is charged today" in html
    assert "one click" in html
    assert "three days before" in html   # the pre-charge reminder we do send


def test_neither_email_uses_pressure_or_performance_language():
    for html in (
        render_free_trial_invite_email("Sam", open_access=False),
        render_free_trial_last_invite_email("Sam"),
    ):
        low = html.lower()
        for banned in ("beat the market", "guaranteed", "hurry", "act now",
                       "last chance", "limited time", "don't miss", "risk-free"):
            assert banned not in low, f"pressure/performance language: {banned!r}"


def test_last_note_leads_with_the_unflattering_truth():
    low = render_free_trial_last_invite_email("Sam").lower()
    assert "do not beat spy" in low
    assert "chance" in low
