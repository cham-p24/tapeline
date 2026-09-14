"""The public record must disclose its own gaps, corrections and limitations.

Founder-approved integrity wave, 2026-09-14 (tickets T-05, T-06, T-29).

Three things were true of production and invisible in every artefact a reader
could hold:

1. On 2026-06-15 migration 0034_clamp_scorecard_scores set `score_at_flag` to
   100 on every row above 100; all 190 rows from the sessions 2026-05-18 to
   2026-06-12 now read 100. A bug had stored values above 100 (120-137 were
   verified for 2026-05-22..06-05), and the originals were not kept, so which
   rows changed is unknown. The export's `restatements` did not list it, and
   its header said "If `restatements` is empty, no published row has ever
   been altered".
2. Four US trading days (2026-08-31, 2026-09-02, 2026-09-04, 2026-09-09) have
   no top 10, and nothing said so.
3. The CSV — the artefact built to be read detached from the site — carried
   none of the restatements at all; they existed only in the JSON meta.

These tests pin the disclosure so it cannot be tidied away, and pin the gap
list as COMPUTED, so a fifth missing day is listed without anyone editing a
disclosure by hand.
"""
from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete

from app.db import SessionLocal
from app.main import app
from app.models import DailyScorecardEntry
from app.services import scorecard_export as ex
from app.services.scorecard_backcheck import missing_trading_sessions

# --------------------------------------------------------------------------
# missing_trading_sessions — pure
# --------------------------------------------------------------------------


def test_a_missing_trading_day_is_listed_automatically():
    # Mon 2026-08-31 .. Fri 2026-09-11, with the four real gaps removed and
    # Labor Day (2026-09-07) a holiday.
    present = [
        date(2026, 9, 1), date(2026, 9, 3), date(2026, 9, 8),
        date(2026, 9, 10), date(2026, 9, 11),
    ]
    got = missing_trading_sessions(date(2026, 8, 28), date(2026, 9, 11), [*present, date(2026, 8, 28)])
    assert got == [date(2026, 8, 31), date(2026, 9, 2), date(2026, 9, 4), date(2026, 9, 9)]


def test_weekends_and_holidays_are_not_gaps():
    # Fri 2026-07-02, then the 2026-07-03 holiday, the weekend, and Mon 07-06.
    assert missing_trading_sessions(
        date(2026, 7, 2), date(2026, 7, 6), [date(2026, 7, 2), date(2026, 7, 6)]
    ) == []
    # Labor Day 2026-09-07 sits between two present sessions.
    assert missing_trading_sessions(
        date(2026, 9, 4), date(2026, 9, 8), [date(2026, 9, 4), date(2026, 9, 8)]
    ) == []


def test_an_empty_or_inverted_range_lists_nothing():
    assert missing_trading_sessions(None, None, []) == []
    assert missing_trading_sessions(date(2026, 9, 10), date(2026, 9, 1), []) == []


# --------------------------------------------------------------------------
# The 2026-06-15 score cap (T-29)
# --------------------------------------------------------------------------


def _meta(present=None) -> dict:
    return ex.dataset_meta(
        row_count=820, session_count=82, delay_days=7,
        first_date=date(2026, 5, 11), last_date=date(2026, 9, 11),
        cutoff=date(2026, 9, 7), present_sessions=present,
        rows_not_back_checked=34,
    )


def test_the_june_score_cap_is_a_listed_restatement():
    r = next((x for x in ex.RESTATEMENTS if x["date"] == "2026-06-15"), None)
    assert r is not None, "the 2026-06-15 score_at_flag overwrite is not disclosed"
    assert r["fields_changed"] == "score_at_flag"
    assert "190" in r["scope"]
    assert "2026-05-18" in r["scope"] and "2026-06-12" in r["scope"]
    # The three facts that make it material, each stated rather than implied.
    assert "above 100" in r["reason"]
    assert "could be ranked" in r["reason"], "does not say lists could be ranked on the bad values"
    # What is verified is stated; what is not is said to be unknown. Migration
    # 0034 kept nothing, and lists recorded after #260 (2026-06-09) could not
    # hold a score above 100, so "every list was ranked on faulty values" and
    # "all 190 rows held scores above 100" are not claims the evidence supports.
    assert "120 to 137" in r["reason"] and "2026-05-22" in r["reason"]
    assert "#260" in r["reason"]
    assert "not known" in r["scope"]
    assert "cannot tell which" in r["magnitude"]
    for overclaim in ("each of these sessions was ranked", "faulty values"):
        blob = " ".join(r.values())
        assert overclaim not in blob, f"the 2026-06-15 restatement still says {overclaim!r}"
    assert "not kept" in r["remedy"] and "cannot be recovered" in r["remedy"]
    # A late disclosure must not pass for a timely one.
    assert "2026-09-14" in r["disclosed"]
    assert "not listed" in r["disclosed"]


def test_restatements_are_in_date_order():
    dates = [r["date"] for r in ex.RESTATEMENTS]
    assert dates == sorted(dates)


def test_the_record_policy_no_longer_claims_rows_were_never_altered():
    meta = _meta()
    for key in ("record_policy", "append_only", "description"):
        text = meta[key]
        for false_claim in (
            "no published row has ever been altered",
            "exactly what was published",
            "written once",
            "never edited",
            "Append-only archive",
        ):
            assert false_claim not in text, f"{key} still says {false_claim!r}"
    policy = meta["record_policy"]
    assert "not re-ranked, back-filled or deleted" in policy
    assert "2026-06-15" in policy and "2026-08-25" in policy


# --------------------------------------------------------------------------
# missing_sessions + known_limitations in meta (T-05)
# --------------------------------------------------------------------------


def test_meta_missing_sessions_is_computed_from_the_rows():
    # Every NYSE session from 2026-05-11 to 2026-09-11 except the four real gaps.
    present = []
    d = date(2026, 5, 11)
    while d <= date(2026, 9, 11):
        present.append(d)
        d += timedelta(days=1)
    gaps = {date(2026, 8, 31), date(2026, 9, 2), date(2026, 9, 4), date(2026, 9, 9)}
    present = [p for p in present if p not in gaps]
    meta = _meta(present)
    assert meta["missing_sessions"] == ["2026-08-31", "2026-09-02", "2026-09-04", "2026-09-09"]


def test_meta_missing_sessions_is_empty_not_guessed_without_rows():
    assert _meta(None)["missing_sessions"] == []


def test_known_limitations_are_dated_and_cover_the_verified_defects():
    lims = ex.KNOWN_LIMITATIONS
    for k in lims:
        for key in ("date", "period", "limitation", "status"):
            assert k.get(key), f"known limitation {k.get('date')!r} is missing {key}"
        date.fromisoformat(k["date"])
    blob = " ".join(k["period"] + " " + k["limitation"] + " " + k["status"] for k in lims)
    for must in (
        "2026-06-15",           # score cap
        "#620", "placeholder",  # random placeholder factors before 24 Aug
        "2026-09-07", "#766",   # sheet-score correction
        "2026-09-06", "#800",   # factor refresh stall
        "2026-08-31", "2026-09-02", "2026-09-04", "2026-09-09",
        "session 2026-08-24",   # list outside the 25 Aug restatement (P5)
        "#775", "6,092 of 11,649",  # factor coverage still incomplete
        # Smart Money values with no Form 4 filing on file (#824)
        "#824", "#833", "16 rows", "856 tickers", "BBH", "BBP", "BIB", "PLX",
        "5 commodity futures contracts", "7 earlier rows",
        "only produces values from 10 to 90",
        # The guard is 80 days on the transaction date, not the 90-day window.
        "records a transaction in the last 80 days",
        "ahead of other Smart Money re-checks",
    ):
        assert must in blob, f"known_limitations does not mention {must!r}"
    smart = next(k for k in lims if "#824" in k["status"])
    assert "Lists not changed" in smart["status"]
    assert "not been established" in smart["limitation"], (
        "where the values came from is unknown and must be stated as unknown"
    )
    assert "futures funds" not in blob, "the 5 are commodity futures contracts, not funds"
    assert "dated inside the window" not in blob, (
        "the contradiction guard is 80 days on the transaction date, not the window"
    )
    coverage = next(k for k in lims if "5,697 of 7,417" in k["limitation"])
    assert coverage["period"] == "all lists to date"
    assert "Fixed" not in coverage["status"], "factor coverage is still incomplete"
    assert ex.dataset_meta(
        row_count=1, session_count=1, delay_days=7, first_date=None,
        last_date=None, cutoff=date(2026, 9, 7),
    )["known_limitations"] == lims


# --------------------------------------------------------------------------
# The CSV carries every restatement (T-06)
# --------------------------------------------------------------------------


async def _no_rows():
    return
    yield  # pragma: no cover - makes this an async generator


async def _render_csv(meta: dict) -> str:
    return "".join([chunk async for chunk in ex.iter_csv(meta, _no_rows())])


@pytest.mark.asyncio
async def test_every_restatement_date_appears_in_the_csv():
    body = await _render_csv(_meta())
    for r in ex.RESTATEMENTS:
        assert f"# Restatement {r['date']}:" in body, (
            f"restatement {r['date']} is in the JSON meta but not in the CSV"
        )
    assert "# Restatement 2026-08-25:" in body
    assert "# Restatement 2026-06-15:" in body
    assert "full append-only archive" not in body
    assert "no published row has ever been altered" not in body


@pytest.mark.asyncio
async def test_the_csv_lists_missing_sessions_and_limitations():
    present = [date(2026, 9, 1), date(2026, 9, 3)]
    meta = ex.dataset_meta(
        row_count=20, session_count=2, delay_days=7,
        first_date=date(2026, 9, 1), last_date=date(2026, 9, 3),
        cutoff=date(2026, 9, 7), present_sessions=present,
        rows_not_back_checked=2,
    )
    body = await _render_csv(meta)
    assert "2026-09-02" in body.split("Missing sessions", 1)[1].splitlines()[0]
    assert "# Rows without a next-session back-check: 2" in body
    assert body.count("# Known limitation ") == len(ex.KNOWN_LIMITATIONS)
    # Still parses: every preamble line is a comment, the header follows.
    lines = body.splitlines()
    header = next(line for line in lines if not line.startswith("#"))
    assert next(csv.reader(io.StringIO(header))) == ex.COLUMNS


# --------------------------------------------------------------------------
# Through the real endpoints
# --------------------------------------------------------------------------

_SYMBOLS = ["GAPDA", "GAPDB", "GAPDC"]
# Mon 2024-02-05 and Wed 2024-02-07: Tue 2024-02-06 is a trading day with no
# entry. Old enough to clear the publication delay; a year no other suite uses.
_MON, _TUE, _WED = date(2024, 2, 5), date(2024, 2, 6), date(2024, 2, 7)


async def _cleanup() -> None:
    async with SessionLocal() as s:
        await s.execute(delete(DailyScorecardEntry).where(DailyScorecardEntry.symbol.in_(_SYMBOLS)))
        await s.commit()


async def _seed(recent: date) -> None:
    await _cleanup()
    rows = [
        (_MON, 1, "GAPDA", 1.0, 0.5),
        (_WED, 1, "GAPDB", -1.0, 0.5),
        (recent, 9, "GAPDC", 2.0, 0.1),  # back-checked but newer than the export cutoff
    ]
    async with SessionLocal() as s:
        for as_of, rank, sym, chg, spy in rows:
            s.add(DailyScorecardEntry(
                as_of=as_of, symbol=sym, rank=rank, score_at_flag=80.0,
                price_at_flag=10.0, price_next_day=10.0 * (1 + chg / 100),
                change_pct_1d_after=chg, spy_change_pct_1d=spy,
                alpha_vs_spy=chg - spy,
            ))
        await s.commit()


@pytest.fixture
def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_json_export_lists_a_missing_session_from_the_database(client):
    recent = datetime.now(UTC).date() - timedelta(days=2)
    await _seed(recent)
    try:
        async with client:
            r = await client.get("/api/scorecard.json")
        assert r.status_code == 200
        meta = r.json()["meta"]
        assert _TUE.isoformat() in meta["missing_sessions"]
        assert _MON.isoformat() not in meta["missing_sessions"]
        assert {x["date"] for x in meta["restatements"]} >= {"2026-06-15", "2026-08-25"}
        assert meta["known_limitations"]
        assert isinstance(meta["rows_not_back_checked"], int)
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_csv_endpoint_carries_both_restatements(client):
    await _seed(datetime.now(UTC).date() - timedelta(days=2))
    try:
        async with client:
            r = await client.get("/api/scorecard.csv")
        assert r.status_code == 200
        assert "# Restatement 2026-08-25:" in r.text
        assert "# Restatement 2026-06-15:" in r.text
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_summary_says_how_many_headline_rows_are_newer_than_the_download(client):
    """The page headline counts every back-checked row; the download stops
    at the delay cutoff. The summary must carry the difference so the page
    can state it (T-06)."""
    recent = datetime.now(UTC).date() - timedelta(days=2)
    await _seed(recent)
    try:
        async with client:
            r = await client.get("/api/scorecard?days=1")
        summary = r.json()["summary"]
        cutoff = date.fromisoformat(summary["export_cutoff"])
        assert cutoff == datetime.now(UTC).date() - timedelta(days=7)
        assert summary["entries_scored_after_export_cutoff"] >= 1
        assert summary["entries_scored_after_export_cutoff"] <= summary["entries_scored"]
        assert _TUE.isoformat() in summary["missing_sessions"]
    finally:
        await _cleanup()
