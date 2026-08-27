"""A never-scored ticker must still get looked at once.

`refresh_active_universe` selects `WHERE score IS NOT NULL`. A freshly
discovered ticker has no score, so it was excluded from the active universe →
never included in `fetch_snapshots` → never got a price or volume → never got
a score. Excluded forever, having never once been measured.

That is the SAME chicken-and-egg the function's own comment describes fixing
on 2026-05-24 for `volume IS NOT NULL AND price IS NOT NULL`. Swapping the
predicate to `score IS NOT NULL` moved the trap up a level instead of removing
it, and nothing surfaced it until discovery (#658) started adding thousands of
real tickers that could never be scored: the published universe stayed frozen
at ~2,460 rows — 750 A-tickers, 626 B, 671 C, and a single E-ticker — while
the table behind it grew.

The fix is a small ADDITIVE quota of bootstrap slots, not a bigger universe.
The point is to let liquidity be MEASURED: a ticker that gets its snapshot and
turns out to be illiquid then loses on dollar volume like everything else,
which is a real answer. Never looking is not.
"""

import pytest

from app.db import session_scope
from app.models import Ticker
from app.services import universe as universe_svc

_SYMS = ["ZZBOOT1", "ZZBOOT2", "ZZBOOT3", "ZZSCORED"]


@pytest.fixture
async def cleanup():
    yield
    async with session_scope() as s:
        for sym in _SYMS:
            t = await s.get(Ticker, sym)
            if t is not None:
                await s.delete(t)
        await s.commit()


async def _seed():
    async with session_scope() as s:
        # A scored, liquid incumbent.
        s.add(Ticker(
            symbol="ZZSCORED", name="Zebra Scored", sector="Tech",
            asset_class="equity", score=71.0, price=100.0, volume=5_000_000,
        ))
        # Never-scored discoveries: no score, no price, no volume — exactly
        # what _refresh_universe inserts.
        for sym in ("ZZBOOT1", "ZZBOOT2", "ZZBOOT3"):
            s.add(Ticker(
                symbol=sym, name=f"Zebra {sym}", sector="Unknown",
                asset_class="equity",
            ))
        await s.commit()


@pytest.mark.asyncio
async def test_never_scored_tickers_are_admitted(cleanup):
    """The core of it: an unscored ticker must reach the active universe, or
    it can never earn the score that would let it in."""
    await _seed()
    await universe_svc.refresh_active_universe()
    syms = {s for s, _n, _sec in universe_svc.active_universe()}

    for sym in ("ZZBOOT1", "ZZBOOT2", "ZZBOOT3"):
        assert sym in syms, (
            f"{sym} has no score and was excluded, so it will never be "
            f"snapshotted, so it will never get a score — the deadlock"
        )


@pytest.mark.asyncio
async def test_scored_tickers_are_still_included(cleanup):
    """The bootstrap must be additive. If it displaced scored names the
    scanner would lose real coverage to make room for unmeasured rows."""
    await _seed()
    await universe_svc.refresh_active_universe()
    syms = {s for s, _n, _sec in universe_svc.active_universe()}
    assert "ZZSCORED" in syms


@pytest.mark.asyncio
async def test_bootstrap_is_bounded(cleanup, monkeypatch):
    """The quota is a trickle, not a floodgate: it widens the bulk
    /v3/snapshot call (250 symbols per request), and an unbounded intake would
    turn one extra request per tick into dozens."""
    monkeypatch.setattr(universe_svc, "BOOTSTRAP_SLOTS", 2)
    await _seed()
    await universe_svc.refresh_active_universe()
    syms = [s for s, _n, _sec in universe_svc.active_universe()]
    admitted = [s for s in syms if s.startswith("ZZBOOT")]
    assert len(admitted) <= 2, (
        f"bootstrap admitted {len(admitted)} rows against a quota of 2"
    )


@pytest.mark.asyncio
async def test_zero_slots_disables_the_bootstrap_entirely(cleanup, monkeypatch):
    """`UNIVERSE_BOOTSTRAP_SLOTS=0` must be a real off switch, so the intake
    can be stopped from the environment without a deploy if it ever costs more
    than expected."""
    monkeypatch.setattr(universe_svc, "BOOTSTRAP_SLOTS", 0)
    await _seed()
    await universe_svc.refresh_active_universe()
    syms = {s for s, _n, _sec in universe_svc.active_universe()}
    assert not any(s.startswith("ZZBOOT") for s in syms)
    assert "ZZSCORED" in syms, "the off switch also dropped scored tickers"


def test_the_bootstrap_query_only_offers_never_scored_rows():
    """The intake must advance through the market rather than re-offering the
    same names forever.

    That property rests on the bootstrap query filtering `score IS NULL`: a
    ticker that earns a score drops out, so the next refresh continues where
    this one stopped. Without the filter the quota would be spent every hour
    on the same alphabetically-first rows — already scored, already covered —
    and the rest of the market would never be reached.

    Checked at the source because the main query returns scored rows too, so
    a scored symbol appearing in the final universe proves nothing about which
    query put it there.

    An earlier version of this test re-queried the DB instead and passed even
    with the filter deleted — it was verifying SQLAlchemy, not the fix.
    """
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(universe_svc.refresh_active_universe)))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module))
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    code = ast.unparse(tree)  # comments and docstrings stripped

    assert "Ticker.score.is_(None)" in code, (
        "the bootstrap query does not restrict to never-scored tickers, so "
        "its quota is spent re-offering rows that already have scores and the "
        "intake never advances"
    )
    assert "Ticker.symbol.asc()" in code, (
        "the bootstrap intake is unordered, so which tickers get their first "
        "look is left to the planner and coverage is not guaranteed to advance"
    )
