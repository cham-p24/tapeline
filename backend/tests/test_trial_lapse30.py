"""Lapsed-trial (no-card) T+30 win-back — "lapse30" stage in run_daily_drip.

Structural gap this pins: run_winback_drip keys off `canceled_at`, which is
only ever set for users who SUBSCRIBED and then cancelled. A trial user who
never added a card (stripe_customer_id stays NULL) therefore exited email
forever after the T+3 "post3" note. The "lapse30" stage is the single
scheduled touch after that: ~30 days post trial_ends_at, tier=free, no
Stripe customer ever, gated on EmailPref.RE_ENGAGEMENT (marketing bucket —
the trial is long over, so TRIAL_DRIP is the wrong gate) and dedup'd via
the "lapse30" drip_state token.

Honesty contract: post3 used to promise "no more drip after this" — that
line is softened to leave room for material changes ("like pricing"), and
the lapse30 copy leads with exactly that: where founding pricing stands
today, stated as current fact. No dead-tier claims, no discount theatre.

Assertion strategy mirrors test_trial_drip.py: assert on the SPECIFIC
seeded user's captured sends / row, never on aggregate counts — the test DB
is shared for the whole session, so residue users from other tests can
inflate orchestrator counts.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

import app.services.email as email_module
from app.db import session_scope
from app.models import User
from app.services.email import (
    render_trial_lapse30_email,
    render_trial_post_expiry_email,
    run_daily_drip,
)
from app.services.email_prefs import DEFAULT_PREFS, EmailPref

# Claims describing the pre-2026-06-20 Free tier (same guard list as
# test_trial_drip.py) — none may appear in customer-facing copy again.
_DEAD_TIER_CLAIMS = ("top 20 tickers", "24-hour", "capped at 5 tickers")


# ── Seed helper ──────────────────────────────────────────────────────────────

async def _seed_lapsed_user(
    *,
    ended_days_ago: float = 30.5,
    tier: str = "free",
    drip_state: str = "11,13,3,7,expired,post3",
    stripe_customer_id: str | None = None,
    email_prefs: int = DEFAULT_PREFS,
) -> tuple[str, str]:
    """Insert a lapsed no-card trial user. Defaults model the real
    population: trial ended over a month ago, downgraded to free, full
    prior drip history in drip_state, never a Stripe customer."""
    uid = f"tl30_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    async with session_scope() as s:
        s.add(User(
            id=uid,
            email=email,
            name="LapseTest",
            tier=tier,
            password_hash="not-used",
            drip_state=drip_state,
            trial_ends_at=datetime.now(UTC) - timedelta(days=ended_days_ago),
            stripe_customer_id=stripe_customer_id,
            email_prefs=email_prefs,
        ))
        await s.commit()
    return uid, email


async def _user_row(uid: str) -> User:
    async with session_scope() as s:
        return (await s.execute(select(User).where(User.id == uid))).scalar_one()


def _capture_sends(monkeypatch):
    sends: list[dict] = []

    async def _track(to, subject, html, **kwargs):
        sends.append({"to": to, "subject": subject, "html": html, **kwargs})
        return {"id": "ok"}

    monkeypatch.setattr(email_module, "send_email", _track)
    return sends


# ════════════════════════════════════════════════════════════════════════════
# Renderer copy — honest, current pricing, no dead-tier claims
# ════════════════════════════════════════════════════════════════════════════

def test_lapse30_copy_states_current_founding_pricing():
    html = render_trial_lapse30_email("Alex")
    assert "$9.99/mo" in html
    assert "$19.99/mo" in html
    assert "locked in for early subscribers" in html
    assert "30-day money back" in html
    assert "watchlist is still saved" in html
    assert "https://tapeline.io/app/billing" in html


def test_lapse30_copy_has_one_cta_and_no_dead_tier_claims():
    html = render_trial_lapse30_email("Alex")
    for claim in _DEAD_TIER_CLAIMS:
        assert claim not in html, (
            f"lapse30 says {claim!r} — that Free tier was retired by the "
            f"2026-06-20 freemium retune"
        )
    # No discount theatre — the honest-brand differentiator.
    assert "% off" not in html
    assert "discount" not in html.lower()
    # Exactly one CTA button, and it points at billing. (The shell footer's
    # utility links — settings/account/billing — are in every email and
    # don't count as CTAs.)
    assert html.count("<v:roundrect") == 1
    assert 'href="https://tapeline.io/app/billing"' in html


def test_post3_no_longer_promises_total_silence():
    """post3's old line ("no more drip after this") would make lapse30 a
    broken promise. The softened line must leave room for material changes."""
    html = render_trial_post_expiry_email("Alex")
    assert "no more drip after this" not in html
    assert "something material" in html
    assert "pricing" in html


# ════════════════════════════════════════════════════════════════════════════
# Stage behaviour — fires once at ~T+30, respects pref + dedup + population
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_lapse30_fires_once_at_t30(monkeypatch):
    """In-window user gets exactly ONE email even across a re-run (worker
    restart on the same day), stamped 'lapse30' — prior drip history in
    drip_state doesn't interfere."""
    sends = _capture_sends(monkeypatch)
    uid, email = await _seed_lapsed_user()

    async with session_scope() as s:
        await run_daily_drip(s)
    async with session_scope() as s:  # same-day worker restart
        await run_daily_drip(s)

    mine = [m for m in sends if m["to"] == email]
    assert len(mine) == 1, f"expected exactly one lapse30 email, got {len(mine)}"
    assert mine[0]["subject"] == "Tapeline — one note, a month on"
    assert "$9.99/mo" in mine[0]["html"]
    # Marketing-class nudge → List-Unsubscribe under the re_engagement bucket.
    assert mine[0].get("unsubscribe_category") == "re_engagement"
    assert "lapse30" in (await _user_row(uid)).drip_state.split(",")


@pytest.mark.asyncio
async def test_lapse30_respects_re_engagement_pref(monkeypatch):
    """RE_ENGAGEMENT opted out → no send, no token. (TRIAL_DRIP being ON
    must not matter — this is a marketing nudge, not a trial email.)"""
    sends = _capture_sends(monkeypatch)
    uid, email = await _seed_lapsed_user(
        email_prefs=DEFAULT_PREFS & ~int(EmailPref.RE_ENGAGEMENT),
    )

    async with session_scope() as s:
        await run_daily_drip(s)

    assert not [m for m in sends if m["to"] == email]
    assert "lapse30" not in (await _user_row(uid)).drip_state.split(",")


@pytest.mark.asyncio
async def test_lapse30_dedups_on_existing_token(monkeypatch):
    sends = _capture_sends(monkeypatch)
    uid, email = await _seed_lapsed_user(
        drip_state="11,13,3,7,expired,lapse30,post3",
    )

    async with session_scope() as s:
        await run_daily_drip(s)

    assert not [m for m in sends if m["to"] == email]


@pytest.mark.asyncio
async def test_lapse30_window_excludes_too_recent_and_too_old(monkeypatch):
    """T+20 hasn't reached the window; T+40 is past it (no backfill blast to
    the historical lapsed base on deploy day)."""
    sends = _capture_sends(monkeypatch)
    uid_recent, email_recent = await _seed_lapsed_user(ended_days_ago=20)
    uid_old, email_old = await _seed_lapsed_user(ended_days_ago=40)

    async with session_scope() as s:
        await run_daily_drip(s)

    for uid, email in ((uid_recent, email_recent), (uid_old, email_old)):
        assert not [m for m in sends if m["to"] == email]
        assert "lapse30" not in (await _user_row(uid)).drip_state.split(",")


@pytest.mark.asyncio
async def test_lapse30_excludes_anyone_who_ever_had_a_card_or_kept_a_tier(monkeypatch):
    """stripe_customer_id set → run_winback_drip / dunning own them.
    tier != free (comped or converted) → nothing lapsed to win back."""
    sends = _capture_sends(monkeypatch)
    uid_card, email_card = await _seed_lapsed_user(stripe_customer_id=f"cus_{_uuid.uuid4().hex[:12]}")
    uid_paid, email_paid = await _seed_lapsed_user(tier="premium")

    async with session_scope() as s:
        await run_daily_drip(s)

    for uid, email in ((uid_card, email_card), (uid_paid, email_paid)):
        assert not [m for m in sends if m["to"] == email]
        assert "lapse30" not in (await _user_row(uid)).drip_state.split(",")
