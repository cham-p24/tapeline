"""Trial-drip truthfulness + expiry-day single-send guarantee.

Pins two bugs found in the 2026-07 email audit:

1. STALE FREEMIUM COPY — the 2026-06-20 freemium retune made Free
   live-but-limited (tier.py: LIVE data, top-10 scanner rows, 5 ticker
   look-ups/day, 3-ticker watchlist), but the day-7 / day-13 / T+0 trial
   emails still sold against the OLD Free tier ("top 20 tickers, 24-hour
   delayed", "watchlist capped at 5 tickers"). The renderers now quote the
   tier.py constants directly, so these tests assert the dead claims are
   gone AND that the quoted caps track the constants — a future retune
   updates the copy automatically and these assertions keep holding.

2. EXPIRY-DAY DOUBLE-SEND — the hourly worker downgrade
   (signal_publisher._downgrade_expired_trials) used to fire
   render_trial_ended_email the hour a trial lapsed, and the daily drip's
   T+0 "expired" stage fired render_trial_expired_email within the same
   ~24h: two end-of-trial emails per user. The worker send was removed —
   run_daily_drip owns T+0, dedup'd via users.drip_state, gated on the
   TRIAL_DRIP preference, and carrying List-Unsubscribe headers.

Also covers the day-11 deadline personalisation: the T-3 email hardcoded
"add a card before Friday", which was wrong for ~6/7ths of users; it now
formats the user's actual trial_ends_at.

Assertion strategy mirrors test_lifecycle_emails.py: assert on the SPECIFIC
seeded user's row / captured sends, never on aggregate counts — the test DB
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
    render_subscription_canceled_email,
    render_trial_day7_email,
    render_trial_day11_email,
    render_trial_day13_email,
    render_trial_ended_email,
    render_trial_expired_email,
    run_daily_drip,
)
from app.services.tier import (
    FREE_DAILY_LOOKUPS,
    FREE_SCANNER_ROWS,
    FREE_WATCHLIST_TICKERS,
)
from app.workers.signal_publisher import _downgrade_expired_trials

# Claims that describe the pre-2026-06-20 Free tier. None of these may ever
# appear in customer-facing email copy again.
_DEAD_TIER_CLAIMS = ("top 20 tickers", "24-hour", "capped at 5 tickers")


# ── Seed helper ──────────────────────────────────────────────────────────────

async def _seed_trial_user(
    *,
    ends_at: datetime,
    tier: str = "premium",
    drip_state: str = "",
) -> tuple[str, str]:
    """Insert a card-less trial user with the given trial_ends_at (in the
    past => already expired). Returns (user_id, email). email_prefs stays
    at the column default (all categories on, incl. TRIAL_DRIP)."""
    uid = f"td_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    async with session_scope() as s:
        s.add(User(
            id=uid,
            email=email,
            name="DripTest",
            tier=tier,
            password_hash="not-used",
            drip_state=drip_state,
            trial_ends_at=ends_at,
        ))
        await s.commit()
    return uid, email


async def _user_row(uid: str) -> User:
    async with session_scope() as s:
        return (await s.execute(select(User).where(User.id == uid))).scalar_one()


# ════════════════════════════════════════════════════════════════════════════
# Renderer copy — the emails must describe the Free tier that actually exists
# ════════════════════════════════════════════════════════════════════════════

def test_no_trial_email_sells_the_dead_free_tier():
    """None of the trial-lifecycle renderers may repeat the pre-retune
    claims. Parametrising over strings would hide which renderer regressed,
    so loop with a labelled assert instead."""
    outputs = {
        "day7": render_trial_day7_email("Alex", None),
        "day11": render_trial_day11_email("Alex", None),
        "day13": render_trial_day13_email("Alex", None),
        "expired": render_trial_expired_email("Alex", None),
        "trial_ended": render_trial_ended_email("Alex"),
        "subscription_canceled": render_subscription_canceled_email(
            "Alex", tier="pro", period_end_iso=None,
        ),
    }
    for name, html in outputs.items():
        for claim in _DEAD_TIER_CLAIMS:
            assert claim not in html, (
                f"{name} still says {claim!r} — that Free tier was retired "
                f"by the 2026-06-20 freemium retune (Free is live-but-limited "
                f"now; see services/tier.py FREE_* constants)"
            )


def test_day7_quotes_current_free_caps():
    html = render_trial_day7_email("Alex", None)
    assert f"top {FREE_SCANNER_ROWS} rows" in html
    assert f"look-ups cap at {FREE_DAILY_LOOKUPS} a day" in html
    assert f"watchlist caps at {FREE_WATCHLIST_TICKERS} tickers" in html


def test_day13_quotes_current_free_caps():
    html = render_trial_day13_email("Alex", None)
    assert f"top {FREE_SCANNER_ROWS} rows" in html
    assert f"look-ups at {FREE_DAILY_LOOKUPS} a day" in html


def test_expired_quotes_current_free_caps():
    html = render_trial_expired_email("Alex", None)
    assert f"top {FREE_SCANNER_ROWS} scanner rows" in html
    assert f"{FREE_DAILY_LOOKUPS} ticker look-ups a day" in html
    assert f"capped at {FREE_WATCHLIST_TICKERS} tickers on Free" in html


def test_subscription_canceled_quotes_current_free_caps():
    html = render_subscription_canceled_email("Alex", tier="pro", period_end_iso=None)
    assert f"top {FREE_SCANNER_ROWS} scanner rows" in html
    assert f"{FREE_DAILY_LOOKUPS} ticker look-ups a day" in html


# ════════════════════════════════════════════════════════════════════════════
# Day-11 deadline — real trial_ends_at date, not a hardcoded weekday
# ════════════════════════════════════════════════════════════════════════════

def test_day11_renders_actual_deadline():
    """2026-07-14 is a Tuesday — the rendered deadline must be that date,
    and the old hardcoded 'before Friday' must be gone."""
    html = render_trial_day11_email(
        "Alex", None, trial_ends_at=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
    )
    assert "before Tuesday, July 14" in html
    assert "Friday" not in html


def test_day11_falls_back_without_deadline():
    """No trial_ends_at (admin preview, legacy callers) → generic-but-honest
    fallback instead of a made-up weekday."""
    html = render_trial_day11_email("Alex", None)
    assert "before your trial ends" in html
    assert "Friday" not in html


@pytest.mark.asyncio
async def test_drip_day11_passes_real_deadline(monkeypatch):
    """run_daily_drip wires the user's trial_ends_at into the T-3 renderer."""
    sends: list[tuple[str, str, str]] = []

    async def _track(to, subject, html, *_a, **_k):
        sends.append((to, subject, html))
        return {"id": "ok"}

    monkeypatch.setattr(email_module, "send_email", _track)

    ends_at = datetime.now(UTC) + timedelta(days=2, hours=12)
    uid, email = await _seed_trial_user(ends_at=ends_at)

    async with session_scope() as s:
        await run_daily_drip(s)

    mine = [h for (to, _subj, h) in sends if to == email]
    assert len(mine) == 1, "day-11 window user should get exactly one email"
    expected_deadline = f"{ends_at:%A, %B} {ends_at.day}"
    assert f"before {expected_deadline}" in mine[0]
    assert "before your trial ends" not in mine[0]
    assert "11" in (await _user_row(uid)).drip_state.split(",")


# ════════════════════════════════════════════════════════════════════════════
# Expiry day — worker downgrades silently; the drip owns the single T+0 email
# ════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_worker_downgrade_sends_no_email(monkeypatch):
    """The hourly downgrade drops tier to free but must NOT email — the
    T+0 'expired' drip stage is the one end-of-trial email. (Before this
    guard, users got render_trial_ended_email from the worker AND
    render_trial_expired_email from the drip on the same day.)"""
    sends: list[str] = []

    async def _track(to, *_a, **_k):
        sends.append(to)
        return {"id": "ok"}

    monkeypatch.setattr(email_module, "send_email", _track)
    uid, email = await _seed_trial_user(
        ends_at=datetime.now(UTC) - timedelta(hours=6),
    )

    await _downgrade_expired_trials()

    row = await _user_row(uid)
    assert row.tier == "free", "expired card-less trial must drop to free"
    assert email not in sends, (
        "worker downgrade emailed the user — the daily drip's 'expired' "
        "stage owns the T+0 email (double-send regression)"
    )


@pytest.mark.asyncio
async def test_expiry_day_sends_exactly_one_email(monkeypatch):
    """Full expiry-day sequence: hourly worker downgrade, then the daily
    drip (possibly more than once — worker restarts re-run it). The user
    must receive exactly ONE end-of-trial email, stamped 'expired'."""
    sends: list[tuple[str, str]] = []

    async def _track(to, subject, *_a, **_k):
        sends.append((to, subject))
        return {"id": "ok"}

    monkeypatch.setattr(email_module, "send_email", _track)
    uid, email = await _seed_trial_user(
        ends_at=datetime.now(UTC) - timedelta(hours=6),
    )

    await _downgrade_expired_trials()
    async with session_scope() as s:
        await run_daily_drip(s)
    async with session_scope() as s:  # second pass = same-day worker restart
        await run_daily_drip(s)

    mine = [(to, subj) for (to, subj) in sends if to == email]
    assert len(mine) == 1, f"expected exactly one expiry email, got {mine}"
    assert mine[0][1] == "Your Tapeline trial ended"
    assert "expired" in (await _user_row(uid)).drip_state.split(",")
