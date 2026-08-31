"""The one-month-free Premium offer must be true, redeemable, and reachable.

Three distinct failure modes, one test each family:

  1. The copy promises something the billing system cannot honour.
  2. The email is sent to an account with no credit on its row, so the promise
     is false for that recipient specifically.
  3. The link points somewhere the recipient cannot open — which a dry run
     cannot catch, because a wrong-but-plausible URL looks fine in a dry run.
     The first dry run of this script really did render http://localhost:3000.
"""
from __future__ import annotations

import re

import pytest

from app.scripts.free_month_offer import CREDIT_MONTHS, OFFER_TOKEN, _tokens
from app.services.email import render_free_month_offer_email

URL = "https://tapeline.io/app/billing?offer=freemonth"


def _text(html: str) -> str:
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


# ── 1. the copy states the terms honestly ────────────────────────────────────


def test_offer_states_the_renewal_price_and_the_cancel_path():
    """An offer that leads with 'free' and hides the renewal is a dark pattern.

    Price, timing and cancellation must all be present in the body.
    """
    t = _text(render_free_month_offer_email("Sam", checkout_url=URL)).lower()
    assert "$19.99" in t, "renewal price missing"
    assert "renews" in t, "does not say it renews"
    assert "cancel" in t, "no cancellation path stated"
    assert "one month" in t or "first month" in t


def test_offer_says_a_card_is_required():
    """The offer is conditional on adding a card. That must not be buried."""
    t = _text(render_free_month_offer_email("Sam", checkout_url=URL)).lower()
    assert "card" in t


def test_offer_carries_no_urgency_or_scarcity():
    """Banned by the house copy rules and by the AFSL descriptive posture.

    A manufactured deadline on a financial product is precisely the wrong
    instinct, and this offer deliberately has no expiry.
    """
    t = _text(render_free_month_offer_email("Sam", checkout_url=URL)).lower()
    for phrase in (
        "act now", "hurry", "last chance", "limited time", "expires",
        "don't miss", "only a few", "ends soon", "today only", "countdown",
    ):
        assert phrase not in t, f"urgency language in offer copy: {phrase!r}"


def test_offer_makes_no_performance_claim():
    t = _text(render_free_month_offer_email("Sam", checkout_url=URL)).lower()
    for phrase in ("guaranteed", "beat the market", "you should buy", "we recommend", "profit"):
        assert phrase not in t, f"performance claim in offer copy: {phrase!r}"


def test_the_button_carries_the_checkout_link():
    html = render_free_month_offer_email("Sam", checkout_url=URL)
    assert URL in html


# ── 2. the credit is what makes it true ──────────────────────────────────────


def test_credit_months_is_one():
    """The copy says 'a month'. If this constant drifts, the copy lies."""
    assert CREDIT_MONTHS == 1


def test_checkout_reads_the_credit_column():
    """The offer is only honourable because billing already spends the credit.

    If this wiring is ever removed, the email becomes a false promise — so
    assert the call site still exists rather than trusting a comment.
    """
    import inspect

    from app.routers import billing

    src = inspect.getsource(billing)
    assert "referral_credit_months=user.referral_credit_months" in src, (
        "checkout no longer passes the referral credit — the free-month offer "
        "would be unredeemable"
    )


def test_webhook_consumes_the_credit():
    """And it must be spent on subscription creation, not left to be reused."""
    import inspect

    from app.routers import webhooks

    src = inspect.getsource(webhooks)
    assert "referral_credit_months" in src, "webhook no longer consumes the credit"


# ── 3. idempotency ───────────────────────────────────────────────────────────


class _Row:
    def __init__(self, v):
        self.drip_state = v


def test_offer_token_makes_a_second_run_a_noop():
    """drip_state is a COMMA-SEPARATED TOKEN STRING, not JSON.

    This test previously built a dict, which is the format the first version
    of the script wrongly assumed. That bug raised "cannot adapt type 'dict'"
    at COMMIT — after the email had already been sent — leaving a promise with
    no credit behind it. Pin the real format.
    """
    assert OFFER_TOKEN in _tokens(
        _Row(f"11,3,act_alert,{OFFER_TOKEN},weekly_2026W36")
    )


def test_tokens_parses_the_real_production_format():
    # An actual value read from production.
    real = "11,13,3,7,act_alert,act_wl,expired,lapse30,post3,re14,weekly_2026W36"
    toks = _tokens(_Row(real))
    assert "act_alert" in toks and "weekly_2026W36" in toks
    assert len(toks) == 11


def test_tokens_handles_empty_and_null():
    assert _tokens(_Row("")) == set()
    assert _tokens(_Row(None)) == set()


def test_add_token_preserves_the_joined_format():
    from app.scripts.free_month_offer import _add_token

    u = _Row("expired,post3")
    _add_token(u, OFFER_TOKEN)
    assert isinstance(u.drip_state, str), "must stay a string or COMMIT fails"
    assert set(u.drip_state.split(",")) == {"expired", "post3", OFFER_TOKEN}
    # idempotent
    _add_token(u, OFFER_TOKEN)
    assert u.drip_state.count(OFFER_TOKEN) == 1


# ── 4. the link guard ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_refuses_a_non_public_checkout_link(monkeypatch):
    """The defect this guard exists for actually happened.

    The script runs against the PRODUCTION database from a machine whose
    APP_URL is http://localhost:3000, so the first dry run rendered a
    localhost link. A dry run cannot catch that on its own — the URL looks
    plausible. So the check lives on the send path.
    """
    from app.config import get_settings
    from app.scripts import free_month_offer

    s = get_settings()
    monkeypatch.setattr(s, "app_url", "http://localhost:3000", raising=False)

    with pytest.raises(SystemExit) as exc:
        await free_month_offer.run(send=True, limit=1)

    assert "not a public https URL" in str(exc.value)
