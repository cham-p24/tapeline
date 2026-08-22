"""Regression check — alert if the production news PIPELINE stalls.

Reads https://api.tapeline.io/api/status and keys off two distinct signals
exposed by the news probe there. The server owns the thresholds and publishes
them in the same payload, so this script holds no copy of its own to drift
(it runs standalone on a GitHub Actions runner and cannot import app code).

    PRIMARY   ingest heartbeat — `ingest_age_seconds`, i.e. how long since WE
              last wrote a news row. Driven by our own 5-min refresh loop and
              therefore phase-independent. Stale => the worker, the vendor
              credentials, or the DB write is genuinely broken. THIS is the
              condition worth waking someone for.

    SECONDARY wire-dead canary — `latest_article_age_seconds`, how old the
              newest VENDOR-published article is. Dominated by vendor delivery
              lag, not our health, so it is bounded loosely and reported at a
              lower severity.

Retuned 2026-08: the old check alerted purely on vendor publish age against a
30/60-min market-hours bar, which fired on ~25% of runs while ingestion was
perfectly healthy. Measured over 21 days of production, even the freshest
articles arrive p50 44 min / p90 96 min after their own published_at, so that
bar sat below the vendor's own p90 delivery lag and could never be met. See
app/services/news_health.py for the full derivation.

Falls back to the legacy /api/news?limit=1 publish-age check (against the
loosened bars) when the API predates the ingest-heartbeat fields, so a
mid-deploy runner still reports something sane.

Designed to be run as a Fly cron (or GitHub Actions cron) every 15
minutes. Exits 0 when fresh, 1 when stale. The 0 / 1 is the signal a
scheduler can act on (Fly machines stop, alerting hooks, etc.).

Alert hysteresis (stateless): without this, a 4-hour stale window with a
15-min cron generates 16 identical alerts. The debounce is derived from
the article's own published_at rather than from a local state file,
because the primary runner is a GitHub Actions cron — a fresh VM every
run, so any file-backed "last status" is always empty and the debounce
never actually suppresses anything.

The stateless rule (see `should_alert_stale`): the article's age tells us
how long we have been stale, so we alert only on the first cron tick
after the threshold is crossed, then re-alert once per --realert-hours
while it stays stale. On a 15-min cron a 4-hour outage yields ~2 alerts
instead of 16, and the periodic re-alert means a skipped/late run can
never swallow the notification entirely.

The exit code (0 fresh, 1 stale) is unaffected — schedulers still see
staleness on every tick — only the webhook noise is throttled.

The state file ($STATE_PATH, default ~/.tapeline-news-freshness-state.json)
is still written where the filesystem persists (Fly cron, local runs). It
is purely advisory now — it powers the "recovered" note and the stale-tick
counter, and nothing breaks when it is missing.

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
    python -m app.scripts.check_news_freshness --interval-minutes 15 --realert-hours 4
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
        # 240 min. Successively 30 -> 60 -> 240: the earlier bars were set from
        # intuition about how often news breaks, but the binding constraint is
        # the VENDOR's delivery lag, which we measured at p50 44 min / p90 96
        # min / p99 117 min for the freshest articles we receive. A 60-min bar
        # is below the vendor's own p90, so it fired constantly with nothing
        # wrong (122 false alerts across 1,992 simulated ticks; 0 at 240 min).
        # Real pipeline stalls are caught by the ingest heartbeat instead.
        return 240 * 60
    if phase == "extended":
        return 240 * 60       # same vendor lag applies pre/post-market
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

# Nominal spacing between cron runs. Must match the scheduler cadence — it is
# the window width used to detect "this is the first tick since we went stale".
DEFAULT_INTERVAL_MINUTES = 15
# How often to re-alert while news stays stale (bounds the noise, and stops a
# skipped run from swallowing the one-and-only alert).
DEFAULT_REALERT_HOURS = 4


def should_alert_stale(
    age_sec: int,
    threshold_sec: int,
    interval_sec: int,
    realert_sec: int,
) -> bool:
    """Stateless hysteresis for the stale-news case.

    `age_sec - threshold_sec` is how long we have been over the line, read
    straight off the article's published_at — no local state needed, so this
    works identically on an ephemeral CI runner and on a long-lived host.

    Consecutive cron ticks are `interval_sec` apart, so exactly one tick lands
    in each `interval_sec`-wide window. We alert on the window that starts at
    the crossing, and on the window starting every `realert_sec` after it:

        age just over threshold      → alert (first detection)
        age threshold + 30 min       → suppressed (already alerted)
        age threshold + 4 h          → alert (periodic re-alert)
    """
    if age_sec < threshold_sec:
        return False
    if interval_sec <= 0:
        return True
    stale_for = age_sec - threshold_sec
    if realert_sec <= 0:
        return stale_for < interval_sec
    return stale_for % realert_sec < interval_sec


def _load_state(path: str) -> dict:
    """Return last-run state, or an empty dict if the file is missing/corrupt.

    State shape: {"last_status": "fresh"|"stale"|"fetch_failed"|"empty_feed",
                  "since": ISO-UTC-string, "consecutive_failures": int}.
    Advisory only — the stale-news debounce is stateless (see
    `should_alert_stale`). A missing file just means no "recovered" note and a
    zeroed stale-tick counter.
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
    """State-file hysteresis, used only for the timestamp-less failure modes.

    fetch_failed / empty_feed have no article timestamp to derive staleness
    duration from, so they fall back to this transition check. Where state does
    not persist (CI) it degrades to alerting on every tick — deliberate: a hard
    outage (API unreachable, empty feed) is worth hearing about every time
    rather than risking silence.

    fresh → fetch_failed   → alert
    fetch_failed → stale   → alert (different failure mode worth knowing)
    fetch_failed → fetch_failed → DO NOT alert (already known)
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
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=DEFAULT_INTERVAL_MINUTES,
        help=(
            "Cron cadence in minutes — the window used to detect the first "
            f"stale tick. Default: {DEFAULT_INTERVAL_MINUTES}"
        ),
    )
    parser.add_argument(
        "--realert-hours",
        type=float,
        default=DEFAULT_REALERT_HOURS,
        help=(
            "Re-alert this often while news stays stale. 0 disables re-alerts. "
            f"Default: {DEFAULT_REALERT_HOURS}"
        ),
    )
    args = parser.parse_args()

    prev = _load_state(args.state_path)
    prev_status = prev.get("last_status", "fresh")
    prev_failures = int(prev.get("consecutive_failures", 0) or 0)

    base = args.base.rstrip("/")
    now = datetime.now(UTC)
    interval_sec = max(int(args.interval_minutes), 0) * 60
    realert_sec = int(max(args.realert_hours, 0) * 3600)

    # ── PRIMARY: /api/status ingest heartbeat ────────────────────────────
    # The server computes health and publishes the thresholds it used, so this
    # script keeps no copy of them. If /api/status is unreachable or predates
    # the ingest fields we fall through to the legacy publish-age probe rather
    # than reporting a false all-clear.
    news: dict = {}
    try:
        status_body = _fetch_json(base + "/api/status")
        news = (status_body.get("checks") or {}).get("news") or {}
    except Exception as e:
        print(f"  (/api/status unavailable: {e}; falling back)", file=sys.stderr)

    ingest_age = news.get("ingest_age_seconds")
    if ingest_age is not None:
        ingest_age = int(ingest_age)
        ingest_limit = int(news.get("ingest_stale_after_seconds") or 7200)
        wire_age = news.get("latest_article_age_seconds")
        wire_limit = news.get("wire_stale_after_seconds")
        wire_dark = bool(news.get("wire_stale"))

        wire_note = ""
        if wire_age is not None and wire_limit:
            wire_note = f", wire {int(wire_age)}s/{int(wire_limit)}s"

        # Real pipeline stall — we have not written a row in too long.
        if ingest_age >= ingest_limit:
            print(
                f"FAIL — news INGEST stalled: last write {ingest_age}s ago "
                f"(limit {ingest_limit}s{wire_note})",
                file=sys.stderr,
            )
            detail = (
                f"no news row written for {ingest_age}s (limit {ingest_limit}s). "
                f"Worker, vendor credentials or DB write is likely broken{wire_note}."
            )
            if args.no_hysteresis or should_alert_stale(
                ingest_age, ingest_limit, interval_sec, realert_sec
            ):
                _maybe_alert(args.webhook, "stale_ingest", detail)
            else:
                print(
                    f"  (alert suppressed — stalled for "
                    f"{ingest_age - ingest_limit}s already)"
                )
            _save_state(args.state_path, "stale_ingest", prev_failures + 1)
            return 1

        # Ingestion is healthy; the vendor wire itself looks dark. Lower
        # severity — nothing of ours is broken, but it is worth knowing.
        if wire_dark:
            print(
                f"FAIL — news wire looks dark: newest article {int(wire_age)}s old "
                f"(limit {int(wire_limit)}s), but ingestion is healthy "
                f"({ingest_age}s since last write)",
                file=sys.stderr,
            )
            if args.no_hysteresis or should_alert_stale(
                int(wire_age), int(wire_limit), interval_sec, realert_sec
            ):
                _maybe_alert(
                    args.webhook,
                    "wire_dark",
                    f"no NEW vendor article for {int(wire_age)}s "
                    f"(limit {int(wire_limit)}s); our ingestion is healthy "
                    f"(last write {ingest_age}s ago)",
                )
            _save_state(args.state_path, "wire_dark", prev_failures + 1)
            return 1

        print(
            f"OK — ingest heartbeat {ingest_age}s (limit {ingest_limit}s"
            f"{wire_note}, phase={session_phase(now)})"
        )
        # fall through to the shared recovery/exit path below

    else:
        # ── FALLBACK: legacy publish-age probe ───────────────────────────
        url = base + "/api/news?limit=1"
        try:
            body = _fetch_json(url)
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

        pub = datetime.fromisoformat(
            items[0]["published_at"].replace("Z", "+00:00")
        )
        age_sec = int((now - pub).total_seconds())
        threshold = threshold_seconds(now)

        label = "OK" if age_sec < threshold else "FAIL"
        print(
            f"{label} — [legacy probe] latest article age {age_sec}s "
            f"(threshold {threshold}s, phase={session_phase(now)}, "
            f"weekday={now.weekday()})"
        )
        if age_sec >= threshold:
            detail = (
                f"age={age_sec}s threshold={threshold}s "
                f"title={items[0].get('title', '')[:60]!r}"
            )
            if args.no_hysteresis or should_alert_stale(
                age_sec, threshold, interval_sec, realert_sec
            ):
                _maybe_alert(args.webhook, "stale_news", detail)
            else:
                print(
                    f"  (alert suppressed — already stale for "
                    f"{age_sec - threshold}s; next re-alert after "
                    f"{realert_sec}s stale)"
                )
            _save_state(args.state_path, "stale_news", prev_failures + 1)
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


def _fetch_json(url: str) -> dict:
    """GET `url` and parse JSON. Raises on any transport/parse failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "tapeline-cron"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


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
