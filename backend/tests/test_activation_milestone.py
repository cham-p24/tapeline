"""Activation milestone (Growth Playbook §4.2).

`User.activated_at` is stamped the FIRST time a user adds a watchlist ticker —
the codebase's activation milestone #1 (consistent with the act_wl activation
drip in services/email.run_activation_drip). The contract these tests pin:

  - A first watchlist add stamps activated_at (was NULL → now set).
  - A second add does NOT overwrite it — the timestamp stays the original, so
    it measures time-to-activation, not last activity (idempotent).

Mirrors test_watchlists.py: dev-bypass premium auth + the shared "dev_user"
ORM row, which we reset to a known (activated_at = NULL, empty watchlist)
state at the top of each test so prior-suite leftovers don't taint the result.
"""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import User, WatchlistItem


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


HEADERS = {"Authorization": "Bearer dev-bypass"}


async def _reset_dev_user_activation() -> None:
    """Clear activated_at on the shared dev-bypass user so the next add is
    its 'first'. The dev-bypass user_id is hardcoded to 'dev_user' in
    services/auth.py; it's auto-created on first authed request, so a direct
    UPDATE here is a no-op until then (the first client call creates it)."""
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.id == "dev_user"))).scalar_one_or_none()
        if u is not None:
            u.activated_at = None
            await s.commit()


async def _wipe_dev_user_watchlist(client_inst) -> None:
    """Empty the dev-bypass user's watchlist + lists so adds start clean."""
    r = await client_inst.get("/api/watchlist", headers=HEADERS)
    for it in r.json()["items"]:
        await client_inst.delete(f"/api/watchlist/{it['id']}", headers=HEADERS)
    r = await client_inst.get("/api/watchlists", headers=HEADERS)
    for wl in r.json()["items"]:
        await client_inst.delete(f"/api/watchlists/{wl['id']}", headers=HEADERS)


async def _get_activated_at():
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.id == "dev_user"))).scalar_one()
        return u.activated_at


@pytest.mark.asyncio
async def test_first_watchlist_add_stamps_activated_at(client):
    async with client:
        # Ensure dev_user exists (first authed call creates it), then reset.
        await _wipe_dev_user_watchlist(client)
        await _reset_dev_user_activation()
        try:
            assert await _get_activated_at() is None

            r = await client.post("/api/watchlist", json={"symbol": "AAPL"}, headers=HEADERS)
            assert r.status_code == 200, r.text

            stamped = await _get_activated_at()
            assert stamped is not None
        finally:
            # Leave the shared dev_user clean (empty watchlist + null activation)
            # so later suites (e.g. test_watchlists) don't trip the
            # (user_id, symbol) UNIQUE constraint on this no-cleanup CI SQLite.
            await _wipe_dev_user_watchlist(client)
            await _reset_dev_user_activation()


@pytest.mark.asyncio
async def test_second_watchlist_add_does_not_overwrite_activated_at(client):
    async with client:
        await _wipe_dev_user_watchlist(client)
        await _reset_dev_user_activation()
        try:
            # First add → stamps activated_at.
            r = await client.post("/api/watchlist", json={"symbol": "MSFT"}, headers=HEADERS)
            assert r.status_code == 200, r.text
            first = await _get_activated_at()
            assert first is not None

            # Second add (different symbol) → must NOT change the timestamp.
            r = await client.post("/api/watchlist", json={"symbol": "NVDA"}, headers=HEADERS)
            assert r.status_code == 200, r.text
            second = await _get_activated_at()
            assert second == first, "activated_at must not be overwritten on later adds"
        finally:
            await _wipe_dev_user_watchlist(client)
            await _reset_dev_user_activation()
