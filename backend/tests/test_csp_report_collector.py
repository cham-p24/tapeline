"""The CSP report collector — what unblocks the flip-to-enforce plan.

`frontend/next.config.js` ships the policy as Report-Only and documents a
"PHASE 1 → flip to enforce after ~1 week of clean reports" plan. That gate was
unreachable: the policy declared no `report-uri` and no `report-to`, so
violations went to the console of whoever had devtools open and nowhere else.
Nothing aggregated them, so "a clean week" was unobservable and the CSP stayed
non-enforcing indefinitely (audited 2026-08-29).

This endpoint does NOT enforce anything. It makes the existing plan
completable, which is the honest fix — flipping a policy that still allows
'unsafe-inline' and 'unsafe-eval' would have been theatre, and flipping it
blind risked breaking the site.

The endpoint is unauthenticated by necessity: the BROWSER posts these, not the
app, and it will not attach credentials. So it is treated as hostile input.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

LEGACY = {
    "csp-report": {
        "document-uri": "https://tapeline.io/pricing",
        "violated-directive": "script-src",
        "effective-directive": "script-src",
        "blocked-uri": "https://evil.example.com/x.js",
        "script-sample": "SECRET_PAGE_CONTENT_SHOULD_NOT_BE_LOGGED",
    }
}

REPORTING_API = [
    {
        "type": "csp-violation",
        "body": {
            "documentURL": "https://tapeline.io/",
            "effectiveDirective": "connect-src",
            "blockedURL": "https://tracker.example.com/beacon",
        },
    }
]


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_accepts_the_legacy_csp_report_format(client, caplog):
    with caplog.at_level("WARNING"):
        r = client.post(
            "/api/csp-report",
            content=json.dumps(LEGACY),
            headers={"content-type": "application/csp-report"},
        )
    assert r.status_code == 204
    assert any("csp_violation" in m for m in caplog.messages)
    assert any("evil.example.com" in m for m in caplog.messages)


def test_accepts_the_reporting_api_format(client, caplog):
    """Browsers disagree on the wire format; both must land."""
    with caplog.at_level("WARNING"):
        r = client.post(
            "/api/csp-report",
            content=json.dumps(REPORTING_API),
            headers={"content-type": "application/reports+json"},
        )
    assert r.status_code == 204
    assert any("connect-src" in m for m in caplog.messages)


def test_script_sample_is_never_logged(client, caplog):
    """`script-sample` can carry page content — including whatever inline
    script was on the page. Logging it would turn a security telemetry
    endpoint into a content leak."""
    with caplog.at_level("WARNING"):
        client.post(
            "/api/csp-report",
            content=json.dumps(LEGACY),
            headers={"content-type": "application/csp-report"},
        )
    joined = " ".join(caplog.messages)
    assert "SECRET_PAGE_CONTENT_SHOULD_NOT_BE_LOGGED" not in joined


def test_oversized_bodies_are_dropped(client, caplog):
    """Public and unauthenticated, so it is a log-flooding target. A real
    report is small."""
    with caplog.at_level("WARNING"):
        r = client.post(
            "/api/csp-report",
            content=json.dumps({"csp-report": {"blocked-uri": "x" * 40_000}}),
            headers={"content-type": "application/csp-report"},
        )
    assert r.status_code == 204
    assert any("oversized" in m for m in caplog.messages)
    assert not any("csp_violation" in m for m in caplog.messages)


@pytest.mark.parametrize(
    "body",
    [b"", b"not json at all", b"[]", b"{}", b'{"csp-report": "not-an-object"}', b"null"],
)
def test_malformed_input_never_raises(client, body):
    """Anyone can POST here. Every shape must be a quiet 204, never a 500 —
    a collector that can be crashed is worse than no collector."""
    r = client.post(
        "/api/csp-report",
        content=body,
        headers={"content-type": "application/csp-report"},
    )
    assert r.status_code == 204


def test_a_report_batch_is_bounded(client, caplog):
    """The Reporting API batches. An unbounded list is a cheap amplification."""
    # Deliberately sized to clear the 16KB body guard while carrying far more
    # than 20 items — otherwise the SIZE cap rejects the whole request and this
    # test passes without the count cap ever running. It did exactly that on
    # the first version (500 items ≈ 35KB), and still passed with the count cap
    # deleted.
    many = [
        {"type": "csp-violation", "body": {"effectiveDirective": "s", "blockedURL": "u"}}
        for _ in range(120)
    ]
    body = json.dumps(many)
    assert len(body) < 16_384, "fixture outgrew the size guard again"

    with caplog.at_level("WARNING"):
        r = client.post("/api/csp-report", content=body)
    assert r.status_code == 204
    logged = [m for m in caplog.messages if "csp_violation" in m]
    assert logged, "nothing was logged — the size guard swallowed the batch"
    assert len(logged) <= 20, f"logged {len(logged)} lines from one request"


def test_extension_noise_is_filtered(client, caplog):
    """Browser extensions inject inline style into every page. Those reports
    are not actionable and would drown the signal the flip-to-enforce decision
    depends on."""
    noise = {
        "csp-report": {
            "effective-directive": "style-src-attr",
            "blocked-uri": "inline",
            "document-uri": "https://tapeline.io/",
        }
    }
    with caplog.at_level("WARNING"):
        client.post("/api/csp-report", content=json.dumps(noise))
    assert not any("csp_violation" in m for m in caplog.messages)


def test_the_policy_actually_points_at_this_endpoint():
    """A collector nothing reports to is the bug this fixes, one level up."""
    import pathlib
    import re

    cfg = (
        pathlib.Path(__file__).resolve().parents[2]
        / "frontend" / "next.config.js"
    ).read_text(encoding="utf-8")
    # Strip whole comment LINES so the prose explaining the directive can't
    # satisfy the assertion.
    #
    # Deliberately not `re.sub(r"//[^\n]*", ...)`: that also eats the "//" in
    # "https://api.tapeline.io/api/csp-report", which is the very string being
    # looked for. It made this test fail against correct config.
    code = "\n".join(
        ln for ln in cfg.splitlines() if not ln.lstrip().startswith("//")
    )
    assert "report-uri" in code, (
        "the CSP declares no reporting destination, so violations are still "
        "invisible and 'a week of clean reports' remains unobservable"
    )
    assert "/api/csp-report" in code
