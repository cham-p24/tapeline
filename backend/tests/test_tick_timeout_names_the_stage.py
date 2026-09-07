"""When the tick is killed, the log must say which job was running.

`tick()` runs about twenty-five distinct jobs under a single 60-second
watchdog, most of them cadence-gated. When it is killed, everything BELOW the
slow job is skipped — and the log said only:

    tick.timeout elapsed=60.0s limit=60s consecutive=7

which is the least useful sentence available about a worker that has silently
stopped doing most of its work. On 2026-09-07 what got skipped included the
sheet refresh, so a parser fix deployed and then never executed, while the
snapshot pass at the TOP of the tick kept writing 7,667 rows a cycle and made
the worker look perfectly healthy from outside.

Diagnosing that took pulling a stream of vendor URLs out of the logs and
running a timing harness by hand on the box. A string assignment per stage
means the next occurrence reads `stage=aggregates_refresh` and is over.
"""
from __future__ import annotations

import asyncio

import pytest

from app.workers import signal_publisher as sp


class _StopLoop(BaseException):
    """BaseException so main()'s `except Exception` arms don't swallow it."""


@pytest.fixture
def harness(monkeypatch):
    logged: list[tuple] = []

    async def _noop():
        pass

    async def _refresh():
        return 1

    async def _sleep(_s):
        raise _StopLoop

    def _error(msg, *args, **kw):
        logged.append((msg, args))

    monkeypatch.setattr(sp, "_init_sentry", lambda: None, raising=True)
    monkeypatch.setattr(sp, "seed_universe", _noop, raising=True)
    monkeypatch.setattr(sp, "warm_factor_caches_from_db", _noop, raising=True)
    monkeypatch.setattr(sp, "refresh_active_universe", _refresh, raising=True)
    monkeypatch.setattr(sp.logger, "error", _error, raising=True)
    monkeypatch.setattr(sp.logger, "critical", lambda *a, **k: None, raising=True)
    monkeypatch.setattr(asyncio, "sleep", _sleep, raising=True)
    return logged


@pytest.mark.asyncio
async def test_a_timeout_reports_the_stage_that_was_running(harness, monkeypatch):
    """The whole point: run main() for one cycle whose tick hangs mid-way."""
    async def _hangs_in_a_known_stage():
        # No asyncio.sleep here: the fixture patches it to end the loop, so
        # awaiting it inside the fake tick would escape before the timeout
        # handler ever ran.
        sp._set_stage("snapshots")
        sp._set_stage("aggregates_refresh")
        raise TimeoutError  # what wait_for raises when it kills the cycle

    monkeypatch.setattr(sp, "tick", _hangs_in_a_known_stage, raising=True)

    with pytest.raises(_StopLoop):
        await sp.main()

    assert harness, "the timeout was never logged"
    msg, args = harness[-1]
    assert "stage=%s" in msg, (
        f"the timeout log does not name the stage: {msg!r}"
    )
    assert "aggregates_refresh" in args, (
        f"the log reported {args!r} rather than the stage that was running; a "
        f"timeout that cannot name the slow job leaves every job below it "
        f"silently skipped"
    )


def test_the_timeout_handler_passes_the_stage_variable():
    """Recording the stage and not logging it is the same silence, with more code.

    The behavioural test above proves the message carries it; this one pins
    that it comes from the live variable rather than a constant that could
    drift, which a log-message assertion alone cannot distinguish.
    """
    import inspect

    src = inspect.getsource(sp.main)
    # Slice from the logger.error call, not from the first mention of
    # "tick.timeout" — that appears earlier in a comment.
    marker = 'logger.error('
    assert marker in src
    call = src[src.index(marker):]
    end = call.index("            )")
    call = call[:end]
    assert "stage=%s" in call, f"no stage in the timeout log: {call!r}"
    assert "_tick_stage," in call, (
        f"the stage placeholder is not fed by _tick_stage: {call!r}"
    )


@pytest.mark.asyncio
async def test_a_clean_cycle_resets_the_stage(harness, monkeypatch):
    """A stale stage would blame the wrong job on the next timeout."""
    async def _finishes():
        sp._set_stage("scorecard_freeze")

    monkeypatch.setattr(sp, "tick", _finishes, raising=True)
    with pytest.raises(_StopLoop):
        await sp.main()
    assert sp._tick_stage == "idle", (
        f"stage stayed {sp._tick_stage!r} after a cycle completed; the next "
        f"timeout would name a job that had already finished"
    )


def test_setting_a_stage_never_raises():
    """It runs on the hot path of every tick and must not be able to break it."""
    for value in ("x", "", "a" * 500):
        sp._set_stage(value)
        assert sp._tick_stage == value
    sp._set_stage("idle")


def test_the_tick_records_stages_throughout_not_just_at_the_top():
    """One marker at the start would only ever blame the first job.

    The failure this exists for is a job in the MIDDLE starving everything
    below it, so the markers have to be spread across the body.
    """
    import inspect
    import re

    src = inspect.getsource(sp.tick)
    markers = re.findall(r'_set_stage\("([^"]+)"\)', src)
    assert len(markers) >= 15, (
        f"only {len(markers)} stage markers in tick(), which runs ~25 jobs — "
        f"a timeout would name a stage far above the one that actually hung"
    )
    assert len(set(markers)) == len(markers), (
        f"duplicate stage labels {[m for m in markers if markers.count(m) > 1]} "
        f"— two jobs sharing a name makes the log ambiguous"
    )
    # Spread, not clustered at the top.
    lines = src.split("\n")
    positions = [i for i, ln in enumerate(lines) if "_set_stage(" in ln]
    assert positions[-1] > len(lines) * 0.6, (
        "every stage marker sits in the first half of tick(); a hang in the "
        "later jobs would still be reported as an early stage"
    )
