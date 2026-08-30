"""Guards on the invalid-symbol purge.

This script DELETES production rows, so the interesting tests are the ones
about what it refuses to touch.

The 25 rows it targets are residue from before
`services/symbols.VALID_SYMBOL_RE` guarded the ingest boundary: 24 x
"\U0001F3C6 <TICKER>" trophy annotations the signal-system writes into column
A, each a ghost duplicate of a real ETF, plus one "币安人生". They are already
filtered off every public surface, so the purge is hygiene rather than a fix —
which is exactly why it must not be allowed to do collateral damage.
"""

import pytest
from sqlalchemy import select

from app.db import session_scope
from app.models import DailyScorecardEntry, Ticker
from app.scripts.purge_invalid_symbols import _find_invalid, _purge
from app.services.symbols import VALID_SYMBOL_RE

GHOST = "\U0001F3C6 ZZTEST"      # trophy-prefixed, exactly the live shape
REAL = "ZZREAL"                   # a legitimate symbol that must survive
REFERENCED = "\U0001F3C6 ZZKEEP"  # invalid, but on the public record


@pytest.fixture
async def seeded():
    async with session_scope() as s:
        for sym in (GHOST, REAL, REFERENCED):
            s.add(Ticker(symbol=sym, name=sym, sector="Unknown", asset_class="equity"))
        await s.commit()
    yield
    async with session_scope() as s:
        for sym in (GHOST, REAL, REFERENCED):
            t = await s.get(Ticker, sym)
            if t is not None:
                await s.delete(t)
        for e in (
            await s.execute(
                select(DailyScorecardEntry).where(DailyScorecardEntry.symbol == REFERENCED)
            )
        ).scalars().all():
            await s.delete(e)
        await s.commit()


@pytest.mark.asyncio
async def test_finds_only_shape_violations(seeded):
    found = await _find_invalid()
    assert GHOST in found
    assert REFERENCED in found
    assert REAL not in found, "a legitimate symbol was flagged for deletion"


@pytest.mark.asyncio
async def test_dry_run_deletes_nothing(seeded):
    """Default behaviour must be inert. This script's whole risk profile is
    that someone runs it without reading the flags."""
    await _purge(apply=False)
    async with session_scope() as s:
        assert await s.get(Ticker, GHOST) is not None


@pytest.mark.asyncio
async def test_apply_removes_the_ghost_but_keeps_real_symbols(seeded):
    await _purge(apply=True)
    async with session_scope() as s:
        assert await s.get(Ticker, GHOST) is None
        assert await s.get(Ticker, REAL) is not None, (
            "the purge deleted a symbol that passes the shape test"
        )


@pytest.mark.asyncio
async def test_refuses_to_delete_a_symbol_on_the_public_record(seeded):
    """The scorecard is append-only and permanent. Deleting the Ticker row
    under a frozen entry would leave that entry pointing at nothing — and no
    ForeignKey exists to stop it, so the check has to be here."""
    async with session_scope() as s:
        s.add(DailyScorecardEntry(
            as_of=__import__("datetime").date(2026, 8, 1),
            symbol=REFERENCED, rank=1,
            score_at_flag=90.0, price_at_flag=100.0,
        ))
        await s.commit()

    await _purge(apply=True)

    async with session_scope() as s:
        assert await s.get(Ticker, REFERENCED) is not None, (
            "a symbol referenced by the permanent public record was deleted"
        )
        # ...while the unreferenced ghost in the same run still went.
        assert await s.get(Ticker, GHOST) is None


def test_the_shape_rule_is_the_shared_one_not_a_copy():
    """If this script re-expressed the rule as its own regex or a SQL LIKE, it
    would drift from the one ingestion and serving enforce, and start deleting
    things they consider valid."""
    import ast
    import inspect
    import textwrap

    from app.scripts import purge_invalid_symbols as mod

    src = textwrap.dedent(inspect.getsource(mod))
    tree = ast.parse(src)
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

    assert "VALID_SYMBOL_RE" in code
    assert "re.compile" not in code, "the script defines its own shape rule"
    assert "LIKE" not in code.upper() or "like(" not in code, (
        "the shape rule was re-expressed in SQL and will drift"
    )


def test_a_real_ticker_is_never_matched_by_the_rule():
    """Sanity on the rule itself, from this script's side: every symbol the
    ghosts duplicate must pass, or the purge would delete the real row too.

    `^GSPC` is deliberately absent. The rule requires a LEADING LETTER, so
    index notation has never matched — `symbols.py`'s docstring used to cite
    it as a supported example anyway, which this test caught. Nothing in the
    app ingests an index, so the regex is the correct half and the docstring
    was fixed rather than the rule.
    """
    for sym in ["SPY", "QQQ", "VTI", "BRK.B", "BRK-B", "CL=F", "ASML", "A"]:
        assert VALID_SYMBOL_RE.match(sym), f"{sym} would be purged"


def test_index_notation_is_not_a_ticker_and_the_docstring_agrees():
    """Pins the contradiction shut from both sides."""
    from app.services import symbols

    assert VALID_SYMBOL_RE.match("^GSPC") is None
    assert "NOT index notation" in (symbols.__doc__ or ""), (
        "the module docstring no longer states that index notation is "
        "excluded, so it can drift back into claiming ^GSPC is supported"
    )
