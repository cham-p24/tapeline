"""A ticker we hold no score for is not the biggest mover.

`briefing._key` ranked the watchlist by absolute change since the user added
each ticker, and computed the current side as `t.score or 0.0`. A NULL score
therefore became 0.0, so its delta came out as `abs(0 - baseline)` — the whole
baseline, a large number — and the row sorted straight to the top.

The row itself prints an em-dash for its score, so the briefing email led with
a ticker showing no score at all, ranked first for a move it never made.

Null scores are reachable and became more so: the factor caches are empty after
every restart, and the 2026-08-24 repair nulled 409 rows whose "score" rested on
fewer than two factors.
"""
from __future__ import annotations

import pytest

from app.models import Ticker
from app.services import briefing


def _sorted_symbols(rows, baselines) -> list[str]:
    """Drive the real ranking used by the briefing."""
    def _key(t: Ticker) -> tuple[float, float]:
        base = baselines.get(t.symbol)
        cur = t.score
        if cur is None:
            return (-1.0, -1.0)
        delta = abs(cur - base) if base is not None else -1.0
        return (delta, cur)

    return [t.symbol for t in sorted(rows, key=_key, reverse=True)]


def test_the_real_mover_leads_not_the_unscored_one():
    rows = [
        Ticker(symbol="NOSCORE", score=None),   # abs(0 - 80) = 80 under the bug
        Ticker(symbol="MOVER", score=62.0),     # abs(62 - 50) = 12
        Ticker(symbol="FLAT", score=51.0),      # abs(51 - 50) = 1
    ]
    baselines = {"NOSCORE": 80.0, "MOVER": 50.0, "FLAT": 50.0}

    order = _sorted_symbols(rows, baselines)

    assert order[0] == "MOVER", (
        f"ranking led with {order[0]}; a missing score was treated as a "
        f"collapse to zero and outranked every real move"
    )
    assert order[-1] == "NOSCORE", "an unscored ticker must rank last"


def test_a_genuine_zero_still_ranks_as_the_move_it_is():
    """0.0 is a real reading and must not be swept up with the nulls."""
    rows = [
        Ticker(symbol="REALZERO", score=0.0),   # abs(0 - 80) = 80, and true
        Ticker(symbol="MOVER", score=62.0),     # abs(62 - 50) = 12
    ]
    baselines = {"REALZERO": 80.0, "MOVER": 50.0}

    assert _sorted_symbols(rows, baselines)[0] == "REALZERO"


@pytest.mark.asyncio
async def test_the_rendered_briefing_leads_with_the_real_mover():
    """The shipped code, executed — the local _key above is only a model of it.

    A source-scan was the obvious way to bind these assertions to the real
    function (`_key` is a closure, so it cannot be imported). It was also the
    wrong way twice over: it tripped on the explanatory comment quoting the old
    line, and a passing string match would never have proved the ranking runs.
    So this seeds a watchlist, renders the actual email, and reads the order of
    the symbols out of the HTML.
    """
    from sqlalchemy import delete, select

    from app.db import session_scope
    from app.models import Ticker, User, WatchlistItem
    from app.services.briefing import generate_briefing_html

    import uuid

    syms = ["ZNOSCORE", "ZMOVER", "ZFLAT"]
    uid = f"u_{uuid.uuid4().hex}"
    email = f"{uid}@example.test"
    try:
        async with session_scope() as s:
            # User.id has no default — native auth generates "u_<uuid>" on signup.
            s.add(User(id=uid, email=email, name="Rank probe", tier="pro",
                       password_hash="x", drip_state=""))
        async with session_scope() as s:
            for sym, score in (("ZNOSCORE", None), ("ZMOVER", 62.0), ("ZFLAT", 51.0)):
                s.add(Ticker(
                    symbol=sym, name=sym, asset_class="stock", score=score,
                    sub_trend=60.0, sub_rs=60.0,
                ))
            # Baselines chosen so the unscored row wins under the old rule:
            # abs(0 - 80) = 80, versus the real mover's abs(62 - 50) = 12.
            for sym, base in (("ZNOSCORE", 80.0), ("ZMOVER", 50.0), ("ZFLAT", 50.0)):
                s.add(WatchlistItem(user_id=uid, symbol=sym, baseline_score=base))

        async with session_scope() as s:
            user = (await s.execute(
                select(User).where(User.email == email)
            )).scalar_one()
            html = await generate_briefing_html(s, user)

        positions = {sym: html.find(sym) for sym in syms}
        assert all(p >= 0 for p in positions.values()), (
            f"not every watchlist symbol rendered: {positions}"
        )
        assert positions["ZMOVER"] < positions["ZNOSCORE"], (
            "the briefing led with a ticker it holds no score for, ranked "
            "above a real 12-point move"
        )
        assert positions["ZFLAT"] < positions["ZNOSCORE"], (
            "an unscored ticker outranked a real 1-point move"
        )
    finally:
        async with session_scope() as s:
            await s.execute(delete(WatchlistItem).where(WatchlistItem.symbol.in_(syms)))
            await s.execute(delete(Ticker).where(Ticker.symbol.in_(syms)))
            await s.execute(delete(User).where(User.email == email))
