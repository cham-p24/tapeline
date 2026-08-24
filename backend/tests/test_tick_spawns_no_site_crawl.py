"""The 60s tick must not crawl a website.

Production incident, 2026-08-24: 180 consecutive `tick.timeout elapsed=60.0s`,
scoring frozen table-wide for ~3 hours. The worker log was solid HEAD requests
to `https://tapeline.io/t/<SYMBOL>` — the daily stale-link audit crawling the
full sitemap from inside the tick.

It was already "detached" via `asyncio.create_task`, and the comment above it
said that made it safe. It did not. Detaching removes the AWAIT dependency, not
the RESOURCE contention: ~1k HTTP requests saturate the same event loop a
shared-cpu-1x/512MB worker needs to finish a tick in 60 seconds.

Two things made it self-sustaining rather than a one-off:

  * The once-a-day latch was a module global, so it re-armed on every process
    start. ~10 deploys that day meant ~10 overlapping full-site crawls per
    machine, across both worker machines.
  * Restarting could not clear it. The machine came back, saw an unset latch,
    and immediately started crawling again — verified live: the first tick
    after a restart timed out at `consecutive=1`.

The audit now runs from .github/workflows/stale-link-audit.yml.

This asserts the tick's own module can no longer start one. It is a source
check by necessity — the failure needs a 512MB box under real network load to
reproduce, which a unit test cannot stage — so it is deliberately narrow: it
pins the specific mechanism (a spawn of the crawl) rather than trying to prove
absence of slowness in general.
"""
from __future__ import annotations

import inspect

from app.workers import signal_publisher

SRC = inspect.getsource(signal_publisher)


def test_the_tick_module_cannot_start_a_sitemap_crawl():
    """No spawn, no runner, no latch — the whole mechanism is gone."""
    assert not hasattr(signal_publisher, "_run_daily_stale_audit"), (
        "the detached stale-audit runner is back in the worker; it wedged the "
        "tick for 3h on 2026-08-24 and belongs in GitHub Actions"
    )
    assert "_run_daily_stale_audit()" not in SRC
    assert "run_stale_audit_alert" not in SRC, (
        "the tick imports the sitemap crawler again"
    )


def test_no_module_global_latch_gates_a_long_job():
    """A module global re-arms on every deploy — that is what made it a storm."""
    assert not hasattr(signal_publisher, "_last_stale_audit_date"), (
        "a process-local latch is back. It cannot survive a restart, so ten "
        "deploys in a day means ten crawls, and a restart re-triggers rather "
        "than clears it."
    )


def test_the_audit_still_runs_somewhere():
    """Removing the capability was not the fix — relocating it was."""
    from pathlib import Path

    wf = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "stale-link-audit.yml"
    assert wf.is_file(), "the stale-link audit lost its home entirely"
    text = wf.read_text(encoding="utf-8")
    assert "run_stale_audit_alert" in text, "the workflow does not run the audit"
    assert "concurrency:" in text, (
        "an overrunning crawl must not be able to overlap itself — that is the "
        "guard the in-worker version never had"
    )
