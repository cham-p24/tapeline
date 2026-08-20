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
