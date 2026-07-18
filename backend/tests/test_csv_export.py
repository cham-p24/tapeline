"""Pro CSV export — GET /api/export/{scanner,watchlist}.csv (routers/export.py).

CSV export is sold on every pricing surface as a Pro feature; this pins the
contract of the endpoint that finally delivers it:

  1. Anonymous callers get 401 (auth required before the tier gate).
  2. FREE users get 403 with the standard Pro-feature detail — the frontend's
     TierGateError parses "Pro" out of it to open the paywall.
  3. PRO users get 200 text/csv with a Content-Disposition attachment and the
     expected header row; the scanner export contains live scanner rows, the
     watchlist export contains the caller's items with current scores.
  4. Formula-injection guard: a user-authored note starting with "=" is
     prefixed with an apostrophe so Excel/Sheets renders it as text.
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

_SYMBOLS = ["CSVX1", "CSVX2"]

_SCANNER_HEADER = (
    "symbol,name,sector,asset_class,score,signal,price,"
    "change_pct_1d,change_pct_5d,change_pct_1m,volume,"
    "confidence_pct,sub_trend,sub_rs,sub_fundamentals,"
    "sub_momentum,sub_macro,sub_smart_money,reason,updated_at"
)

_WATCHLIST_HEADER = (
    "symbol,note,added_at,baseline_score,current_score,"
    "score_delta,signal,price,change_pct_1d,"
    "alert_threshold_delta,reason"
)


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


async def _insert_tickers() -> None:
    """Insert rows that pass EVERY live_clauses() floor (score<=100, no space
    in symbol, >=2 factors, change_pct_1d + confidence_pct set, clean
    asset_class, fresh updated_at) AND the scanner's default dollar-volume
    floor (price*volume >= 50k)."""
    now = datetime.now(UTC)
    async with SessionLocal() as s:
        for i, sym in enumerate(_SYMBOLS):
            await s.merge(Ticker(
                symbol=sym,
                name=f"CSV Export Test {i}",
                sector="Information Technology",
                asset_class="equity",
                score=90.0 - i,
                signal="STRONG SETUP",
                price=100.0,
                change_pct_1d=1.5,
                change_pct_5d=3.0,
                change_pct_1m=6.0,
                volume=1_000_000,
                sub_trend=80.0,
                sub_rs=70.0,
                sub_momentum=60.0,
                confidence_pct=85.0,
                reason="Test row for CSV export.",
                updated_at=now,
            ))
        await s.commit()


async def _delete_tickers() -> None:
    async with SessionLocal() as s:
        await s.execute(delete(WatchlistItem).where(WatchlistItem.symbol.in_(_SYMBOLS)))
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SYMBOLS)))
        await s.commit()


async def _signup_user(client: httpx.AsyncClient, tier: str) -> dict:
    """Create a user, force them to the given tier (signup auto-starts a
    Premium trial), and return the session cookies."""
    r = await client.post(
        "/api/auth/signup",
        json={
            "email": f"csv-{tier}-{uuid.uuid4().hex[:10]}@example.com",
            "password": "TestPassword!2026",
            "name": "Csv",
        },
    )
    assert r.status_code == 200, r.text
    uid = r.json()["user"]["id"]
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        u.tier = tier
        u.trial_ends_at = None
        await s.commit()
    return dict(r.cookies)


@pytest.mark.asyncio
async def test_export_requires_login(client):
    """Anonymous callers get 401 on both endpoints — auth precedes the gate."""
    async with client:
        for path in ("/api/export/scanner.csv", "/api/export/watchlist.csv"):
            r = await client.get(path)
            assert r.status_code == 401, f"{path}: {r.text}"


@pytest.mark.asyncio
async def test_free_user_403s_with_standard_detail(client, monkeypatch):
    """FREE gets the standard Pro-feature 403 on both endpoints — the exact
    phrase matters: the frontend TierGateError parses 'Pro' from it."""
    _patch_signup_gates(monkeypatch)
    async with client:
        cookies = await _signup_user(client, "free")
        for path in ("/api/export/scanner.csv", "/api/export/watchlist.csv"):
            r = await client.get(path, cookies=cookies)
            assert r.status_code == 403, f"{path}: {r.text}"
            assert r.json()["detail"] == "CSV export is a Pro feature"


@pytest.mark.asyncio
async def test_pro_user_gets_scanner_csv(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    await _insert_tickers()
    try:
        async with client:
            cookies = await _signup_user(client, "pro")
            # q=CSVX narrows to our test rows so the assertion is deterministic
            # against whatever else the shared test DB holds.
            r = await client.get("/api/export/scanner.csv?q=CSVX", cookies=cookies)
            assert r.status_code == 200, r.text
            assert r.headers["content-type"].startswith("text/csv")
            dispo = r.headers["content-disposition"]
            assert dispo.startswith('attachment; filename="tapeline-scanner-')
            assert dispo.endswith('.csv"')

            lines = r.text.splitlines()
            assert lines[0] == _SCANNER_HEADER
            body = "\n".join(lines[1:])
            for sym in _SYMBOLS:
                assert sym in body
            # Default sort is score desc → CSVX1 (90.0) before CSVX2 (89.0).
            assert body.index("CSVX1") < body.index("CSVX2")
    finally:
        await _delete_tickers()


@pytest.mark.asyncio
async def test_pro_user_gets_watchlist_csv_with_sanitized_note(client, monkeypatch):
    _patch_signup_gates(monkeypatch)
    await _insert_tickers()
    try:
        async with client:
            cookies = await _signup_user(client, "pro")
            # Note starts with "=" — the classic spreadsheet formula-injection
            # vector; the export must neutralise it with a leading apostrophe.
            r = await client.post(
                "/api/watchlist",
                json={"symbol": "CSVX1", "note": "=SUM(A1)"},
                cookies=cookies,
            )
            assert r.status_code == 200, r.text

            r = await client.get("/api/export/watchlist.csv", cookies=cookies)
            assert r.status_code == 200, r.text
            assert r.headers["content-type"].startswith("text/csv")
            assert r.headers["content-disposition"].startswith(
                'attachment; filename="tapeline-watchlist-'
            )

            lines = r.text.splitlines()
            assert lines[0] == _WATCHLIST_HEADER
            body = "\n".join(lines[1:])
            assert "CSVX1" in body
            # Current score joined from the Ticker row (90.0 at insert).
            assert "90.0" in body
            # Injection guard: the raw "=SUM(A1)" must never appear at the
            # start of a cell — only the apostrophe-prefixed form.
            assert "'=SUM(A1)" in body
            assert ",=SUM(A1)" not in body
    finally:
        await _delete_tickers()


@pytest.mark.asyncio
async def test_premium_user_also_gets_export(client, monkeypatch):
    """The gate is min-tier Pro, so Premium passes too."""
    _patch_signup_gates(monkeypatch)
    async with client:
        cookies = await _signup_user(client, "premium")
        r = await client.get("/api/export/watchlist.csv", cookies=cookies)
        assert r.status_code == 200, r.text
        assert r.text.splitlines()[0] == _WATCHLIST_HEADER
