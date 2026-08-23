"""What OUR calls on this ticker did next — the one thing no rival publishes.

`daily_scorecard` freezes the algo's top-10 each day and a back-check job fills
in the next session's outcome. `flag_record` on GET /api/ticker/{symbol} is
that record for a single ticker: every flag, most recent first, plus a summary.

Contract pinned here:

  1. The summary arithmetic: how many times we flagged it, how many of those
     have a resolved next-session outcome, how many of THOSE beat SPY, and the
     median alpha over them. Hand-built rows, hand-computed answers.
  2. LOSSES ARE PRESENT. A losing flag appears in `flags` and counts in the
     denominator; a record that hides its losers is marketing, not a record.
     This is the test that must never be "fixed".
  3. A flag with no back-check yet is `beat_spy: null` — not false. "We do not
     know yet" and "it lost" are different statements.
  4. The never-flagged state (~8,400 of 8,879 symbols) is clean and is not an
     error: zero counts, empty list, null median, 200 OK.
  5. The horizon is stated as next-session, and nothing in the payload implies
     a 1-week / 1-month / 3-month figure — the schema stores none.
  6. A suspect vendor print is COUNTED and disclosed, never dropped.
  7. Row visibility mirrors the scorecard router's delay for non-paying
     viewers, and the payload SAYS how many rows that withheld. The delay is on
     recency only: it never removes a row for having lost.

See routers/ticker.py (_flag_record_payload) and models/scorecard.py.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.main import app
from app.models import DailyScorecardEntry, Ticker, User


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


FLAGGED = "FRFLAG"      # has a history — wins AND losses
NEVER = "FRNEVER"       # in the universe, never flagged — the common case
PENDING = "FRPEND"      # flagged, back-check has not run yet
_SYMBOLS = (FLAGGED, NEVER, PENDING)


def _days_ago(n: int) -> date:
    """UTC, matching the boundary _flag_record_payload's delay filter uses."""
    return datetime.now(UTC).date() - timedelta(days=n)


async def _reset() -> None:
    async with session_scope() as s:
        await s.execute(
            delete(DailyScorecardEntry).where(DailyScorecardEntry.symbol.in_(_SYMBOLS))
        )
        await s.execute(delete(Ticker).where(Ticker.symbol.in_(_SYMBOLS)))
        await s.commit()


# The FLAGGED history, hand-built. Every date is well outside the scorecard's
# 7-day delay window, so the DEFAULT (anonymous) view sees all five — the delay
# itself is exercised separately at the bottom of this file.
#
#   alpha  +2.0   beat SPY
#   alpha  -3.5   LOST   <- must survive to the payload
#   alpha  +0.5   beat SPY
#   alpha  -1.0   LOST
#   alpha   0.0   matched SPY exactly — NOT a beat
#
# resolved = 5, beat = 2, sorted alphas [-3.5, -1.0, 0.0, 0.5, 2.0] -> median 0.0
_FLAG_HISTORY = [
    # (days_ago, rank, score_at_flag, price_at_flag, price_next_day, chg, spy, alpha)
    (10, 1, 91.0, 100.0, 103.0, 3.0, 1.0, 2.0),
    (20, 4, 88.0, 50.0, 48.0, -4.0, -0.5, -3.5),
    (30, 2, 90.0, 20.0, 20.2, 1.0, 0.5, 0.5),
    (40, 7, 85.0, 10.0, 9.9, -1.0, 0.0, -1.0),
    (50, 9, 84.0, 200.0, 202.0, 1.0, 1.0, 0.0),
]

# PENDING's single flag is also outside the delay window, so its row shape can
# be inspected anonymously without entangling this with the tier gate.
_PENDING_DAYS_AGO = 20


@pytest.fixture(autouse=True)
async def _seed():
    await _reset()
    async with session_scope() as s:
        for sym in _SYMBOLS:
            s.add(
                Ticker(
                    symbol=sym,
                    name=f"{sym} Inc",
                    sector="Flag Record Test",
                    asset_class="equity",
                    score=70.0,
                )
            )
        for d, rank, score, px, nxt, chg, spy, alpha in _FLAG_HISTORY:
            s.add(
                DailyScorecardEntry(
                    as_of=_days_ago(d),
                    symbol=FLAGGED,
                    rank=rank,
                    score_at_flag=score,
                    price_at_flag=px,
                    price_next_day=nxt,
                    change_pct_1d_after=chg,
                    spy_change_pct_1d=spy,
                    alpha_vs_spy=alpha,
                )
            )
        # Flagged, next session not yet back-checked.
        s.add(
            DailyScorecardEntry(
                as_of=_days_ago(_PENDING_DAYS_AGO),
                symbol=PENDING,
                rank=3,
                score_at_flag=89.0,
                price_at_flag=42.0,
                price_next_day=None,
                change_pct_1d_after=None,
                spy_change_pct_1d=None,
                alpha_vs_spy=None,
            )
        )
        await s.commit()
    yield
    await _reset()


async def _record(client: httpx.AsyncClient, symbol: str, **kw) -> dict:
    r = await client.get(f"/api/ticker/{symbol}", **kw)
    assert r.status_code == 200, r.text
    return r.json()["flag_record"]


# ---------------------------------------------------------------------------
# 1 — summary arithmetic
# ---------------------------------------------------------------------------

async def test_summary_arithmetic(client) -> None:
    async with client:
        rec = await _record(client, FLAGGED)

    assert rec["flag_count"] == 5
    assert rec["resolved_count"] == 5
    # alpha == 0.0 matched SPY; matching is not beating.
    assert rec["beat_spy_count"] == 2
    assert rec["median_alpha_vs_spy"] == 0.0
    assert rec["first_flagged_on"] == _days_ago(50).isoformat()
    assert rec["last_flagged_on"] == _days_ago(10).isoformat()


async def test_rows_are_most_recent_first(client) -> None:
    async with client:
        rec = await _record(client, FLAGGED)
    dates = [f["as_of"] for f in rec["flags"]]
    assert dates == sorted(dates, reverse=True)
    assert dates[0] == _days_ago(10).isoformat()


async def test_row_fields_are_carried_through_unaltered(client) -> None:
    async with client:
        rec = await _record(client, FLAGGED)
    newest = rec["flags"][0]
    assert newest["rank"] == 1
    assert newest["score_at_flag"] == 91.0
    assert newest["price_at_flag"] == 100.0
    assert newest["price_next_day"] == 103.0
    assert newest["change_pct_1d_after"] == 3.0
    assert newest["spy_change_pct_1d"] == 1.0
    assert newest["alpha_vs_spy"] == 2.0
    assert newest["beat_spy"] is True


# ---------------------------------------------------------------------------
# 2 — losses are present, never filtered
# ---------------------------------------------------------------------------

async def test_a_losing_flag_is_in_the_output(client) -> None:
    """THE point of the block. If this test ever needs "fixing", stop.

    The -3.5 alpha day is our worst call on this ticker. It must be present in
    the row list, marked as not beating SPY, and counted in the denominator the
    hit numbers are read against.
    """
    async with client:
        rec = await _record(client, FLAGGED)

    alphas = [f["alpha_vs_spy"] for f in rec["flags"]]
    assert -3.5 in alphas, "the losing flag was filtered out of the record"
    assert -1.0 in alphas

    worst = next(f for f in rec["flags"] if f["alpha_vs_spy"] == -3.5)
    assert worst["beat_spy"] is False
    assert worst["change_pct_1d_after"] == -4.0
    assert worst["price_next_day"] == 48.0

    # And it counts: 2 of 5, not 2 of 2.
    assert rec["resolved_count"] == 5
    assert rec["beat_spy_count"] == 2
    assert len([f for f in rec["flags"] if f["beat_spy"] is False]) == 3


async def test_median_alpha_is_taken_over_every_resolved_row(client) -> None:
    """Not over the winners: the median of all five alphas is 0.0, while the
    median of just the two that beat SPY would be 1.25."""
    async with client:
        rec = await _record(client, FLAGGED)
    assert rec["median_alpha_vs_spy"] == 0.0
    assert rec["median_alpha_vs_spy"] != 1.25


# ---------------------------------------------------------------------------
# 3 — unresolved is not the same as lost
# ---------------------------------------------------------------------------

async def test_unresolved_flag_is_null_not_false(client) -> None:
    async with client:
        rec = await _record(client, PENDING)

    assert rec["flag_count"] == 1
    assert rec["resolved_count"] == 0, "no back-check yet"
    assert rec["beat_spy_count"] == 0
    assert rec["median_alpha_vs_spy"] is None, "unknown is null, never 0"

    assert len(rec["flags"]) == 1
    row = rec["flags"][0]
    assert row["beat_spy"] is None, "'not back-checked yet' is not 'it lost'"
    assert row["price_next_day"] is None
    assert row["alpha_vs_spy"] is None
    assert row["price_at_flag"] == 42.0


# ---------------------------------------------------------------------------
# 4 — never flagged is a clean state, not an error
# ---------------------------------------------------------------------------

async def test_never_flagged_is_clean(client) -> None:
    """~8,400 of 8,879 symbols land here. 200, zeros, empty list, null median."""
    async with client:
        r = await client.get(f"/api/ticker/{NEVER}")
    assert r.status_code == 200, r.text
    rec = r.json()["flag_record"]

    assert rec["flag_count"] == 0
    assert rec["resolved_count"] == 0
    assert rec["beat_spy_count"] == 0
    assert rec["median_alpha_vs_spy"] is None
    assert rec["flags"] == []
    assert rec["first_flagged_on"] is None
    assert rec["last_flagged_on"] is None
    assert rec["flags_hidden_recent"] == 0
    assert rec["flags_truncated"] is False
    assert rec["suspect_outlier_count"] == 0


# ---------------------------------------------------------------------------
# 5 — the horizon is next-session and nothing implies otherwise
# ---------------------------------------------------------------------------

async def test_horizon_is_stated_and_no_longer_horizon_is_implied(client) -> None:
    """The schema stores ONE next-session outcome. The payload may not carry a
    1w / 1m / 3m figure, because there is no honest value to put in one."""
    async with client:
        rec = await _record(client, FLAGGED)

    assert rec["horizon"] == "next_session"
    assert rec["horizon_label"] == "next trading session"

    forbidden = (
        "1w", "1m", "3m", "6m", "1y", "week", "month", "year", "ytd",
        "since", "cumulative", "annual", "total_return", "to_date",
    )
    keys = set(rec) | {k for f in rec["flags"] for k in f}
    for key in keys:
        low = key.lower()
        assert not any(bad in low for bad in forbidden), (
            f"{key!r} implies a horizon the scorecard table does not store"
        )


# ---------------------------------------------------------------------------
# 6 — a suspect print is disclosed, not dropped
# ---------------------------------------------------------------------------

async def test_a_suspect_vendor_print_is_counted_not_filtered(client) -> None:
    """Raw vendor closes occasionally carry unadjusted-split prices that produce
    market-impossible 1-day moves. /api/scorecard drops those from its AVERAGES.
    Here they stay in — the row is published, it counts toward resolved_count,
    and the payload discloses that we distrust the print rather than silently
    deleting it."""
    from app.routers.scorecard import _OUTLIER_PCT_THRESHOLD

    async with session_scope() as s:
        s.add(
            DailyScorecardEntry(
                as_of=_days_ago(60),
                symbol=FLAGGED,
                rank=5,
                score_at_flag=86.0,
                price_at_flag=1.0,
                price_next_day=8.0,
                change_pct_1d_after=700.0,   # far past the suspect threshold
                spy_change_pct_1d=0.5,
                alpha_vs_spy=699.5,
            )
        )
        await s.commit()

    async with client:
        rec = await _record(client, FLAGGED)

    assert rec["flag_count"] == 6
    assert rec["resolved_count"] == 6, "the suspect row still counts"
    assert 699.5 in [f["alpha_vs_spy"] for f in rec["flags"]], "still published"
    assert rec["suspect_outlier_count"] == 1
    assert rec["suspect_outlier_threshold_pct"] == _OUTLIER_PCT_THRESHOLD


# ---------------------------------------------------------------------------
# 7 — row visibility mirrors the scorecard delay, and says so
# ---------------------------------------------------------------------------

async def test_recent_rows_are_delayed_for_non_payers_and_disclosed(client) -> None:
    """A flag inside the delay window is withheld from the ROW LIST for an
    anonymous viewer — but the summary still counts it, and the payload states
    how many rows were withheld so the page never looks broken."""
    from app.routers.scorecard import _FREE_DELAY_DAYS

    await _add_todays_flag()

    async with client:
        rec = await _record(client, FLAGGED)

    assert rec["flag_count"] == 6, "the summary counts every flag"
    assert len(rec["flags"]) == 5, "today's flag is withheld from the row list"
    assert rec["flags_hidden_recent"] == 1
    assert rec["flags_delay_days"] == _FREE_DELAY_DAYS
    assert _days_ago(0).isoformat() not in [f["as_of"] for f in rec["flags"]]


async def test_paying_viewer_sees_the_recent_row(client, monkeypatch) -> None:
    await _add_todays_flag()

    async with client:
        cookies = await _sign_up_pro(client, monkeypatch)
        rec = await _record(client, FLAGGED, cookies=cookies)

    assert rec["flag_count"] == 6
    assert len(rec["flags"]) == 6
    assert rec["flags_hidden_recent"] == 0
    assert rec["flags_delay_days"] == 0
    assert _days_ago(0).isoformat() in [f["as_of"] for f in rec["flags"]]


async def test_the_delay_never_removes_a_row_for_losing(client) -> None:
    """The gate is on recency only. Every loss outside the window is visible to
    an anonymous viewer — losses are not what gets held back."""
    async with client:
        rec = await _record(client, FLAGGED)
    assert sorted(f["alpha_vs_spy"] for f in rec["flags"]) == [
        -3.5, -1.0, 0.0, 0.5, 2.0
    ]


async def test_a_failed_read_is_null__not_a_fake_never_flagged_state(
    client, monkeypatch
) -> None:
    """`flag_record: null` means "we could not read the record". It must never
    be collapsed with flag_count 0, which means "we never flagged this". The
    page still renders either way — this endpoint backs the public SSR pages
    and may not 500."""
    from app.routers import ticker as ticker_module

    def _boom(*_a, **_k):
        raise RuntimeError("scorecard read exploded")

    monkeypatch.setattr(ticker_module, "_flag_record_payload", _boom)
    async with client:
        r = await client.get(f"/api/ticker/{FLAGGED}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["flag_record"] is None
    assert body["score"] == 70.0, "the raw values still render"


async def _add_todays_flag() -> None:
    """A flag from today — inside the non-payer delay window, unresolved."""
    async with session_scope() as s:
        s.add(
            DailyScorecardEntry(
                as_of=_days_ago(0),
                symbol=FLAGGED,
                rank=1,
                score_at_flag=93.0,
                price_at_flag=110.0,
                price_next_day=None,
                change_pct_1d_after=None,
                spy_change_pct_1d=None,
                alpha_vs_spy=None,
            )
        )
        await s.commit()


async def _sign_up_pro(client: httpx.AsyncClient, monkeypatch) -> dict:
    """Sign up a user and put them on `pro` — entitled to un-delayed picks."""
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    email = f"flagrec-{_uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "TestPassword!2026", "name": "FlagRec"},
    )
    assert r.status_code == 200, r.text
    cookies = dict(r.cookies)
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
        u.tier = "pro"
        await s.commit()
    return cookies
