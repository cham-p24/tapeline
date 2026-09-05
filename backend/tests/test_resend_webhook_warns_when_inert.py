"""The Resend bounce webhook must SAY when it is doing nothing.

`POST /api/webhooks/resend` no-ops when `RESEND_WEBHOOK_SECRET` is unset. That
choice is deliberate and correct — the previous 503 made Resend retry with
exponential backoff and buried Sentry in noise from a config state rather than
a bug.

What was wrong is that the no-op was *silent*. The endpoint's own docstring
claimed:

    "We log once per process at module load (further down) instead of
     per-request so this doesn't fall off the operator's radar entirely."

There was no such log anywhere in the file. The sentence describing the
safeguard was the entire safeguard.

Why this endpoint specifically: it is the only thing that marks an address
undeliverable. Inert, we keep mailing addresses that hard-bounce, and the
sending domain's reputation degrades — a symptom that looks nothing like its
cause, on a product whose alerts and digests are all email.

Once per process, not per request: per-request is the log spam the 503 was
removed to avoid.
"""
from __future__ import annotations

import logging

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers import webhooks


@pytest.fixture(autouse=True)
def _reset_latch():
    """The warning latches for the process, so tests must reset it."""
    webhooks._resend_secret_warned = False
    yield
    webhooks._resend_secret_warned = False


async def _post_bounce() -> int:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/webhooks/resend",
            json={"type": "email.bounced", "data": {"to": ["x@example.com"]}},
        )
    return resp.status_code


async def test_it_warns_when_the_secret_is_missing(caplog, monkeypatch) -> None:
    """The load-bearing one. Revert `_warn_resend_secret_missing()` and this fails."""
    monkeypatch.setattr(webhooks.settings, "resend_webhook_secret", "", raising=False)

    with caplog.at_level(logging.WARNING, logger="app.routers.webhooks"):
        status = await _post_bounce()

    assert status == 200, "the no-op must stay a 200 — a 503 makes Resend retry-storm"

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, (
        "the webhook accepted and discarded a bounce event without logging "
        "anything — this is the silent-inert state the docstring claimed to "
        "prevent and did not"
    )
    text = " ".join(r.getMessage() for r in warnings)
    assert "RESEND_WEBHOOK_SECRET" in text, "the log must name the missing setting"
    assert "fly secrets set" in text, (
        "the log must name the FIX — an operator reading one line at 3am should "
        "not have to go source-diving to act on it"
    )


async def test_it_warns_only_once_per_process(caplog, monkeypatch) -> None:
    """Per-request logging is the spam that got the old 503 removed."""
    monkeypatch.setattr(webhooks.settings, "resend_webhook_secret", "", raising=False)

    with caplog.at_level(logging.WARNING, logger="app.routers.webhooks"):
        for _ in range(5):
            await _post_bounce()

    matching = [
        r for r in caplog.records
        if r.levelno >= logging.WARNING and "webhook_secret_missing" in r.getMessage()
    ]
    assert len(matching) == 1, f"expected exactly 1 warning across 5 posts, got {len(matching)}"


async def test_a_configured_secret_does_not_warn(caplog, monkeypatch) -> None:
    """The warning must not fire in the healthy state.

    A signature check on a bogus payload still rejects the request — that is
    fine and expected. What must NOT happen is the missing-secret warning,
    which would train an operator to ignore it.
    """
    monkeypatch.setattr(webhooks.settings, "resend_webhook_secret", "whsec_test_not_a_real_secret", raising=False)

    with caplog.at_level(logging.WARNING, logger="app.routers.webhooks"):
        await _post_bounce()

    assert not [
        r for r in caplog.records if "webhook_secret_missing" in r.getMessage()
    ], "warned about a missing secret while one was configured"


def test_the_docstring_is_tied_to_the_code_that_implements_it() -> None:
    """Source-level, because the original defect WAS a docstring.

    First attempt at this test asserted `"at module load" not in doc` — and it
    failed, on the correction paragraph that *quotes* the false sentence in
    order to record it. A substring check cannot tell a claim from a citation
    of a retracted claim, which is the same brittleness this repo keeps
    hitting from the other direction (assertions passing against their own
    explanatory prose).

    So this asserts the durable thing instead: the docstring names the
    function that actually does the logging, and that function exists. Delete
    the helper and this fails; rename it and this fails. Neither can drift
    into prose-only again without going red.

    The behavioural tests above are the real guard. This one exists so that
    the failure message points at the docstring, which is where the bug lived.
    """
    import inspect

    doc = inspect.getdoc(webhooks.resend_webhook) or ""
    assert "_warn_resend_secret_missing" in doc, (
        "the docstring must name the function that implements the warning — "
        "the original defect was a docstring describing a safeguard that was "
        "never written"
    )
    assert callable(getattr(webhooks, "_warn_resend_secret_missing", None)), (
        "the docstring names a warning helper that does not exist — this is "
        "precisely the 2026-09-05 defect, reintroduced"
    )
