"""A number is only a decision aid once it is LOCATABLE.

`peer_percentiles` places a ticker's composite score and its six sub-factors
against its sector peers. The value of the block is entirely in its honesty, so
this file pins the refusals as hard as it pins the arithmetic.

Contract pinned here:

  1. The percentile is `strictly below / covered peers`, rounded half-up, with
     the ticker itself counted in the denominator. Hand-built fixture sector,
     hand-computed expectations — including the strictly-below BOUNDARY, where
     peers holding exactly the ticker's value must not be counted as below it.
  2. Every entry prints the denominator `n` it was computed against, and `n`
     counts ONLY peers holding a non-null value for that field. A peer with no
     Fundamentals score is not a peer for Fundamentals.
  3. Below MIN_PEERS covered peers we refuse: percentile is None with
     reason="insufficient_peers". A percentile off a handful of rows is worse
     than no percentile.
  4. "Uncategorized" is not a peer group — nor are NULL / "Unknown" / "N/A".
     Those tickers fall back to the whole covered universe AND the label says
     so, so the caller can always print what the comparison was against.
  5. A field the ticker has no value for returns None with reason="no_value" —
     never 0, never a synthesised number.
  6. The block reaches the wire: GET /api/ticker/{symbol} carries it, nullable
     end to end, alongside the existing key_stats block.

See services/percentile.py for MIN_PEERS' justification and the peer-group rule.
"""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.main import app
from app.models import Ticker
from app.services.percentile import (
    BASIS_SECTOR,
    BASIS_UNIVERSE,
    MIN_PEERS,
    REASON_INSUFFICIENT_PEERS,
    REASON_NO_VALUE,
    UNIVERSE_LABEL,
    peer_group_for,
    peer_percentiles,
)


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# A sector nothing else in the shared test DB uses, so the denominators below
# are exactly what this file seeds and nothing leaks in from another test.
PCT_SECTOR = "PctTestSector"
THIN_SECTOR = "PctThinSector"
PREFIX = "PCTL"


async def _wipe() -> None:
    """Drop every row this module owns. The suite shares one SQLite file."""
    async with session_scope() as s:
        await s.execute(delete(Ticker).where(Ticker.symbol.like(f"{PREFIX}%")))
        await s.commit()


async def _seed(rows: list[dict]) -> None:
    async with session_scope() as s:
        for r in rows:
            s.add(Ticker(asset_class="equity", **r))
        await s.commit()


async def _percentiles(symbol: str, **kw) -> dict:
    async with session_scope() as s:
        t = (
            await s.execute(select(Ticker).where(Ticker.symbol == symbol))
        ).scalar_one()
        return await peer_percentiles(s, t, **kw)


# ---------------------------------------------------------------------------
# 1 + 2 — arithmetic and denominators, against a hand-built sector
# ---------------------------------------------------------------------------

# A 40-member sector (comfortably over MIN_PEERS=30) with hand-chosen scores.
#
#   score:  PCTL00 = 0, PCTL01 = 1, ... PCTL39 = 39   (all 40 covered)
#   sub_trend: only the first 32 carry a value, 0..31  (n = 32, still >= 30)
#   sub_fundamentals: only 5 carry a value            (n = 5,  below the floor)
#   sub_smart_money: nobody carries a value           (n = 0)
#
# Everything below is computed by hand from those three lines.
_SECTOR_N = 40
_TREND_COVERED = 32
_FUND_COVERED = 5


def _sector_rows() -> list[dict]:
    rows = []
    for i in range(_SECTOR_N):
        rows.append(
            {
                "symbol": f"{PREFIX}{i:02d}",
                "name": f"Percentile fixture {i}",
                "sector": PCT_SECTOR,
                "score": float(i),
                "sub_trend": float(i) if i < _TREND_COVERED else None,
                "sub_fundamentals": float(i) if i < _FUND_COVERED else None,
                "sub_smart_money": None,
                # Every member shares one rs value — the ties fixture (below).
                "sub_rs": 50.0,
            }
        )
    return rows


@pytest.fixture(autouse=True)
async def _fixture_sector():
    await _wipe()
    await _seed(_sector_rows())
    yield
    await _wipe()


async def test_percentile_is_strictly_below_over_covered_peers() -> None:
    """score for PCTL30 is 30.0; exactly 30 of the 40 peers score below it."""
    out = await _percentiles(f"{PREFIX}30")
    score = out["fields"]["score"]

    assert score["value"] == 30.0
    assert score["n"] == _SECTOR_N, "denominator is the covered peers, self included"
    # 30 strictly below / 40 covered = 75.0 -> 75
    assert score["percentile"] == 75
    assert score["reason"] is None
    assert score["peer_group"] == PCT_SECTOR
    assert score["basis"] == BASIS_SECTOR


async def test_lowest_and_highest_members_of_the_group() -> None:
    """The floor has nothing below it; the top has everything but itself."""
    low = (await _percentiles(f"{PREFIX}00"))["fields"]["score"]
    assert low["percentile"] == 0, "0 peers below / 40 -> 0th"

    high = (await _percentiles(f"{PREFIX}39"))["fields"]["score"]
    # 39 below / 40 = 97.5 -> 98 (half-up). Never 100: the ticker is inside its
    # own denominator, so it is never above itself.
    assert high["percentile"] == 98


async def test_ties_are_not_counted_as_below__the_boundary() -> None:
    """THE boundary case: a peer holding exactly our value is not below it.

    All 40 members share sub_rs = 50.0. If the comparison were `<=` every
    member would read 98th percentile — forty tickers each 'ahead of' the other
    thirty-nine. Strictly `<` puts all forty on 0, which is the truth: none of
    them is above any other.
    """
    for sym in (f"{PREFIX}00", f"{PREFIX}17", f"{PREFIX}39"):
        rs = (await _percentiles(sym))["fields"]["rs"]
        assert rs["value"] == 50.0
        assert rs["n"] == _SECTOR_N
        assert rs["percentile"] == 0, f"{sym}: ties must not count as below"


async def test_group_size_makes_thin_coverage_legible() -> None:
    """`n` alone says "compared against 5"; group_size says "5 OF 40".

    Without the group size a reader cannot tell a well-covered factor from a
    barely-covered one — both just print some n. The gap between group_size and
    a field's n IS our coverage of that factor in that group.
    """
    out = await _percentiles(f"{PREFIX}02")
    assert out["group_size"] == _SECTOR_N
    assert out["fields"]["score"]["n"] == _SECTOR_N, "fully covered"
    assert out["fields"]["trend"]["n"] == _TREND_COVERED < out["group_size"]
    assert out["fields"]["fundamentals"]["n"] == _FUND_COVERED
    assert out["fields"]["smart_money"]["n"] == 0, "covered by nobody in the group"
    for entry in out["fields"].values():
        assert entry["n"] <= out["group_size"]


async def test_n_counts_only_peers_holding_a_value_for_that_field() -> None:
    """A peer with no Trend score is not a peer FOR TREND.

    32 of the 40 members carry sub_trend. PCTL16 holds 16.0, so 16 of those 32
    are below it — 50th percentile of 32, not of 40.
    """
    out = await _percentiles(f"{PREFIX}16")
    trend = out["fields"]["trend"]
    assert trend["n"] == _TREND_COVERED
    assert trend["percentile"] == 50
    # Same ticker, same sector, different denominator per field — which is the
    # entire point of computing coverage per field.
    assert out["fields"]["score"]["n"] == _SECTOR_N


async def test_half_up_rounding_is_not_bankers_rounding() -> None:
    """PCTL34: 34/40 = 85.0. PCTL39: 39/40 = 97.5 must round UP to 98."""
    assert (await _percentiles(f"{PREFIX}34"))["fields"]["score"]["percentile"] == 85
    assert (await _percentiles(f"{PREFIX}39"))["fields"]["score"]["percentile"] == 98


# ---------------------------------------------------------------------------
# 3 — the MIN_PEERS refusal
# ---------------------------------------------------------------------------

async def test_thin_coverage_refuses_to_rank() -> None:
    """5 covered peers is not a peer group. No percentile, and a stated reason."""
    fund = (await _percentiles(f"{PREFIX}02"))["fields"]["fundamentals"]
    assert fund["value"] == 2.0, "the ticker DOES have a fundamentals score"
    assert fund["n"] == _FUND_COVERED
    assert fund["n"] < MIN_PEERS
    assert fund["percentile"] is None, "a percentile off 5 rows must not be published"
    assert fund["reason"] == REASON_INSUFFICIENT_PEERS
    # The denominator is still reported: "we cover 5 peers here" is information.
    assert fund["peer_group"] == PCT_SECTOR


async def test_refusal_boundary_is_exactly_min_peers() -> None:
    """n == MIN_PEERS ranks; n == MIN_PEERS - 1 refuses. No off-by-one."""
    sym = f"{PREFIX}10"
    at_floor = await _percentiles(sym, min_peers=_SECTOR_N)
    assert at_floor["fields"]["score"]["percentile"] is not None
    assert at_floor["min_peers"] == _SECTOR_N

    above_floor = await _percentiles(sym, min_peers=_SECTOR_N + 1)
    assert above_floor["fields"]["score"]["percentile"] is None
    assert above_floor["fields"]["score"]["reason"] == REASON_INSUFFICIENT_PEERS


async def test_a_sector_smaller_than_the_floor_never_ranks() -> None:
    """A whole sector under the floor is refused wholesale, not approximated."""
    await _seed(
        [
            {
                "symbol": f"{PREFIX}T{i}",
                "name": f"Thin {i}",
                "sector": THIN_SECTOR,
                "score": float(i * 10),
            }
            for i in range(3)
        ]
    )
    out = await _percentiles(f"{PREFIX}T2")
    assert out["peer_group"] == THIN_SECTOR
    assert out["basis"] == BASIS_SECTOR
    score = out["fields"]["score"]
    assert score["n"] == 3
    assert score["percentile"] is None
    assert score["reason"] == REASON_INSUFFICIENT_PEERS


# ---------------------------------------------------------------------------
# 4 — "Uncategorized" is not a peer group
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "sector",
    [None, "", "   ", "Uncategorized", "uncategorized", "Unknown", "N/A", "n/a"],
)
async def test_no_sector_sentinels_fall_back_to_the_universe(sector) -> None:
    label, basis = peer_group_for(sector)
    assert basis == BASIS_UNIVERSE
    assert label == UNIVERSE_LABEL


@pytest.mark.parametrize("sector", ["Health Care", "Financials", "Semiconductors"])
async def test_a_real_sector_is_used_verbatim(sector) -> None:
    label, basis = peer_group_for(sector)
    assert basis == BASIS_SECTOR
    assert label == sector, "the printed label must be the value we grouped on"


async def test_uncategorized_ticker_ranks_against_the_universe_and_says_so() -> None:
    """The fallback must be legible in the payload, not just in behaviour.

    PCTLU holds score 20.0. Its peer group is NOT the 40-member fixture sector
    (it has no sector at all) — it is every covered ticker, and the label has
    to say that so the page can print the comparison it actually made.
    """
    await _seed(
        [
            {
                "symbol": f"{PREFIX}U",
                "name": "Uncategorized fixture",
                "sector": "Uncategorized",
                "score": 20.0,
            }
        ]
    )
    out = await _percentiles(f"{PREFIX}U")

    assert out["basis"] == BASIS_UNIVERSE
    assert out["peer_group"] == UNIVERSE_LABEL
    score = out["fields"]["score"]
    assert score["basis"] == BASIS_UNIVERSE
    assert score["peer_group"] == UNIVERSE_LABEL
    # The universe denominator is every scored row in the DB, so it must be at
    # least the 41 rows this module seeded — and strictly larger than the
    # sector group, proving the fallback widened the comparison rather than
    # quietly ranking inside "Uncategorized".
    assert score["n"] >= _SECTOR_N + 1


async def test_uncategorized_tickers_are_not_ranked_against_each_other() -> None:
    """Two sector-less tickers must not form a peer group of two."""
    await _seed(
        [
            {
                "symbol": f"{PREFIX}U1",
                "name": "Sectorless A",
                "sector": None,
                "score": 5.0,
            },
            {
                "symbol": f"{PREFIX}U2",
                "name": "Sectorless B",
                "sector": "Uncategorized",
                "score": 95.0,
            },
        ]
    )
    a = await _percentiles(f"{PREFIX}U1")
    b = await _percentiles(f"{PREFIX}U2")
    assert a["peer_group"] == b["peer_group"] == UNIVERSE_LABEL
    assert a["fields"]["score"]["n"] == b["fields"]["score"]["n"]
    assert a["fields"]["score"]["n"] > 2


# ---------------------------------------------------------------------------
# 5 — no value of our own
# ---------------------------------------------------------------------------

async def test_field_with_no_value_returns_none_not_zero() -> None:
    """Nobody in the fixture has a smart-money score, including the ticker."""
    sm = (await _percentiles(f"{PREFIX}20"))["fields"]["smart_money"]
    assert sm["value"] is None
    assert sm["percentile"] is None, "0 would be a fabricated ranking"
    assert sm["reason"] == REASON_NO_VALUE
    assert sm["n"] == 0


async def test_no_value_is_reported_ahead_of_a_thin_denominator() -> None:
    """A ticker we hold nothing for is unrankable however many peers exist.

    PCTL35 has no sub_trend (only the first 32 do) but the group covers 32 —
    over the floor. The honest answer is "we have no value", not "not enough
    peers".
    """
    trend = (await _percentiles(f"{PREFIX}35"))["fields"]["trend"]
    assert trend["value"] is None
    assert trend["n"] == _TREND_COVERED >= MIN_PEERS
    assert trend["percentile"] is None
    assert trend["reason"] == REASON_NO_VALUE


async def test_every_field_is_present_and_self_describing() -> None:
    """Each entry carries its own denominator and label — no reaching upward."""
    out = await _percentiles(f"{PREFIX}05")
    assert set(out["fields"]) == {
        "score",
        "trend",
        "rs",
        "fundamentals",
        "smart_money",
        "macro",
        "momentum",
    }
    for key, entry in out["fields"].items():
        assert set(entry) == {
            "value",
            "percentile",
            "n",
            "peer_group",
            "basis",
            "reason",
        }, key
        assert entry["peer_group"] == out["peer_group"], key
        assert entry["basis"] == out["basis"], key
        # A published percentile ALWAYS has a denominator over the floor; a
        # withheld one ALWAYS has a stated reason. Never both, never neither.
        if entry["percentile"] is None:
            assert entry["reason"] in (REASON_NO_VALUE, REASON_INSUFFICIENT_PEERS), key
        else:
            assert entry["reason"] is None, key
            assert entry["n"] >= out["min_peers"], key
            assert 0 <= entry["percentile"] <= 100, key


# ---------------------------------------------------------------------------
# 6 — it reaches the wire
# ---------------------------------------------------------------------------

async def test_ticker_endpoint_carries_the_block(client) -> None:
    async with client as c:
        r = await c.get(f"/api/ticker/{PREFIX}30")
        assert r.status_code == 200, r.text
        body = r.json()
        # PCTL02 is one of the five tickers that DOES carry a fundamentals
        # score, so it exercises the thin-denominator refusal over the wire
        # rather than the no-value one.
        thin = (await c.get(f"/api/ticker/{PREFIX}02")).json()["peer_percentiles"]

    assert "key_stats" in body, "the new block sits alongside the existing one"
    block = body["peer_percentiles"]
    assert block is not None
    assert block["peer_group"] == PCT_SECTOR
    assert block["basis"] == BASIS_SECTOR
    assert block["min_peers"] == MIN_PEERS
    assert block["fields"]["score"]["percentile"] == 75
    assert block["fields"]["score"]["n"] == _SECTOR_N
    # The refusals survive JSON serialisation as nulls + reasons, not as zeros.
    assert block["fields"]["smart_money"]["percentile"] is None
    assert block["fields"]["smart_money"]["reason"] == REASON_NO_VALUE
    assert thin["fields"]["fundamentals"]["value"] == 2.0
    assert thin["fields"]["fundamentals"]["n"] == _FUND_COVERED
    assert thin["fields"]["fundamentals"]["percentile"] is None
    assert thin["fields"]["fundamentals"]["reason"] == REASON_INSUFFICIENT_PEERS


async def test_the_page_still_renders_when_the_block_cannot_be_built(
    client, monkeypatch
) -> None:
    """A failed aggregate nulls the block; it never 500s the ticker page."""
    from app.routers import ticker as ticker_module

    async def _boom(*_a, **_k):
        raise RuntimeError("peer aggregate exploded")

    monkeypatch.setattr(ticker_module, "peer_percentiles", _boom)
    async with client as c:
        r = await c.get(f"/api/ticker/{PREFIX}30")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["peer_percentiles"] is None
    assert body["score"] == 30.0, "the raw values still render"
