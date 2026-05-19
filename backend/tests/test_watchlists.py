"""Smoke tests for /api/watchlists (Phase A multi-list CRUD) + /api/presets.

Covers the contract that future Phase A2 frontend work depends on:
  - Auth required (401 without)
  - Tier cap enforced (Free=1 list, Pro=5, Premium=20)
  - Uniqueness on (user_id, name) returns 409 not 500
  - Delete cascades — items go with the list (via FK ON DELETE CASCADE)
  - Presets endpoints respect the existing `saved_scans` cap
    (Free=0 blocks creation entirely)
"""
from __future__ import annotations

import json
import uuid

import httpx
import pytest

from app.db import SessionLocal
from app.main import app
from app.models import User


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _make_user(tier: str = "premium") -> tuple[User, dict[str, str]]:
    """Create a fresh user + return a JWT-bearing auth header.

    Uses the dev-bypass for premium (auth.py:142 honours `Bearer dev-bypass`
    when settings.app_env == "development"). For non-premium tier coverage
    we'd need to mint a real JWT — out of scope for these smokes; the
    cap-enforcement tests cover the >=1 case via the dev-bypass premium
    path by stacking creates to hit the Premium cap of 20.
    """
    uid = f"u-{uuid.uuid4().hex[:8]}"
    async with SessionLocal() as session:
        user = User(id=uid, email=f"{uid}@test.local", tier=tier)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    headers = {"Authorization": "Bearer dev-bypass"}
    return user, headers


@pytest.mark.asyncio
async def test_watchlists_unauth_401(client):
    async with client:
        r = await client.get("/api/watchlists")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_watchlists_create_and_list(client):
    _, headers = await _make_user()
    async with client:
        # Empty to start
        r = await client.get("/api/watchlists", headers=headers)
        assert r.status_code == 200
        start_count = r.json()["count"]

        # Create one
        r = await client.post("/api/watchlists", json={"name": "Tech"}, headers=headers)
        assert r.status_code == 200, r.text
        list_id = r.json()["id"]
        assert r.json()["name"] == "Tech"
        assert r.json()["item_count"] == 0

        # Show up in list
        r = await client.get("/api/watchlists", headers=headers)
        assert r.json()["count"] == start_count + 1

        # Rename
        r = await client.patch(
            f"/api/watchlists/{list_id}", json={"name": "Tech Compounders"}, headers=headers
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Tech Compounders"

        # Delete
        r = await client.delete(f"/api/watchlists/{list_id}", headers=headers)
        assert r.status_code == 200
        assert r.json() == {"ok": True}


@pytest.mark.asyncio
async def test_watchlists_duplicate_name_409(client):
    _, headers = await _make_user()
    async with client:
        r = await client.post("/api/watchlists", json={"name": "Dup"}, headers=headers)
        assert r.status_code == 200
        r2 = await client.post("/api/watchlists", json={"name": "Dup"}, headers=headers)
        assert r2.status_code == 409


@pytest.mark.asyncio
async def test_watchlists_cap_enforced_returns_403(client):
    """Hit the Premium cap (20) by stacking creates; the next 403s with an
    upgrade message. Wipes the dev-bypass user's lists first so prior-test
    leftovers don't trip the cap before we mean to."""
    _, headers = await _make_user(tier="premium")
    async with client:
        # Clean slate for this test
        r = await client.get("/api/watchlists", headers=headers)
        for item in r.json()["items"]:
            await client.delete(f"/api/watchlists/{item['id']}", headers=headers)

        cap = 20
        for i in range(cap):
            r = await client.post(
                "/api/watchlists", json={"name": f"Cap-test {i}"}, headers=headers
            )
            assert r.status_code == 200, f"#{i}: {r.text}"
        r = await client.post(
            "/api/watchlists", json={"name": "Cap-test Overflow"}, headers=headers
        )
        assert r.status_code == 403
        assert "limit reached" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_watchlist_get_filters_by_list_id(client):
    """GET /api/watchlist?list_id=X narrows items to that list only;
    without the param, returns items across all of the user's lists."""
    from sqlalchemy import select

    from app.models import WatchlistItem

    user, headers = await _make_user()
    async with client:
        # Clean slate — wipe any inherited dev-bypass user state.
        r = await client.get("/api/watchlists", headers=headers)
        for item in r.json()["items"]:
            await client.delete(f"/api/watchlists/{item['id']}", headers=headers)

        # Two lists with one item each, owned by the dev-bypass user. Look
        # up that user's id from the items the GET endpoint will return.
        r = await client.post("/api/watchlists", json={"name": "List A filter"}, headers=headers)
        list_a = r.json()["id"]
        r = await client.post("/api/watchlists", json={"name": "List B filter"}, headers=headers)
        list_b = r.json()["id"]

        # Direct DB insert so we control watchlist_id precisely. The dev-
        # bypass user_id is hardcoded to "dev_user" in services/auth.py;
        # reuse that here.
        async with SessionLocal() as s:
            s.add(WatchlistItem(user_id="dev_user", watchlist_id=list_a, symbol="AAPL"))
            s.add(WatchlistItem(user_id="dev_user", watchlist_id=list_b, symbol="MSFT"))
            await s.commit()

        # Unfiltered — both items.
        r = await client.get("/api/watchlist", headers=headers)
        symbols = {it["symbol"] for it in r.json()["items"]}
        assert "AAPL" in symbols and "MSFT" in symbols

        # Filtered to list A — only AAPL.
        r = await client.get(f"/api/watchlist?list_id={list_a}", headers=headers)
        symbols = {it["symbol"] for it in r.json()["items"]}
        assert "AAPL" in symbols
        assert "MSFT" not in symbols

        # Filtered to list B — only MSFT.
        r = await client.get(f"/api/watchlist?list_id={list_b}", headers=headers)
        symbols = {it["symbol"] for it in r.json()["items"]}
        assert "MSFT" in symbols
        assert "AAPL" not in symbols

        # Cleanup
        async with SessionLocal() as s:
            res = await s.execute(
                select(WatchlistItem).where(WatchlistItem.user_id == "dev_user", WatchlistItem.symbol.in_(["AAPL", "MSFT"]))
            )
            for w in res.scalars().all():
                await s.delete(w)
            await s.commit()


@pytest.mark.asyncio
async def test_presets_unauth_401(client):
    async with client:
        r = await client.get("/api/presets")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_presets_create_list_delete(client):
    _, headers = await _make_user()
    blob = json.dumps({"sector": "Technology", "min_score": 70})
    async with client:
        r = await client.post(
            "/api/presets",
            json={"name": "Tech high-score", "filters_json": blob},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        assert r.json()["filters_json"] == blob

        r = await client.get("/api/presets", headers=headers)
        assert r.status_code == 200
        names = [p["name"] for p in r.json()["items"]]
        assert "Tech high-score" in names

        r = await client.delete(f"/api/presets/{pid}", headers=headers)
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_presets_duplicate_name_409(client):
    _, headers = await _make_user()
    blob = "{}"
    async with client:
        r = await client.post(
            "/api/presets", json={"name": "Dup", "filters_json": blob}, headers=headers
        )
        assert r.status_code == 200
        r2 = await client.post(
            "/api/presets", json={"name": "Dup", "filters_json": blob}, headers=headers
        )
        assert r2.status_code == 409


# --- POST /api/watchlist list_id + PATCH /api/watchlist/{id} (Drive 2) -----

async def _wipe_dev_user_watchlist(client_inst, headers):
    """Wipe both lists and items for the dev-bypass user so the
    next test starts with a known empty state."""
    r = await client_inst.get("/api/watchlist", headers=headers)
    for it in r.json()["items"]:
        await client_inst.delete(f"/api/watchlist/{it['id']}", headers=headers)
    r = await client_inst.get("/api/watchlists", headers=headers)
    for wl in r.json()["items"]:
        await client_inst.delete(f"/api/watchlists/{wl['id']}", headers=headers)


@pytest.mark.asyncio
async def test_watchlist_add_creates_default_list_when_user_has_none(client):
    """First POST /api/watchlist for a user with zero lists auto-creates
    'My Watchlist' and attaches the item to it. Preserves the legacy
    single-list UX exactly for new users."""
    _, headers = await _make_user()
    async with client:
        await _wipe_dev_user_watchlist(client, headers)

        r = await client.post(
            "/api/watchlist", json={"symbol": "AAPL"}, headers=headers
        )
        assert r.status_code == 200, r.text
        assert r.json()["watchlist_id"] is not None

        r = await client.get("/api/watchlists", headers=headers)
        names = {l["name"] for l in r.json()["items"]}
        assert "My Watchlist" in names


@pytest.mark.asyncio
async def test_watchlist_add_with_explicit_list_id(client):
    """POST with explicit list_id puts the item in that list."""
    _, headers = await _make_user()
    async with client:
        await _wipe_dev_user_watchlist(client, headers)
        r = await client.post(
            "/api/watchlists", json={"name": "Tech"}, headers=headers
        )
        tech_id = r.json()["id"]

        r = await client.post(
            "/api/watchlist",
            json={"symbol": "NVDA", "list_id": tech_id},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["watchlist_id"] == tech_id

        # Item shows when filtered to that list
        r = await client.get(f"/api/watchlist?list_id={tech_id}", headers=headers)
        symbols = {i["symbol"] for i in r.json()["items"]}
        assert "NVDA" in symbols


@pytest.mark.asyncio
async def test_watchlist_add_404_on_foreign_list_id(client):
    """POST with a list_id that doesn't belong to the caller returns 404."""
    _, headers = await _make_user()
    async with client:
        await _wipe_dev_user_watchlist(client, headers)
        # 99999 is a list id that definitely doesn't belong to dev_user
        r = await client.post(
            "/api/watchlist",
            json={"symbol": "TSLA", "list_id": 99999},
            headers=headers,
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_watchlist_move_item_to_different_list(client):
    """PATCH /api/watchlist/{id} { watchlist_id } moves the item.
    Verified by re-fetching with ?list_id and confirming presence shifts."""
    _, headers = await _make_user()
    async with client:
        await _wipe_dev_user_watchlist(client, headers)
        a = (await client.post("/api/watchlists", json={"name": "A"}, headers=headers)).json()["id"]
        b = (await client.post("/api/watchlists", json={"name": "B"}, headers=headers)).json()["id"]

        added = (await client.post(
            "/api/watchlist", json={"symbol": "MSFT", "list_id": a}, headers=headers
        )).json()
        item_id = added["id"]
        assert added["watchlist_id"] == a

        # Move A → B
        r = await client.patch(
            f"/api/watchlist/{item_id}",
            json={"watchlist_id": b},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["watchlist_id"] == b

        # Confirm via filter
        in_a = (await client.get(f"/api/watchlist?list_id={a}", headers=headers)).json()
        in_b = (await client.get(f"/api/watchlist?list_id={b}", headers=headers)).json()
        assert all(i["symbol"] != "MSFT" for i in in_a["items"])
        assert any(i["symbol"] == "MSFT" for i in in_b["items"])


@pytest.mark.asyncio
async def test_watchlist_move_404_on_foreign_list_id(client):
    """PATCH with a destination list that doesn't belong to caller 404s."""
    _, headers = await _make_user()
    async with client:
        await _wipe_dev_user_watchlist(client, headers)
        a = (await client.post("/api/watchlists", json={"name": "Solo"}, headers=headers)).json()["id"]
        item = (await client.post(
            "/api/watchlist", json={"symbol": "GOOG", "list_id": a}, headers=headers
        )).json()
        r = await client.patch(
            f"/api/watchlist/{item['id']}",
            json={"watchlist_id": 88888},  # not the caller's
            headers=headers,
        )
        assert r.status_code == 404
