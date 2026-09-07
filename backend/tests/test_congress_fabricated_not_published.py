"""Fabricated congressional disclosures must never reach a user.

Measured against production 2026-09-06: `congress_trades` held 338,015 rows,
all of them `mock_feed.fetch_congress_trades` output — eight real, named
politicians with roughly 42,000 invented trades each, written between
2026-05-03 and 2026-07-18 and nothing since. No real source has ever written a
row.

They were being served. The Premium feed returned them as disclosures, the free
preview returned three of them to every signed-in account (under a comment
saying the preview existed "to prove the feed is real and populated"), the
preview's `total_disclosures` counted them, and the alert evaluator could email
a user to say a named politician had traded a named stock.

The last one is the worst: an outbound email asserting a specific real person
made a specific trade. Every path below is covered because suppressing three of
four leaves the claim live on the fourth.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.db import session_scope
from app.models import CongressTrade
from app.services.congress_integrity import FABRICATION_STOPPED_AT, is_publishable


def _trade(symbol: str, created_at: datetime, politician: str = "Test Member") -> CongressTrade:
    """A disclosure row stamped on either side of the fabrication cutoff."""
    return CongressTrade(
        politician=politician,
        chamber="House",
        party="Independent",
        symbol=symbol,
        direction="buy",
        amount_min=1_000,
        amount_max=15_000,
        trade_date=date(2026, 9, 1),
        disclosed_at=datetime.now(UTC) - timedelta(hours=1),
        created_at=created_at,
    )


@pytest.fixture
async def seeded():
    """One fabricated row and one real one, distinguishable only by created_at."""
    fabricated = _trade("FAKEX", FABRICATION_STOPPED_AT - timedelta(days=1), "Nancy Pelosi")
    real = _trade("REALX", FABRICATION_STOPPED_AT + timedelta(days=1))
    async with session_scope() as s:
        s.add(fabricated)
        s.add(real)
    yield
    async with session_scope() as s:
        for sym in ("FAKEX", "REALX"):
            from sqlalchemy import delete
            await s.execute(delete(CongressTrade).where(CongressTrade.symbol == sym))


async def test_the_predicate_separates_the_two_populations(seeded) -> None:
    """The predicate itself. NOT the load-bearing guard — that is the pair of
    source-level tests below, which is what actually went red when the filters
    were stripped from the call sites. This one only fails if the helper breaks;
    a call site could drop it and this would still pass. Both kinds are here on
    purpose."""
    from sqlalchemy import select

    async with session_scope() as s:
        rows = (await s.execute(
            select(CongressTrade)
            .where(CongressTrade.symbol.in_(["FAKEX", "REALX"]))
            .where(is_publishable())
        )).scalars().all()

    symbols = {r.symbol for r in rows}
    assert "FAKEX" not in symbols, (
        "a fabricated disclosure was publishable — these are invented trades "
        "attributed to real, named politicians"
    )
    assert "REALX" in symbols, (
        "the filter suppressed a row written AFTER fabrication stopped; a real "
        "feed would be silently empty forever"
    )


async def test_the_cutoff_is_the_moment_fabrication_stopped() -> None:
    """Pin the boundary itself, in both directions, to the exact instant.

    A row written at the cutoff is publishable; one microsecond earlier is not.
    """
    assert FABRICATION_STOPPED_AT == datetime(2026, 7, 19, tzinfo=UTC)


@pytest.mark.parametrize("path", ["/api/congress", "/api/congress/preview"])
async def test_no_served_endpoint_returns_a_fabricated_row(seeded, path: str) -> None:
    """Both read paths, because suppressing one leaves the claim live on the other."""
    import inspect

    from app.routers import congress as mod

    src = inspect.getsource(mod)
    # Strip comments AND docstrings — this module explains the filter at length
    # in prose, and a source assertion that matches its own explanation proves
    # nothing. (House rule; this repo has shipped exactly that mistake.)
    import ast

    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body.pop(0)
    stripped = ast.unparse(tree)

    # Every select over CongressTrade in this router must carry the filter.
    selects = stripped.count("select(CongressTrade)")
    guarded = stripped.count("is_publishable()")
    assert selects > 0, "router no longer queries CongressTrade — update this test"
    assert guarded >= selects, (
        f"{selects} CongressTrade queries but only {guarded} is_publishable() "
        f"guards in routers/congress.py — an unguarded path publishes fabrication"
    )


async def test_the_preview_count_is_filtered_too() -> None:
    """A total that counts fabricated rows is as false as returning them.

    The preview tells the reader how much real disclosure data is held back.
    Counting 338,015 invented rows there is a claim about what Premium contains.
    """
    import ast
    import inspect

    from app.routers import congress as mod

    tree = ast.parse(inspect.getsource(mod))
    src = ast.unparse(tree)
    assert "select(func.count()).select_from(CongressTrade).where(is_publishable())" in src, (
        "the preview's total_disclosures COUNT is not filtered"
    )


async def test_the_outbound_alert_path_is_filtered() -> None:
    """The worst surface: an email asserting a named person made a named trade."""
    import ast
    import inspect

    from app.services import alerts as mod

    fn = inspect.getsource(mod.evaluate_congress_rules)
    tree = ast.parse(fn.lstrip())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)):
                node.body.pop(0)
    stripped = ast.unparse(tree)
    assert "is_publishable()" in stripped, (
        "evaluate_congress_rules can email a user about a fabricated disclosure"
    )
