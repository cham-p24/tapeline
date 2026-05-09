"""Regression check — alert if production news goes stale.

Hits https://api.tapeline.io/api/news?limit=1 and asserts the latest
article is younger than a market-hours-aware threshold:

    Market hours (NYSE 9:30 AM – 8:00 PM ET, Mon–Fri): < 30 min
    Off-hours weekday:                                   < 4 h
    Weekend:                                             < 16 h

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


def is_market_hours(now_utc: datetime) -> bool:
    """NYSE-ish window in UTC. 9:30 AM ET = 13:30 UTC (winter) / 14:30 UTC
    (summer DST). We're conservative — treat 13:00–24:00 UTC Mon–Fri as
    "market or near-market hours". Weekend = always off-hours."""
    if now_utc.weekday() >= 5:  # Sat/Sun
        return False
    return 13 <= now_utc.hour < 24


def threshold_seconds(now_utc: datetime) -> int:
    """Pick the right freshness threshold based on when we're checking."""
    if is_market_hours(now_utc):
        return 30 * 60  # 30 min during market hours
    if now_utc.weekday() < 5:
        return 4 * 60 * 60  # 4 h off-hours weekday
    return 16 * 60 * 60  # 16 h weekends — Benzinga goes very quiet


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
    market = "market-hrs" if is_market_hours(now) else "off-hrs"
    print(
        f"{label} — latest article age {age_sec}s "
        f"(threshold {threshold}s, {market}, "
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
