"""The extension shows an account exactly what the website shows it.

`GET /api/extension/record/{symbol}` called `get_scorecard_for_symbol` with
`user=None`, which pins the caller to the free tier's publication delay
(`scorecard._FREE_DELAY_DAYS`). The endpoint is authenticated, so this was not
a safety measure — a Pro subscriber's extension reported a `lastSeen` up to a
week behind the same subscriber's view of the same record on the site.

Only the row list was affected. The summary stats are tier-invariant by design
(the per-ticker proof signal should not change with what you pay), so hit rate,
median alpha and best/worst were already complete for everyone.

These drive the real endpoint against a seeded record: a free account still
gets the delay, a paying one does not, and neither sees a different set of
summary numbers.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.db import session_scope
from app.models import DailyScorecardEntry, Ticker, User
from app.routers.extension import record
from app.routers.scorecard import _FREE_DELAY_DAYS

SYM = "ZEXTRC"  # <=6 chars: scorecard._SYMBOL_RE


async def _make_user(tier: str) -> User:
    uid = f"u_{uuid.uuid4().hex}"
    async with session_scope() as s:
        s.add(User(
            id=uid, email=f"{uid}@example.test", name="Ext probe",
            tier=tier, password_hash="x", drip_state="",
        ))
    async with session_scope() as s:
        return (await s.execute(select(User).where(User.id == uid))).scalar_one()


@pytest.fixture
async def seeded():
    """One pick inside the delay window, one comfortably outside it."""
    today = datetime.now(UTC).date()
    fresh = today - timedelta(days=1)                      # hidden from free
    old = today - timedelta(days=_FREE_DELAY_DAYS + 30)    # visible to all
    async with session_scope() as s:
        s.add(Ticker(symbol=SYM, name=SYM, asset_class="stock", score=70.0,
                     sub_trend=70.0, sub_rs=70.0))
        for as_of in (fresh, old):
            s.add(DailyScorecardEntry(
                symbol=SYM, as_of=as_of, rank=1, score_at_flag=70.0,
                price_at_flag=10.0, price_next_day=10.5,
                change_pct_1d_after=5.0, spy_change_pct_1d=1.0,
                alpha_vs_spy=4.0,
            ))
    yield {"fresh": fresh, "old": old}
    async with session_scope() as s:
        await s.execute(delete(DailyScorecardEntry).where(DailyScorecardEntry.symbol == SYM))
        await s.execute(delete(Ticker).where(Ticker.symbol == SYM))


async def _record_for(tier: str) -> dict:
    user = await _make_user(tier)
    try:
        async with session_scope() as s:
            return await record(symbol=SYM, user=user, session=s)
    finally:
        async with session_scope() as s:
            await s.execute(delete(User).where(User.id == user.id))


@pytest.mark.asyncio
async def test_a_paying_account_sees_the_live_row(seeded):
    out = await _record_for("pro")

    assert out["lastSeen"] == seeded["fresh"].isoformat(), (
        f"a Pro account's extension reported lastSeen={out['lastSeen']}, not "
        f"the pick from yesterday — it is still pinned to the free delay"
    )


@pytest.mark.asyncio
async def test_a_free_account_still_gets_the_publication_delay(seeded):
    """The gate must still gate. Parity, not a paywall hole."""
    out = await _record_for("free")

    assert out["lastSeen"] == seeded["old"].isoformat(), (
        f"a free account saw lastSeen={out['lastSeen']}; the "
        f"{_FREE_DELAY_DAYS}-day publication delay is not being applied"
    )


@pytest.mark.asyncio
async def test_the_summary_stats_are_the_same_for_both(seeded):
    """Tier-invariant by design — the proof signal is not a paid feature."""
    pro = await _record_for("pro")
    free = await _record_for("free")

    for k in ("appearances", "hitRate", "medianAlpha", "best", "worst"):
        assert pro[k] == free[k], (
            f"{k} differs by tier (pro={pro[k]!r} free={free[k]!r}); the "
            f"per-ticker summary is meant to be identical for every viewer"
        )
    assert pro["appearances"] == 2, "both entries should count toward the summary"
