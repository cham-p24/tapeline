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
# finnhub_feed.py added 2026-09-06. This list existed, and its own comment
# below already said the failure mode is not "polygon_feed regressed" but
# "a new outbound integration copies the identical mistake". Finnhub WAS
# that integration and was never added: eight call sites shipped the key as
# `?token=` into the httpx INFO log and Sentry. The guard was right about
# what would happen and was not pointed at the place it happened.
VENDOR_MODULES = [
    "polygon_feed.py",
    "historical_bars.py",
    "news_feed.py",
    "finnhub_feed.py",
]


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


def _key_call_nodes(tree: ast.AST) -> list[ast.Call]:
    """Every call that returns a vendor credential, by NAME not by vendor.

    `_api_key()`, `settings.finnhub_api_key`, `_token()` — the point is to be
    vendor-agnostic, because the failure this suite exists for is always "a NEW
    integration copies the mistake", never "the old one regressed".
    """
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None) or ""
        if "api_key" in name or name in {"_key", "_token", "_api_key"}:
            out.append(node)
    return out


@pytest.mark.parametrize("module", VENDOR_MODULES)
def test_no_module_puts_a_key_into_a_params_dict(module):
    """Vendor-AGNOSTIC. The string check above only ever matched "apiKey",
    which is Polygon's parameter name — so when finnhub_feed.py was added to
    VENDOR_MODULES it changed nothing, because Finnhub calls the parameter
    "token" and the assertion could never fire for it. Eight Finnhub call sites
    shipped the key in the query string with the module sitting in the list.

    This walks the AST instead: any call returning a credential, used as a VALUE
    inside a dict that is passed as `params=`, is the defect regardless of what
    the vendor names the field.
    """
    tree = _strip_docstrings(ast.parse((SERVICES / module).read_text(encoding="utf-8")))
    key_calls = {id(n) for n in _key_call_nodes(tree)}

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg != "params":
                continue
            for sub in ast.walk(kw.value):
                if id(sub) in key_calls:
                    offenders.append(f"line {getattr(sub, 'lineno', '?')}")

    # Also catch the indirection: `params = {..., "token": _api_key()}` on one
    # line and `params=params` on another. Any dict literal in the module whose
    # values include a credential call is the same leak one step removed.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for value in node.values:
            for sub in ast.walk(value):
                if id(sub) in key_calls:
                    offenders.append(f"dict at line {getattr(node, 'lineno', '?')}")

    assert not offenders, (
        f"{module} puts a vendor credential into a query-parameter dict "
        f"({', '.join(sorted(set(offenders)))}). Send it as a header — httpx "
        f"logs full URLs at INFO, so a query-param key reaches the log, every "
        f"stack trace, Sentry, and any workflow that streams stdout."
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
    import textwrap

    from app.services import polygon_feed

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
