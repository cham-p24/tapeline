"""The vendor API key must never travel in a URL.

WHAT HAPPENED
-------------
Massive/Polygon accept the key either as `?apiKey=<key>` or as
`Authorization: Bearer <key>`. This codebase used the query-string form
everywhere, and that form leaks by construction:

  * httpx logs the full request URL at INFO, and `app/main.py` calls
    `logging.basicConfig(level=logging.INFO)` globally;
  * `httpx.HTTPStatusError` embeds the URL in its message, so it reaches
    every stack trace and Sentry event;
  * anything that streams application logs somewhere else carries it along.

On 2026-08-27 that last one bit: the `rederive-scorecard` workflow streams
this code's stdout into GitHub Actions, and on a PUBLIC repository four runs
published the live key in world-readable logs — 1,086 plaintext occurrences.
GitHub masks values registered as GitHub secrets; this key lives in Fly, so
nothing masked it.

A header is not logged by httpx, is scrubbed by Sentry's default
`Authorization` filter, and never lands in a stack trace.

These tests are source-level on purpose: the failure mode is "someone adds a
new endpoint and copies the old pattern", which no runtime test of the
existing endpoints would catch.
"""

import ast
import inspect
import pathlib

import pytest

SERVICES = pathlib.Path(__file__).resolve().parents[1] / "app" / "services"

#: Every module that talks to the Massive/Polygon HTTP API.
VENDOR_MODULES = ["polygon_feed.py", "historical_bars.py", "news_feed.py"]


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    """Drop every docstring node in place.

    `ast.unparse` removes comments but KEEPS docstrings, which is not enough
    here: the docstring on `auth_headers` necessarily explains what
    `?apiKey=` was and why it is gone, and that prose alone made this suite
    fail against correct code. The test must see executable code only.
    """
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        body = getattr(node, "body", None)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return tree


def _code_only(path: pathlib.Path) -> str:
    """Executable source only — no comments, no docstrings.

    This repo has repeatedly shipped assertions that passed against the
    explanatory comment sitting above the line they were meant to pin. Here
    the same trap runs the other way: prose describing the fix must not be
    able to FAIL the test for it either.
    """
    return ast.unparse(_strip_docstrings(ast.parse(path.read_text(encoding="utf-8"))))


@pytest.mark.parametrize("module", VENDOR_MODULES)
def test_no_module_puts_the_key_in_a_url_or_query_param(module):
    code = _code_only(SERVICES / module)
    assert "apiKey" not in code, (
        f"{module} still passes the vendor key as a query parameter. httpx "
        f"logs full URLs at INFO and HTTPStatusError embeds them, so the key "
        f"reaches logs, stack traces and Sentry on every call — and, via any "
        f"workflow that streams logs, a public GitHub Actions log."
    )


def test_the_shared_helper_sends_a_bearer_header():
    from app.services.polygon_feed import auth_headers

    assert auth_headers("secret-value") == {"Authorization": "Bearer secret-value"}


def test_the_helper_sends_no_header_at_all_when_there_is_no_key():
    """An `Authorization: Bearer ` with an empty key is worse than nothing: it
    turns a clear 401 into an ambiguous one and hides an unconfigured
    deployment."""
    from app.services.polygon_feed import auth_headers

    assert auth_headers("") == {}
    assert auth_headers(None) in ({}, auth_headers()), (
        "None must fall back to the configured key, not send an empty bearer"
    )


def test_the_paging_cursor_no_longer_splices_the_key_back_in():
    """`discover_active_us_tickers` walks Polygon's paged reference endpoint.
    It used to re-append `apiKey=` to every `next_url`, which is how a single
    universe refresh could emit the key hundreds of times."""
    from app.services import polygon_feed

    import textwrap

    code = ast.unparse(
        _strip_docstrings(
            ast.parse(
                textwrap.dedent(inspect.getsource(polygon_feed.discover_active_us_tickers))
            )
        )
    )
    assert "apiKey" not in code
    assert "auth_headers()" in code, (
        "the paged walk sends no auth header, so paging past the first page "
        "will 401"
    )


def test_every_vendor_request_actually_passes_headers():
    """Removing `apiKey` from the params without adding the header would make
    every call unauthenticated — a silent outage rather than a leak. Each
    module must reference the helper."""
    for module in VENDOR_MODULES:
        code = _code_only(SERVICES / module)
        assert "auth_headers" in code, (
            f"{module} dropped the query-param key but never added the header"
        )


# ---------------------------------------------------------------------------
# Meta Conversions API — the same leak, a different vendor.
#
# The rule above was written for Massive/Polygon and scoped to VENDOR_MODULES,
# so `services/meta_capi.py` sat outside it and shipped the identical mistake:
# `params={"access_token": token}`. Every conversion sent from production wrote
# a 208-character Meta access token into the Fly logs, by the same mechanism
# documented at the top of this file.
#
# Meta accepts `Authorization: Bearer <token>` — verified against the live
# endpoint from the production machine on 2026-09-01, which returned the same
# response for header auth as for the query-string form.
#
# Kept in THIS file rather than a new one because the failure is not
# "polygon_feed regressed", it is "a new outbound integration copies the
# query-string pattern". The next vendor belongs here too.
# ---------------------------------------------------------------------------

META_MODULE = "meta_capi.py"


def test_meta_capi_does_not_put_the_access_token_in_a_query_param():
    code = _code_only(SERVICES / META_MODULE)
    assert "access_token" not in code, (
        "meta_capi.py passes the Meta access token as a query parameter. httpx "
        "logs full URLs at INFO and app/main.py sets INFO globally, so every "
        "conversion event writes the token into the application log. Send it as "
        'headers={"Authorization": f"Bearer {token}"} instead — Meta accepts it '
        "and httpx does not log headers."
    )


def test_meta_capi_sends_the_token_as_a_bearer_header():
    code = _code_only(SERVICES / META_MODULE)
    assert "Authorization" in code and "Bearer" in code, (
        "meta_capi.py must authenticate with an Authorization: Bearer header."
    )


def test_an_unconfigured_production_process_says_so_out_loud():
    """A missing key must never be a silent no-op in production.

    On 2026-08-31 a signup from a paid Meta ad reported no conversion because
    the process serving it had no META_* in its environment. The code logged
    that at DEBUG, Meta reported no error, and the only symptom was an ad
    account optimising toward a conversion it had never observed. The event was
    unrecoverable; the silence is what made it unfindable for two days.
    """
    code = _code_only(SERVICES / META_MODULE)
    assert "APP_ENV" in code, (
        "meta_capi must branch on APP_ENV so an unconfigured PRODUCTION process "
        "warns instead of no-oping at debug level."
    )
    assert "logger.warning" in code, (
        "the unconfigured branch must be able to log at warning, not only debug."
    )
