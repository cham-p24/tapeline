"""Thresholds + phase logic for news-pipeline health.

Single source of truth for "is the news pipeline healthy", shared by the
/api/status probe (app/main.py) and — indirectly — by the freshness cron
(app/scripts/check_news_freshness.py), which reads the numbers back off the
API response rather than hard-coding its own copy. The cron runs as a
standalone stdlib script in GitHub Actions and cannot import this module, so
"server owns the thresholds, cron consumes them" is what keeps the two from
drifting.

WHY TWO SIGNALS (retuned 2026-08)
---------------------------------
The original check measured only `max(published_at)` — the newest article the
vendor has published to us — and alerted when it exceeded a 30/60-min bar
during market hours. That fired on ~25% of cron runs with nothing wrong.
Measured against 21 days of production data:

  * The wire is busy: consecutive publish gaps are p50 0.3 min.
  * But the VENDOR delivers late: even the freshest articles we receive land
    p50 44 min / p90 96 min after their own published_at, and we poll every
    5 min — so that lag is vendor-side, not ours.
  * A 60-min bar therefore sits *below* the p90 delivery lag. It could never
    be satisfied, and failures clustered exactly where the bar was tightest
    (active 16.9%, extended 16.0%, overnight 0%, weekend 0%).

So `published_at` cannot measure OUR health. `max(created_at)` — the ingest
heartbeat — can: it is driven by our own refresh loop, and is remarkably
phase-independent (p90 1.9–3.1 min in EVERY session phase, longest silence in
21 days: 54 min).

  INGEST HEARTBEAT (primary)  -> flat thresholds, no phase tiers needed.
  WIRE FRESHNESS   (canary)   -> loose, phase-aware; "the wire looks dead".

Both bounds below were validated by replaying 21 days of production ingest
history over a simulated 15-minute cron: 0 false alerts out of 1,992 ticks
(the previous wire bars produced 122).
"""
from __future__ import annotations

from datetime import datetime

# ── Primary: ingestion heartbeat ────────────────────────────────────────────
# 120 min is ~2.2x the worst ingest silence observed in 21 days (54 min), so a
# genuine stall (dead worker, revoked vendor key, failing DB write — the
# 2026-05-09 incident class) still surfaces inside two hours.
NEWS_INGEST_STALE_SECONDS = 120 * 60
# Sustained silence — escalates the public pill from "degraded" to "down".
NEWS_INGEST_DOWN_SECONDS = 240 * 60


def news_session_phase(now_utc: datetime) -> str:
    """Classify a UTC instant into an NYSE session phase.

    Uses a slightly wider envelope than the real session so it holds across the
    EDT/EST shift without a tzdata lookup:
        active:    13 <= UTC < 21   (NYSE open + 1h DST buffer)
        extended:  8 <= UTC < 13, or 21 <= UTC < 24, or hour 0  (pre/post)
        overnight: 1 <= UTC < 8     (deepest US news-quiet window)
        weekend:   Sat/Sun
    """
    if now_utc.weekday() >= 5:
        return "weekend"
    h = now_utc.hour
    if 13 <= h < 21:
        return "active"
    if 8 <= h < 13 or 21 <= h < 24 or h == 0:
        return "extended"
    return "overnight"


# ── Secondary: wire-dead canary ─────────────────────────────────────────────
# Deliberately loose. This is NOT a health metric — it is dominated by vendor
# delivery lag — so it only ever escalates "ok" -> "stale", never to "down".
# 240 min clears the measured p99 fresh-delivery lag (117 min) and the p99
# frontier-advance gap (148 min) with margin. Overnight/weekend keep their
# existing wider bars, which already produced zero false alerts.
_WIRE_CANARY_SECONDS = {
    "active": 240 * 60,
    "extended": 240 * 60,
    "overnight": 300 * 60,
    "weekend": 960 * 60,
}


def news_wire_canary_seconds(now_utc: datetime) -> int:
    """Age at which `max(published_at)` suggests the wire itself has gone dark."""
    return _WIRE_CANARY_SECONDS[news_session_phase(now_utc)]
