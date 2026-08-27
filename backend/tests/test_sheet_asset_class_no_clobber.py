"""A blank sheet cell is a NO-READ, not a vote for "equity".

`upsert_tickers` rewrites `Ticker.asset_class` on EVERY sheet refresh — every
5 minutes — so that dirty legacy values (emoji-prefixed "📈 stock",
"🥇 commodity etf") self-heal. That is a good reason to overwrite.

The bug was the fallback. `normalize_asset_class` turned a blank or
unrecognised cell into `"equity"`, so the refresh did not self-heal, it
ASSERTED: every sheet-governed row whose Asset Class column is empty had
"equity" written over it four times an hour.

That silently undid the reconciliation `_refresh_universe` had just done.
Verified live on 2026-08-28: after discovery corrected ASML (which is NOT in
the sheet) the fix held, while SPY, QQQ, IWM, DIA, VTI, GLD, SMH, XLK and
ARKG — all sheet-governed — reverted to `equity` on the next sheet tick.

It is user-visible: `frontend/lib/filters.ts` buckets the scanner's
asset-class filter off this column, so those ETFs were absent whenever anyone
filtered to ETFs, and `/t/SPY` rendered "Equity".

This is the same rule the tick's CACHE_DERIVED_COLUMNS COALESCE already
enforces, and which `polygon_feed.fetch_snapshots` documents at length: a
cache miss must be written as NULL, never as a plausible-looking default.
"""

import pytest

from app.services.sheet_feed import normalize_asset_class

# ---------------------------------------------------------------------------
# The normaliser must distinguish "nothing to say" from "equity"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cell", [None, "", "   ", "\t", "weird unmapped value"])
def test_blank_or_unrecognised_cells_yield_none(cell):
    assert normalize_asset_class(cell) is None, (
        "a cell the sheet did not fill is being reported as a real reading, "
        "which licenses an overwrite of the vendor's value"
    )


@pytest.mark.parametrize(
    "cell,expected",
    [
        ("equity", "equity"),
        ("stock", "equity"),
        ("ETF", "etf"),
        ("etf", "etf"),
        ("commodity etf", "etf"),
        ("sector etf", "etf"),
        ("\U0001F947 commodity etf", "etf"),  # the emoji self-heal case
        ("\U0001F4C8 stock", "equity"),
    ],
)
def test_real_values_still_normalise_and_self_heal(cell, expected):
    """The overwrite exists to clean dirty legacy values. That must keep
    working — the fix is to stop writing a DEFAULT, not to stop writing."""
    assert normalize_asset_class(cell) == expected


# ---------------------------------------------------------------------------
# The upsert must only write when there is something to write
# ---------------------------------------------------------------------------


def _code(fn) -> str:
    """Executable source only — comments and docstrings stripped, since this
    repo has shipped assertions that matched their own explanatory prose."""
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
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
    return ast.unparse(tree)


def test_the_update_path_is_conditional_not_defaulted():
    from app.services.sheet_feed import upsert_tickers

    code = _code(upsert_tickers)
    assert "if r['asset_class']:" in code or 'if r["asset_class"]:' in code, (
        "the sheet upsert writes asset_class unconditionally"
    )
    assert "t.asset_class = r['asset_class'] or 'equity'" not in code, (
        "the sheet still asserts 'equity' over a blank cell, so it will "
        "clobber the vendor's value every 5 minutes"
    )


@pytest.mark.asyncio
async def test_a_blank_sheet_cell_leaves_an_existing_etf_alone():
    """The end-to-end statement of the bug: a row correctly reconciled to
    `etf` must survive a sheet refresh whose Asset Class cell is empty."""
    from sqlalchemy import select

    from app.db import session_scope
    from app.models import Ticker
    from app.services.sheet_feed import parse_all_signals_csv, upsert_tickers

    sym = "ZZSHEET"
    try:
        async with session_scope() as s:
            s.add(Ticker(
                symbol=sym, name="Zebra Index ETF", sector="Funds & ETFs",
                asset_class="etf",
            ))
            await s.commit()

        # Build the row through the REAL parser so this fixture cannot drift
        # from the production row shape. Ticker + Score filled, Asset Class
        # deliberately EMPTY — exactly what the live sheet sends for the
        # benchmark tickers this bug hit.
        csv_text = "\n".join([
            "Ticker,Type,Asset Class,Strategy,Conviction,Score",
            f"{sym},,,,,61",
            "",
        ])
        rows = parse_all_signals_csv(csv_text)
        assert rows and rows[0]["asset_class"] is None, (
            "the parser no longer reports a blank Asset Class cell as a no-read"
        )
        async with session_scope() as s:
            await upsert_tickers(s, rows)

        async with session_scope() as s:
            t = await s.get(Ticker, sym)
            assert t.asset_class == "etf", (
                "a blank sheet cell overwrote a correctly-typed ETF back to "
                "equity — this is the every-5-minutes clobber"
            )
    finally:
        async with session_scope() as s:
            for t in (await s.execute(
                select(Ticker).where(Ticker.symbol == sym)
            )).scalars().all():
                await s.delete(t)
            await s.commit()
