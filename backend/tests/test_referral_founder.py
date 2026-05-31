"""Referral leaderboard + milestones + founder-touch (PR3).

Covers conversion levers #5 (referral momentum) and #4 (personal founder
hello):

  1. run_founder_touch_drip — one-shot personal note to a HIGH-VALUE, ENGAGED
     early user: signed up 5-7 days ago, on an active Premium trial OR paying
     (stripe_customer_id), AND has ≥1 watchlist item. Stamped on
     User.founder_touch_sent_at (its own column, front-loaded in migration
     0029 — so the feature ships migration-free). Gated on
     EmailPref.RE_ENGAGEMENT.

  2. run_referral_milestone_drip — celebratory note at 3 / 5 / 10 / 25
     confirmed signups. Sends only the HIGHEST newly-crossed tier, dedup'd
     per-tier via "ref_m{n}" tokens in User.drip_state. Transactional reward
     mail (not email_prefs-gated).

  3. /api/referrals/leaderboard — top referrers, privacy-masked, plus the
     caller's own rank. _mask_referrer is unit-tested directly for the masking
     contract; the endpoint test asserts wiring + ordering + no-PII-leak.

Both drips only stamp on a NON-skipped send. send_email returns
{"skipped": True} without RESEND_API_KEY (always the case in CI), so the
"fires" tests monkeypatch send_email to a delivered result, while the
"skipped-no-stamp" tests omit the patch to mirror CI's real no-key behaviour.

Assertion strategy mirrors test_lifecycle_emails.py: assert on the SPECIFIC
seeded user's state, never aggregate counts — the test DB is shared for the
whole session, so other tests' users can inflate the orchestrator's return
counts.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

import app.services.email as email_module
from app.db import session_scope
from app.main import app
from app.models import User, WatchlistItem
from app.routers.referrals import _mask_referrer
from app.services.email import (
    render_founder_touch_email,
    render_referral_milestone_email,
    run_founder_touch_drip,
    run_referral_milestone_drip,
)
from app.services.email_prefs import DEFAULT_PREFS, EmailPref


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _fake_send_ok(*_a, **_k):
    """A delivered send — no 'skipped' key, so the drip stamps state."""
    return {"id": "test-msg"}


# ── Seed helpers ─────────────────────────────────────────────────────────────

async def _seed_ft_user(
    *,
    age: timedelta,
    tier: str = "premium",
    trial: bool = False,
    paid: bool = False,
    with_watchlist: bool = False,
    re_engagement: bool = True,
    ft_sent: datetime | None = None,
) -> tuple[str, str]:
    """Seed a founder-touch candidate. `trial` sets a future trial_ends_at;
    `paid` sets a stripe_customer_id; `with_watchlist` adds the engagement
    artefact the drip requires. Returns (user_id, email)."""
    uid = f"ft_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    prefs = DEFAULT_PREFS
    if not re_engagement:
        prefs &= ~int(EmailPref.RE_ENGAGEMENT)
    now = datetime.now(UTC)
    kwargs: dict = {
        "id": uid, "email": email, "name": "FTTest", "tier": tier,
        "password_hash": "not-used", "email_prefs": prefs,
        "created_at": now - age, "founder_touch_sent_at": ft_sent,
    }
    if trial:
        kwargs["trial_ends_at"] = now + timedelta(days=7)
    if paid:
        kwargs["stripe_customer_id"] = f"cus_{uid}"
    async with session_scope() as s:
        s.add(User(**kwargs))
        if with_watchlist:
            s.add(WatchlistItem(user_id=uid, symbol="AAPL"))
        await s.commit()
    return uid, email


async def _seed_referrer_with(n: int, *, drip_state: str = "") -> tuple[str, str]:
    """A referrer plus `n` accounts that list them as referred_by. Returns
    (referrer_id, referrer_email)."""
    rid = f"refr_{_uuid.uuid4().hex}"
    email = f"{rid}@example.com"
    async with session_scope() as s:
        s.add(User(
            id=rid, email=email, name="Refr Owner", tier="premium",
            password_hash="not-used", email_prefs=DEFAULT_PREFS,
            drip_state=drip_state,
        ))
        for i in range(n):
            cid = f"{rid}_c{i}"
            s.add(User(
                id=cid, email=f"{cid}@example.com", name="Child",
                tier="free", password_hash="x", email_prefs=DEFAULT_PREFS,
                referred_by=rid,
            ))
        await s.commit()
    return rid, email


async def _drip_state(uid: str) -> str:
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        return u.drip_state or ""


async def _ft_sent(uid: str):
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        return u.founder_touch_sent_at


# ════════════════════════════════════════════════════════════════════════════
# Renderers — smoke
# ════════════════════════════════════════════════════════════════════════════

def test_founder_touch_renderer():
    html = render_founder_touch_email("Alex")
    assert "Alex" in html
    assert "Christian" in html          # founder signature
    assert "reply" in html.lower()      # the one ask: hit reply
    assert len(html) > 200


def test_founder_touch_renderer_fallback_name():
    html = render_founder_touch_email("there")
    assert "Hey there" in html


def test_referral_milestone_renderer_basic():
    html = render_referral_milestone_email("Alex", milestone=3, total_signups=3)
    assert "Alex" in html
    assert "3" in html
    assert "Premium" in html
    assert len(html) > 200


def test_referral_milestone_renderer_free_year_line():
    near = render_referral_milestone_email("Alex", milestone=10, total_signups=11)
    assert "free year" in near.lower()
    past = render_referral_milestone_email("Alex", milestone=25, total_signups=25)
    assert "free year" in past.lower()


# ════════════════════════════════════════════════════════════════════════════
# Founder-touch drip — run_founder_touch_drip
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_founder_touch_fires_for_engaged_trial(monkeypatch):
    """6 days in, active Premium trial, has a watchlist ticker → stamped."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_ft_user(age=timedelta(days=6), trial=True, with_watchlist=True)
    async with session_scope() as s:
        await run_founder_touch_drip(s)
    assert await _ft_sent(uid) is not None


@pytest.mark.asyncio
async def test_founder_touch_fires_for_engaged_paid(monkeypatch):
    """Paying customer (stripe_customer_id) in-window with a watchlist → stamped."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_ft_user(
        age=timedelta(days=6), tier="pro", paid=True, with_watchlist=True,
    )
    async with session_scope() as s:
        await run_founder_touch_drip(s)
    assert await _ft_sent(uid) is not None


@pytest.mark.asyncio
async def test_founder_touch_skips_no_watchlist(monkeypatch):
    """In-window trial user who never added a ticker → not 'engaged', skipped."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_ft_user(age=timedelta(days=6), trial=True, with_watchlist=False)
    async with session_scope() as s:
        await run_founder_touch_drip(s)
    assert await _ft_sent(uid) is None


@pytest.mark.asyncio
async def test_founder_touch_skips_free_unpaid(monkeypatch):
    """Engaged + in-window but neither paying nor on an active trial → not
    high-value, so excluded by the paid-OR-trial gate."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_ft_user(age=timedelta(days=6), tier="free", with_watchlist=True)
    async with session_scope() as s:
        await run_founder_touch_drip(s)
    assert await _ft_sent(uid) is None


@pytest.mark.asyncio
async def test_founder_touch_skips_too_new(monkeypatch):
    """4 days in → below the 5-day floor, too early."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_ft_user(age=timedelta(days=4), trial=True, with_watchlist=True)
    async with session_scope() as s:
        await run_founder_touch_drip(s)
    assert await _ft_sent(uid) is None


@pytest.mark.asyncio
async def test_founder_touch_skips_too_old(monkeypatch):
    """9 days in → past the 7-day ceiling."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_ft_user(age=timedelta(days=9), trial=True, with_watchlist=True)
    async with session_scope() as s:
        await run_founder_touch_drip(s)
    assert await _ft_sent(uid) is None


@pytest.mark.asyncio
async def test_founder_touch_dedupes(monkeypatch):
    """founder_touch_sent_at already set → one note ever, never re-sent."""
    already = datetime.now(UTC) - timedelta(days=1)
    _, email = await _seed_ft_user(
        age=timedelta(days=6), trial=True, with_watchlist=True, ft_sent=already,
    )
    sends: list[str] = []

    async def _track(to, *_a, **_k):
        sends.append(to)
        return {"id": "ok"}

    monkeypatch.setattr(email_module, "send_email", _track)
    async with session_scope() as s:
        await run_founder_touch_drip(s)
    assert email not in sends


@pytest.mark.asyncio
async def test_founder_touch_respects_re_engagement_optout(monkeypatch):
    """In-window engaged user with RE_ENGAGEMENT cleared → no send."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    uid, _ = await _seed_ft_user(
        age=timedelta(days=6), trial=True, with_watchlist=True, re_engagement=False,
    )
    async with session_scope() as s:
        await run_founder_touch_drip(s)
    assert await _ft_sent(uid) is None


@pytest.mark.asyncio
async def test_founder_touch_skipped_send_does_not_stamp():
    """No RESEND_API_KEY → send_email returns skipped:True → not stamped (next
    pass retries once the key is live). No monkeypatch, mirroring CI."""
    uid, _ = await _seed_ft_user(age=timedelta(days=6), trial=True, with_watchlist=True)
    async with session_scope() as s:
        await run_founder_touch_drip(s)
    assert await _ft_sent(uid) is None


# ════════════════════════════════════════════════════════════════════════════
# Referral-milestone drip — run_referral_milestone_drip
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_milestone_fires_at_three(monkeypatch):
    """3 confirmed signups → ref_m3 stamped."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    rid, _ = await _seed_referrer_with(3)
    async with session_scope() as s:
        await run_referral_milestone_drip(s)
    assert "ref_m3" in await _drip_state(rid)


@pytest.mark.asyncio
async def test_milestone_picks_highest_crossed(monkeypatch):
    """6 signups crosses both 3 and 5 → only the HIGHEST tier (ref_m5) fires."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    rid, _ = await _seed_referrer_with(6)
    async with session_scope() as s:
        await run_referral_milestone_drip(s)
    state = await _drip_state(rid)
    assert "ref_m5" in state
    assert "ref_m3" not in state


@pytest.mark.asyncio
async def test_milestone_skips_below_threshold(monkeypatch):
    """2 signups → below the smallest milestone (3), nothing stamped."""
    monkeypatch.setattr(email_module, "send_email", _fake_send_ok)
    rid, _ = await _seed_referrer_with(2)
    async with session_scope() as s:
        await run_referral_milestone_drip(s)
    assert await _drip_state(rid) == ""


@pytest.mark.asyncio
async def test_milestone_dedupes(monkeypatch):
    """Already stamped ref_m3 → that tier never re-sends."""
    rid, email = await _seed_referrer_with(3, drip_state="ref_m3")
    sends: list[str] = []

    async def _track(to, *_a, **_k):
        sends.append(to)
        return {"id": "ok"}

    monkeypatch.setattr(email_module, "send_email", _track)
    async with session_scope() as s:
        await run_referral_milestone_drip(s)
    assert email not in sends
    assert await _drip_state(rid) == "ref_m3"


@pytest.mark.asyncio
async def test_milestone_skipped_send_does_not_stamp():
    """No RESEND_API_KEY → skipped:True → not stamped. No monkeypatch."""
    rid, _ = await _seed_referrer_with(3)
    async with session_scope() as s:
        await run_referral_milestone_drip(s)
    assert await _drip_state(rid) == ""


# ════════════════════════════════════════════════════════════════════════════
# Leaderboard masking — _mask_referrer (privacy contract, pure unit)
# ════════════════════════════════════════════════════════════════════════════

def test_mask_referrer_caller_is_you():
    u = SimpleNamespace(name="Sam Smith", email="sam@example.com")
    assert _mask_referrer(u, is_caller=True) == "You"


def test_mask_referrer_full_name_first_plus_initial():
    u = SimpleNamespace(name="Sam Smith", email="sam@example.com")
    assert _mask_referrer(u, is_caller=False) == "Sam S."


def test_mask_referrer_single_name_passes_through():
    u = SimpleNamespace(name="Sam", email="sam@example.com")
    assert _mask_referrer(u, is_caller=False) == "Sam"


def test_mask_referrer_no_name_masks_email_local():
    u = SimpleNamespace(name="", email="samuel@example.com")
    out = _mask_referrer(u, is_caller=False)
    assert out == "sa***"
    assert "@" not in out


def test_mask_referrer_none_user():
    assert _mask_referrer(None, is_caller=False) == "A Tapeline user"


# ════════════════════════════════════════════════════════════════════════════
# Leaderboard endpoint — wiring + ordering + no-PII-leak
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_leaderboard_endpoint(client):
    """Seeds two referrers, hits the endpoint as the dev-bypass user, and
    asserts: 200, the documented keys, rows ordered by signups desc, and NO
    PII (no email addresses, no full seeded names) in any display label."""
    await _seed_referrer_with(8)
    await _seed_referrer_with(4)
    async with client:
        # Touch /api/me so the dev-bypass user row exists.
        await client.get("/api/me", headers={"Authorization": "Bearer dev-bypass"})
        r = await client.get(
            "/api/referrals/leaderboard",
            headers={"Authorization": "Bearer dev-bypass"},
        )
        assert r.status_code == 200
        body = r.json()
        assert {"leaderboard", "your_rank", "your_signups", "total_referrers"} <= set(body)
        lb = body["leaderboard"]
        assert isinstance(lb, list) and len(lb) >= 1
        # Strictly non-increasing by signup count.
        sigs = [row["signups"] for row in lb]
        assert sigs == sorted(sigs, reverse=True)
        # Privacy: never leak a raw email or the full seeded name.
        for row in lb:
            assert "@" not in row["display"]
            assert row["display"] != "Refr Owner"
            assert set(row) >= {"rank", "display", "is_you", "signups"}
