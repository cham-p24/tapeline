"""A coin must be reachable on every surface a stock is, or it is not shipped.

Crypto reached production scored, searchable and in the scanner — and every
per-coin PAGE returned 404:

    /api/ticker/X:BTCUSD    -> 404
    /api/ticker/X%3ABTCUSD  -> 404

`clean_symbol(symbol)` on the serving path rejects a namespaced pair, because
`allow_crypto` defaults to False. That default is right for INGESTION: it is
what stops a human-typed sheet cell reading "SOL" from being stored as a coin
and overwriting Emeren Group, a real NYSE company. It is wrong for a LOOKUP of
an already-namespaced symbol, which cannot collide with anything — the prefix
is precisely what makes it distinct.

This is the fourth time in one day that correct crypto rows were unreachable
through some surface, each time for a different reason:

  1. `confidence_pct` unset            -> invisible to every ranked surface
  2. the equity tick nulled the prices -> invisible again
  3. `clean_symbol` on the detail route -> pages 404
  4. and the same on MCP + the extension

So the test is a SWEEP over the serving call sites rather than one assertion
about one route. The failure mode has no symptom on the surface that works.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from app.services.symbols import clean_symbol, is_crypto_symbol

PAIR = "X:BTCUSD"

#: Every module that resolves a caller-supplied symbol for SERVING. Ingestion
#: modules are deliberately absent — sheet_feed must keep refusing pairs.
SERVING_MODULES = [
    "app/routers/ticker.py",
    "app/routers/mcp.py",
    "app/routers/extension.py",
]


def _repo_backend() -> Path:
    import app

    return Path(app.__file__).resolve().parent.parent


@pytest.mark.parametrize("relpath", SERVING_MODULES)
def test_every_serving_lookup_accepts_a_namespaced_pair(relpath):
    """Any `clean_symbol(...)` on a serving path must opt into crypto.

    Parsed rather than grepped so a call spread over several lines, or one
    whose argument is an expression, is still seen.
    """
    source = (_repo_backend() / relpath).read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name != "clean_symbol":
            continue
        if not any(kw.arg == "allow_crypto" for kw in node.keywords):
            offenders.append(node.lineno)

    assert not offenders, (
        f"{relpath} resolves a symbol with clean_symbol() and no "
        f"allow_crypto= at line(s) {offenders}. A namespaced pair is rejected "
        f"there, so every crypto row is unreachable through this surface while "
        f"looking perfectly healthy on the others."
    )


def test_ingestion_still_refuses_pairs_by_default():
    """The other half. Widening the default would re-open the collision."""
    assert clean_symbol(PAIR) is None
    assert clean_symbol(PAIR, allow_crypto=True) == PAIR


def test_the_sheet_parser_is_not_in_the_serving_list():
    """Guards the list above against a well-meaning future edit.

    sheet_feed reads a human-typed column and is where the SOL/Emeren
    collision came from. It must keep refusing pairs, so it must never be
    added to SERVING_MODULES to "make crypto work everywhere".
    """
    assert not any("sheet_feed" in m for m in SERVING_MODULES)

    from app.services import sheet_feed

    src = inspect.getsource(sheet_feed.parse_all_signals_csv)
    assert "allow_crypto" not in src, (
        "the workbook parser now accepts namespaced pairs; a coin typed into "
        "the sheet can be stored again, which is the 2026-09-03 incident"
    )


@pytest.mark.parametrize(
    "symbol,expected",
    [
        ("X:BTCUSD", True),
        ("x:btcusd", True),   # normalised before the shape test
        ("  X:ETHUSD  ", True),
        ("BTC", False),
        ("SOL", False),
        ("BRK.B", False),
        ("CL=F", False),
    ],
)
def test_the_namespace_test_is_exact(symbol, expected):
    """Serving keys off this, so a false positive would route a stock to a coin."""
    assert is_crypto_symbol(symbol) is expected
