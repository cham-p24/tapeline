"""A card-required trial must never charge without warning.

We collect a card up front and charge it when the trial ends. `run_daily_drip`
cannot be that warning: it filters on `stripe_customer_id IS NULL`, so a
trialist with a card on file is invisible to it by design (and its day-11/13
CTAs are signed Stripe *Checkout* links, which would open a SECOND subscription
for someone who already has one).

So the pre-charge notice rides on Stripe's `customer.subscription.trial_will_end`
event, which fires ~3 days out. These tests pin that guarantee: the branch
exists, it quotes Stripe's own date and amount (never an invented one), and the
CTA points at billing rather than a new checkout.
"""
from __future__ import annotations

from app.services.email import render_trial_precharge_reminder_email


def test_reminder_states_date_amount_and_how_to_stop():
    html = render_trial_precharge_reminder_email(
        "Sam",
        tier="premium",
        amount_label="$19.99 USD/month",
        charge_date_label="Friday, September 5",
    )
    # The three facts a person needs before being charged.
    assert "Friday, September 5" in html
    assert "$19.99 USD/month" in html
    assert "nothing at all" in html          # cancelling costs them nothing
    # One click to stop, pointed at billing — NOT at a Stripe Checkout link
    # (that would create a second subscription for a card-on-file trialist).
    assert "tapeline.io/app/billing" in html
    assert "checkout.stripe.com" not in html
    assert "Manage or cancel" in html


def test_reminder_carries_no_urgency_or_retention_pressure():
    """If someone wants to stop, this email's job is to help them stop."""
    html = render_trial_precharge_reminder_email(
        "Sam",
        tier="premium",
        amount_label="$19.99 USD/month",
        charge_date_label="Friday, September 5",
    ).lower()
    # Substrings only — the shared email shell carries CSS comments, so match
    # phrases that cannot occur incidentally in boilerplate.
    for banned in (
        "hurry", "act now", "last chance", "don't miss", "limited time",
        "expires soon", "final notice", "beat the market", "only a few",
    ):
        assert banned not in html, f"pressure language leaked in: {banned!r}"


def test_webhook_handles_trial_will_end():
    """The branch must stay wired — without it we charge with zero notice."""
    import pathlib

    src = pathlib.Path("app/routers/webhooks.py").read_text(encoding="utf-8")
    assert 'customer.subscription.trial_will_end' in src
    assert "render_trial_precharge_reminder_email" in src
    # The quoted figures must come off Stripe's object, not our own guess.
    assert 'obj.get("trial_end")' in src
    assert 'price.get("unit_amount")' in src


def test_signup_paths_do_not_grant_a_cardless_trial():
    """Both signup doors must agree: no free trial without a card.

    A card-free trial on the OAuth path would be a side door around the card
    requirement the email path enforces.
    """
    import pathlib

    for path in ("app/routers/auth.py", "app/routers/oauth.py"):
        src = pathlib.Path(path).read_text(encoding="utf-8")
        assert 'tier="premium"' not in src, (
            f"{path} still creates an account on premium — the trial is "
            f"card-required and is granted by the Stripe trialing webhook"
        )

# ── The trial cannot be shortened out from under the warning ────────────────
#
# The reminder above fires on Stripe's `customer.subscription.trial_will_end`,
# which lands about three days out and no earlier. A trial shorter than that
# ends before the warning can reach anyone, so the T-3 promise on /legal/refund
# would become false the moment TRIAL_DAYS dropped to 2. These tests make that
# a build failure rather than a discovery in a chargeback.


def test_trial_length_cannot_drop_below_the_warning_window():
    from app.routers.billing import MIN_TRIAL_DAYS, TRIAL_DAYS

    assert MIN_TRIAL_DAYS >= 3, (
        "MIN_TRIAL_DAYS is the width of Stripe's trial_will_end window. Below 3 "
        "the pre-charge email cannot fire before the charge, whatever it is set to."
    )
    assert TRIAL_DAYS >= MIN_TRIAL_DAYS, (
        f"TRIAL_DAYS={TRIAL_DAYS} would charge a customer without the three-day "
        f"notice /legal/refund promises. Move the notice off Stripe's fixed T-3 "
        f"event before lowering this."
    )


def test_new_trials_are_clamped_to_the_floor():
    """The mint site clamps, so the floor holds even if TRIAL_DAYS is edited."""
    import pathlib

    src = pathlib.Path("app/routers/billing.py").read_text(encoding="utf-8")
    assert "max(TRIAL_DAYS, MIN_TRIAL_DAYS)" in src, (
        "the new-trial branch must clamp to MIN_TRIAL_DAYS — without it, a "
        "shortened TRIAL_DAYS reaches Stripe before the import-time invariant "
        "is the only thing left protecting the customer"
    )


def test_refund_policy_still_promises_the_three_day_notice():
    """The floor exists to keep this sentence true — pin them together.

    If the copy is ever reworded away from a three-day promise, this test
    should be updated in the SAME change that reconsiders MIN_TRIAL_DAYS,
    rather than the two drifting apart silently.
    """
    import pathlib

    page = pathlib.Path("../frontend/app/legal/refund/page.tsx")
    if not page.exists():  # backend-only checkouts
        return
    text = " ".join(page.read_text(encoding="utf-8").split())
    assert "we email you three days before" in text, (
        "/legal/refund no longer promises the three-day pre-charge notice. If "
        "that was deliberate, revisit MIN_TRIAL_DAYS in routers/billing.py too."
    )
