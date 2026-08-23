"""Lifecycle emails — activation nudges + annual-upgrade nudge (PR2).

Covers the two orchestrators added for conversion lever #2 (annual nudge) and
#3 (activation):

  1. run_activation_drip — two one-shot prompts dedup'd via User.drip_state,
     both aligned to the first-session aha and gated on the fail-safe
     lifecycle.has_recorded_activity helper (any recorded activity suppresses
     the nudge — an empty watchlist alone is no longer enough):
       "act_wl"    signed up 24-72h ago, no recorded activity (any tier) —
                   the three-step aha checklist (watchlist, scan, scorecard)
       "act_alert" signed up 3-5d ago, no recorded activity, alert-capable
                   tier (pro/premium) — leads with the zero-setup scorecard
                   (token name historical; see run_activation_drip)
       "act_arm"   the INVERSE cohort, added to close a blind spot: 2-10d in,
                   alert-capable tier, HAS a watchlist and has ZERO alert
                   rules. Both stages above require no recorded activity, so
                   the most engaged trialist in the funnel — watchlist built,
                   alert never felt — matched nothing and was emailed nothing.

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
    render_activation_arm_alerts_email,
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
    watchlist_symbols: tuple[str, ...] = (),
    with_alert: bool = False,
    activated_at: datetime | None = None,
    last_seen_at: datetime | None = None,
) -> tuple[str, str]:
    """Insert a fresh user aged `age` ago. Returns (user_id, email).

    `created_at` is overridden explicitly (the column's server_default only
    fills when the value is omitted), so we can place the user inside or
    outside an orchestrator's signup window. `trial_drip=False` clears the
    TRIAL_DRIP bit (the activation gate); `with_watchlist` / `with_alert` add
    the artefact whose ABSENCE the activation drip looks for. `activated_at`
    and `last_seen_at` simulate recorded activity (an activation stamp / a
    return visit) so the has_recorded_activity gate can be exercised.

    `watchlist_symbols` overrides the single default item — the act_arm stage
    quotes the real watchlist COUNT in its copy, so its tests need to control
    how many rows exist.
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
            activated_at=activated_at,
            last_seen_at=last_seen_at,
        ))
        if with_watchlist:
            for sym in (watchlist_symbols or ("AAPL",)):
                s.add(WatchlistItem(user_id=uid, symbol=sym))
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


# ── Aligns the drip to the aha milestone: target only NOT-yet-activated users ─
# The drip must nudge users who have not reached the first-session aha (add a
# watchlist ticker + run a scan + view the scorecard), measured with the
# existing fail-safe lifecycle.has_recorded_activity helper. An empty watchlist
# is no longer sufficient — any recorded activity suppresses the nudge.

@pytest.mark.asyncio
async def test_act_wl_skips_activated_user(monkeypatch):
    """In-window + empty watchlist, but activated_at is stamped (recorded
    activity) → NOT the activation target, so no 'you haven't started' nudge."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(
        age=timedelta(hours=48), tier="free",
        activated_at=datetime.now(UTC) - timedelta(hours=1),
    )
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == ""


@pytest.mark.asyncio
async def test_act_wl_skips_returned_user(monkeypatch):
    """Empty watchlist but the user came BACK after signup (last_seen_at well
    past created_at) → has_recorded_activity is True (fail-safe), so no nudge.
    This is the signal SQL can't express, proving the Python re-check runs."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    now = datetime.now(UTC)
    uid, _ = await _seed_user(
        age=timedelta(hours=48), tier="free",
        last_seen_at=now - timedelta(hours=40),  # ~8h after a 48h-ago signup
    )
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == ""


@pytest.mark.asyncio
async def test_act_alert_skips_activated_user(monkeypatch):
    """Alert-capable, in the 3-5d window, empty watchlist, but activated_at is
    stamped → the realigned drip suppresses the nudge for an activated user."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(
        age=timedelta(days=4), tier="premium",
        activated_at=datetime.now(UTC) - timedelta(days=1),
    )
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


# ════════════════════════════════════════════════════════════════════════════
# Activation drip — act_arm (watchlist built, ZERO alert rules, 2-10d in)
#
# The blind spot this stage closes: act_wl and act_alert both require "still no
# recorded activity", so the ENGAGED trialist — watchlist built, no alert ever —
# matched neither and received nothing. These tests pin the cohort filter from
# both sides: it must select the watchlist-having/zero-alert user and must NOT
# leak onto the zero-activity user or the one who already has a rule.
#
# Day 7 is the anchor age throughout: outside act_wl (24-72h) and act_alert
# (3-5d), inside act_arm (2-10d), so a bare `drip_state == "act_arm"` assertion
# is unambiguous about WHICH stage fired.
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_act_arm_fires_for_watchlist_without_alert_rule(monkeypatch):
    """The cohort that had no email at all: 7 days in, premium, a watchlist,
    zero alert rules → act_arm stamped."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(
        age=timedelta(days=7), tier="premium", with_watchlist=True,
    )
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == "act_arm"


@pytest.mark.asyncio
async def test_act_arm_excludes_zero_activity_user(monkeypatch):
    """Same window, but NO watchlist. act_arm is the engaged-cohort stage —
    it must not become a second dormant-user nudge. (At day 7 the dormant
    stages are both out of window, so this user gets nothing.)"""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(age=timedelta(days=7), tier="premium")
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == ""


@pytest.mark.asyncio
async def test_act_arm_excludes_user_who_already_has_an_alert_rule(monkeypatch):
    """Watchlist AND an alert rule → the whole point of the message is already
    done. Telling them to arm their first alert would be false."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(
        age=timedelta(days=7), tier="premium",
        with_watchlist=True, with_alert=True,
    )
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == ""


@pytest.mark.asyncio
async def test_act_arm_skips_free_tier(monkeypatch):
    """Alerts are Pro+. Nudging a Free user toward a gated feature is a dead
    end, so the cohort is tier-restricted exactly as act_alert is."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(
        age=timedelta(days=7), tier="free", with_watchlist=True,
    )
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == ""


@pytest.mark.asyncio
async def test_act_arm_skips_outside_the_signup_window(monkeypatch):
    """Bounded window, not just a lower bound — a user 40 days past signup is
    not mid-trial and must not be swept up."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(
        age=timedelta(days=40), tier="premium", with_watchlist=True,
    )
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == ""


@pytest.mark.asyncio
async def test_act_arm_respects_trial_drip_optout(monkeypatch):
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_user(
        age=timedelta(days=7), tier="premium",
        with_watchlist=True, trial_drip=False,
    )
    async with session_scope() as s:
        await run_activation_drip(s)
    assert await _drip_state(uid) == ""


@pytest.mark.asyncio
async def test_act_arm_dedupes(monkeypatch):
    """Already stamped → never re-sent, even though the user still matches the
    cohort (they still have no alert rule). Sends are tracked so the assertion
    proves absence of a SEND, not just an unchanged token."""
    sends: list[str] = []

    async def _track(to, *_a, **_k):
        sends.append(to)
        return {"id": "test-msg"}

    monkeypatch.setattr(email_module, "send_email", _track)
    uid, email = await _seed_user(
        age=timedelta(days=7), tier="premium",
        with_watchlist=True, drip_state="act_arm",
    )
    async with session_scope() as s:
        await run_activation_drip(s)
    assert email not in sends
    assert await _drip_state(uid) == "act_arm"


@pytest.mark.asyncio
async def test_act_arm_quotes_the_users_real_watchlist_count(monkeypatch):
    """The copy names a number, so the orchestrator has to wire the REAL count
    through — a hardcoded or off-by-one figure is a truthfulness bug in a 1:1
    email. Three items seeded; the rendered body must say three."""
    sends: list[tuple[str, str]] = []

    async def _track(to, _subject, html, *_a, **_k):
        sends.append((to, html))
        return {"id": "test-msg"}

    monkeypatch.setattr(email_module, "send_email", _track)
    _, email = await _seed_user(
        age=timedelta(days=7), tier="premium",
        with_watchlist=True, watchlist_symbols=("AAPL", "MSFT", "NVDA"),
    )
    async with session_scope() as s:
        await run_activation_drip(s)

    mine = [html for (to, html) in sends if to == email]
    assert len(mine) == 1, "engaged trialist should get exactly one act_arm email"
    assert "3 tickers" in mine[0]
    # Sanity: not the seeded-default count from the single-item helper.
    assert "1 ticker," not in mine[0]


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
    # The act_wl nudge is the three-step aha checklist: watchlist, scan,
    # scorecard. All three surfaces are named; none is a performance claim.
    lowered = html.lower()
    assert "watchlist" in lowered
    assert "scan" in lowered
    assert "scorecard" in lowered


def test_activation_watchlist_renderer_free_recipient_drops_the_watchlist_step():
    # act_wl reaches every tier. After the 2026-08-02 cutover a Free recipient
    # has no saved watchlist, so telling them to "add a ticker to your watchlist"
    # is a dead end (403). For has_watchlist=False the nudge must drop that step
    # entirely and lead with "score a ticker you follow" — same aha, still free.
    html = render_activation_watchlist_email("Alex", has_watchlist=False)
    lowered = html.lower()
    assert "Alex" in html
    # The dead-end instruction ("add a ticker … to your watchlist") is gone.
    # (Note: the button URL keeps utm_campaign=activation_watchlist, so we
    # assert on the visible instruction phrases, not the bare word.)
    assert "to your watchlist" not in lowered
    assert "add a ticker you follow" not in lowered
    assert "score a ticker" in lowered
    assert "scan" in lowered
    assert "scorecard" in lowered


def test_activation_alert_renderer():
    html = render_activation_alert_email("Alex")
    assert "Alex" in html
    assert len(html) > 200
    # Realigned to the aha: this stage now leads with the zero-setup public
    # scorecard (the token name "act_alert" is retained only for governor /
    # worker compatibility — see run_activation_drip).
    assert "scorecard" in html.lower()


def test_activation_arm_alerts_renderer_names_the_count_and_the_gap():
    html = render_activation_arm_alerts_email("Alex", watchlist_count=7)
    assert "Alex" in html
    assert len(html) > 200
    # The one personal fact the message is allowed to quote (Rule 7: an
    # ACTIVITY count, not a performance figure).
    assert "7 tickers" in html
    lowered = html.lower()
    assert "alert rule" in lowered
    # Points at the one-click arming surface, which lives on the watchlist page.
    assert "/app/watchlist" in html


def test_activation_arm_alerts_renderer_pluralises_a_single_ticker():
    """A one-item watchlist must not read 'You're watching 1 tickers' — the
    count is the whole personalisation, so getting its grammar wrong is the
    most visible possible defect."""
    html = render_activation_arm_alerts_email("Alex", watchlist_count=1)
    assert "1 ticker," in html
    assert "1 tickers" not in html


def test_activation_arm_alerts_renderer_makes_no_outcome_claim():
    """Rule 1/7. The engaged-trialist message is the one a growth edit would
    most want to sharpen with 'here's what you'd have caught' — which is a
    performance claim, since a missed setup is only regrettable for the return
    it implies. Asserted on rendered HTML: that is what reaches the inbox."""
    lowered = render_activation_arm_alerts_email("Alex", watchlist_count=7).lower()
    for phrase in (
        "you'd have caught", "would have caught", "what you missed",
        "missed out", "since you added", "your best performer",
        "is up", "is down", "gained", "returned", "profit",
        "beat the market", "outperform", "you should",
    ):
        assert phrase not in lowered, f"outcome/advice language — {phrase!r}"


def test_activation_arm_alerts_renderer_carries_no_urgency():
    """Rule 6. Only the user's own real trial date may be mentioned, calmly."""
    lowered = render_activation_arm_alerts_email("Alex", watchlist_count=7).lower()
    # Phrase list mirrors test_lifecycle_governor._URGENCY_LANGUAGE. A bare
    # "only " is deliberately NOT here: it matches prose in the shared email
    # shell's CSS comments, and the scarcity forms are what Rule 6 polices.
    for phrase in ("countdown", "act now", "hurry", "last chance",
                   "don't miss out", "expires in", "limited time",
                   "before it's too late", "only a few", "spots left"):
        assert phrase not in lowered, f"Rule 6 violation — {phrase!r}"


def test_activation_arm_alerts_renderer_trial_note_is_optional_and_calm():
    """The trial line is the single permitted time statement. The trial now
    runs on a card, so the note must name the first-charge date and the
    one-click way out — calmly, with no countdown."""
    ends = datetime(2026, 8, 1, tzinfo=UTC)
    with_note = render_activation_arm_alerts_email(
        "Alex", watchlist_count=7, trial_ends_at=ends,
    )
    assert "1 Aug 2026" in with_note
    lowered_note = with_note.lower()
    assert "first charge" in lowered_note
    assert "cancel in one click" in lowered_note
    without = render_activation_arm_alerts_email("Alex", watchlist_count=7)
    assert "trial runs to" not in without.lower()


def test_annual_upgrade_renderer_each_tier():
    pro = render_annual_upgrade_email("Alex", tier="pro")
    assert "Alex" in pro
    assert "$20" in pro          # Pro annual saving
    assert "Pro" in pro
    premium = render_annual_upgrade_email("Alex", tier="premium")
    assert "Alex" in premium
    assert "$40" in premium     # Premium annual saving
    assert "Premium" in premium


def test_annual_upgrade_renderer_unknown_tier_falls_back():
    """An unexpected tier string must not render blank — falls back to Pro."""
    html = render_annual_upgrade_email("Alex", tier="mystery")
    assert "Alex" in html
    assert "$20" in html         # Pro fallback pitch
