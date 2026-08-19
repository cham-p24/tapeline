"""Ticker market_cap column, migration, and scanner surfacing (GAP #10).

VOLUME already existed; this adds MARKET CAP end to end:
  * the ORM column is present and nullable,
  * the 0049 migration adds/drops it cleanly (upgrade/downgrade smoke),
  * the scanner API returns market_cap on each row (a real value AND null).
"""
from __future__ import annotations

import importlib.util
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy import Float, delete, select

from app.db import SessionLocal
from app.main import app
from app.models import Ticker, User


# ── ORM column ───────────────────────────────────────────────────────────────
def test_ticker_has_nullable_market_cap_column():
    col = Ticker.__table__.c.market_cap
    assert isinstance(col.type, Float)
    assert col.nullable is True


# ── Migration upgrade/downgrade smoke ────────────────────────────────────────
def test_market_cap_migration_upgrade_downgrade():
    mig_path = (
        Path(__file__).resolve().parent.parent
        / "alembic" / "versions" / "20260820_0049_ticker_market_cap.py"
    )
    spec = importlib.util.spec_from_file_location("mig_0049", mig_path)
    mig = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mig)

    # Chains onto the prior head.
    assert mig.revision == "0049_ticker_market_cap"
    assert mig.down_revision == "0048_backfill_activated_at"

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    engine = sa.create_engine("sqlite://")  # in-memory
    with engine.begin() as conn:
        conn.execute(
            sa.text("CREATE TABLE tickers (symbol VARCHAR(20) PRIMARY KEY, volume BIGINT)")
        )
        ctx = MigrationContext.configure(conn)
        # The migration module does `from alembic import op`; bind that name to
        # an Operations object wired to this connection so upgrade/downgrade run.
        mig.op = Operations(ctx)

        def _cols() -> set[str]:
            return {row[1] for row in conn.execute(sa.text("PRAGMA table_info(tickers)"))}

        assert "market_cap" not in _cols()
        mig.upgrade()
        assert "market_cap" in _cols(), "upgrade must add market_cap"
        mig.downgrade()
        assert "market_cap" not in _cols(), "downgrade must drop market_cap"


# ── Scanner API surfaces market_cap ──────────────────────────────────────────
_MC_SET = "MCSETX"    # market_cap populated
_MC_NULL = "MCNULLX"  # market_cap null → em-dash in UI
_SYMBOLS = [_MC_SET, _MC_NULL]


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _rows() -> list[dict]:
    now = datetime.now(UTC)
    common = dict(
        sector="Information Technology",
        asset_class="stock",
        signal="HIGH CONVICTION",
        change_pct_1d=1.0,
        confidence_pct=80.0,
        sub_trend=70.0,
        sub_momentum=65.0,
        reason="Strong trend with momentum confirmation.",
        # Liquid ($50M) so both clear the scanner's default $1M floor.
        price=50.0,
        volume=1_000_000,
        updated_at=now,
    )
    return [
        {"symbol": _MC_SET, "name": "Cap Set Co", "score": 98.0,
         "market_cap": 2_500_000_000.0, **common},
        {"symbol": _MC_NULL, "name": "Cap Null Co", "score": 97.5,
         "market_cap": None, **common},
    ]


async def _insert():
    async with SessionLocal() as s:
        for row in _rows():
            await s.merge(Ticker(**row))
        await s.commit()


async def _cleanup():
    async with SessionLocal() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SYMBOLS)))
        await s.commit()


def _patch_signup_gates(monkeypatch) -> None:
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


async def _signup_premium(client: httpx.AsyncClient):
    r = await client.post(
        "/api/auth/signup",
        json={"email": f"mc-{uuid.uuid4().hex[:10]}@example.com",
              "password": "TestPassword!2026", "name": "MC"},
    )
    assert r.status_code == 200, r.text
    user_id = r.json()["user"]["id"]
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        u.tier = "premium"
        await s.commit()
    return r.cookies


@pytest.mark.asyncio
async def test_scanner_returns_market_cap(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    await _insert()
    try:
        async with client:
            cookies = await _signup_premium(client)
            r = await client.get("/api/scanner?min_score=97&limit=200", cookies=cookies)
            assert r.status_code == 200, r.text
            by_sym = {i["symbol"]: i for i in r.json()["items"]}

            assert _MC_SET in by_sym and _MC_NULL in by_sym
            # Every row carries the key (so the UI can render it or an em-dash).
            assert "market_cap" in by_sym[_MC_SET]
            assert "market_cap" in by_sym[_MC_NULL]
            assert by_sym[_MC_SET]["market_cap"] == 2_500_000_000.0
            assert by_sym[_MC_NULL]["market_cap"] is None
    finally:
        await _cleanup()
