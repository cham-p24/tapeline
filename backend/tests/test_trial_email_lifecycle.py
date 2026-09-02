"""The email sequence for a card-required trial.

Collecting a card up front changes what every message in the lifecycle must say.
Three failures are possible here and all of them are the expensive kind:

  1. Telling a trialist who has paid NOTHING that they are "in" on a paid plan.
     `customer.subscription.created` fires with status "trialing" the instant a
     card trial starts, and the pre-existing welcome-to-paid receipt was wired to
     fire on it — a receipt for a charge that never happened, which is the
     shortest path to an "I never agreed to pay" dispute.
  2. Never telling someone their first REAL charge went through, because the
     receipt only fired on `.created` and a conversion is a trialing -> active
     `.updated`.
  3. Leaving someone who cancelled mid-trial unsure whether money will be taken.

These tests pin the wiring and, more importantly, the claims each email makes.
"""
from __future__ import annotations

import pathlib

from app.services.email import (
    render_subscription_started_email,
    render_trial_canceled_email,
    render_trial_started_email,
)

WEBHOOKS = pathlib.Path("app/routers/webhooks.py").read_text(encoding="utf-8")


def test_trial_start_is_not_wired_to_the_paid_receipt():
    """status 'trialing' must NOT reach render_subscription_started_email."""
    assert "is_trial_start" in WEBHOOKS
    assert "render_trial_started_email" in WEBHOOKS
    # The paid receipt must sit behind is_paid_start. (The identical status
    # tuple appears elsewhere for TIER GRANTING, which is correct — a trialist
    # should get premium access — so check the receipt's own guard, not the
    # string.)
    receipt_at = WEBHOOKS.index("render_subscription_started_email")
    guard_at = WEBHOOKS.index("if is_paid_start and user.email:")
    trial_guard_at = WEBHOOKS.index("if is_trial_start and user.email:")
    assert guard_at < receipt_at, "the paid receipt is no longer behind is_paid_start"
    assert trial_guard_at < guard_at, "trial-start branch must precede the receipt"


def test_conversion_from_trial_sends_the_paid_receipt():
    """A trial's first real charge must be captured — INCLUDING when the first
    card attempt is declined.

    This used to assert the literal source string
        prior_status == "trialing" and p["status"] == "active"
    which pinned the implementation rather than the behaviour, and pinned a
    BUGGY one: Stripe retries a declined first charge for days, so a converting
    trial commonly goes trialing -> past_due -> active. By the time it reached
    active the prior status was past_due, so the receipt and the founder's
    revenue alert both stayed silent on a sale that had completed.

    `is_paid_start` now latches "has this subscription EVER been active",
    reusing the stripe_webhook_events idempotency table. The behavioural cases
    live in test_billing_edge_cases.py; this keeps the wiring assertion that
    belongs with the rest of the lifecycle.
    """
    assert "is_paid_start" in WEBHOOKS
    assert "paid_start:" in WEBHOOKS, "the first-charge latch is gone"

    # The bug, pinned shut. Checked against EXECUTABLE source only: WEBHOOKS is
    # the raw file, and the comment explaining why prior_status was removed
    # necessarily contains the words "prior_status". Asserting on raw text
    # failed against that comment — the same class of mistake as a test passing
    # against its own prose, just pointing the other way.
    import ast
    import textwrap

    executable = ast.unparse(ast.parse(textwrap.dedent(WEBHOOKS)))
    assert "prior_status" not in executable, (
        "prior_status is back — a trial converting through a declined first "
        "attempt arrives at active with prior_status == 'past_due'"
    )


def test_cancel_during_trial_is_confirmed_as_no_charge():
    assert "cancelled_before_any_charge" in WEBHOOKS
    assert "render_trial_canceled_email" in WEBHOOKS


def test_trial_started_email_states_the_terms_not_a_purchase():
    html = render_trial_started_email(
        "Sam",
        tier="premium",
        amount_label="$19.99 USD/month",
        charge_date_label="Friday, September 5",
    )
    # The three facts, stated plainly.
    assert "$0" in html
    assert "Friday, September 5" in html
    assert "$19.99 USD/month" in html
    assert "nothing at all" in html
    # It must NOT read as a receipt for money taken.
    low = html.lower()
    for claim in ("you're in", "thanks for your payment", "payment received",
                  "receipt", "you have been charged"):
        assert claim not in low, f"trial-start email reads as a purchase: {claim!r}"
    # And it must promise the reminder we actually send (trial_will_end, T-3).
    assert "three days before" in low


def test_cancel_email_leads_with_no_money_taken_and_does_not_argue():
    html = render_trial_canceled_email("Sam", tier="premium")
    low = html.lower()
    assert "not been charged" in low or "no payment was taken" in low
    # A cancellation confirmation that argues earns a chargeback, not a return.
    for claim in ("are you sure", "before you go", "special offer",
                  "discount", "last chance", "reconsider"):
        assert claim not in low, f"cancellation email pushes back: {claim!r}"


def test_paid_receipt_still_reads_as_a_real_purchase():
    """The receipt itself is unchanged — it just fires later now."""
    html = render_subscription_started_email(
        user_name="Sam", tier="premium", billing_period="monthly",
        amount_cents=1999, currency="usd",
    )
    assert "19.99" in html
