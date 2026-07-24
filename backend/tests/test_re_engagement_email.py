"""Tests for the 2-touch dormant re-engagement series (+ sunset) and the
last_seen_at side effect that drives it.

Covered here: the touch-1 / touch-2 renderers (pure functions), the
activity-only content guard (neither renderer can emit ticker performance),
and the drip sequencing — touch 2 only after touch 1 while still dormant, a
returned user gets neither, and sunset stamps a terminal token without
sending. The governor-level suppression that the sunset token triggers is
pinned in test_lifecycle_governor.py.

The drip function uses a real async session with the in-memory SQLite test
DB. We don't actually deliver mail (settings.resend_api_key is unset in CI,
so send_email returns {skipped: True} which the drip treats as "skip the
token bump") — tests needing a confirmed send monkeypatch send_email.

The last_seen_at bump tests fire signed-cookie requests through the
in-memory ASGI client and assert the column gets populated.
"""
from __future__ import annotations

import asyncio
import inspect
import re
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.main import app
from app.models import User
from app.services.email import (
    RE_ENGAGEMENT_SUBJECT,
    RE_ENGAGEMENT_TOUCH2_SUBJECT,
    RE_TOUCH1_TOKEN,
    RE_TOUCH2_TOKEN,
    render_re_engagement_email,
    render_re_engagement_touch2_email,
    run_re_engagement_drip,
)
from app.services.lifecycle import RE_SUNSET_TOKEN


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ----- renderer ---------------------------------------------------------------

def test_re_engagement_renders_with_name():
    """Touch 1 drops the user's name into the headline, reports system
    activity, and signs off as Christian — the public founder identity."""
    html = render_re_engagement_email("Alice")
    assert "Alice" in html
    assert "scores kept updating" in html
    assert "Christian" in html  # founder sign-off
    # Brand fix from PR #44 — must NEVER regress to chamara@ in this renderer.
    assert "chamara@tapeline.io" not in html
    # Re-engagement CTAs must carry the campaign UTM so analytics can
    # attribute conversions back to this nudge.
    assert "utm_campaign=re_engagement" in html


def test_re_engagement_falls_back_to_trader_label():
    """If we call the renderer with a generic 'trader' placeholder (the
    drip default when User.name is null), the email still reads cleanly."""
    html = render_re_engagement_email("trader")
    assert "Your scores kept updating, trader" in html


def test_touch1_reports_system_activity_with_counts():
    """When the drip passes real trading-day counts, touch 1 surfaces them as
    SYSTEM activity — scanner scoring + scorecard rows + look-up reset — and
    links to both the app and the public scorecard."""
    html = render_re_engagement_email(
        "Alice", trading_days_away=10, scorecard_rows_appended=10,
    )
    assert "10 sessions" in html
    assert "10 dated rows" in html
    assert "look-ups have reset" in html
    assert "/app/scanner" in html      # app link
    assert "/scorecard" in html        # public scorecard link


def test_touch2_is_founder_signed_single_question():
    """Touch 2 is a plain founder note: Christian introduces himself, asks one
    open question, offers a plain return link, thanks the reader."""
    html = render_re_engagement_touch2_email("Alice")
    assert "Hi Alice" in html
    assert "I'm Christian" in html
    assert "what would have made Tapeline worth returning to?" in html
    assert "/app/scanner" in html
    assert "Thanks for giving it a try" in html


# ----- drip filter window -----------------------------------------------------

@pytest.mark.asyncio
async def test_drip_targets_only_dormant_users_in_window():
    """run_re_engagement_drip filters on last_seen_at in [now-16d, now-14d)
    — 48h wide so one missed worker day can't skip the touch. A user
    outside that window (too recent or too dormant already) must not
    receive the email."""
    now = datetime.now(UTC)

    async with session_scope() as s:
        # Fresh — saw the app 2 days ago, must NOT trigger
        u_fresh = User(
            id=f"re_fresh_{int(now.timestamp())}",
            email=f"fresh_{int(now.timestamp())}@example.com",
            name="Fresh", tier="free",
            last_seen_at=now - timedelta(days=2),
        )
        # In the 14-day window — must trigger
        u_target = User(
            id=f"re_target_{int(now.timestamp())}",
            email=f"target_{int(now.timestamp())}@example.com",
            name="Target", tier="free",
            last_seen_at=now - timedelta(days=14, hours=12),
        )
        # Long-dormant 30 days, past the window — must NOT trigger
        u_old = User(
            id=f"re_old_{int(now.timestamp())}",
            email=f"old_{int(now.timestamp())}@example.com",
            name="Old", tier="free",
            last_seen_at=now - timedelta(days=30),
        )
        s.add_all([u_fresh, u_target, u_old])
        await s.commit()

        counts = await run_re_engagement_drip(s)

        # No api key in CI, so send_email skips and we get 0 actual sends.
        # The filter logic still ran — re-read the users and assert no
        # drip_state token was added (skip path doesn't advance state).
        for u_id in (u_fresh.id, u_target.id, u_old.id):
            row = await s.execute(select(User).where(User.id == u_id))
            user = row.scalar_one()
            assert "re14" not in (user.drip_state or "")

        # Cleanup
        for u in (u_fresh, u_target, u_old):
            await s.delete(u)
        await s.commit()

        assert counts == {"re14": 0, "re24": 0, "re_sunset": 0}


@pytest.mark.asyncio
async def test_drip_skips_active_trial_users():
    """A user still on their trial (trial_ends_at in the future) must NOT
    receive the re-engagement email even if last_seen_at is in the
    14-day window — the trial drip is the right channel for them."""
    now = datetime.now(UTC)

    async with session_scope() as s:
        u = User(
            id=f"re_trial_{int(now.timestamp())}",
            email=f"trial_{int(now.timestamp())}@example.com",
            name="OnTrial", tier="premium",
            last_seen_at=now - timedelta(days=14, hours=12),
            trial_ends_at=now + timedelta(days=3),  # still on trial
        )
        s.add(u)
        await s.commit()

        await run_re_engagement_drip(s)

        # User must NOT have re14 token even though dormant — they're on
        # an active trial and the trial drip owns this surface.
        row = await s.execute(select(User).where(User.id == u.id))
        user = row.scalar_one()
        assert "re14" not in (user.drip_state or "")

        await s.delete(user)
        await s.commit()


@pytest.mark.asyncio
async def test_re14_still_fires_after_missed_day(monkeypatch):
    """48h window recovery: last_seen_at 15.5d ago sits a day past the old
    [now-15d, now-14d) window — a single failed/missed drip run used to age
    the user out forever. The widened [now-16d, now-14d) window still
    catches them, exactly once (re14 token dedupes the second run)."""
    import uuid

    import app.services.email as email_module

    sends: list[str] = []

    async def _track(to, *_a, **_k):
        sends.append(to)
        return {"id": "ok"}

    monkeypatch.setattr(email_module, "send_email", _track)

    now = datetime.now(UTC)
    uid = f"re_missed_{uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    async with session_scope() as s:
        u = User(
            id=uid, email=email, name="Missed", tier="free",
            last_seen_at=now - timedelta(days=15, hours=12),
        )
        s.add(u)
        await s.commit()

        await run_re_engagement_drip(s)
        await run_re_engagement_drip(s)  # same-day re-run — token must dedupe

        row = await s.execute(select(User).where(User.id == uid))
        user = row.scalar_one()
        assert "re14" in (user.drip_state or "").split(",")
        assert sends.count(email) == 1, (
            f"expected exactly one re14 email, got {sends.count(email)}"
        )

        await s.delete(user)
        await s.commit()


# ----- last_seen_at side effect ----------------------------------------------

@pytest.mark.asyncio
async def test_dev_bypass_bumps_last_seen_at(client):
    """Hitting /api/me with the dev-bypass token resolves the dev_user
    and bumps last_seen_at via _bump_last_seen. After the hit, the
    column should be populated to roughly 'now'."""
    async with client:
        # Reset any prior bump so we can assert the new write
        async with session_scope() as s:
            result = await s.execute(select(User).where(User.id == "dev_user"))
            existing = result.scalar_one_or_none()
            if existing is not None:
                existing.last_seen_at = None
                await s.commit()

        r = await client.get("/api/me", headers={"Authorization": "Bearer dev-bypass"})
        assert r.status_code == 200

        # Re-read; last_seen_at should be set now.
        async with session_scope() as s:
            result = await s.execute(select(User).where(User.id == "dev_user"))
            user = result.scalar_one_or_none()
            assert user is not None
            assert user.last_seen_at is not None
            # Bumped within the last 5 seconds
            now = datetime.now(UTC)
            seen = user.last_seen_at
            if seen.tzinfo is None:
                seen = seen.replace(tzinfo=UTC)
            assert (now - seen) < timedelta(seconds=5)


def test_async_loop_is_sane():
    """Sanity: confirms the test env can run a trivial coroutine. Used to
    catch test-runner config drift (asyncio_mode etc.)."""
    async def _ok():
        return 1
    assert asyncio.run(_ok()) == 1


# ----- activity-only content guard (the load-bearing compliance piece) -------
#
# Rule 7 (docs/COMPLIANCE_COPY_RULES.md) forbids ever telling a named user how
# THEIR self-selected securities moved. The guard is structural: neither
# renderer accepts an input that could carry ticker performance, so the
# rendered HTML cannot contain it. These two tests pin that as an enforced
# contract, not a guideline.

# Phrases that would report per-user ticker PERFORMANCE.
_PERFORMANCE_BLOCKLIST = [
    r"\bgained\b", r"\blost\b", r"\brallied\b", r"\bsurged\b", r"\bdropped\b",
    r"\bbeat\b", r"vs\.?\s*spy", r"you\s+missed", r"[+]\d+\s*%",
    r"your\s+watchlist[^.<>]{0,40}\b(?:up|down)\b",
]

# Parameter-name fragments that would betray a ticker-performance input path.
# If someone later adds e.g. `watchlist_performance=` or `best_ticker_pct=`,
# the signature test below fails before any copy can ship.
_FORBIDDEN_PARAM_FRAGMENTS = (
    "ticker", "watchlist", "symbol", "performance", "moved", "return",
    "gain", "loss", "pct", "percent", "price", "holding", "position",
    "alpha", "spy",
)


@pytest.mark.parametrize(
    "html",
    [
        render_re_engagement_email(
            "Alice", trading_days_away=11, scorecard_rows_appended=11,
        ),
        render_re_engagement_touch2_email("Alice"),
    ],
    ids=["touch1", "touch2"],
)
def test_renderers_cannot_emit_ticker_performance(html):
    """Rendered HTML for BOTH touches contains none of the performance
    blocklist — even with every activity input populated."""
    lowered = html.lower()
    for pattern in _PERFORMANCE_BLOCKLIST:
        assert re.search(pattern, lowered) is None, (
            f"re-engagement copy leaked a performance phrase matching {pattern!r}"
        )


def test_reengagement_renderers_accept_only_activity_inputs():
    """The stronger guard: neither renderer even ACCEPTS a parameter that
    could carry per-user ticker performance."""
    for fn in (render_re_engagement_email, render_re_engagement_touch2_email):
        for pname in inspect.signature(fn).parameters:
            low = pname.lower()
            for frag in _FORBIDDEN_PARAM_FRAGMENTS:
                assert frag not in low, (
                    f"{fn.__name__} exposes a performance-shaped parameter "
                    f"{pname!r} (fragment {frag!r}) — rule 7 violation risk"
                )


# ----- 2-touch sequencing + sunset -------------------------------------------


def _tracker():
    sends: list[tuple[str, str]] = []

    async def _track(to, subject, *_a, **_k):
        sends.append((to, subject))
        return {"id": "ok"}

    return sends, _track


@pytest.mark.asyncio
async def test_touch1_sends_with_new_subject(monkeypatch):
    """A user in the [14d, 16d) window with no prior token gets touch 1 under
    the normalised subject and the re14 token."""
    import app.services.email as email_module
    sends, track = _tracker()
    monkeypatch.setattr(email_module, "send_email", track)

    now = datetime.now(UTC)
    uid = f"re_t1_{uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    async with session_scope() as s:
        s.add(User(
            id=uid, email=email, name="Ann Example", tier="free",
            last_seen_at=now - timedelta(days=14, hours=12),
        ))
        await s.commit()

        await run_re_engagement_drip(s)

        row = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        assert RE_TOUCH1_TOKEN in (row.drip_state or "").split(",")
        assert (email, RE_ENGAGEMENT_SUBJECT) in sends

        await s.delete(row)
        await s.commit()


@pytest.mark.asyncio
async def test_touch2_fires_only_after_touch1_and_while_dormant(monkeypatch):
    """Touch 2 (re24) fires at ~24d dormant ONLY for a user who already got
    touch 1 (re14 present). A same-age user WITHOUT re14 gets neither touch."""
    import app.services.email as email_module
    sends, track = _tracker()
    monkeypatch.setattr(email_module, "send_email", track)

    now = datetime.now(UTC)
    ready_id = f"re2_ready_{uuid.uuid4().hex}"
    ready_email = f"{ready_id}@example.com"
    no1_id = f"re2_no1_{uuid.uuid4().hex}"
    no1_email = f"{no1_id}@example.com"
    async with session_scope() as s:
        s.add_all([
            User(
                id=ready_id, email=ready_email, name="Ready", tier="free",
                last_seen_at=now - timedelta(days=25),
                drip_state=RE_TOUCH1_TOKEN,
            ),
            User(
                id=no1_id, email=no1_email, name="NoTouch1", tier="free",
                last_seen_at=now - timedelta(days=25),
                drip_state="",
            ),
        ])
        await s.commit()

        await run_re_engagement_drip(s)

        ready = (await s.execute(select(User).where(User.id == ready_id))).scalar_one()
        no1 = (await s.execute(select(User).where(User.id == no1_id))).scalar_one()

        # Had touch 1 → touch 2 fires.
        assert RE_TOUCH2_TOKEN in (ready.drip_state or "").split(",")
        assert (ready_email, RE_ENGAGEMENT_TOUCH2_SUBJECT) in sends

        # No touch 1, and 25d is past the touch-1 window → nothing at all.
        assert RE_TOUCH2_TOKEN not in (no1.drip_state or "")
        assert RE_TOUCH1_TOKEN not in (no1.drip_state or "")
        assert no1_email not in [to for (to, _s) in sends]

        # Idempotent: a second run doesn't re-send touch 2 to this user.
        await run_re_engagement_drip(s)
        assert sum(1 for (to, _s) in sends if to == ready_email) == 1

        for u in (ready, no1):
            await s.delete(u)
        await s.commit()


@pytest.mark.asyncio
async def test_returned_user_gets_neither_touch(monkeypatch):
    """A user whose last_seen_at was refreshed (they came back) sits in none of
    the dormancy windows, so neither touch fires — even if they still carry the
    re14 token from an earlier dormant spell."""
    import app.services.email as email_module
    sends, track = _tracker()
    monkeypatch.setattr(email_module, "send_email", track)

    now = datetime.now(UTC)
    uid = f"re_ret_{uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    async with session_scope() as s:
        s.add(User(
            id=uid, email=email, name="Returned", tier="free",
            last_seen_at=now - timedelta(days=1),   # active again
            drip_state=RE_TOUCH1_TOKEN,
        ))
        await s.commit()

        await run_re_engagement_drip(s)

        row = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        assert RE_TOUCH2_TOKEN not in (row.drip_state or "")
        assert RE_SUNSET_TOKEN not in (row.drip_state or "")
        assert email not in [to for (to, _s) in sends]

        await s.delete(row)
        await s.commit()


@pytest.mark.asyncio
async def test_sunset_stamps_terminal_token_without_sending(monkeypatch):
    """A user who received touch 2 and stayed dormant past the touch-2 window
    is stamped with the terminal sunset token and sent NOTHING further."""
    import app.services.email as email_module
    sends, track = _tracker()
    monkeypatch.setattr(email_module, "send_email", track)

    now = datetime.now(UTC)
    uid = f"re_sunset_{uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    async with session_scope() as s:
        s.add(User(
            id=uid, email=email, name="Done", tier="free",
            last_seen_at=now - timedelta(days=30),   # past the [24d,26d) window
            drip_state=f"{RE_TOUCH1_TOKEN},{RE_TOUCH2_TOKEN}",
        ))
        await s.commit()

        counts = await run_re_engagement_drip(s)

        row = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        assert RE_SUNSET_TOKEN in (row.drip_state or "").split(",")
        assert email not in [to for (to, _s) in sends]  # sunset sends nothing
        assert counts["re_sunset"] >= 1

        await s.delete(row)
        await s.commit()
