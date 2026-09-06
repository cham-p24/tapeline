"""The two COMPOSITE FACTORS must run before the display-column backfills.

Scar tissue twice over, and the reason is scheduling rather than correctness.
The Finnhub stages are serial and paced at ~1.1s/request against per-run budgets
of 2,500, so the whole chain takes about two hours. The latches that gate it are
in-memory globals, so every deploy resets them and the chain restarts from stage
one. Whatever sits at the back of that chain is what never runs.

── THE FIRST LESSON (2026-08-31), still true ───────────────────────────────
With `_refresh_fundamentals_cache` and `_refresh_insider_cache` at the FRONT, a
day of active deploys meant the column stages were never reached: market_cap sat
at 49 of 8,879 rows in production and pe_ttm / beta / eps_ttm / dividend_yield
sat at zero, so the ticker page rendered an em-dash for every one of them while
the code was "working". Position in this chain decides what converges.

── THE SECOND LESSON (2026-09-07), which reversed the order ────────────────
The fix above was filed under "user-visible COLUMNS first, internal caches
last". That framing was wrong about what those two passes are. They are not
internal caches: they populate `sub_fundamentals` and `sub_smart_money`, two of
the six factors, carrying 30% of the composite between them. A factor with no
reading scores as NEUTRAL 50 by design (services/score.py), which caps a
both-missing row's composite at 85 whatever the other four say.

Measured on production 2026-09-07 with those two stages at the back: 5,697 of
7,417 scored rows had BOTH factors NULL, including 1,001 of the 1,035 rows over
$10B — NVDA, AAPL, MSFT, AMZN, META, TSLA and SPY among them. The best composite
any both-null row had ever reached was 80.2 against a top-ten cutoff of 81.1, so
the published record was drawn entirely from the covered minority and contained
no mega-caps at all.

A stale key statistic renders an em-dash beside a number. A missing factor
silently rewrites which names get published. So the factors go first — and the
columns still converge, because every stage is now self-gating (the backfills
query `WHERE <col> IS NULL`; the two factor passes select on their `last_*_at`
stamp), so a completed stage costs one query and falls straight through.

If someone reorders this again, the symptom is silent and takes a day to notice
— hence the test. Reordering is legitimate; doing it without reading both
lessons above is not.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

from app.workers import signal_publisher

_STAGES = (
    "_refresh_fundamentals_cache",
    "_refresh_insider_cache",
    "_backfill_market_cap",
    "_backfill_key_statistics",
    "_backfill_sectors",
)


def _chain_node() -> ast.AsyncFunctionDef:
    tree = ast.parse(
        pathlib.Path(inspect.getfile(signal_publisher)).read_text(encoding="utf-8")
    )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AsyncFunctionDef)
            and node.name == "_serial_finnhub_refreshes"
        ):
            return node
    raise AssertionError("_serial_finnhub_refreshes not found")


def _call_order() -> list[str]:
    """Stage calls in source order, read from the AST.

    AST rather than a regex over `inspect.getsource`. The block of comments
    above these calls discusses every stage by name, including in the order
    they used to run, and a text scan has no way to tell an explanation of the
    change from the change. The AST cannot see a comment or a docstring at all,
    which is the property the house rule is after — not merely a pattern
    careful enough to dodge today's prose.

    Sorted by position because `ast.walk` is breadth-first, not source order.
    """
    found = []
    for sub in ast.walk(_chain_node()):
        if isinstance(sub, ast.Call):
            name = getattr(sub.func, "id", None)
            if name in _STAGES:
                found.append((sub.lineno, sub.col_offset, name))
    return [name for _, _, name in sorted(found)]


def test_every_stage_is_still_in_the_chain():
    assert set(_call_order()) == set(_STAGES)


def test_the_composite_factors_run_before_the_display_columns():
    order = _call_order()
    factors = ["_refresh_fundamentals_cache", "_refresh_insider_cache"]
    columns = ["_backfill_market_cap", "_backfill_key_statistics", "_backfill_sectors"]
    last_factor = max(order.index(c) for c in factors)
    first_column = min(order.index(c) for c in columns)
    assert last_factor < first_column, (
        f"a display-column backfill runs before a composite-factor pass "
        f"(order: {order}). That is the arrangement under which 77% of scored "
        f"rows had no fundamentals and no smart-money reading, and the public "
        f"record contained no mega-caps."
    )


def test_market_cap_runs_first_among_the_column_backfills():
    """It also fills sector on the way past, so it does part of the next stage's
    job. That relative ordering survived the 2026-09-07 reversal — only the
    factors moved ahead of the whole column group."""
    columns = [s for s in _call_order() if s.startswith("_backfill_")]
    assert columns[0] == "_backfill_market_cap"


def test_next_earnings_sync_is_wired_into_the_calendar_refresh():
    """The column shipped with nothing writing it; keep it written."""
    src = inspect.getsource(signal_publisher._seed_calendar)
    assert "_sync_next_earnings_dates" in src
    sync = inspect.getsource(signal_publisher._sync_next_earnings_dates)
    # Stale dates must be cleared, or a symbol whose event passed keeps it forever.
    assert "SET next_earnings_date = NULL" in sync
    assert "MIN(e.report_date)" in sync
    assert "report_date >= :today" in sync
