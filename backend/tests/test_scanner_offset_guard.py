"""Scanner offset scrape guard (routers/scanner.py).

The scanner caps `limit` to the tier's row_cap (Free=10) but historically left
`offset` open — so a Free or anonymous client could page the ENTIRE ~2,500-row
scored universe 10 rows at a time by walking offset. That defeats the whole
point of the free row cap (it's a scrape hole against the scored universe, the
core paid asset). The guard pins offset=0 for non-paying callers (Free +
anonymous) while keeping full pagination for Pro/Premium. Contract pinned here:

  1. Anonymous caller: offset is ignored — offset=0 and offset=N return the
     SAME first page (their row_cap rows), so they can never walk past it.
  2. Premium caller: pagination still works — offset shifts the window.

All test rows clear the full live_clauses() quality bar and sit in a unique
sector for isolation; deleted in each test's finally block.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import app
from app.models import Ticker, User

_SECTOR = "OffsetGuardSector"
_N = 15  # more than the Free/anon row_cap (10) so offset would matter
_SYMBOLS = [f"OGX{i:02d}" for i in range(_N)]


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _patch_signup_gates(monkeypatch) -> None:
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_args, **_kwargs):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


def _ticker_rows() -> list[dict]:
    now = datetime.now(UTC)
    common = dict(
        sector=_SECTOR,
        asset_class="stock",
        signal="HIGH CONVICTION",
        change_pct_1d=1.0,
        confidence_pct=80.0,
        sub_trend=70.0,
        sub_momentum=65.0,
        reason="Strong trend with momentum confirmation.",
        updated_at=now,
        price=50.0,
        volume=1_000_000,  # $50M dollar-volume, well above the liquidity floor
    )
    # Distinct, descending scores so the score-sort order is deterministic.
    return [
        {"symbol": sym, "name": f"Offset Test Co {i}", "score": 95.0 - i, **common}
        for i, sym in enumerate(_SYMBOLS)
    ]


async def _insert_tickers() -> None:
    async with SessionLocal() as s:
        for row in _ticker_rows():
            await s.merge(Ticker(**row))
        await s.commit()


async def _delete_tickers() -> None:
    async with SessionLocal() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SYMBOLS)))
        await s.commit()


async def _signup(client: httpx.AsyncClient) -> tuple[dict, str]:
    r = await client.post(
        "/api/auth/signup",
        json={
            "email": f"offset-{uuid.uuid4().hex[:10]}@example.com",
            "password": "TestPassword!2026",
            "name": "Offset",
        },
    )
    assert r.status_code == 200, r.text
    return dict(r.cookies), r.json()["user"]["id"]


async def _set_tier(user_id: str, tier: str) -> None:
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        u.tier = tier
        await s.commit()


@pytest.mark.asyncio
async def test_anonymous_offset_is_clamped_to_first_page(client):
    """An anonymous caller can't walk offset past their row_cap — offset=0 and
    offset=10 return the identical first page (top row_cap rows by score)."""
    await _insert_tickers()
    try:
        async with client:
            page0 = await client.get(
                f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200&offset=0"
            )
            page_off = await client.get(
                f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200&offset=10"
            )
            assert page0.status_code == 200, page0.text
            assert page_off.status_code == 200, page_off.text

            syms0 = [i["symbol"] for i in page0.json()["items"]]
            syms_off = [i["symbol"] for i in page_off.json()["items"]]

            # Row cap pins the count to 10 for anon...
            assert len(syms0) == 10, "anon should get exactly row_cap (10) rows"
            # ...and offset is ignored, so the second request is the SAME page,
            # not the next 5 rows (OGX10..OGX14 must never leak this way).
            assert syms0 == syms_off, "offset must be clamped for anonymous callers"
            assert "OGX14" not in syms_off
    finally:
        await _delete_tickers()


@pytest.mark.asyncio
async def test_premium_pagination_still_works(client, monkeypatch):
    """Pro/Premium keep real pagination — offset shifts the window."""
    _patch_signup_gates(monkeypatch)
    await _insert_tickers()
    try:
        async with client:
            cookies, uid = await _signup(client)
            await _set_tier(uid, "premium")

            full = await client.get(
                f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200&offset=0",
                cookies=cookies,
            )
            paged = await client.get(
                f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200&offset=5",
                cookies=cookies,
            )
            assert full.status_code == 200, full.text
            assert paged.status_code == 200, paged.text

            full_syms = [i["symbol"] for i in full.json()["items"]]
            paged_syms = [i["symbol"] for i in paged.json()["items"]]

            # Premium sees all 15 sector rows unpaged...
            assert len(full_syms) == _N
            # ...and offset=5 skips the top 5, proving pagination is intact.
            assert paged_syms == full_syms[5:]
            assert full_syms[0] not in paged_syms
    finally:
        await _delete_tickers()
