"""One anonymous POST must not be able to buy unbounded work.

THE BUG
-------
`POST /mcp` accepted a JSON-RPC batch and ran the whole array:

    replies = [r for r in [await _dispatch(m, session) for m in body] ...]

`tools/call` dispatches are DB-backed — `get_daily_picks` runs the full
`list_scanner` query, and `_record_tool_call` opens its own session and commits
an upsert — so a single 10,000-element array bought 10,000 sequential queries on
the one 2-CPU api machine. `fly.toml` runs no second api machine, deliberately.

It compounded: `/mcp` is mounted OUTSIDE `/api/` (`prefix="/mcp"`), and the
rate-limit middleware tested `path.startswith("/api/")` — so the one
unauthenticated, DB-backed surface on the box was the one surface with no
limiter at all. Verified live on 2026-09-06: 12 rapid anonymous POSTs, all 200.

WHAT IS NOT THE BUG
-------------------
Being unauthenticated. `mcp.py`'s own header says every tool returns what an
anonymous visitor already sees, and gating the top of the funnel is the opposite
of the point — AI citation is the channel that has produced revenue. So the cap
is on WORK, not on identity. Nothing here adds auth, and a test below pins that
so a later "hardening" pass does not quietly close the funnel.
"""

import pytest

from app.routers.mcp import MAX_BATCH_SIZE


def test_there_is_a_batch_cap_at_all():
    assert isinstance(MAX_BATCH_SIZE, int)
    assert MAX_BATCH_SIZE > 0


def test_the_cap_is_generous_enough_for_real_clients_and_tight_enough_to_matter():
    """Real MCP clients batch in single digits. The number only has to bound
    the blast radius — the failure was unbounded, not 'slightly too high'."""
    assert 5 <= MAX_BATCH_SIZE <= 200, (
        "below ~5 breaks ordinary clients; above ~200 stops bounding anything"
    )


def _code() -> str:
    """Executable source only — this module's docstring quotes the very
    comprehension it bans, and the router's comments quote the limit."""
    import ast
    import inspect
    import textwrap

    from app.routers import mcp

    tree = ast.parse(textwrap.dedent(inspect.getsource(mcp)))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module))
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_the_handler_checks_the_length_before_dispatching():
    """The check must sit BEFORE the comprehension. A cap applied afterwards
    bounds the response, not the work, which is the whole cost.

    Structural on purpose. The first version of this test asserted
    `"MAX_BATCH_SIZE" in code`, which the module-level ASSIGNMENT satisfies on
    its own — deleting the entire `if len(body) > MAX_BATCH_SIZE` block left it
    green. Watched that happen, which is the only reason this walks the AST.
    """
    import ast
    import inspect
    import textwrap

    from app.routers import mcp

    tree = ast.parse(textwrap.dedent(inspect.getsource(mcp)))

    # The handler is whichever function actually runs the batch.
    handler = None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if "_dispatch" in ast.unparse(node) and "body" in ast.unparse(node):
            handler = node
            break
    assert handler is not None, "could not find the batch handler"

    # A LOAD of the constant inside the handler — not its definition.
    uses = [
        n.lineno
        for n in ast.walk(handler)
        if isinstance(n, ast.Name)
        and n.id == "MAX_BATCH_SIZE"
        and isinstance(n.ctx, ast.Load)
    ]
    assert uses, (
        "the handler never reads MAX_BATCH_SIZE — the constant exists but "
        "nothing enforces it, so a batch of any size still executes in full"
    )

    comprehensions = [
        n.lineno
        for n in ast.walk(handler)
        if isinstance(n, (ast.ListComp, ast.GeneratorExp))
        and "_dispatch" in ast.unparse(n)
    ]
    assert comprehensions, "the dispatch comprehension moved; re-point this test"
    assert min(uses) < min(comprehensions), (
        "the length check runs after the batch has already executed"
    )


def test_mcp_is_inside_the_rate_limiter():
    """`/mcp` is mounted outside `/api/`, so the middleware has to name it."""
    import ast
    import inspect
    import textwrap

    from app import main

    tree = ast.parse(textwrap.dedent(inspect.getsource(main)))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module))
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    code = ast.unparse(tree)
    assert 'startswith(\'/mcp\')' in code or 'startswith("/mcp")' in code, (
        "the rate-limit middleware does not cover /mcp, which is mounted "
        "outside /api/ and is the only unauthenticated DB-backed surface"
    )


def test_nothing_added_authentication_to_mcp():
    """The opposite failure. Every tool returns what an anonymous visitor can
    already see; gating it would close the one channel that has produced
    revenue. If a later hardening pass adds auth, this should be a deliberate
    decision and not a side effect of a DoS fix."""
    code = _code()
    for banned in ("current_user_required", "require_admin", "Depends(current_user"):
        assert banned not in code, (
            f"{banned} would gate the public MCP server; the cap is on work, "
            f"not on identity"
        )


@pytest.mark.parametrize("size", [1, 5, MAX_BATCH_SIZE])
def test_ordinary_batch_sizes_are_under_the_cap(size):
    assert size <= MAX_BATCH_SIZE
