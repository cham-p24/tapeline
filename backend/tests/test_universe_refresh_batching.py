"""The universe refresh must land its writes in small, independent batches.

`_refresh_universe` used to do all its work inside ONE transaction. That was
fine while it was insert-only and added a handful of new listings a week.
Widening discovery (#658) turned the same code path into ~8,900 INSERTs plus
~2,400 single-row UPDATEs — thousands of round-trips to Neon inside a single
open write transaction.

Live consequence, measured 2026-08-28: `discover_active_us_tickers` was
verified returning all 11,364 tickers (E=480 among them), and yet EBAY, EOG,
EQT, EXC, ELV and ETN were still absent from the table hours and three deploys
later. The fetch was right; the write never landed.

`_backfill_sectors` records the same lesson for its own long run — do the work
outside a session and land it in short batched transactions — so this follows
that pattern: plan in memory, write in chunks, and let one bad chunk cost one
chunk instead of the whole pass.
"""

import pytest
from sqlalchemy import select

from app.db import session_scope
from app.models import Ticker
from app.workers import signal_publisher as sp

_PREFIX = "ZZBATCH"


@pytest.fixture
async def cleanup():
    yield
    async with session_scope() as s:
        rows = (await s.execute(
            select(Ticker).where(Ticker.symbol.like(f"{_PREFIX}%"))
        )).scalars().all()
        for t in rows:
            await s.delete(t)
        await s.commit()


def _discovery(rows):
    async def _fake(*_a, **_k):
        return rows

    return _fake


@pytest.mark.asyncio
async def test_inserts_and_edits_both_land(monkeypatch, cleanup):
    async with session_scope() as s:
        s.add(Ticker(
            symbol=f"{_PREFIX}OLD", name=f"{_PREFIX}OLD", sector="Unknown",
            asset_class="equity",
        ))
        await s.commit()

    rows = [
        {"symbol": f"{_PREFIX}OLD", "name": "Zebra Old Corp.",
         "sector": "Unknown", "asset_class": "etf"},
    ] + [
        {"symbol": f"{_PREFIX}{i:03d}", "name": f"Zebra {i}",
         "sector": "Unknown", "asset_class": "equity"}
        for i in range(12)
    ]
    monkeypatch.setattr(
        "app.services.polygon_feed.discover_active_us_tickers", _discovery(rows)
    )
    monkeypatch.setattr(sp, "_UNIVERSE_WRITE_BATCH", 5)  # force several batches

    await sp._refresh_universe()

    async with session_scope() as s:
        got = {
            t.symbol: t for t in (await s.execute(
                select(Ticker).where(Ticker.symbol.like(f"{_PREFIX}%"))
            )).scalars().all()
        }

    assert len(got) == 13, f"expected 12 new + 1 existing, got {len(got)}"
    assert got[f"{_PREFIX}OLD"].name == "Zebra Old Corp.", "the edit did not land"
    assert got[f"{_PREFIX}OLD"].asset_class == "etf"
    assert got[f"{_PREFIX}011"].name == "Zebra 11", "later batches did not land"


@pytest.mark.asyncio
async def test_one_failing_batch_does_not_lose_the_others(monkeypatch, cleanup):
    """The reason for batching at all.

    With a single transaction, any failure anywhere discarded the entire
    pass — which is the shape of what happened in production. Now a bad chunk
    costs that chunk, the rest still commits, and the shortfall is logged as
    an ERROR rather than silently swallowed.
    """
    rows = [
        {"symbol": f"{_PREFIX}{i:03d}", "name": f"Zebra {i}",
         "sector": "Unknown", "asset_class": "equity"}
        for i in range(10)
    ]
    monkeypatch.setattr(
        "app.services.polygon_feed.discover_active_us_tickers", _discovery(rows)
    )
    monkeypatch.setattr(sp, "_UNIVERSE_WRITE_BATCH", 5)

    real_scope = sp.session_scope
    calls = {"n": 0}

    def flaky_scope(*a, **k):
        calls["n"] += 1
        if calls["n"] == 2:      # first WRITE batch (call 1 is the read)
            raise RuntimeError("simulated batch failure")
        return real_scope(*a, **k)

    monkeypatch.setattr(sp, "session_scope", flaky_scope)
    await sp._refresh_universe()
    monkeypatch.setattr(sp, "session_scope", real_scope)

    async with session_scope() as s:
        got = {
            t.symbol for t in (await s.execute(
                select(Ticker).where(Ticker.symbol.like(f"{_PREFIX}%"))
            )).scalars().all()
        }

    assert got, (
        "a single failing batch wiped the whole pass — this is exactly the "
        "all-or-nothing behaviour the batching exists to remove"
    )
    assert len(got) == 5, f"expected the 5 rows of the surviving batch, got {len(got)}"


def test_the_pass_does_not_hold_one_transaction_across_all_writes():
    """Pinned at the source: the defect is structural, and a green run against
    a 13-row fixture would not reveal it at 11,000 rows.

    Comments and docstrings are stripped before matching, since the prose
    explaining the fix necessarily mentions the thing it removed.
    """
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(sp._refresh_universe)))
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
    code = ast.unparse(tree)

    assert "_UNIVERSE_WRITE_BATCH" in code, "the writes are not chunked"
    # The read is its own scope; the writes get theirs. More than one
    # session_scope means the pass is no longer all-or-nothing.
    assert code.count("session_scope()") >= 3, (
        "the pass still opens a single session, so ~11,000 writes share one "
        "transaction and any failure discards all of them"
    )
