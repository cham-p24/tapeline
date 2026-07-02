"""Day-1 watchlist seeding on onboarding submit (routers/me.py).

Onboarding promises "we'll pre-tune your scanner filters" — the seeder makes
that promise real on the alerts/digest side by giving an EMPTY watchlist the
top live-scored tickers at submit time. Contract pinned here:

  1. Submit with a chosen sector → 3 items, all from that sector's canonical
     bucket, and the response reports which symbols were seeded.
  2. Submit skipped / no sector → overall top-3 (still 3 items).
  3. NEVER overwrites: a user who already has watchlist items gets nothing
     added, nothing removed.
  4. Idempotent: re-submitting onboarding doesn't duplicate the seeds.
  5. Seeding does NOT stamp activated_at — activation measures the user's
     own first add (Growth Playbook §4.2), not ours.

Tickers are inserted with the full live_clauses() quality bar (fresh
updated_at, clean asset_class, 2+ factors, change/confidence present) and
deleted again in each test's finally block so this suite leaves no
high-score ghosts behind for other suites ranking Ticker by score.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import app
from app.models import Ticker, User, WatchlistItem


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _random_email() -> str:
    return f"seed-{uuid.uuid4().hex[:10]}@example.com"


def _patch_signup_gates(monkeypatch) -> None:
    """Bypass Turnstile + IP/fingerprint caps for loopback multi-signup tests
    (same shape as test_smoke._patch_signup_gates)."""
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_args, **_kwargs):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


# Six clean, live rows: three Energy, three Information Technology. Scores are
# high-but-valid so the sector query deterministically finds >=3 rows; sector
# membership (not exact symbols) is asserted so pre-existing rows from other
# suites can't flake these tests.
_SEED_SYMBOLS = ["SEEDE1", "SEEDE2", "SEEDE3", "SEEDT1", "SEEDT2", "SEEDT3"]


def _ticker_rows() -> list[dict]:
    now = datetime.now(UTC)
    rows = []
    for i, (sym, sector) in enumerate([
        ("SEEDE1", "Energy"),
        ("SEEDE2", "Energy"),
        ("SEEDE3", "Energy"),
        ("SEEDT1", "Information Technology"),
        ("SEEDT2", "Information Technology"),
        ("SEEDT3", "Information Technology"),
    ]):
        rows.append({
            "symbol": sym,
            "name": f"Seed Test Co {i}",
            "sector": sector,
            "asset_class": "stock",
            "score": 97.0 - i,          # valid (<=100), high enough to rank
            "signal": "HIGH CONVICTION",
            "price": 50.0 + i,
            "change_pct_1d": 1.0,       # live_clauses: must be non-null
            "confidence_pct": 80.0,     # live_clauses: must be non-null
            "sub_trend": 70.0,          # live_clauses: >=2 populated factors
            "sub_momentum": 65.0,
            "reason": "Strong trend with momentum confirmation.",
            "updated_at": now,          # inside the relative freshness window
        })
    return rows


async def _insert_seed_tickers() -> None:
    async with SessionLocal() as s:
        for row in _ticker_rows():
            await s.merge(Ticker(**row))  # merge → rerun-safe on a dirty dev DB
        await s.commit()


async def _delete_seed_tickers() -> None:
    async with SessionLocal() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SEED_SYMBOLS)))
        await s.commit()


async def _signup(client: httpx.AsyncClient):
    r = await client.post(
        "/api/auth/signup",
        json={"email": _random_email(), "password": "TestPassword!2026", "name": "Seed"},
    )
    assert r.status_code == 200, r.text
    return r.cookies, r.json()["user"]["id"]


async def _sector_of(symbol: str) -> str | None:
    async with SessionLocal() as s:
        t = (await s.execute(select(Ticker).where(Ticker.symbol == symbol))).scalar_one_or_none()
        return t.sector if t else None


async def _activated_at(user_id: str):
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        return u.activated_at


@pytest.mark.asyncio
async def test_onboarding_seeds_top3_from_first_chosen_sector(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    await _insert_seed_tickers()
    try:
        async with client:
            cookies, user_id = await _signup(client)

            r = await client.post(
                "/api/me/onboarding",
                json={"sectors_of_interest": ["energy", "technology"]},
                cookies=cookies,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["onboarding_completed_at"] is not None
            seeded = body["watchlist_seeded"]
            assert len(seeded) == 3

            # Every seeded symbol must be from the FIRST chosen sector's
            # canonical bucket ("energy" → "Energy").
            for sym in seeded:
                assert await _sector_of(sym) == "Energy", (
                    f"{sym} seeded from outside the user's first sector"
                )

            # The watchlist itself reflects the seeds, each with honest
            # provenance in the note and a baseline score for smart alerts.
            r_wl = await client.get("/api/watchlist", cookies=cookies)
            assert r_wl.status_code == 200
            items = r_wl.json()["items"]
            assert {i["symbol"] for i in items} == set(seeded)
            assert all(i["baseline_score"] is not None for i in items)
            assert all("Starter pick" in (i["note"] or "") for i in items)
            # Items land in a real (auto-created default) list, so the
            # multi-list UI and the EOD digest both see them.
            assert all(i["watchlist_id"] is not None for i in items)

            # Seeding must NOT stamp activation — that's the user's own move.
            assert await _activated_at(user_id) is None
    finally:
        await _delete_seed_tickers()


@pytest.mark.asyncio
async def test_onboarding_skip_seeds_overall_top3(client, monkeypatch):
    """No sector chosen (skip) → seeder falls back to the overall top of the
    live universe so alerts + digest still have fuel from day 1."""
    _patch_signup_gates(monkeypatch)
    await _insert_seed_tickers()
    try:
        async with client:
            cookies, _user_id = await _signup(client)

            r = await client.post("/api/me/onboarding", json={"skipped": True}, cookies=cookies)
            assert r.status_code == 200, r.text
            assert len(r.json()["watchlist_seeded"]) == 3

            r_wl = await client.get("/api/watchlist", cookies=cookies)
            assert r_wl.json()["count"] == 3
    finally:
        await _delete_seed_tickers()


@pytest.mark.asyncio
async def test_onboarding_never_touches_existing_watchlist(client, monkeypatch):
    """A user who already added tickers keeps their watchlist EXACTLY as-is —
    no additions, no removals, regardless of chosen sectors."""
    _patch_signup_gates(monkeypatch)
    await _insert_seed_tickers()
    try:
        async with client:
            cookies, _user_id = await _signup(client)

            r_add = await client.post(
                "/api/watchlist", json={"symbol": "SEEDT1"}, cookies=cookies
            )
            assert r_add.status_code == 200, r_add.text

            r = await client.post(
                "/api/me/onboarding",
                json={"sectors_of_interest": ["energy"]},
                cookies=cookies,
            )
            assert r.status_code == 200, r.text
            assert r.json()["watchlist_seeded"] == []

            r_wl = await client.get("/api/watchlist", cookies=cookies)
            items = r_wl.json()["items"]
            assert [i["symbol"] for i in items] == ["SEEDT1"]
    finally:
        await _delete_seed_tickers()


@pytest.mark.asyncio
async def test_onboarding_resubmit_does_not_duplicate_seeds(client, monkeypatch):
    """Onboarding stays open for edits from /app/settings — a re-submit must
    not re-seed on top of the first run's items."""
    _patch_signup_gates(monkeypatch)
    await _insert_seed_tickers()
    try:
        async with client:
            cookies, _user_id = await _signup(client)

            r1 = await client.post(
                "/api/me/onboarding",
                json={"sectors_of_interest": ["technology"]},
                cookies=cookies,
            )
            assert r1.status_code == 200
            first = set(r1.json()["watchlist_seeded"])
            assert len(first) == 3

            r2 = await client.post(
                "/api/me/onboarding",
                json={"sectors_of_interest": ["energy"]},
                cookies=cookies,
            )
            assert r2.status_code == 200
            assert r2.json()["watchlist_seeded"] == []

            r_wl = await client.get("/api/watchlist", cookies=cookies)
            assert r_wl.json()["count"] == 3
            assert {i["symbol"] for i in r_wl.json()["items"]} == first
    finally:
        await _delete_seed_tickers()


@pytest.mark.asyncio
async def test_watchlist_items_survive_seed_ticker_cleanup(client, monkeypatch):
    """Sanity: seeded WatchlistItem rows have no FK on symbol, so deleting the
    test tickers (this suite's cleanup) can't cascade a user's watchlist away.
    Also proves the seeded rows are ordinary items the user can delete."""
    _patch_signup_gates(monkeypatch)
    await _insert_seed_tickers()
    try:
        async with client:
            cookies, user_id = await _signup(client)
            r = await client.post(
                "/api/me/onboarding",
                json={"sectors_of_interest": ["energy"]},
                cookies=cookies,
            )
            assert r.status_code == 200
            assert len(r.json()["watchlist_seeded"]) == 3

            # User can remove a seeded item like any other.
            r_wl = await client.get("/api/watchlist", cookies=cookies)
            first_id = r_wl.json()["items"][0]["id"]
            r_del = await client.delete(f"/api/watchlist/{first_id}", cookies=cookies)
            assert r_del.status_code == 200

            async with SessionLocal() as s:
                remaining = (
                    await s.execute(
                        select(WatchlistItem).where(WatchlistItem.user_id == user_id)
                    )
                ).scalars().all()
            assert len(remaining) == 2
    finally:
        await _delete_seed_tickers()
