"""The snapshot pass must fit inside the tick's 60-second budget.

`fetch_snapshots` batches 250 symbols per `/v3/snapshot` request and used to
issue those batches one after another. That was invisible while the universe
was 2,750 symbols — 11 batches, about 7 seconds. #763 widened it to everything
we score: 7,667 symbols, 31 batches. Measured on the worker, each request takes
~0.67s, so the pass became **21.3 seconds** of a tick the watchdog kills at 60.

Combined with the rest of the tick that was enough to wedge it. Production
showed `tick.timeout consecutive=7` with every single outbound request in the
window going to `/v3/snapshot`, and every job below the snapshot stopped
running — including the sheet refresh, which is why #766's parser fix deployed
and then never executed.

The batches are independent reads of one endpoint, so that wall clock was pure
waiting. What matters in the tests below is not that concurrency is "faster" in
the abstract, but that three properties survive it:

  - every symbol is still fetched, in batches of the documented size
  - a failing batch still aborts the WHOLE pass, so the caller publishes
    nothing rather than a partial universe that looks like a normal tick
  - the fan-out stays bounded, so widening the universe again cannot turn into
    a thundering herd against the vendor
"""
from __future__ import annotations

import asyncio
import time

import pytest

from app.services import polygon_feed as pf


@pytest.fixture
def vendor(monkeypatch):
    """A stand-in /v3/snapshot that costs wall clock and records concurrency."""
    state = {"calls": [], "in_flight": 0, "peak": 0, "spans": []}

    async def _request(_client, path, **kw):
        assert path == "/v3/snapshot"
        syms = kw["params"]["ticker.any_of"].split(",")
        state["calls"].append(syms)
        started = time.monotonic()
        state["in_flight"] += 1
        state["peak"] = max(state["peak"], state["in_flight"])
        try:
            await asyncio.sleep(0.05)
        finally:
            state["in_flight"] -= 1
            state["spans"].append((started, time.monotonic()))
        return {"results": [{"ticker": s} for s in syms]}

    monkeypatch.setattr(pf, "_request", _request, raising=True)
    monkeypatch.setattr(pf, "_api_key", lambda: "test-key", raising=True)
    monkeypatch.setattr(
        pf, "_to_scanner_row", lambda t: {"symbol": t["ticker"]}, raising=True
    )
    return state


def _symbols(n: int) -> list[str]:
    return [f"S{i:05d}" for i in range(n)]


@pytest.mark.asyncio
async def test_every_symbol_is_still_fetched(vendor):
    """Concurrency must not drop a batch."""
    syms = _symbols(1000)
    await pf.fetch_snapshots(symbols=syms)
    fetched = [s for call in vendor["calls"] for s in call]
    assert sorted(fetched) == sorted(syms), (
        f"{len(syms) - len(set(fetched))} symbols were never requested"
    )


@pytest.mark.asyncio
async def test_batches_use_the_documented_size(vendor):
    syms = _symbols(1000)
    await pf.fetch_snapshots(symbols=syms)
    assert len(vendor["calls"]) == 4, "1000 symbols is 4 batches of 250"
    assert all(len(c) <= pf.SNAPSHOT_BATCH_SIZE for c in vendor["calls"])


@pytest.mark.asyncio
async def test_the_pass_is_not_serialised(vendor):
    """The regression. 31 sequential 0.67s requests is 21s of a 60s tick.

    Asserted as OVERLAP, not as elapsed time. The first version of this test
    compared the request phase against a wall-clock threshold and failed on a
    loaded CI runner — 0.47s against a 0.36s bound — because scheduling noise
    on a shared machine dwarfs the 0.05s stand-in sleeps. It was measuring the
    runner, not the code.

    Whether requests overlap is the actual property, and it is exact: if any
    request begins before another ends, the pass is concurrent, on any machine
    at any speed.
    """
    batches = 12
    await pf.fetch_snapshots(symbols=_symbols(250 * batches))

    assert len(vendor["spans"]) == batches
    ordered = sorted(vendor["spans"])
    overlaps = sum(
        1
        for (start_a, end_a), (start_b, _) in zip(ordered, ordered[1:], strict=False)
        if start_b < end_a
    )
    assert overlaps > 0, (
        f"none of the {batches} requests overlapped another — they are still "
        f"going out one at a time, which is what pushed the snapshot pass to "
        f"21s and wedged the tick"
    )
    assert vendor["peak"] > 1, "no two requests were ever in flight together"


@pytest.mark.asyncio
async def test_the_fan_out_stays_bounded(vendor):
    """Unbounded gather over a widening universe is a thundering herd.

    The universe grew from 2,750 to 7,667 in a day. The next widening must not
    turn into 40 simultaneous requests at the vendor.
    """
    syms = _symbols(250 * 20)
    await pf.fetch_snapshots(symbols=syms)
    assert vendor["peak"] <= pf.SNAPSHOT_CONCURRENCY, (
        f"{vendor['peak']} requests were in flight at once, above the "
        f"{pf.SNAPSHOT_CONCURRENCY} cap"
    )


@pytest.mark.asyncio
async def test_a_failing_batch_publishes_nothing(monkeypatch):
    """The property that must survive the rewrite.

    A vendor outage must not be laundered into a partial universe. Half a
    result set looks exactly like a normal tick while silently leaving the
    missing names on yesterday's prices — worse than serving nothing, because
    nothing is visible and self-heals.
    """
    calls = {"n": 0}

    async def _flaky(_client, _path, **kw):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("vendor 503")
        syms = kw["params"]["ticker.any_of"].split(",")
        return {"results": [{"ticker": s} for s in syms]}

    monkeypatch.setattr(pf, "_request", _flaky, raising=True)
    monkeypatch.setattr(pf, "_api_key", lambda: "test-key", raising=True)
    monkeypatch.setattr(pf, "_is_production", lambda: True, raising=True)
    monkeypatch.setattr(
        pf, "_to_scanner_row", lambda t: {"symbol": t["ticker"]}, raising=True
    )

    rows = await pf.fetch_snapshots(symbols=_symbols(250 * 6))
    assert rows == [], (
        f"one failed batch still returned {len(rows)} rows — a partial "
        f"universe was published as if the tick had succeeded"
    )


@pytest.mark.asyncio
async def test_a_single_batch_still_works(vendor):
    """The small-universe path (dev, tests, a cold fallback) is unchanged."""
    await pf.fetch_snapshots(symbols=_symbols(10))
    assert len(vendor["calls"]) == 1
    assert vendor["peak"] == 1


def test_the_concurrency_cap_is_a_real_bound():
    """A cap of 1 is the serial behaviour this exists to remove; a huge one is
    no cap at all."""
    assert 2 <= pf.SNAPSHOT_CONCURRENCY <= 16, (
        f"SNAPSHOT_CONCURRENCY={pf.SNAPSHOT_CONCURRENCY} is not a meaningful "
        f"bound between 'still serial' and 'thundering herd'"
    )
