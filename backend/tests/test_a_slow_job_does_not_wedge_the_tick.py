"""A periodic job that overruns must cost one cycle, not every cycle.

The cadence-gated jobs in `tick()` all look like this:

    if _last_x is None or (started - _last_x).total_seconds() > INTERVAL:
        await do_the_work()
        _last_x = started          # <- stamped AFTER

Stamping after is the natural way to write it and it is a trap. The tick runs
under a 60-second watchdog. When the watchdog kills the cycle mid-job, that
assignment never runs, so the next tick sees the same stale timestamp, starts
the same expensive job, and is killed in the same place. Nothing below it ever
runs again — and "below it" is most of the worker.

Production, 2026-09-07, once the stage label existed to show it:

    tick.timeout elapsed=60.0s limit=60s consecutive=1 stage=news_refresh+backcheck
    tick.timeout elapsed=60.0s limit=60s consecutive=2 stage=news_refresh+backcheck
    tick.timeout elapsed=60.0s limit=60s consecutive=3 stage=news_refresh+backcheck

every cycle. The sheet refresh sits below that block and never ran once, so
#766's parser fix deployed and then sat there doing nothing while scores stayed
wrong. Meanwhile the snapshot pass at the TOP of the tick kept writing 7,667
rows a cycle, so every external signal said the worker was fine.

Stamping the cadence BEFORE the work turns a permanent wedge into a single
missed cycle. For a 5-minute news refresh that is plainly the right trade: news
being five minutes stale is a non-event; a worker that does nothing else for
hours is not.
"""
from __future__ import annotations

import inspect
import re

import pytest

from app.workers import signal_publisher as sp


def _tick_source() -> str:
    return inspect.getsource(sp.tick)


# Each entry: the module global holding the cadence, and the awaited call it
# guards. Both must appear in tick() with the stamp BEFORE the await.
CADENCED_JOBS = [
    ("_last_news_refresh", "_refresh_news()"),
    ("_last_backcheck", "_run_backcheck()"),
]


@pytest.mark.parametrize("stamp,call", CADENCED_JOBS)
def test_the_cadence_is_stamped_before_the_work(stamp, call):
    """The fix. Stamping after means a killed cycle retries forever."""
    src = _tick_source()
    assign = f"{stamp} = started"
    assert assign in src, f"{stamp} is never stamped in tick()"
    assert call in src, f"{call} is not called from tick()"

    stamp_at = src.index(assign)
    call_at = src.index(call)
    assert stamp_at < call_at, (
        f"{stamp} is stamped AFTER {call}. When the 60s watchdog kills the "
        f"cycle mid-job the stamp never happens, so the next tick starts the "
        f"same job and dies in the same place — permanently, and every job "
        f"below it stops running"
    )


def test_the_news_insert_loop_is_bounded():
    """40 sequential transactions against a remote database, inside a 60s tick.

    The per-article isolation is deliberate (one over-wide row used to roll
    back the whole batch and leave the news bar 14h stale), so the loop keeps
    it and bounds the wall clock instead.
    """
    src = inspect.getsource(sp._refresh_news)
    assert "NEWS_INSERT_BUDGET_SECONDS" in src, (
        "the per-article insert loop has no wall-clock bound"
    )
    assert re.search(r"break", src), "the budget is read but never breaks the loop"
    assert 0 < sp.NEWS_INSERT_BUDGET_SECONDS <= 30, (
        f"NEWS_INSERT_BUDGET_SECONDS={sp.NEWS_INSERT_BUDGET_SECONDS} is not a "
        f"meaningful fraction of the 60s tick watchdog"
    )


def test_skipping_the_tail_loses_nothing():
    """Bounding is only safe because the loop is idempotent.

    Articles past the budget are picked up on the next 5-minute refresh, and
    the loop skips anything whose primary key already exists. If that lookup
    ever went away, a budget would start dropping news permanently.
    """
    src = inspect.getsource(sp._refresh_news)
    assert "NewsItem.id ==" in src, (
        "the insert loop no longer checks for an existing row by id, so "
        "articles skipped by the budget would be lost rather than retried"
    )


def test_the_two_jobs_have_distinct_stages():
    """`stage=news_refresh+backcheck` named two jobs at once and cost a round
    of guessing about which one was slow."""
    src = _tick_source()
    markers = re.findall(r'_set_stage\("([^"]+)"\)', src)
    for name in ("news_refresh", "backcheck", "edgar_8k"):
        assert name in markers, f"no distinct stage marker for {name}"
    assert "news_refresh+backcheck" not in markers, (
        "the combined label is back; a timeout under it cannot say which of "
        "the two jobs was running"
    )


def test_every_cadenced_job_in_the_tick_stamps_before_its_work():
    """Sweep, so a NEW periodic job cannot reintroduce the wedge.

    Finds every `_last_* = started` in tick() and checks that the cadence test
    guarding it appears before the assignment rather than the other way round.
    A job added later with the natural stamp-after ordering fails here.
    """
    src = _tick_source()
    offenders = []
    for m in re.finditer(r"^\s*(_last_\w+) = started\s*$", src, re.M):
        name = m.group(1)
        # The `if` that guards this job mentions the same global.
        guard = re.search(rf"if {re.escape(name)} is None", src)
        if not guard:
            continue  # stamped without a cadence guard; not this test's concern
        if m.start() > guard.start():
            # Stamp comes after the guard opens — fine only if it also comes
            # before the first await inside that block.
            block = src[guard.start():]
            first_await = block.find("await ")
            stamp_in_block = block.find(f"{name} = started")
            if first_await != -1 and stamp_in_block > first_await:
                offenders.append(name)
    assert not offenders, (
        f"these periodic jobs stamp their cadence AFTER their first await: "
        f"{offenders}. A cycle killed by the 60s watchdog will restart them "
        f"every tick forever and starve every job below them."
    )

# ── jobs too slow for a 60-second tick must be dispatched, not awaited ──────

SLOW_JOBS_THAT_MUST_BE_DETACHED = [
    ("_refresh_watchlisted_news", "two live HTTP calls per symbol across hundreds of symbols"),
    ("_refresh_workbook_tabs", "five CSV fetches plus a ~4,100-row upsert"),
]


@pytest.mark.parametrize("fn,why", SLOW_JOBS_THAT_MUST_BE_DETACHED)
def test_the_slow_jobs_are_spawned_not_awaited(fn, why):
    """Bounding a job that cannot fit only shortens the damage; detaching ends it.

    Stamping the cadence first (above) stops a slow job wedging the worker
    FOREVER, but it still costs a whole cycle every time the job runs, and the
    job itself never gets to finish. The sheet refresh showed exactly that: with
    the cadence fixed it stopped repeating, and instead was killed mid-refresh
    once per cadence — so the score corrections it carries never landed at all.

    A job that genuinely cannot fit in 60 seconds belongs off the tick.
    """
    src = _tick_source()
    assert f"_spawn({fn}(" in src, (
        f"{fn} is awaited inline in tick(), but it does {why} — the 60s "
        f"watchdog will kill the cycle mid-job, so the work never completes "
        f"and every job below it is skipped"
    )
    assert f"await {fn}(" not in src, (
        f"{fn} is still awaited inline somewhere in tick()"
    )


def test_a_detached_job_still_latches_before_dispatch():
    """Dispatch without latching would spawn a new copy every single tick."""
    src = _tick_source()
    for stamp, fn in (
        ("_last_watchlisted_news_refresh", "_refresh_watchlisted_news"),
        ("_last_sheet_refresh", "_refresh_workbook_tabs"),
    ):
        assign_at = src.index(f"{stamp} = started")
        spawn_at = src.index(f"_spawn({fn}(")
        assert assign_at < spawn_at, (
            f"{stamp} is latched after {fn} is dispatched, so every tick "
            f"spawns another copy of a job that takes minutes"
        )
