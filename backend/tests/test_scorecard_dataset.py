"""Public scorecard dataset — GET /api/scorecard.csv and /api/scorecard.json.

The scorecard's only real claim is that it is checkable. These endpoints are
what makes that true off-site, so the tests pin two separate things:

  1. The MECHANICS — both routes are registered at the extension-style paths
     (they are built by concatenating ".csv" onto the router's
     "/api/scorecard" prefix, which is easy to break silently), they need no
     auth, they stream the whole archive rather than a trailing window, and
     the artefact carries its own context.

  2. The COMPLIANCE INVARIANTS — the payload contains raw rows only. No
     annualised return, no risk-adjusted ratio, no cumulative total, no
     hypothetical P&L, no win streak, no backtest. Publishing the archive is
     a description; summarising it into a performance figure is a
     representation, and the whole point of asserting it here is that the
     failure mode is a future well-meant addition rather than a deliberate
     one.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete

from app.db import SessionLocal
from app.main import app
from app.models import DailyScorecardEntry
from app.services import scorecard_export

# Symbols unique to this module so teardown can't touch other suites' rows.
_SYMBOLS = ["DSETA", "DSETB", "DSETC"]

# Old enough to clear the 7-day publication delay by a wide margin, and
# spread over two sessions so the "distinct sessions" count is meaningful.
_OLD = date(2025, 3, 3)
_OLDER = date(2025, 3, 4)


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _seed() -> None:
    """Two sessions of entries, deliberately including a LOSING row.

    A losing row is not incidental to the fixture — the archive's claim is
    that it keeps them, so an export that quietly dropped negatives would
    still pass a test seeded only with winners.
    """
    await _cleanup()
    rows = [
        # session, rank, symbol, score, price, next, chg, spy, alpha
        (_OLD, 1, "DSETA", 91.0, 100.0, 102.0, 2.0, 0.5, 1.5),
        (_OLD, 2, "DSETB", 88.0, 50.0, 49.0, -2.0, 0.5, -2.5),   # lagged SPY
        (_OLDER, 1, "DSETC", 84.0, 20.0, None, None, None, None),  # not back-checked
    ]
    async with SessionLocal() as s:
        for as_of, rank, sym, score, price, nxt, chg, spy, alpha in rows:
            s.add(DailyScorecardEntry(
                as_of=as_of, symbol=sym, rank=rank,
                score_at_flag=score, price_at_flag=price,
                price_next_day=nxt, change_pct_1d_after=chg,
                spy_change_pct_1d=spy, alpha_vs_spy=alpha,
            ))
        await s.commit()


async def _cleanup() -> None:
    async with SessionLocal() as s:
        await s.execute(delete(DailyScorecardEntry).where(DailyScorecardEntry.symbol.in_(_SYMBOLS)))
        await s.commit()


def _split_csv(body: str) -> tuple[list[str], list[dict]]:
    """Split the artefact into its `#` preamble and its parsed data rows."""
    comments = [ln for ln in body.splitlines() if ln.startswith("#")]
    data = "\n".join(ln for ln in body.splitlines() if not ln.startswith("#") and ln.strip())
    return comments, list(csv.DictReader(io.StringIO(data)))


# --------------------------------------------------------------------------
# Mechanics
# --------------------------------------------------------------------------


def test_both_export_routes_are_registered():
    """The paths are built by string concatenation off the router prefix
    (".csv" + "/api/scorecard"), which no other router in the tree does. If
    that ever stops resolving, this fails here instead of 404ing in prod."""
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/scorecard.csv" in paths
    assert "/api/scorecard.json" in paths


@pytest.mark.asyncio
async def test_csv_is_public_and_returns_every_entry(client):
    """No auth, correct content type, a download filename, and the COMPLETE
    archive — not the 30-day window the web view renders."""
    await _seed()
    try:
        async with client:
            r = await client.get("/api/scorecard.csv")
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("text/csv")
        disposition = r.headers["content-disposition"]
        assert "attachment" in disposition
        assert "tapeline-scorecard-" in disposition and ".csv" in disposition

        comments, rows = _split_csv(r.text)
        seeded = [row for row in rows if row["symbol"] in _SYMBOLS]
        assert len(seeded) == 3
        assert comments, "the artefact must carry its context in-file"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_csv_header_matches_the_published_column_contract(client):
    await _seed()
    try:
        async with client:
            r = await client.get("/api/scorecard.csv")
        _, rows = _split_csv(r.text)
        assert list(rows[0].keys()) == scorecard_export.COLUMNS
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_losing_rows_are_present_and_unmodified(client):
    """The archive keeps its losing days — that is the entire asset. A
    negative alpha must survive the export byte-for-byte."""
    await _seed()
    try:
        async with client:
            r = await client.get("/api/scorecard.csv")
        _, rows = _split_csv(r.text)
        loser = next(row for row in rows if row["symbol"] == "DSETB")
        assert float(loser["change_pct_1d_after"]) == -2.0
        assert float(loser["alpha_vs_spy"]) == -2.5
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_pending_backcheck_renders_as_empty_not_none(client):
    """An entry whose next-day price hasn't been recorded yet must produce an
    empty cell. The literal string "None" would read as a value."""
    await _seed()
    try:
        async with client:
            r = await client.get("/api/scorecard.csv")
        _, rows = _split_csv(r.text)
        pending = next(row for row in rows if row["symbol"] == "DSETC")
        assert pending["price_next_day"] == ""
        assert pending["alpha_vs_spy"] == ""
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_json_shape_and_public_access(client):
    await _seed()
    try:
        async with client:
            r = await client.get("/api/scorecard.json")
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("application/json")
        body = r.json()
        assert set(body) == {"meta", "rows"}
        seeded = [row for row in body["rows"] if row["symbol"] in _SYMBOLS]
        assert len(seeded) == 3
        assert set(seeded[0]) == set(scorecard_export.COLUMNS)
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_recent_entries_are_held_back_by_the_publication_delay(client):
    """The export applies the same delay as the anonymous web view, and says
    so in the metadata rather than applying it silently."""
    recent = datetime.now(UTC).date() - timedelta(days=1)
    async with SessionLocal() as s:
        s.add(DailyScorecardEntry(
            as_of=recent, symbol="DSETA", rank=1,
            score_at_flag=90.0, price_at_flag=10.0,
        ))
        await s.commit()
    try:
        async with client:
            r = await client.get("/api/scorecard.json")
        body = r.json()
        assert all(row["date"] != recent.isoformat() for row in body["rows"])
        assert body["meta"]["publication_delay_days"] == 7
        assert "publication_delay" in body["meta"]
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_since_filter_and_bad_since_rejected(client):
    await _seed()
    try:
        async with client:
            r = await client.get("/api/scorecard.json", params={"since": _OLDER.isoformat()})
            assert r.status_code == 200
            seeded = [row for row in r.json()["rows"] if row["symbol"] in _SYMBOLS]
            assert [row["symbol"] for row in seeded] == ["DSETC"]

            bad = await client.get("/api/scorecard.json", params={"since": "not-a-date"})
            assert bad.status_code == 400
    finally:
        await _cleanup()


# --------------------------------------------------------------------------
# Context carried into the artefact
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_csv_preamble_carries_the_context_offsite(client):
    """A CSV gets opened months later by someone who never saw the site. The
    methodology, the append-only rule, the delay, n, the general-information
    statement and the past-performance statement have to be IN the file."""
    await _seed()
    try:
        async with client:
            r = await client.get("/api/scorecard.csv")
        preamble = "\n".join(_split_csv(r.text)[0]).lower()
        assert scorecard_export.METHODOLOGY_URL.lower() in preamble
        assert "append-only" in preamble
        assert "publication delay" in preamble
        assert "rows:" in preamble and "sessions:" in preamble
        assert "general information only" in preamble
        assert "past performance is not indicative of future performance" in preamble
        assert "not personal financial advice" in preamble
        # The invitation to check our arithmetic — the whole reason the file
        # exists — must travel with it.
        assert "publish the correction" in preamble
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_json_meta_carries_the_same_context(client):
    await _seed()
    try:
        async with client:
            r = await client.get("/api/scorecard.json")
        meta = r.json()["meta"]
        assert meta["methodology_url"] == scorecard_export.METHODOLOGY_URL
        assert meta["append_only"]
        assert meta["publication_delay_days"] == 7
        assert meta["sample_size_rows"] >= 3
        assert meta["sample_size_sessions"] >= 2
        assert "not personal financial advice" in meta["general_information"]
        assert "Past performance is not indicative of future performance" in meta["past_performance"]
        assert meta["columns"] == scorecard_export.COLUMNS
    finally:
        await _cleanup()


# --------------------------------------------------------------------------
# Compliance invariants — raw rows only
# --------------------------------------------------------------------------


def _all_keys(node) -> list[str]:
    """Every dict key anywhere in a nested JSON structure."""
    if isinstance(node, dict):
        keys = list(node)
        for value in node.values():
            keys += _all_keys(value)
        return keys
    if isinstance(node, list):
        return [k for item in node for k in _all_keys(item)]
    return []


@pytest.mark.asyncio
async def test_json_payload_contains_no_derived_performance_keys(client):
    """No annualised return, Sharpe/Sortino, cumulative total, drawdown,
    hypothetical P&L, win streak or backtest anywhere in the payload —
    including inside `meta`. A factual archive may be published; a
    performance summary derived from it may not."""
    await _seed()
    try:
        async with client:
            r = await client.get("/api/scorecard.json")
        body = r.json()
        offenders = [
            key for key in _all_keys(body)
            for bad in scorecard_export._FORBIDDEN_KEY_SUBSTRINGS
            if bad in key.lower()
        ]
        assert offenders == [], f"derived-performance keys in the payload: {offenders}"
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_csv_columns_contain_no_derived_performance_fields(client):
    await _seed()
    try:
        async with client:
            r = await client.get("/api/scorecard.csv")
        _, rows = _split_csv(r.text)
        header = " ".join(rows[0].keys()).lower()
        for bad in scorecard_export._FORBIDDEN_KEY_SUBSTRINGS:
            assert bad not in header, f"derived-performance column: {bad}"
    finally:
        await _cleanup()


def test_published_column_contract_is_raw_rows_only():
    """Guards the constant itself, so adding a derived column to COLUMNS
    fails even before an endpoint is exercised."""
    joined = " ".join(scorecard_export.COLUMNS).lower()
    for bad in scorecard_export._FORBIDDEN_KEY_SUBSTRINGS:
        assert bad not in joined, f"derived-performance column in COLUMNS: {bad}"


def test_meta_text_makes_no_performance_representation():
    """The prose we ship inside the artefact must itself stay descriptive —
    the metadata is user-facing copy that travels further than the page."""
    meta = scorecard_export.dataset_meta(
        row_count=269, session_count=30, delay_days=7,
        first_date=date(2026, 6, 1), last_date=date(2026, 7, 11),
        cutoff=date(2026, 7, 11),
    )
    prose = " ".join(str(v) for v in meta.values()).lower()
    # Only affirmative claims are listed. The `derived_statistics` line has to
    # be able to NAME the statistics we refuse to publish ("...does not
    # publish an annualised return, ... or a backtest derived from this
    # data"), and negating a prohibited claim requires naming it.
    for banned in (
        "beat the market", "outperform", "winning stocks", "best picks",
        "strong buy", "guaranteed", "proven returns", "you should buy",
        "if you had",
    ):
        assert banned not in prose, f"performance claim in dataset metadata: {banned}"
    # The refusal must actually be stated, not merely implied by absence.
    assert "does not publish" in meta["derived_statistics"].lower()


def test_serialise_entry_clamps_impossible_legacy_scores():
    """A handful of corrupt historical rows stored raw factor values above
    100. The clamp keeps them from reaching a published artefact as
    impossible scores."""
    row = scorecard_export.serialise_entry(DailyScorecardEntry(
        as_of=_OLD, symbol="DSETA", rank=1,
        score_at_flag=412.0, price_at_flag=10.0,
    ))
    assert row["score_at_flag"] == 100.0


def test_json_meta_is_serialisable_with_no_dates_left_raw():
    """`iter_json` json.dumps() the meta object directly, so a stray `date`
    would raise mid-stream, after headers were already sent."""
    meta = scorecard_export.dataset_meta(
        row_count=1, session_count=1, delay_days=7,
        first_date=_OLD, last_date=_OLD, cutoff=_OLD,
    )
    assert json.loads(json.dumps(meta))["first_session"] == _OLD.isoformat()
