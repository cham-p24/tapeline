"""Every Meta CAPI call site must report the page the event happened on.

WHY THIS EXISTS
---------------
`event_source_url` was defined on `send_event` and consumed when building the
payload, and **no call site ever passed it** — from the day CAPI shipped
(#542, 2026-08-21) until 2026-09-04. The field looked wired. Reading
`meta_capi.py` alone, it was wired. It was simply never populated.

Meta wants `event_source_url` for events whose `action_source` is `website`,
and it is one of the inputs to Event Match Quality — the score the delivery
model uses to decide who to show ads to. A conversion feed that omits it is
quietly worth less than one that does not, and nothing in the product surfaces
that.

This is the same shape as the two bugs that preceded it (#706's silent no-op on
missing credentials, #708's browser event that could never fire for a real
customer): the code is present, the code is correct, and the code is not
reached. A unit test of `send_event` passes in all three cases. Only a test
that looks at the CALLERS catches them.

Source-level and AST-based on purpose: the failure mode is "someone adds a
fifth conversion call and copies an existing one", which no runtime test of the
four existing calls would ever see.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROUTERS = pathlib.Path(__file__).resolve().parents[1] / "app" / "routers"

#: Every meta_capi tracking helper that builds a `website` event.
TRACKERS = ("track_complete_registration", "track_start_trial", "track_purchase")


def _meta_capi_calls(path: pathlib.Path) -> list[ast.Call]:
    """Every `meta_capi.track_*(...)` call in a module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr in TRACKERS:
            found.append(node)
    return found


def _all_calls() -> list[tuple[str, str, frozenset[str]]]:
    """(module, helper, kwarg names) per call site — plain data, so a failing
    parametrised case is identified by `auth.py::track_purchase` rather than by
    a full AST dump."""
    out: list[tuple[str, str, frozenset[str]]] = []
    for path in sorted(ROUTERS.rglob("*.py")):
        for call in _meta_capi_calls(path):
            fn = call.func.attr  # type: ignore[union-attr]
            kwargs = frozenset(kw.arg for kw in call.keywords if kw.arg)
            out.append((path.name, fn, kwargs))
    return out


def test_there_are_call_sites_to_check() -> None:
    """Guard the guard: an empty sweep would make everything below vacuous."""
    calls = _all_calls()
    assert len(calls) >= 4, f"expected at least 4 meta_capi call sites, found {len(calls)}"


@pytest.mark.parametrize(
    "module,fn,kwargs",
    _all_calls(),
    ids=[f"{m}::{f}" for m, f, _ in _all_calls()],
)
def test_every_call_site_reports_its_source_url(
    module: str, fn: str, kwargs: frozenset[str]
) -> None:
    assert "event_source_url" in kwargs, (
        f"{module}: {fn}() does not pass event_source_url. Meta wants it for "
        f"website events and derives part of Event Match Quality from it. Use "
        f"meta_capi.source_url(<page path>) — the user's signup_landing_path "
        f"for signup events, or the page the checkout began on."
    )


def test_source_url_builds_an_absolute_url() -> None:
    from app.services.meta_capi import source_url

    url = source_url("/signup")
    assert url is not None
    assert url.endswith("/signup")
    assert url.startswith("http")


def test_source_url_cannot_be_pointed_at_another_origin() -> None:
    """A stored path must never be able to relocate the reported source.

    `signup_landing_path` is written from a client-supplied value, so a
    protocol-relative path (`//evil.com/x`) would otherwise join into a URL on
    someone else's origin and be reported to Meta as ours.
    """
    from app.services.meta_capi import source_url

    hostile = source_url("//evil.com/pwned")
    assert hostile is not None
    assert "evil.com" not in hostile


def test_the_payload_actually_carries_it() -> None:
    """Behavioural companion: the kwarg must survive into the event body."""
    import asyncio

    from app.services import meta_capi

    captured: dict = {}

    class _Resp:
        status_code = 200
        text = "{}"

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, params=None, json=None, headers=None):
            captured.update(json or {})
            return _Resp()

    import os

    os.environ["META_PIXEL_ID"] = "123"
    os.environ["META_CAPI_ACCESS_TOKEN"] = "tok"
    original = meta_capi.httpx.AsyncClient
    meta_capi.httpx.AsyncClient = _Client  # type: ignore[assignment]
    try:
        asyncio.run(
            meta_capi.track_complete_registration(
                user_id="u_1",
                email="a@b.com",
                event_source_url="https://tapeline.io/signup",
            )
        )
    finally:
        meta_capi.httpx.AsyncClient = original  # type: ignore[assignment]
        os.environ.pop("META_PIXEL_ID", None)
        os.environ.pop("META_CAPI_ACCESS_TOKEN", None)

    event = captured["data"][0]
    assert event["event_source_url"] == "https://tapeline.io/signup"


# ---------------------------------------------------------------------------
# The pinned Graph API version.
#
# Pinning is correct — an upstream default change must never silently alter
# payload handling on the conversion feed. But a pin is only safe if someone
# notices when it goes stale, and nobody did: v21.0 sat in this module from
# #542 until 2026-09-04, while Meta returned
# `x-ad-api-version-warning: You are calling a deprecated version of the Ads
# API` on every live call. The signal was in the response headers all along.
#
# Verified against the live endpoint 2026-09-04 with an empty `data` array
# (so no event is recorded): v21.0/v22.0/v23.0 warn, v24.0/v25.0 do not. A
# bogus version is served as v20.0 and errors with "Unknown path components",
# which is the control proving an echoed version really exists.
#
# Offline on purpose: CI must not depend on Meta's endpoint or hold a token.
# The re-verification command lives in the module comment next to the pin.
# ---------------------------------------------------------------------------

#: Confirmed deprecated on 2026-09-04. Never pin to these.
DEPRECATED_GRAPH_VERSIONS = frozenset({"v21.0", "v22.0", "v23.0"})

#: Floor below which a version is either deprecated or predates the check.
MIN_GRAPH_MAJOR = 24


def test_graph_api_version_is_not_deprecated() -> None:
    from app.services.meta_capi import GRAPH_API_VERSION

    assert GRAPH_API_VERSION not in DEPRECATED_GRAPH_VERSIONS, (
        f"GRAPH_API_VERSION is pinned to {GRAPH_API_VERSION}, which Meta's own "
        f"x-ad-api-version-warning header marks deprecated. Re-run the probe in "
        f"the comment beside the pin in services/meta_capi.py and move to the "
        f"oldest version that returns no warning."
    )


def test_graph_api_version_is_well_formed_and_current_enough() -> None:
    import re

    from app.services.meta_capi import GRAPH_API_VERSION

    m = re.fullmatch(r"v(\d+)\.(\d+)", GRAPH_API_VERSION)
    assert m, f"GRAPH_API_VERSION {GRAPH_API_VERSION!r} is not a vMAJOR.MINOR string"
    assert int(m.group(1)) >= MIN_GRAPH_MAJOR, (
        f"GRAPH_API_VERSION {GRAPH_API_VERSION} is below v{MIN_GRAPH_MAJOR}.0, the "
        f"oldest version confirmed non-deprecated on 2026-09-04."
    )


def test_the_pinned_version_is_what_the_request_actually_uses() -> None:
    """The constant must reach the URL — a pin nothing reads is not a pin."""
    import ast
    import inspect
    import textwrap

    from app.services import meta_capi

    src = textwrap.dedent(inspect.getsource(meta_capi.send_event))
    # Strip the docstring so prose about versions cannot satisfy this.
    tree = ast.parse(src)
    fn = tree.body[0]
    body = getattr(fn, "body", [])
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        fn.body = body[1:]
    code = ast.unparse(tree)
    assert "GRAPH_API_VERSION" in code, (
        "send_event no longer interpolates GRAPH_API_VERSION into the request URL"
    )
