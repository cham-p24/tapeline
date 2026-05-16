"""Pull Vercel Analytics event counts and render a 6-step funnel report.

The events come from frontend `track()` calls scattered across the app:

  signup_started       -> /signup mount + form submit attempt
  signup_completed     -> /signup successful POST response
  trial_started        -> /signup right after signup_completed (paired)
  scanner_first_use    -> first /app/scanner page load per session
  checkout_started     -> /app/billing 'Continue to Stripe' click
  trial_converted      -> /app/billing post-checkout, when Stripe webhook
                          downgrades trial_state to paid

Usage:
    cd C:/Project 1/scripts
    python funnel_report.py                       # last 7 days
    python funnel_report.py --days 30             # last 30 days
    python funnel_report.py --markdown report.md  # write a markdown report

Env required (read from .env if present, else os.environ):
    VERCEL_TOKEN      -> personal access token, scope: analytics:read
                         create at https://vercel.com/account/tokens
    VERCEL_PROJECT_ID -> the prj_... id, find via:
                         https://vercel.com/cham-p24s-projects/tapeline/settings
                         (General -> Project ID)
    VERCEL_TEAM_ID    -> optional, team_... id if project lives under a team

Doesn't write anywhere on the filesystem unless --markdown is passed.
Safe to run on the dev machine; no production side effects.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


FUNNEL_STEPS: list[tuple[str, str]] = [
    # (event_name, display_label)
    ("signup_started",     "Signup form opened"),
    ("signup_completed",   "Signup successful"),
    ("trial_started",      "Premium trial active"),
    ("scanner_first_use",  "First scanner visit"),
    ("checkout_started",   "Checkout clicked"),
    ("trial_converted",    "Paid (trial converted)"),
]


def _load_env(env_path: Path | None = None) -> None:
    """Best-effort load of KEY=VALUE pairs from a .env file in the script
    directory (and the repo root one level up). Does NOT overwrite values
    that are already set in os.environ — explicit env wins."""
    candidates = []
    if env_path is not None:
        candidates.append(env_path)
    here = Path(__file__).resolve().parent
    candidates.extend([here / ".env", here.parent / ".env"])
    for path in candidates:
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _vercel_request(path: str, params: dict[str, str]) -> dict[str, Any]:
    """GET against Vercel's API with auth + team-scoping. Returns the
    parsed JSON. Raises RuntimeError with a readable message on failure."""
    token = os.environ.get("VERCEL_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "VERCEL_TOKEN is not set. Create one at "
            "https://vercel.com/account/tokens (scope: analytics:read)."
        )
    team_id = os.environ.get("VERCEL_TEAM_ID", "").strip()
    if team_id:
        params = {**params, "teamId": team_id}
    qs = urlencode(params)
    url = f"https://api.vercel.com{path}?{qs}"
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(req, timeout=20) as resp:  # noqa: S310 (trusted host)
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Vercel API {exc.code}: {body[:400]}") from None
    except URLError as exc:
        raise RuntimeError(f"Vercel API unreachable: {exc}") from None


def fetch_event_count(event: str, since: datetime, until: datetime) -> int:
    """Pull the total count for one event name over [since, until].

    Vercel's Analytics API returns event series; we sum across all
    breakdown buckets. The exact endpoint is
    /v1/web/insights/events/<eventName> for a project. If the API shape
    changes, this is the function to patch.
    """
    project_id = os.environ.get("VERCEL_PROJECT_ID", "").strip()
    if not project_id:
        raise RuntimeError(
            "VERCEL_PROJECT_ID is not set. Find it at "
            "https://vercel.com/cham-p24s-projects/tapeline/settings"
        )
    params = {
        "projectId": project_id,
        "event": event,
        "from": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": until.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": "production",
    }
    data = _vercel_request("/v1/web/insights/events", params)
    # Vercel responds with a `data` array of buckets; each has a `total`
    # (or per-property counts). Sum defensively.
    total = 0
    for bucket in data.get("data", []) or []:
        v = bucket.get("total")
        if isinstance(v, int):
            total += v
        elif isinstance(v, float):
            total += int(v)
    return total


def render_funnel(counts: dict[str, int], days: int) -> str:
    """Markdown table with absolute counts and step-over-step conversion."""
    lines = [
        f"# Tapeline funnel — last {days} days",
        "",
        f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "| Step | Event | Count | Δ from prev | Cumulative conv. |",
        "|---:|---|---:|---:|---:|",
    ]
    top = counts.get(FUNNEL_STEPS[0][0], 0)
    prev = top
    for i, (event, label) in enumerate(FUNNEL_STEPS, 1):
        n = counts.get(event, 0)
        step_drop = "—" if i == 1 or prev == 0 else f"{(n / prev * 100):.1f}%"
        cumulative = "—" if top == 0 else f"{(n / top * 100):.1f}%"
        lines.append(f"| {i} | `{event}` — {label} | {n:,} | {step_drop} | {cumulative} |")
        prev = n
    lines.append("")
    lines.append("**Reading the table.** *Δ from prev* is the percentage of the previous")
    lines.append("step's users that completed this one — the local conversion rate.")
    lines.append("*Cumulative conv.* is the percentage of step 1 that reached this step.")
    lines.append("")
    lines.append(
        "If `signup_started` is high but `signup_completed` is low, the bottleneck "
        "is form friction (Turnstile, validation, password rules). If "
        "`scanner_first_use` is much lower than `trial_started`, the issue is "
        "activation — users sign up but don't engage. `checkout_started` to "
        "`trial_converted` is where Stripe and pricing live."
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a Tapeline acquisition funnel from Vercel Analytics events.",
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="Lookback window in days (default 7).",
    )
    parser.add_argument(
        "--markdown", type=Path, default=None,
        help="Write the markdown report to this file instead of stdout.",
    )
    parser.add_argument(
        "--env", type=Path, default=None,
        help="Path to a .env file to load before reading os.environ.",
    )
    args = parser.parse_args()

    _load_env(args.env)

    until = datetime.now(UTC)
    since = until - timedelta(days=args.days)

    counts: dict[str, int] = {}
    for event, _label in FUNNEL_STEPS:
        try:
            counts[event] = fetch_event_count(event, since, until)
        except RuntimeError as exc:
            sys.stderr.write(f"[funnel_report] {event}: {exc}\n")
            return 2

    report = render_funnel(counts, args.days)
    if args.markdown:
        args.markdown.write_text(report, encoding="utf-8")
        sys.stderr.write(f"[funnel_report] wrote {args.markdown}\n")
    else:
        sys.stdout.write(report + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
