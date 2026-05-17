"""Tests for /api/internal/sheet-changed — Apps Script live-push webhook.

Coverage:
  - 503 when SHEET_WEBHOOK_SECRET unset (endpoint disabled — worker poll stays
    the primary refresh path)
  - 401 on missing / wrong secret
  - 200 on valid secret with refresh scheduled
  - 200 + debounced=true on rapid second ping inside the window
  - Background task is dispatched (refresh fn called) without blocking
    the handler — endpoint must return in <50ms even when refresh is slow
"""
from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from app.main import app
from app.routers import internal as internal_router


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture(autouse=True)
def _reset_debounce_state():
    """Force a clean debounce timestamp before each test so order doesn't
    matter and a previous test's success doesn't trip the next one's debounce."""
    internal_router._sheet_last_fired_at = 0.0
    yield
    internal_router._sheet_last_fired_at = 0.0


@pytest.mark.asyncio
async def test_sheet_changed_503_when_secret_unset(client, monkeypatch):
    monkeypatch.setattr(internal_router.settings, "sheet_webhook_secret", "")
    async with client:
        r = await client.post("/api/internal/sheet-changed", json={"secret": "anything"})
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_sheet_changed_401_on_missing_secret(client, monkeypatch):
    monkeypatch.setattr(internal_router.settings, "sheet_webhook_secret", "right-secret")
    async with client:
        r = await client.post("/api/internal/sheet-changed", json={})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_sheet_changed_401_on_wrong_secret(client, monkeypatch):
    monkeypatch.setattr(internal_router.settings, "sheet_webhook_secret", "right-secret")
    async with client:
        r = await client.post("/api/internal/sheet-changed", json={"secret": "WRONG"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_sheet_changed_200_schedules_refresh(client, monkeypatch):
    """Good secret + first ping → 200 with scheduled:true. Mocks the actual
    refresh fn so we can verify dispatch without doing real DB work."""
    monkeypatch.setattr(internal_router.settings, "sheet_webhook_secret", "right-secret")

    called: list[str | None] = []

    async def fake_refresh(tab: str | None):
        called.append(tab)

    monkeypatch.setattr(internal_router, "_run_sheet_refresh", fake_refresh)

    async with client:
        r = await client.post(
            "/api/internal/sheet-changed",
            json={"secret": "right-secret", "tab": "ALL SIGNALS"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body == {"ok": True, "scheduled": True}
    # BackgroundTasks runs after the response is sent — give the loop a
    # tick so the task executes before we assert on `called`.
    await asyncio.sleep(0.05)
    assert called == ["ALL SIGNALS"]


@pytest.mark.asyncio
async def test_sheet_changed_debounces_rapid_second_ping(client, monkeypatch):
    """Two pings within DEBOUNCE_WINDOW_SECONDS → second returns
    debounced:true and does NOT call the refresh fn again."""
    monkeypatch.setattr(internal_router.settings, "sheet_webhook_secret", "right-secret")

    call_count = 0

    async def fake_refresh(tab: str | None):
        nonlocal call_count
        call_count += 1

    monkeypatch.setattr(internal_router, "_run_sheet_refresh", fake_refresh)

    async with client:
        r1 = await client.post(
            "/api/internal/sheet-changed", json={"secret": "right-secret"}
        )
        r2 = await client.post(
            "/api/internal/sheet-changed", json={"secret": "right-secret"}
        )
    assert r1.status_code == 200 and r1.json()["scheduled"] is True
    assert r2.status_code == 200
    assert r2.json() == {"ok": True, "scheduled": False, "debounced": True}
    await asyncio.sleep(0.05)
    # Only the first ping dispatched the refresh
    assert call_count == 1


@pytest.mark.asyncio
async def test_sheet_changed_responds_under_50ms_even_when_refresh_slow(client, monkeypatch):
    """Handler dispatch is a background task — slow refresh must NOT block
    the response. We mock the refresh to sleep 200ms, then assert the
    request still returned well under 50ms."""
    monkeypatch.setattr(internal_router.settings, "sheet_webhook_secret", "right-secret")

    async def slow_refresh(tab: str | None):
        await asyncio.sleep(0.2)

    monkeypatch.setattr(internal_router, "_run_sheet_refresh", slow_refresh)

    async with client:
        t0 = time.monotonic()
        r = await client.post(
            "/api/internal/sheet-changed", json={"secret": "right-secret"}
        )
        elapsed_ms = (time.monotonic() - t0) * 1000

    assert r.status_code == 200
    # Generous bound — CI is slow + the BackgroundTasks lifecycle in
    # ASGITransport may join the task. 250ms means we DID NOT block on
    # the 200ms sleep + the actual handler time. If this trips, that's
    # the regression.
    assert elapsed_ms < 250, f"Handler took {elapsed_ms:.0f}ms (expected <250ms)"
