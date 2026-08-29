"""api.tapeline.io must send the same baseline security headers as the site.

Audited 2026-08-29 against production: `curl -D- https://api.tapeline.io/api/health`
returned NO security headers at all — no HSTS, no nosniff, no frame policy —
while https://tapeline.io had HSTS with preload, X-Frame-Options: DENY, nosniff
and a CSP. The API is the origin the session cookie is scoped to and the one
the billing calls traverse, so it was the wrong half to leave bare.

The specific risk HSTS closes: a first request to `http://api.tapeline.io`
can be intercepted and downgraded before any redirect happens. The header has
to come from the API origin itself — the frontend's HSTS covers
`tapeline.io`, and `includeSubDomains` there only helps once that response
has been seen.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

EXPECTED = {
    "strict-transport-security": "max-age=63072000; includeSubDomains; preload",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("header,value", sorted(EXPECTED.items()))
def test_health_response_carries_the_header(client, header, value):
    r = client.get("/api/health")
    assert r.headers.get(header) == value, (
        f"{header} missing or wrong on /api/health — got {r.headers.get(header)!r}"
    )


@pytest.mark.parametrize(
    "path",
    [
        "/api/health",
        "/api/scorecard",
        "/api/public/signals?limit=1",
        "/api/ticker/AAPL",
        "/api/does-not-exist",          # 404s are responses too
    ],
)
def test_every_route_shape_gets_them(client, path):
    r = client.get(path)
    missing = [h for h in EXPECTED if h not in r.headers]
    assert not missing, f"{path} ({r.status_code}) is missing {missing}"


def test_a_rate_limited_response_gets_them_too():
    """The rate-limit branch returns BEFORE call_next, so it has its own call
    to the header helper. A 429 with no HSTS is exactly as downgradeable as a
    200 with none, and this is the branch most likely to be forgotten.

    Source-level: driving a real 429 needs the limiter's IP bucket exhausted,
    which is slow and flaky in a unit test, and the risk here is that someone
    adds another early `return JSONResponse(...)` and forgets the headers.
    """
    import ast
    import inspect
    import textwrap

    from app import main

    tree = ast.parse(textwrap.dedent(inspect.getsource(main.log_and_rate_limit)))
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

    returns = code.count("return ")
    applies = code.count("_apply_security_headers(")
    assert applies >= 2, (
        f"log_and_rate_limit has {returns} return paths but only {applies} "
        f"call(s) to _apply_security_headers — an early return is shipping "
        f"bare headers"
    )


def test_no_csp_is_sent_on_json_responses():
    """Deliberate: a CSP governs how a DOCUMENT loads subresources. These
    responses are JSON, so a CSP here would be cargo cult and would only
    create confusion about which policy applies where."""
    with TestClient(app) as c:
        r = c.get("/api/health")
    assert "content-security-policy" not in r.headers


def test_the_helper_does_not_clobber_a_route_specific_value():
    """`setdefault`, not assignment — a route that deliberately chose its own
    value for one of these keeps it."""
    from starlette.responses import JSONResponse

    from app.main import _apply_security_headers

    r = JSONResponse({"ok": True})
    r.headers["X-Frame-Options"] = "SAMEORIGIN"
    _apply_security_headers(r)
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert r.headers["x-content-type-options"] == "nosniff"
