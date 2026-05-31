"""Lifecycle emails — activation nudges + annual-upgrade nudge (PR2).

Covers the two orchestrators added for conversion lever #2 (annual nudge) and
#3 (activation):

  1. run_activation_drip — two one-shot prompts dedup'd via User.drip_state:
       "act_wl"    signed up 24-72h ago, zero watchlist items (any tier)
       "act_alert" signed up 3-5d ago, alert-capable tier (pro/premium),
                   no alert rule yet

  2. run_annual_nudge_drip — monthly subscribers ~28-45 days post-conversion
       "annual_p"  switch-to-annual upsell. Monthly vs annual is INFERRED from
                   (current_period_end - created_at).days < 180, since the
                   billing interval isn't persisted locally.

Both drips only stamp drip_state on a NON-skipped send. send_email returns
{"skipped": True} without RESEND_API_KEY (always the case in CI), so the
"fires" tests monkeypatch send_email to a delivered result to exercise the
selection + dedupe logic, while the "skipped-no-stamp" tests omit the patch to
mirror CI's real no-key behaviour.

Assertion strategy mirrors test_retention_flow.py: we assert on the SPECIFIC
seeded user's drip_state, never the aggregate counts dict. The test DB is
shared for the whole session (conftest creates tables once, never truncates),
so users left behind by other tests can inflate the orchestrator's return
counts. Per-user row assertions stay deterministic regardless of residue.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

import app.services.email as email_module
from app.db import session_scope
from app.models import AlertRule, Subscription, User, WatchlistItem
from app.services.email import (
    render_activation_alert_email,
    render_activation_watchlist_email,
    render_annual_upgrade_email,
    run_activation_drip,
    run_annual_nudge_drip,
)
from app.services.email_prefs import DEFAULT_PREFS, EmailPref


async def _fake_send_ok(*_a, **_k):
    """A delivered send — no 'skipped' key, so the drip stamps state."""
    return {"id": "test-msg"}


# ── Seed helpers ─────────────────────────────────────────────────────────────

async def _seed_user(
    *,
    age: timedelta,
    tier: str = "premium",
    trial_drip: bool = True,
    re_engagement: bool = True,
    drip_state: str = "",
    with_watchlist: bool = False,
    with_alert: bool = False,
) -> tuple[str, str]:
    """Insert a fresh user aged `age` ago. Returns (user_id, email).

    `created_at` is overridden explicitly (the column's server_default only
    fills when the value is omitted), so we can place the user inside or
    outside an orchestrator's signup window. `trial_drip=False` clears the
    TRIAL_DRIP bit (the activation gate); `with_watchlist` / `with_alert` add
    the artefact whose ABSENCE the activation drip looks for.
    """
    uid = f"lc_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    prefs = DEFAULT_PREFS
    if not trial_drip:
        prefs &= ~int(EmailPref.TRIAL_DRIP)
    if not re_engagement:
        prefs &= ~int(EmailPref.RE_ENGAGEMENT)
    created = datetime.now(UTC) - age
    async with session_scope() as s:
        s.add(User(
            id=uid,
            email=email,
            name="LCTest",
            tier=tier,
            password_hash="not-used",
            email_prefs=prefs,
            drip_state=drip_state,
            created_at=created,
        ))
        if with_watchlist:
            s.add(WatchlistItem(user_id=uid, symbol="AAPL"))
        if with_alert:
            s.add(AlertRule(user_id=uid, name="t", rule_type="score"))
        await s.commit()
    return uid, email


async def _seed_subscriber(
    *,
    sub_age: timedelta,
    period: timedelta,
    tier: str = "pro",
    status: str = "active",
    re_engagement: bool = True,
    drip_state: str = "",
) -> tuple[str, str]:
    """Insert a paid user + one Subscription row for the annual-nudge tests.

    The subscription is created `sub_age` ago (the window anchor) with a
    `period`-long billing cycle (`current_period_end = created + period`,
    which is also the monthly-vs-annual inference anchor: < 180d => monthly).
    """
    uid = f"lc_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    prefs = DEFAULT_PREFS
    if not re_engagement:
        prefs &= ~int(EmailPref.RE_ENGAGEMENT)
    created = datetime.now(UTC) - sub_age
    async with session_scope() as s:
        s.add(User(
            id=uid,
            email=email,
            name="LCSub",
            tier=tier,
            password_hash="not-used",
            email_prefs=prefs,
            drip_state=drip_state,
            stripe_customer_id=f"cus_{uid}",
        ))
        s.add(Subscription(
            id=f"sub_{uid}",
            user_id=uid,
            status=status,
            tier=tier,
            created_at=created,
            current_period_end=created + period,
        ))
        await s.commit()
    return uid, email


async def _drip_state(uid: str) -> str:
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        return u.drip_state or ""


# ════════════════════════════════════════════════════════════════════════════
# Activation drip — act_wl (empty watchlist, 24-72h after signup)
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_act_wl_fires_for_empty_watchlist(monkeypatch):
    """Signed up 48h ago, no watchlist item, any tier → act_wl stamped."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(age=timedelta(hours=48), tier="free")
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == "act_wl"


@pytest.mark.asyncio
async def test_act_wl_skips_when_watchlist_present(monkeypatch):
    """Already added a ticker → not the activation target."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(age=timedelta(hours=48), tier="free", with_watchlist=True)
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == ""


@pytest.mark.asyncio
async def test_act_wl_skips_too_new(monkeypatch):
    """Signed up <24h ago → below the window's lower edge, no nudge yet."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(age=timedelta(hours=12), tier="free")
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == ""


@pytest.mark.asyncio
async def test_act_wl_skips_too_old(monkeypatch):
    """Signed up >72h ago → past the window's upper edge (free tier so the
    act_alert window doesn't pick them up either)."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(age=timedelta(hours=100), tier="free")
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == ""


@pytest.mark.asyncio
async def test_act_wl_dedupes(monkeypatch):
    """Already stamped act_wl → never re-sent. Track sends to prove the second
    pass doesn't email this address (the orchestrator swallows exceptions, so a
    raise-guard would be hidden — assert on the captured send list instead)."""
    uid, email = await _seed_user(
        age=timedelta(hours=48), tier="free", drip_state="act_wl",
    )
    sends: list[str] = []

    async def _track(to, *_a, **_k):
        sends.append(to)
        return {"id": "ok"}

    monkeypatch.setattr(email_module, "send_email", _track)
    async with session_scope() as s:
        await run_activation_drip(s)
    assert email not in sends
    assert await _drip_state(uid) == "act_wl"


@pytest.mark.asyncio
async def test_act_wl_respects_trial_drip_optout(monkeypatch):
    """In-window + empty watchlist, but TRIAL_DRIP bit cleared → no send.
    Delivered fake proves '' means 'gated', not 'skipped'."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(age=timedelta(hours=48), tier="free", trial_drip=False)
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == ""


# ════════════════════════════════════════════════════════════════════════════
# Activation drip — act_alert (no alert rule, 3-5d after signup, pro/premium)
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_act_alert_fires_for_premium_no_rule(monkeypatch):
    """Signed up 4 days ago, premium, no alert rule → act_alert stamped (and
    NOT act_wl — 4d is past the watchlist window)."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(age=timedelta(days=4), tier="premium")
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == "act_alert"


@pytest.mark.asyncio
async def test_act_alert_skips_free_tier(monkeypatch):
    """Free tier can't create alerts (Pro+ feature) → never nudged toward one,
    so no act_alert even with no rule."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(age=timedelta(days=4), tier="free")
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == ""


@pytest.mark.asyncio
async def test_act_alert_skips_when_rule_present(monkeypatch):
    """Already has an alert rule → activation milestone hit, no nudge."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(age=timedelta(days=4), tier="premium", with_alert=True)
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == ""


@pytest.mark.asyncio
async def test_activation_skipped_send_does_not_stamp():
    """Without RESEND_API_KEY, send_email returns skipped:True — an eligible
    user must NOT be stamped (next worker pass retries once the key is live).
    No monkeypatch here, mirroring CI's real behaviour."""
    uid, _ = await _seed_user(age=timedelta(hours=48), tier="free")
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == ""


# ════════════════════════════════════════════════════════════════════════════
# Annual-upgrade nudge — run_annual_nudge_drip
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_annual_nudge_fires_for_monthly_pro(monkeypatch):
    """Pro sub created 35 days ago with a ~30-day period (< 180d => monthly) →
    annual_p stamped."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_subscriber(
        sub_age=timedelta(days=35), period=timedelta(days=30), tier="pro",
    )
    async with session_scope() as s:
        await run_annual_nudge_drip(s)
    assert await _drip_state(uid) == "annual_p"


@pytest.mark.asyncio
async def test_annual_nudge_fires_for_monthly_premium(monkeypatch):
    """Same path holds for premium (per-tier pitch resolves on user.tier)."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_subscriber(
        sub_age=timedelta(days=35), period=timedelta(days=30), tier="premium",
    )
    async with session_scope() as s:
        await run_annual_nudge_drip(s)
    assert await _drip_state(uid) == "annual_p"


@pytest.mark.asyncio
async def test_annual_nudge_skips_annual_sub(monkeypatch):
    """A sub whose period is a full year (>= 180d) is ALREADY annual — must
    never be nudged to 'switch to annual'."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_subscriber(
        sub_age=timedelta(days=35), period=timedelta(days=365), tier="pro",
    )
    async with session_scope() as s:
        await run_annual_nudge_drip(s)
    assert await _drip_state(uid) == ""


@pytest.mark.asyncio
async def test_annual_nudge_skips_too_new(monkeypatch):
    """Sub created 20 days ago → below the 28-day floor, too early to nudge."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_subscriber(
        sub_age=timedelta(days=20), period=timedelta(days=30), tier="pro",
    )
    async with session_scope() as s:
        await run_annual_nudge_drip(s)
    assert await _drip_state(uid) == ""


@pytest.mark.asyncio
async def test_annual_nudge_skips_too_old(monkeypatch):
    """Sub created 50 days ago → past the 45-day ceiling (also where the
    monthly-vs-annual inference stops being reliable), so excluded."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_subscriber(
        sub_age=timedelta(days=50), period=timedelta(days=30), tier="pro",
    )
    async with session_scope() as s:
        await run_annual_nudge_drip(s)
    assert await _drip_state(uid) == ""


@pytest.mark.asyncio
async def test_annual_nudge_dedupes(monkeypatch):
    """Already stamped annual_p → one nudge ever; the second pass must not
    re-send (assert on the captured send list, not a swallowed raise-guard)."""
    uid, email = await _seed_subscriber(
        sub_age=timedelta(days=35), period=timedelta(days=30),
        tier="pro", drip_state="annual_p",
    )
    sends: list[str] = []

    async def _track(to, *_a, **_k):
        sends.append(to)
        return {"id": "ok"}

    monkeypatch.setattr(email_module, "send_email", _track)
    async with session_scope() as s:
        await run_annual_nudge_drip(s)
    assert email not in sends
    assert await _drip_state(uid) == "annual_p"


@pytest.mark.asyncio
async def test_annual_nudge_respects_re_engagement_optout(monkeypatch):
    """In-window monthly sub, but RE_ENGAGEMENT bit cleared → no send."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_subscriber(
        sub_age=timedelta(days=35), period=timedelta(days=30),
        tier="pro", re_engagement=False,
    )
    async with session_scope() as s:
        await run_annual_nudge_drip(s)
    assert await _drip_state(uid) == ""


@pytest.mark.asyncio
async def test_annual_nudge_skipped_send_does_not_stamp():
    """No RESEND_API_KEY → send_email returns skipped:True → eligible monthly
    subscriber is NOT stamped. No monkeypatch, mirroring CI."""
    uid, _ = await _seed_subscriber(
        sub_age=timedelta(days=35), period=timedelta(days=30), tier="pro",
    )
    async with session_scope() as s:
        await run_annual_nudge_drip(s)
    assert await _drip_state(uid) == ""


# ════════════════════════════════════════════════════════════════════════════
# Renderers — smoke (full HTML, name + key copy present)
# ════════════════════════════════════════════════════════════════════════════

def test_activation_watchlist_renderer():
    html = render_activation_watchlist_email("Alex")
    assert "Alex" in html
    assert len(html) > 200
    assert "watchlist" in html.lower()


def test_activation_alert_renderer():
    html = render_activation_alert_email("Alex")
    assert "Alex" in html
    assert len(html) > 200
    assert "alert" in html.lower()


def test_annual_upgrade_renderer_each_tier():
    pro = render_annual_upgrade_email("Alex", tier="pro")
    assert "Alex" in pro
    assert "$60" in pro          # Pro annual saving
    assert "Pro" in pro
    premium = render_annual_upgrade_email("Alex", tier="premium")
    assert "Alex" in premium
    assert "$120" in premium     # Premium annual saving
    assert "Premium" in premium


def test_annual_upgrade_renderer_unknown_tier_falls_back():
    """An unexpected tier string must not render blank — falls back to Pro."""
    html = render_annual_upgrade_email("Alex", tier="mystery")
    assert "Alex" in html
    assert "$60" in html         # Pro fallback pitch
