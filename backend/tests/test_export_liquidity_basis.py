"""The CSV export measures its liquidity floor the way /api/scanner does.

/api/export/scanner.csv mirrors the scanner by hand. The scanner measures
dollar-volume on the 30-day average volume, falling back to the session's
running volume; the export read the running volume alone, so an export could
hold rows the on-screen scanner dropped (and the reverse), and which ones
depended on the time of day. Found in review of #881, 2026-09-19.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal, session_scope
from app.main import app
from app.models import Ticker, User

_PREFIX = "ZEXL"
_SECTOR = "ExportLiquidicals"


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _patch_signup_gates(monkeypatch) -> None:
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


async def _seed() -> None:
    now = datetime.now(UTC)
    rows = {
        # $5M on the running volume, $25k on the 30-day average: out at $1M.
        f"{_PREFIX}A": dict(volume=100_000, avg_volume_30d=500),
        # $500 running, $50M on average: in at $1M.
        f"{_PREFIX}B": dict(volume=10, avg_volume_30d=1_000_000),
        # Liquid either way.
        f"{_PREFIX}C": dict(volume=1_000_000, avg_volume_30d=1_000_000),
    }
    async with session_scope() as s:
        for i, (sym, vol) in enumerate(rows.items()):
            s.add(Ticker(
                symbol=sym, name=f"{sym} Inc", asset_class="equity", sector=_SECTOR,
                score=90.0 - i, signal="HIGH CONVICTION", updated_at=now,
                change_pct_1d=0.1, confidence_pct=70, sub_trend=70, sub_rs=70,
                sub_momentum=70, price=50.0, **vol,
            ))


async def _clear(user_id: str | None = None) -> None:
    async with SessionLocal() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.like(f"{_PREFIX}%")))
        if user_id:
            await s.execute(delete(User).where(User.id == user_id))
        await s.commit()


@pytest.mark.asyncio
async def test_the_export_keeps_exactly_the_rows_the_scanner_keeps(client, monkeypatch):
    """Mutation: the export's old `price * volume` clause, which keeps A and
    drops B."""
    _patch_signup_gates(monkeypatch)
    await _clear()
    await _seed()
    uid = None
    try:
        async with client:
            r = await client.post("/api/auth/signup", json={
                "email": f"exl-{uuid.uuid4().hex[:10]}@example.com",
                "password": "TestPassword!2026", "name": "EXL",
            })
            assert r.status_code == 200, r.text
            uid = r.json()["user"]["id"]
            async with SessionLocal() as s:
                u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
                u.tier = "pro"
                await s.commit()

            scan = await client.get(f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200")
            csv = await client.get(f"/api/export/scanner.csv?sector={_SECTOR}&min_score=0")
            assert scan.status_code == 200 and csv.status_code == 200, csv.text

        on_screen = {i["symbol"] for i in scan.json()["items"] if i["symbol"].startswith(_PREFIX)}
        exported = {
            line.split(",")[0] for line in csv.text.splitlines()[1:]
            if line.startswith(_PREFIX)
        }
        assert on_screen == {f"{_PREFIX}B", f"{_PREFIX}C"}, on_screen
        assert exported == on_screen, f"export={sorted(exported)} scanner={sorted(on_screen)}"
    finally:
        await _clear(uid)
