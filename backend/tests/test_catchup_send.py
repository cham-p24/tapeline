"""The catch-up send must never promise a trial to someone who cannot take one.

That is the whole correctness burden of this script. `billing._trial_ineligible_reason`
returns "already_trialed" for any account carrying a LEGACY `trial_ends_at` from
the pre-#536 auto-granted no-card trial — one trial per account, forever. Sending
those users a "start your 14-day trial" email would be false advertising on a
financial product.

The audience split is therefore not a nicety, and these tests pin it.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.scripts.catchup_send import (
    CATCHUP_TOKEN,
    FORWARD_FLOW_GRACE_DAYS,
    _drip_state,
    _render,
)


class _U:
    """Stand-in carrying only what the split and the renderer read."""

    def __init__(self, **kw):
        self.id = kw.get("id", "u_1")
        self.name = kw.get("name", "Sam")
        self.email = kw.get("email", "sam@example.com")
        self.tier = kw.get("tier", "free")
        self.is_lifetime = kw.get("is_lifetime", False)
        self.trial_started_at = kw.get("trial_started_at")
        self.trial_ends_at = kw.get("trial_ends_at")
        self.stripe_customer_id = kw.get("stripe_customer_id")
        self.drip_state = kw.get("drip_state")
        self.email_prefs = kw.get("email_prefs", 31)
        self.email_undeliverable_at = kw.get("email_undeliverable_at")
        self.created_at = kw.get(
            "created_at", datetime.now(UTC) - timedelta(days=60)
        )


def _reason(u):
    from app.routers.billing import _trial_ineligible_reason

    return _trial_ineligible_reason(u)


# ── the split itself ─────────────────────────────────────────────────────────


def test_legacy_trial_user_is_ineligible_for_a_new_trial():
    """The premise the whole audience split rests on."""
    legacy = _U(trial_ends_at=datetime.now(UTC) - timedelta(days=40))
    assert _reason(legacy) == "already_trialed"


def test_never_trialled_user_is_eligible():
    assert _reason(_U()) is None


# ── the copy each audience receives ──────────────────────────────────────────


def test_legacy_trial_copy_never_offers_a_trial():
    """The false-advertising guard.

    An account that cannot start a trial must not be sent an invitation to
    start one — not in the subject, not in the body.
    """
    legacy = _U(trial_ends_at=datetime.now(UTC) - timedelta(days=40))
    subject, html = _render(legacy, "legacy_trial")
    haystack = f"{subject} {html}".lower()

    # Target the OFFER, not the word. The changelog copy legitimately says
    # "no card, no trial clock" — a negation describing the free plan — so a
    # naive search for "trial" passes for the wrong reason. These three
    # markers appear only when a trial is actually being offered.
    #
    # (The first version of this test checked for "start a trial" / "14-day
    # trial", phrases the invite email never uses. It passed against the
    # deliberately-broken build. Watched it fail, then fixed it.)
    for phrase in ("premium trial", "$0 today", "card required"):
        assert phrase not in haystack, f"legacy-trial copy offers a trial: {phrase!r}"

    # And the invite, for contrast, must carry them — otherwise the assertion
    # above proves nothing.
    _s, invite_html = _render(_U(), "never_trialled")
    assert "premium trial" in invite_html.lower()


def test_never_trialled_copy_is_the_invite():
    never = _U()
    subject, html = _render(never, "never_trialled")
    assert subject and html
    # The invite is the one place a trial may be mentioned at all.
    assert len(html) > 500


def test_neither_audience_gets_banned_marketing_language():
    """The AFSL descriptive-only posture applies to email as much as the site."""
    banned = [
        "act now", "last chance", "hurry", "don't miss", "limited time",
        "guaranteed", "beat the market", "you should buy", "we recommend",
    ]
    for bucket, u in (
        ("never_trialled", _U()),
        ("legacy_trial", _U(trial_ends_at=datetime.now(UTC) - timedelta(days=40))),
    ):
        subject, html = _render(u, bucket)
        haystack = f"{subject} {html}".lower()
        for phrase in banned:
            assert phrase not in haystack, f"{bucket} copy contains {phrase!r}"


# ── idempotency ──────────────────────────────────────────────────────────────


def test_drip_state_parses_dict_and_json_and_garbage():
    assert _drip_state(_U(drip_state={"a": 1})) == {"a": 1}
    assert _drip_state(_U(drip_state='{"b": 2}')) == {"b": 2}
    assert _drip_state(_U(drip_state="not json")) == {}
    assert _drip_state(_U(drip_state=None)) == {}


def test_an_already_caught_up_user_is_recognised():
    """The stamp is what makes a second run a no-op."""
    u = _U(drip_state={CATCHUP_TOKEN: "2026-08-31T00:00:00+00:00"})
    assert CATCHUP_TOKEN in _drip_state(u)


def test_grace_window_is_long_enough_to_clear_the_drip_stages():
    """Must exceed the invite drip's last window (12-16 days) or a user could
    receive both the automated stage and this catch-up."""
    assert FORWARD_FLOW_GRACE_DAYS > 16


@pytest.mark.asyncio
async def test_collect_is_read_only_by_construction():
    """`collect` must not write — it is what the dry run calls."""
    import inspect

    from app.scripts import catchup_send

    src = inspect.getsource(catchup_send.collect)
    for banned in ("session.add", "session.commit", "send_email", "drip_state ="):
        assert banned not in src, f"collect() performs a write: {banned}"
