"""Picks published and picks back-checked are two different counts.

`entries_scored` counts only rows carrying an `alpha_vs_spy`, because every
rate in the summary is computed over those. Four public surfaces and the MCP
`entries_logged` field printed that number under the word "logged".

It is structurally always the smaller one: the top 10 are written the moment
they print, and the back-check cannot exist until the next session's close. So
the record read smaller than it is, on the landing hero, on /scorecard, in the
server-rendered citation AI answer engines quote, and in the MCP tool an
assistant reads directly. Production on 2026-09-02: 770 logged, 738
back-checked.

These tests drive the real endpoint against real rows rather than the
aggregation helper, because the defect was never in the arithmetic — it was in
which query fed which word.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.models.scorecard import DailyScorecardEntry
from app.routers.scorecard import get_scorecard

# Far enough back that a stray real row cannot collide with these dates.
BASE_DAY = date(2001, 3, 5)


async def _seed(*, back_checked: int, logged_only: int) -> list[int]:
    """Rows with an alpha, plus rows still awaiting their next-day close."""
    ids: list[int] = []
    async with session_scope() as s:
        for i in range(back_checked):
            e = DailyScorecardEntry(
                as_of=BASE_DAY + timedelta(days=i % 3),
                symbol=f"BC{i}",
                rank=(i % 10) + 1,
                score_at_flag=70.0,
                price_at_flag=100.0,
                price_next_day=101.0,
                change_pct_1d_after=1.0,
                spy_change_pct_1d=0.5,
                alpha_vs_spy=0.5,
            )
            s.add(e)
        for i in range(logged_only):
            # The newest session: logged, no back-check yet. Exactly the rows
            # that made "logged" and "scored" diverge in production.
            e = DailyScorecardEntry(
                as_of=BASE_DAY + timedelta(days=9),
                symbol=f"LO{i}",
                rank=(i % 10) + 1,
                score_at_flag=80.0,
                price_at_flag=50.0,
                price_next_day=None,
                change_pct_1d_after=None,
                spy_change_pct_1d=None,
                alpha_vs_spy=None,
            )
            s.add(e)
    async with session_scope() as s:
        rows = (
            await s.execute(
                select(DailyScorecardEntry.id).where(
                    DailyScorecardEntry.as_of >= BASE_DAY,
                    DailyScorecardEntry.as_of <= BASE_DAY + timedelta(days=9),
                )
            )
        ).scalars().all()
        ids.extend(rows)
    return ids


async def _cleanup(ids: list[int]) -> None:
    async with session_scope() as s:
        await s.execute(delete(DailyScorecardEntry).where(DailyScorecardEntry.id.in_(ids)))


async def _summary() -> dict:
    async with session_scope() as s:
        data = await get_scorecard(session=s, user=None, days=30)
    return data["summary"]


@pytest.mark.asyncio
async def test_the_api_reports_both_counts_and_they_differ():
    ids = await _seed(back_checked=12, logged_only=7)
    try:
        summary = await _summary()
        assert "entries_logged" in summary, (
            "the summary has no entries_logged field, so every surface that "
            "wants to say 'logged' has only the back-checked count to print"
        )
        assert summary["entries_logged"] >= 19
        assert summary["entries_scored"] >= 12
        assert summary["entries_logged"] - summary["entries_scored"] >= 7, (
            f"the 7 not-yet-back-checked picks are missing from the logged "
            f"count: logged={summary['entries_logged']} "
            f"scored={summary['entries_scored']}"
        )
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_entries_logged_counts_rows_with_no_alpha():
    """The whole point: a pick with no back-check yet is still a published pick.

    Proven by adding only alpha-less rows and watching one count move.
    """
    ids = await _seed(back_checked=4, logged_only=0)
    try:
        before = await _summary()
        more = await _seed(back_checked=0, logged_only=5)
        ids.extend(more)
        after = await _summary()

        assert after["entries_logged"] == before["entries_logged"] + 5, (
            "publishing 5 more picks did not move entries_logged — it is not "
            "counting the rows that have no next-day close yet"
        )
        assert after["entries_scored"] == before["entries_scored"], (
            "entries_scored moved when nothing was back-checked; the rates "
            "computed over it would now have the wrong denominator"
        )
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_the_mcp_tool_names_both_numbers_correctly():
    """`entries_logged` was fed `entries_scored` in the MCP payload.

    That field is read verbatim by AI assistants, which is the channel two real
    signups came through, so it understated the record to exactly the audience
    least able to check it.
    """
    from app.routers.mcp import _tool_track_record

    ids = await _seed(back_checked=9, logged_only=6)
    try:
        async with session_scope() as s:
            out = await _tool_track_record({}, s)

        assert out["entries_logged"] > out["entries_back_checked"], (
            f"the MCP tool reports logged={out['entries_logged']} and "
            f"back_checked={out['entries_back_checked']}; with 6 picks awaiting "
            f"a back-check the logged figure must be the larger one"
        )
        summary = await _summary()
        assert out["entries_logged"] == summary["entries_logged"]
        assert out["entries_back_checked"] == summary["entries_scored"]
    finally:
        await _cleanup(ids)


@pytest.mark.asyncio
async def test_an_empty_archive_reports_zero_not_none():
    """`entries_logged` must be a number even with nothing to count.

    A None here renders as "null picks logged" on a server-rendered page.
    """
    summary = await _summary()
    assert isinstance(summary["entries_logged"], int)
    assert summary["entries_logged"] >= 0


@pytest.mark.asyncio
async def test_the_counts_are_tier_invariant():
    """The delay gate filters per-day picks, never the headline counts.

    A free viewer sees picks delayed; the record's size is the same fact for
    everyone, and a summary that shrank for non-payers would misstate it.
    """
    from app.models import User

    ids = await _seed(back_checked=6, logged_only=4)
    uid = f"u_{uuid.uuid4().hex}"
    try:
        async with session_scope() as s:
            s.add(User(
                id=uid, email=f"{uid}@example.test", name="Tier probe",
                tier="free", password_hash="x", drip_state="",
                created_at=datetime.now(UTC),
            ))
        async with session_scope() as s:
            free_user = (await s.execute(select(User).where(User.id == uid))).scalar_one()
            free = (await get_scorecard(session=s, user=free_user, days=30))["summary"]
        anon = await _summary()

        assert free["entries_logged"] == anon["entries_logged"]
        assert free["entries_scored"] == anon["entries_scored"]
    finally:
        async with session_scope() as s:
            await s.execute(delete(User).where(User.id == uid))
        await _cleanup(ids)
