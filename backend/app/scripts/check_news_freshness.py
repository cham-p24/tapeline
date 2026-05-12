"""Regression check — alert if production news goes stale.

Hits https://api.tapeline.io/api/news?limit=1 and asserts the latest
article is younger than a market-hours-aware threshold:

    Active session  (NYSE 9:30 AM – 4:00 PM ET, Mon–Fri):  < 30 min
    Extended hours  (pre-market + after-hours):            < 90 min
    Overnight       (8 PM – 4 AM ET, Mon–Fri):             < 4 h
    Weekend:                                               < 16 h

Designed to be run as a Fly cron (or GitHub Actions cron) every 15
minutes. Exits 0 when fresh, 1 when stale. The 0 / 1 is the signal a
scheduler can act on (Fly machines stop, alerting hooks, etc.).

Why this exists:
    On 2026-05-09 production news went 14 hours stale because a single
    Benzinga round-up article overflowed the tickers VARCHAR(200)
    column and rolled back the whole batch INSERT. The bug was
    invisible from the homepage — `worker_last_tick` showed healthy,
    `/api/status` reported "ok", but news.latest_article_age was
    quietly climbing for hours. /api/status now exposes news health
    natively (after that incident), but a separate cron probe is
    cheap belt-and-suspenders.

Usage:
    python -m app.scripts.check_news_freshness
    python -m app.scripts.check_news_freshness --base https://api.tapeline.io
    python -m app.scripts.check_news_freshness --webhook https://hooks.slack.com/...
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, datetime

DEFAULT_BASE = "https://api.tapeline.io"


def session_phase(now_utc: datetime) -> str:
    """Classify current time into NYSE session phase.

    All times in UTC. NYSE DST shifts ET by 1 hour between summer/winter:
        Summer (Mar–Nov, EDT, UTC−4): 9:30 AM ET = 13:30 UTC; 4 PM = 20:00; 8 PM = 24:00
        Winter (Nov–Mar, EST, UTC−5): 9:30 AM ET = 14:30 UTC; 4 PM = 21:00; 8 PM = 25:00 (next-day 01:00)

    To cover both without a tzdata lookup, we use a slightly wider envelope
    that's still tight enough to flag real bugs:
        active:    13 ≤ UTC < 21   (NYSE open + a 1h buffer for DST)
        extended:  8  ≤ UTC < 13   (pre-market) OR 21 ≤ UTC < 25  (after-hours)
        overnight: 1  ≤ UTC < 8    (late-night ET)
        weekend:   Sat/Sun any time
    """
    if now_utc.weekday() >= 5:  # Sat/Sun
        return "weekend"
    h = now_utc.hour
    if 13 <= h < 21:
        return "active"
    if 8 <= h < 13 or 21 <= h < 24 or h == 0:
        return "extended"
    return "overnight"


def threshold_seconds(now_utc: datetime) -> int:
    """Pick the right freshness threshold based on the current session phase."""
    phase = session_phase(now_utc)
    if phase == "active":
        return 30 * 60        # 30 min during the regular NYSE session
    if phase == "extended":
        return 90 * 60        # 90 min during pre/post-market (sparser news)
    if phase == "overnight":
        return 4 * 60 * 60    # 4 h weekday overnight
    return 16 * 60 * 60       # 16 h weekend — Benzinga goes very quiet


# Backwards-compat alias used by some test/CLI code that imports it.
def is_market_hours(now_utc: datetime) -> bool:
    """True only during the active NYSE session (use session_phase for tiers)."""
    return session_phase(now_utc) == "active"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=DEFAULT_BASE, help="API base URL")
    parser.add_argument(
        "--webhook",
        help="Optional webhook URL to POST a JSON alert to on failure",
    )
    args = parser.parse_args()

    url = args.base.rstrip("/") + "/api/news?limit=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "tapeline-cron"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
    except Exception as e:
        print(f"FAIL — could not fetch {url}: {e}", file=sys.stderr)
        _maybe_alert(args.webhook, "fetch_failed", str(e))
        return 1

    items = body.get("items") or []
    if not items:
        print("FAIL — /api/news returned 0 items", file=sys.stderr)
        _maybe_alert(args.webhook, "empty_feed", "no items in response")
        return 1

    now = datetime.now(UTC)
    pub = datetime.fromisoformat(items[0]["published_at"].replace("Z", "+00:00"))
    age_sec = int((now - pub).total_seconds())
    threshold = threshold_seconds(now)
    fresh = age_sec < threshold

    label = "OK" if fresh else "FAIL"
    phase = session_phase(now)
    print(
        f"{label} — latest article age {age_sec}s "
        f"(threshold {threshold}s, phase={phase}, "
        f"weekday={now.weekday()})"
    )
    if not fresh:
        _maybe_alert(
            args.webhook,
            "stale_news",
            f"age={age_sec}s threshold={threshold}s title={items[0].get('title', '')[:60]!r}",
        )
        return 1
    return 0


def _maybe_alert(webhook: str | None, kind: str, detail: str) -> None:
    """Best-effort notification. Never fails the run because of webhook errors."""
    if not webhook:
        return
    try:
        payload = json.dumps({
            "text": f":warning: Tapeline news-freshness check: {kind} — {detail}",
        }).encode()
        req = urllib.request.Request(
            webhook,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as e:
        print(f"  (webhook failed: {e})", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
