"""News-pipeline health monitoring — thresholds, /api/status probe, and cron.

Regression guard for the 2026-08 retune. The freshness cron was alerting on
~25% of its runs while the pipeline was completely healthy, because it measured
`max(published_at)` — the VENDOR's publish time — against a 30/60-min bar.
Measured over 21 days of production, even the freshest articles we receive land
p50 44 min / p90 96 min after their own published_at (and we poll every 5 min,
so that lag is vendor-side). The bar sat below the vendor's own p90 delivery
lag and could never be satisfied.

The fix splits the two signals:
    ingest heartbeat (max(created_at)) -> PRIMARY, phase-independent, is OUR health
    wire freshness   (max(published_at)) -> loose canary, is the VENDOR's behaviour

The load-bearing test here is
`test_healthy_ingest_with_old_published_at_does_not_alert` — that is precisely
the state that produced the false alerts.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.scripts import check_news_freshness as chk
from app.services.news_health import (
    NEWS_INGEST_DOWN_SECONDS,
    NEWS_INGEST_STALE_SECONDS,
    news_session_phase,
    news_wire_canary_seconds,
)

# ── thresholds ───────────────────────────────────────────────────────────────

def test_ingest_threshold_clears_the_worst_observed_silence():
    """120 min vs the worst real ingest silence in 21 days (54 min)."""
    assert NEWS_INGEST_STALE_SECONDS == 120 * 60
    assert NEWS_INGEST_STALE_SECONDS > 54 * 60 * 2  # >2x headroom
    assert NEWS_INGEST_DOWN_SECONDS > NEWS_INGEST_STALE_SECONDS


def test_ingest_threshold_is_phase_independent():
    """The heartbeat is driven by OUR poll loop, so it must not vary by phase —
    measured p90 was 1.9-3.1 min in every session phase."""
    assert isinstance(NEWS_INGEST_STALE_SECONDS, int)  # a scalar, not a mapping


@pytest.mark.parametrize(
    "iso,expected",
    [
        ("2026-08-19T15:00:00+00:00", "active"),     # Wed midday UTC
        ("2026-08-19T09:00:00+00:00", "extended"),   # Wed pre-market
        ("2026-08-19T22:00:00+00:00", "extended"),   # Wed after-hours
        ("2026-08-19T04:00:00+00:00", "overnight"),  # Wed deep night
        ("2026-08-22T15:00:00+00:00", "weekend"),    # Saturday
    ],
)
def test_session_phase_classification(iso, expected):
    assert news_session_phase(datetime.fromisoformat(iso)) == expected


def test_wire_canary_clears_measured_vendor_lag():
    """The canary must sit above the vendor's p99 delivery lag (117 min) and the
    p99 frontier-advance gap (148 min) — otherwise it re-creates the bug."""
    active = news_wire_canary_seconds(datetime.fromisoformat("2026-08-19T15:00:00+00:00"))
    assert active >= 240 * 60
    assert active > 148 * 60          # p99 frontier advance
    # The old 60-min active bar is exactly what fired falsely.
    assert active > 60 * 60


# ── cron: primary ingest-heartbeat path ──────────────────────────────────────

def _status(ingest_age, wire_age=600, wire_stale=False):
    return {
        "checks": {
            "news": {
                "status": "ok",
                "ingest_age_seconds": ingest_age,
                "ingest_stale_after_seconds": NEWS_INGEST_STALE_SECONDS,
                "latest_article_age_seconds": wire_age,
                "wire_stale_after_seconds": 240 * 60,
                "wire_stale": wire_stale,
            }
        }
    }


def _run(monkeypatch, payload, tmp_path, argv=()):
    """Run the cron against a canned /api/status payload; capture alerts."""
    alerts: list[tuple[str, str]] = []
    monkeypatch.setattr(chk, "_fetch_json", lambda url: payload)
    monkeypatch.setattr(
        chk, "_maybe_alert", lambda hook, kind, detail: alerts.append((kind, detail))
    )
    monkeypatch.setattr(
        "sys.argv",
        ["check", "--webhook", "https://hook.test",
         "--state-path", str(tmp_path / "state.json"), *argv],
    )
    return chk.main(), alerts


def test_healthy_ingest_with_old_published_at_does_not_alert(monkeypatch, tmp_path):
    """THE REGRESSION. Ingestion is healthy (wrote 3 min ago) but the newest
    vendor article is 108 min old — the exact state that fired ~25% of runs."""
    code, alerts = _run(
        monkeypatch, _status(ingest_age=180, wire_age=6488, wire_stale=False), tmp_path
    )
    assert code == 0, "a healthy pipeline must exit 0 even when the wire is slow"
    assert alerts == [], f"must not alert on vendor lag, got {alerts}"


def test_stalled_ingest_alerts(monkeypatch, tmp_path):
    """A genuine stall — no row written since just past the limit — is what we
    DO want to hear. Age sits in the first cron window after the crossing, so
    the stateless hysteresis lets it through."""
    code, alerts = _run(
        monkeypatch, _status(ingest_age=NEWS_INGEST_STALE_SECONDS + 60), tmp_path
    )
    assert code == 1
    assert [k for k, _ in alerts] == ["stale_ingest"]
    assert "no news row" in alerts[0][1]


def test_stalled_ingest_still_fails_but_stops_re_alerting(monkeypatch, tmp_path):
    """Deep into a known stall the exit code stays 1 (schedulers keep seeing it)
    while the webhook is throttled — 16 identical pages per 4h outage was the
    original reason hysteresis exists."""
    code, alerts = _run(
        monkeypatch, _status(ingest_age=NEWS_INGEST_STALE_SECONDS + 3600), tmp_path
    )
    assert code == 1, "still unhealthy"
    assert alerts == [], "already-known stall must not re-page every 15 min"


def test_wire_dark_alerts_separately_from_a_pipeline_stall(monkeypatch, tmp_path):
    """Ingestion healthy but the wire is genuinely dark -> distinct, lower-
    severity signal, never conflated with 'our pipeline broke'."""
    code, alerts = _run(
        monkeypatch,
        _status(ingest_age=120, wire_age=240 * 60 + 60, wire_stale=True),
        tmp_path,
    )
    assert code == 1
    assert [k for k, _ in alerts] == ["wire_dark"]
    assert "ingestion is healthy" in alerts[0][1]


def test_ingest_stall_takes_precedence_over_wire_dark(monkeypatch, tmp_path):
    """If both trip, report the actionable one."""
    code, alerts = _run(
        monkeypatch,
        _status(
            ingest_age=NEWS_INGEST_STALE_SECONDS + 60,
            wire_age=240 * 60 + 60,
            wire_stale=True,
        ),
        tmp_path,
    )
    assert code == 1
    assert [k for k, _ in alerts] == ["stale_ingest"]


def test_falls_back_to_legacy_probe_when_ingest_fields_absent(monkeypatch, tmp_path):
    """Mid-deploy (or an older API) the ingest fields are missing — the cron must
    still evaluate something rather than report a false all-clear."""
    calls: list[str] = []

    def fake_fetch(url: str) -> dict:
        calls.append(url)
        if url.endswith("/api/status"):
            return {"checks": {"news": {"status": "ok"}}}  # no ingest fields
        return {"items": [{"published_at": datetime.now(UTC).isoformat(),
                           "title": "fresh"}]}

    monkeypatch.setattr(chk, "_fetch_json", fake_fetch)
    monkeypatch.setattr(chk, "_maybe_alert", lambda *a: None)
    monkeypatch.setattr(
        "sys.argv", ["check", "--state-path", str(tmp_path / "s.json")]
    )
    assert chk.main() == 0
    assert any(u.endswith("/api/status") for u in calls)
    assert any("/api/news" in u for u in calls), "must fall back to the news probe"


# ── /api/status wiring ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_status_exposes_the_ingest_heartbeat():
    """The cron reads its thresholds off this payload, so the fields must be
    present and self-describing. Asserted against the live endpoint rather than
    the helper, because the wiring is what broke before."""
    import httpx

    from app.db import session_scope
    from app.main import app
    from app.models import NewsItem

    async with session_scope() as s:
        s.add(NewsItem(
            id="newshealth-probe-1",
            title="probe", publisher="t", url="https://example.test/1",
            # Published long ago, ingested NOW — the shape that used to be
            # misreported as unhealthy.
            published_at=datetime.now(UTC) - timedelta(hours=4),
            tickers="AAPL",
        ))
        await s.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        news = (await c.get("/api/status")).json()["checks"]["news"]

    # Self-describing contract the cron depends on.
    for field in (
        "ingest_age_seconds",
        "latest_ingested_at",
        "ingest_stale_after_seconds",
        "latest_article_age_seconds",
        "wire_stale",
        "wire_stale_after_seconds",
    ):
        assert field in news, f"/api/status must expose {field} for the cron"

    assert news["ingest_stale_after_seconds"] == NEWS_INGEST_STALE_SECONDS
    assert isinstance(news["wire_stale"], bool)
    # We just wrote a row, so the heartbeat is fresh and the pipeline is not
    # "down" no matter how old the newest article happens to be.
    assert news["ingest_age_seconds"] < 300
    assert news["status"] != "down"
