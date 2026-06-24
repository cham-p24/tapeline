"""Regression check — alert if production news goes stale.

Hits https://api.tapeline.io/api/news?limit=1 and asserts the latest
article is younger than a market-hours-aware threshold:

    Active session  (NYSE 9:30 AM – 4:00 PM ET, Mon–Fri):  < 30 min
    Extended hours  (pre-market + after-hours):            < 90 min
    Overnight       (1 AM – 4 AM ET, Mon–Fri):             < 5 h
    Weekend:                                               < 16 h

Designed to be run as a Fly cron (or GitHub Actions cron) every 15
minutes. Exits 0 when fresh, 1 when stale. The 0 / 1 is the signal a
scheduler can act on (Fly machines stop, alerting hooks, etc.).

Alert hysteresis: a state file ($STATE_PATH, default
~/.tapeline-news-freshness-state.json) records the last-seen fresh/stale
status. We only POST a webhook alert on a FRESH→STALE transition, not on
every consecutive stale tick. Without this, a 4-hour stale window with
a 15-min cron generates 16 identical Sentry alerts; with it, we get
exactly 1 alert when it goes stale and 1 "recovered" note when it comes
back. The exit code (0 fresh, 1 stale) is unaffected — schedulers still
see staleness on every tick — only the webhook noise is throttled.

Why this exists:
    On 2026-05-09 production news went 14 hours stale because a single
    round-up news article overflowed the tickers VARCHAR(200)
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
    python -m app.scripts.check_news_freshness --state-path /tmp/freshness.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

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
        # 60 min: the 30-min bar cried wolf on routine ingestion lag (e.g. a
        # 35-min-old article during a slow news-wire minute), emailing a CI
        # failure each time. 60 min still catches a genuine stall within the
        # hour without alerting on normal jitter.
        return 60 * 60
    if phase == "extended":
        return 90 * 60        # 90 min during pre/post-market (sparser news)
    if phase == "overnight":
        # 5 h weekday overnight. 1–4 AM ET is the deepest US news quiet window:
        # the news wire has zero output for hours on a normal weekday morning and a
        # tighter 4h threshold ended up firing a borderline alert on 2026-05-14
        # at 1:03 AM ET (article was 4h 28min old — 28 min past the threshold).
        # 5h absorbs that without making the check toothless — if news genuinely
        # breaks during this window we'll still catch it within ~75 min.
        return 5 * 60 * 60
    return 16 * 60 * 60       # 16 h weekend — the news wire goes very quiet


# Backwards-compat alias used by some test/CLI code that imports it.
def is_market_hours(now_utc: datetime) -> bool:
    """True only during the active NYSE session (use session_phase for tiers)."""
    return session_phase(now_utc) == "active"


DEFAULT_STATE_PATH = str(Path.home() / ".tapeline-news-freshness-state.json")


def _load_state(path: str) -> dict:
    """Return last-run state, or an empty dict if the file is missing/corrupt.

    State shape: {"last_status": "fresh"|"stale"|"fetch_failed"|"empty_feed",
                  "since": ISO-UTC-string, "consecutive_failures": int}.
    A missing file is treated as "never run" → first stale tick WILL alert.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f) or {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_state(path: str, status: str, consecutive_failures: int) -> None:
    """Best-effort state write. Never raises — a write failure must not
    fail the cron run (we'd rather lose hysteresis than fail a healthy check).
    """
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        payload = {
            "last_status": status,
            "since": datetime.now(UTC).isoformat(),
            "consecutive_failures": consecutive_failures,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except OSError as e:
        print(f"  (state write failed: {e})", file=sys.stderr)


def _should_alert(prev_status: str, new_status: str) -> bool:
    """Hysteresis rule: alert only on transitions into a failure state.

    fresh → stale          → alert (state changed)
    stale → stale          → DO NOT alert (already known stale)
    fresh → fetch_failed   → alert
    fetch_failed → stale   → alert (different failure mode worth knowing)
    anything → fresh       → DO NOT alert here (handled separately as recovery)
    """
    if new_status == "fresh":
        return False
    return prev_status != new_status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=DEFAULT_BASE, help="API base URL")
    parser.add_argument(
        "--webhook",
        help="Optional webhook URL to POST a JSON alert to on failure",
    )
    parser.add_argument(
        "--state-path",
        default=DEFAULT_STATE_PATH,
        help=(
            "Where to persist last-run status for hysteresis. "
            f"Default: {DEFAULT_STATE_PATH}"
        ),
    )
    parser.add_argument(
        "--no-hysteresis",
        action="store_true",
        help="Disable hysteresis — alert on every stale tick (old behaviour).",
    )
    args = parser.parse_args()

    prev = _load_state(args.state_path)
    prev_status = prev.get("last_status", "fresh")
    prev_failures = int(prev.get("consecutive_failures", 0) or 0)

    url = args.base.rstrip("/") + "/api/news?limit=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "tapeline-cron"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
    except Exception as e:
        print(f"FAIL — could not fetch {url}: {e}", file=sys.stderr)
        new_status = "fetch_failed"
        if args.no_hysteresis or _should_alert(prev_status, new_status):
            _maybe_alert(args.webhook, new_status, str(e))
        _save_state(args.state_path, new_status, prev_failures + 1)
        return 1

    items = body.get("items") or []
    if not items:
        print("FAIL — /api/news returned 0 items", file=sys.stderr)
        new_status = "empty_feed"
        if args.no_hysteresis or _should_alert(prev_status, new_status):
            _maybe_alert(args.webhook, new_status, "no items in response")
        _save_state(args.state_path, new_status, prev_failures + 1)
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
        new_status = "stale_news"
        detail = (
            f"age={age_sec}s threshold={threshold}s "
            f"title={items[0].get('title', '')[:60]!r}"
        )
        if args.no_hysteresis or _should_alert(prev_status, new_status):
            _maybe_alert(args.webhook, new_status, detail)
        else:
            print(
                f"  (alert suppressed — already in {prev_status} state since "
                f"{prev.get('since', 'unknown')})"
            )
        _save_state(args.state_path, new_status, prev_failures + 1)
        return 1

    # Fresh path — log recovery if we were previously stale.
    if prev_status != "fresh" and prev_status:
        _maybe_alert(
            args.webhook,
            "recovered",
            f"news fresh again after {prev_failures} stale ticks "
            f"(was {prev_status} since {prev.get('since', 'unknown')})",
        )
    _save_state(args.state_path, "fresh", 0)
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
