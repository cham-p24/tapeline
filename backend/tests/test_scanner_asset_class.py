"""Asset class is filtered by the SERVER, not after the fetch.

WHAT THIS FIXES. The scanner offered Stocks / ETFs & funds / Other, and applied
it in `frontend/lib/filters.ts` over rows that had already come back. Three
things were wrong with that, and only the first is cosmetic:

  1. The tier row cap is applied server-side, so a Free user asking for ETFs
     got their 10 rows off the unfiltered ranking and THEN dropped the stocks
     — routinely showing an empty screen while the live universe held 1,637
     ETFs. The cap was spent on rows the user had just excluded.
  2. `total_matched` (the "N more behind the cap" number) comes from the
     server's WHERE stack and could not see a client-side filter, so the page
     had to suppress the locked-remainder band entirely whenever a bucket was
     chosen.
  3. The CSV export never applied it at all. Narrowing to "ETFs & funds" and
     clicking Export downloaded stocks — silently, with no error.

Every test here drives the real endpoint and asserts on the response, so a
regression to post-filtering fails rather than merely looking different.

Fixtures use both a canonical value and a SYNONYM ("stock" for equity, "fund"
for etf) because the mapping is the vendor's, not ours, and the synonym arms
are what stop a future vendor casing/wording change from silently emptying a
bucket.
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
from app.services.asset_class import ASSET_BUCKETS, asset_bucket_clause, bucket_of

_SECTOR = "AssetClassProbeSector"

#: (symbol, asset_class, expected bucket). Both synonyms per named bucket, an
#: "other" value, and an UNCLASSIFIED row.
#:
#: THERE IS NO "UNCLASSIFIED" ROW HERE, and the two dead ends that led to that
#: are worth recording so nobody re-adds one:
#:   * `asset_class` is String(20) NOT NULL with a Python default of "equity",
#:     so passing None does not store a NULL — it silently stores an equity,
#:     and a test built on it asserts nothing while looking thorough.
#:   * A blank or decorated value ("  ", "📈 stock") never reaches a
#:     ranked surface at all: live_clauses includes asset_class_clean_clauses(),
#:     which requires a clean single-token ASCII value. So on every surface a
#:     user can see, asset_class is already a clean token and the three buckets
#:     partition it completely.
#: test_the_quality_floor_excludes_a_decorated_class covers that upstream rule.
_FIXTURES: list[tuple[str, str, str]] = [
    ("ACE01", "equity", "equity"),
    ("ACE02", "stock", "equity"),
    ("ACE03", "etf", "etf"),
    ("ACE04", "fund", "etf"),
    ("ACE05", "future_commodity", "other"),
]
_SYMBOLS = [s for s, _, _ in _FIXTURES]


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


async def _insert() -> None:
    now = datetime.now(UTC)
    async with SessionLocal() as s:
        for i, (sym, ac, _) in enumerate(_FIXTURES):
            await s.merge(Ticker(
                symbol=sym, name=f"Asset Class Co {i}", sector=_SECTOR,
                asset_class=ac, signal="HIGH CONVICTION", score=95.0 - i,
                change_pct_1d=1.0, confidence_pct=80.0,
                sub_trend=70.0, sub_momentum=65.0,
                reason="Trend and momentum confirm the composite.",
                updated_at=now, price=50.0, volume=1_000_000,
            ))
        await s.commit()


async def _cleanup(user_id: str | None = None) -> None:
    async with SessionLocal() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SYMBOLS)))
        if user_id:
            await s.execute(delete(User).where(User.id == user_id))
        await s.commit()


async def _signup(client: httpx.AsyncClient) -> str:
    r = await client.post("/api/auth/signup", json={
        "email": f"ac-{uuid.uuid4().hex[:10]}@example.com",
        "password": "TestPassword!2026", "name": "AC",
    })
    assert r.status_code == 200, r.text
    return r.json()["user"]["id"]


async def _set_tier(user_id: str, tier: str) -> None:
    async with SessionLocal() as s:
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one()
        u.tier = tier
        await s.commit()


def _syms(body: dict) -> set[str]:
    return {i["symbol"] for i in body["items"]}


# ═════════════════════════════════════════════════════════════════════════════
# The buckets themselves
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bucket", "expected"),
    [
        ("equity", {"ACE01", "ACE02"}),
        ("etf", {"ACE03", "ACE04"}),
        ("other", {"ACE05"}),
    ],
)
async def test_each_bucket_returns_exactly_its_members(client, bucket, expected):
    await _insert()
    try:
        async with client:
            r = await client.get(
                f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200&asset_class={bucket}"
            )
            assert r.status_code == 200, r.text
            got = _syms(r.json()) & set(_SYMBOLS)
        assert got == expected
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_no_bucket_returns_every_classified_row(client):
    await _insert()
    try:
        async with client:
            r = await client.get(f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200")
            assert r.status_code == 200
            got = _syms(r.json()) & set(_SYMBOLS)
        assert got == set(_SYMBOLS), "an unfiltered scan must not drop anything"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_the_quality_floor_excludes_a_decorated_class(client):
    """Bucketing never has to cope with a junk asset_class, because the value
    is already guaranteed clean before it gets there.

    live_clauses -> asset_class_clean_clauses() requires a single-token ASCII
    value, so the raw sheet decorations that really exist in this table
    ("📈 stock", 22 rows in prod) are dropped from every ranked surface.
    Pinned here because the bucket mapping's completeness depends on it: if
    this floor were relaxed, "other" would silently start collecting garbage.
    """
    now = datetime.now(UTC)
    async with SessionLocal() as s:
        await s.merge(Ticker(
            symbol="ACE90", name="Decorated", sector=_SECTOR,
            asset_class="📈 stock", signal="HIGH CONVICTION", score=99.0,
            change_pct_1d=1.0, confidence_pct=80.0, sub_trend=70.0,
            sub_momentum=65.0, reason="Trend and momentum confirm the composite.",
            updated_at=now, price=50.0, volume=1_000_000,
        ))
        await s.commit()
    try:
        async with client:
            r = await client.get(f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200")
            assert r.status_code == 200
            assert "ACE90" not in _syms(r.json()), (
                "a decorated asset_class reached a ranked surface"
            )
    finally:
        async with SessionLocal() as s:
            await s.execute(delete(Ticker).where(Ticker.symbol == "ACE90"))
            await s.commit()


@pytest.mark.asyncio
async def test_an_unknown_bucket_is_rejected_not_silently_empty(client):
    """A screener that returns nothing looks like "no matches". An invalid
    filter must be a 422 so it cannot be mistaken for a real empty result."""
    await _insert()
    try:
        async with client:
            r = await client.get(f"/api/scanner?sector={_SECTOR}&asset_class=banana")
            assert r.status_code == 422, r.text
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_the_bucket_matching_is_case_insensitive(client):
    """The column is lowercase today; a vendor casing change must not empty a
    bucket."""
    async with SessionLocal() as s:
        await s.merge(Ticker(
            symbol="ACE07", name="Shouty ETF", sector=_SECTOR, asset_class="ETF",
            signal="HIGH CONVICTION", score=80.0, change_pct_1d=1.0,
            confidence_pct=80.0, sub_trend=70.0, sub_momentum=65.0,
            reason="Trend and momentum confirm the composite.",
            updated_at=datetime.now(UTC), price=50.0, volume=1_000_000,
        ))
        await s.commit()
    try:
        async with client:
            r = await client.get(
                f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200&asset_class=etf"
            )
            assert r.status_code == 200
            assert "ACE07" in _syms(r.json())
    finally:
        async with SessionLocal() as s:
            await s.execute(delete(Ticker).where(Ticker.symbol == "ACE07"))
            await s.commit()


# ═════════════════════════════════════════════════════════════════════════════
# The reasons it had to move server-side
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_a_capped_tier_spends_its_rows_on_the_bucket_it_asked_for(client, monkeypatch):
    """THE bug. Free gets row_cap rows; filtering after that meant the cap was
    spent on names the user had already excluded, so asking for ETFs could show
    an empty screen while ETFs existed."""
    _patch_signup_gates(monkeypatch)
    # Two ETFs ranked BELOW enough equities to fill a Free page on their own.
    now = datetime.now(UTC)
    filler = [f"ACF{i:02d}" for i in range(12)]
    async with SessionLocal() as s:
        for i, sym in enumerate(filler):
            await s.merge(Ticker(
                symbol=sym, name=f"Filler {i}", sector=_SECTOR, asset_class="equity",
                signal="HIGH CONVICTION", score=99.0 - i * 0.1, change_pct_1d=1.0,
                confidence_pct=80.0, sub_trend=70.0, sub_momentum=65.0,
                reason="Trend and momentum confirm the composite.",
                updated_at=now, price=50.0, volume=1_000_000,
            ))
        await s.commit()
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            await _set_tier(uid, "free")
            from app.services import tier as tier_mod
            monkeypatch.setattr(tier_mod, "free_open_access", lambda *_a, **_k: False)

            r = await client.get(
                f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200&asset_class=etf"
            )
            assert r.status_code == 200, r.text
            body = r.json()

        assert body["row_cap"] == 10
        got = _syms(body)
        assert got == {"ACE03", "ACE04"}, (
            "the capped page did not spend its rows on the requested bucket — "
            f"got {sorted(got)}"
        )
    finally:
        async with SessionLocal() as s:
            await s.execute(delete(Ticker).where(Ticker.symbol.in_(filler)))
            await s.commit()
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_total_matched_counts_only_the_selected_bucket(client, monkeypatch):
    """It is computed from the server's WHERE stack. With the filter client-side
    it counted the unfiltered universe, which is why the page had to hide the
    locked-remainder band whenever a bucket was chosen."""
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            await _set_tier(uid, "free")
            from app.services import tier as tier_mod
            monkeypatch.setattr(tier_mod, "free_open_access", lambda *_a, **_k: False)

            r = await client.get(
                f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200&asset_class=etf"
            )
            assert r.status_code == 200
            body = r.json()

        # Two ETFs in this sector, well under the cap of 10.
        assert body["count"] == 2
        assert body["total_matched"] == 2, (
            "total_matched still counts rows outside the selected bucket"
        )
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_the_csv_export_honours_the_bucket(client, monkeypatch):
    """Its absence on the export was a live bug: filter to ETFs, click Export,
    download stocks."""
    _patch_signup_gates(monkeypatch)
    await _insert()
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            await _set_tier(uid, "premium")
            r = await client.get(
                f"/api/export/scanner.csv?sector={_SECTOR}&min_score=0&asset_class=etf"
            )
            assert r.status_code == 200, r.text
            body = r.text

        assert "ACE03" in body and "ACE04" in body, "the requested ETFs are missing"
        for sym in ("ACE01", "ACE02", "ACE05", "ACE06"):
            assert sym not in body, f"{sym} is not an ETF but was exported"
    finally:
        await _cleanup(uid)


@pytest.mark.asyncio
async def test_the_export_rejects_an_unknown_bucket_too(client, monkeypatch):
    """Scanner and export mirror each other by hand; a filter that validates on
    one and not the other is how the CSV drifted in the first place."""
    _patch_signup_gates(monkeypatch)
    uid = None
    try:
        async with client:
            uid = await _signup(client)
            await _set_tier(uid, "premium")
            r = await client.get("/api/export/scanner.csv?asset_class=banana")
            assert r.status_code == 422, r.text
    finally:
        await _cleanup(uid)


# ═════════════════════════════════════════════════════════════════════════════
# The mapping is one definition
# ═════════════════════════════════════════════════════════════════════════════

def test_bucket_of_matches_the_frontend_mapping():
    """Mirrors frontend/lib/filters.ts assetBucket(), which this replaced.

    `bucket_of` and `asset_bucket_clause` must agree, so both trim and
    lowercase; test_the_bucket_matching_is_case_insensitive covers the SQL half.
    """
    assert bucket_of("equity") == "equity"
    assert bucket_of("stock") == "equity"
    assert bucket_of("etf") == "etf"
    assert bucket_of("fund") == "etf"
    assert bucket_of("future_commodity") == "other"
    assert bucket_of(None) == ""
    assert bucket_of("") == ""
    assert bucket_of("   ") == ""
    assert bucket_of("  ETF  ") == "etf"


def test_no_bucket_asked_for_means_no_clause():
    """None, not a true-clause: the WHERE stack must be byte-identical to the
    unfiltered query so total_matched and the page agree."""
    assert asset_bucket_clause(None) is None
    assert asset_bucket_clause("") is None


@pytest.mark.asyncio
async def test_the_buckets_partition_every_classified_row(client):
    """No classified fixture row is missed by all three buckets, and none is
    claimed by two. A gap would hide tickers from every filtered view."""
    await _insert()
    try:
        async with client:
            seen: dict[str, list[str]] = {}
            for bucket in ASSET_BUCKETS:
                r = await client.get(
                    f"/api/scanner?sector={_SECTOR}&min_score=0&limit=200&asset_class={bucket}"
                )
                assert r.status_code == 200
                for sym in _syms(r.json()) & set(_SYMBOLS):
                    seen.setdefault(sym, []).append(bucket)

        classified = {s for s, _, b in _FIXTURES if b}
        assert set(seen) == classified, (
            f"buckets do not cover every classified row: {sorted(classified - set(seen))}"
        )
        doubled = {s: b for s, b in seen.items() if len(b) > 1}
        assert not doubled, f"rows claimed by more than one bucket: {doubled}"
    finally:
        await _cleanup()
