"""The worker gets a whole core, and the watchdog never starts a standby.

WHAT WAS MEASURED, 2026-09-11
-----------------------------
Scores went stale again two days after the rollback fix (#798). Postgres was
idle while the tick sat in `score_upsert`: across three samples there was one
active session and no UPDATE, and no lock waits. The time was going somewhere
inside the worker process. Inside both worker VMs:

    primary 2879770f913628   busy 7%  idle 3%  STEAL 90%   127MB free of 459
    standby 080e971dad0298   busy 9%  idle 0%  STEAL 91%    72MB free of 459

Both were `shared-cpu-1x`. Once its burst balance is spent, Fly gives that
preset 5ms of every 80ms (6.25% of a core), and the kernel reports what it
withholds as steal. The worker is one single-threaded asyncio process doing
12,000 symbols plus a concurrency-8 aggregates pass, so it needs about one full
core, sustained. So every tick hit the 240s ceiling, the heartbeat went stale,
and the cloud watchdog restarted both machines and alerted the founder. Each
restart wiped every in-process cache, and the throttled VM took about an hour
to get back to writing.

THE SECOND BUG, WHICH MADE IT WORSE
-----------------------------------
The "standby" was running. Fly keeps a standby stopped until the machine it
covers loses its host. But the watchdog restarted every machine it found, and
restarting a stopped machine starts it. So the standby became a second full
worker, doubling vendor calls (Finnhub was returning 429s) and writes.

Identifying a standby is the part that is easy to get wrong. In
`flyctl machines list --json` the `config.standbys` field sits ON THE STANDBY
and names the machine it covers. The obvious filter, "exclude any id another
machine lists as a standby", would have excluded the covered machine and still
restarted the standby. In production the covered machine did not even exist:
the standby was covering 2867642a1e9668, which is gone. The fixture below is
that exact shape.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FLY_TOML = ROOT / "fly.toml"
WATCHDOG = ROOT / ".github" / "workflows" / "uptime-monitor.yml"

PRIMARY = "2879770f913628"
STANDBY = "080e971dad0298"
API = "2862092fe7e458"

#: What `flyctl machines list -a tapeline-backend --json` returned on
#: 2026-09-11, cut down to the fields the watchdog's filters read.
MACHINES = [
    {
        "id": PRIMARY,
        "state": "started",
        "config": {"metadata": {"fly_process_group": "worker"}, "standbys": None},
    },
    {
        "id": STANDBY,
        "state": "started",
        "config": {
            "metadata": {"fly_process_group": "worker"},
            "standbys": ["2867642a1e9668"],
        },
    },
    {
        "id": API,
        "state": "started",
        "config": {"metadata": {"fly_process_group": "api"}},
    },
]

#: The two filters as they were before this change. Kept on purpose as the
#: known-bad baseline: the test below asserts they DO select the standby, which
#: proves this fixture actually exercises the standby branch. A fixture that
#: never reaches the branch under test is how this repo shipped a guard that
#: passed while the bug was live.
PRE_FIX_FILTERS = [
    ".[].id",
    '.[] | select((.config.metadata.fly_process_group // .process_group // "") == "worker") | .id',
]

_NEEDS_JQ = pytest.mark.skipif(
    shutil.which("jq") is None,
    reason="jq is not installed here; CI's ubuntu-latest image ships it",
)


def _mb(value: object) -> int:
    m = re.fullmatch(r"\s*(\d+)\s*(mb|gb)?\s*", str(value).lower())
    assert m, f"unparseable memory value: {value!r}"
    return int(m.group(1)) * (1024 if m.group(2) == "gb" else 1)


def _worker_vm() -> dict:
    """The [[vm]] block for the worker process, parsed as TOML.

    Parsed rather than grepped: fly.toml's own comment above that block says
    "shared-cpu-1x:512mb" and "performance-1x:2gb", so a text search could pass
    or fail on the prose either way.
    """
    cfg = tomllib.loads(FLY_TOML.read_text(encoding="utf-8"))
    vms = [vm for vm in cfg.get("vm", []) if vm.get("processes") == ["worker"]]
    assert len(vms) == 1, f"expected exactly one [[vm]] for the worker, found {len(vms)}"
    return vms[0]


class TestTheWorkerGetsAWholeCore:
    def test_the_worker_is_not_on_a_throttled_shared_cpu(self):
        vm = _worker_vm()
        assert vm.get("cpu_kind") == "performance", (
            f"worker cpu_kind is {vm.get('cpu_kind')!r}. A shared vCPU is "
            f"throttled to 6.25% of a core once its burst balance runs out, "
            f"and at 12,000 symbols that measured 90% steal and a tick that "
            f"could not finish"
        )
        assert int(vm.get("cpus", 0)) >= 1

    def test_the_worker_has_memory_headroom(self):
        vm = _worker_vm()
        assert _mb(vm["memory"]) >= 2048, (
            f"worker memory {vm['memory']!r}: at 512mb the VM had 72-127MB "
            f"available and no swap"
        )


def _script_without_comments() -> str:
    """The workflow file with every `#` comment line removed.

    The comments this change added quote the old behaviour and name the
    standby field, so leaving them in could satisfy an assertion about the code.
    """
    lines = WATCHDOG.read_text(encoding="utf-8").splitlines()
    return "\n".join(ln for ln in lines if not ln.lstrip().startswith("#"))


def _machine_list_filters() -> list[str]:
    """Every jq filter applied to `flyctl machines list` output in the watchdog.

    These are the only places the watchdog chooses which machines to restart.
    """
    found = re.findall(
        r"flyctl machines list.*?jq -r '([^']*)'", _script_without_comments(), flags=re.S,
    )
    assert len(found) >= 2, (
        f"expected the recover() filter and the worker-restart filter, found "
        f"{len(found)}. Re-point this test if the watchdog was restructured"
    )
    return found


def _jq(expr: str) -> list[str]:
    out = subprocess.run(
        ["jq", "-r", expr], input=json.dumps(MACHINES),
        capture_output=True, text=True, check=True,
    )
    return out.stdout.split()


class TestTheWatchdogNeverStartsAStandby:
    def test_every_machine_selection_excludes_standbys(self):
        for expr in _machine_list_filters():
            assert ".config.standbys" in expr, (
                f"this filter chooses machines to restart and does not exclude "
                f"standbys, so restarting would START the stopped standby: {expr}"
            )

    @_NEEDS_JQ
    def test_the_filters_skip_the_real_standby_and_keep_the_real_worker(self):
        for expr in _machine_list_filters():
            chosen = _jq(expr)
            assert STANDBY not in chosen, f"{expr!r} still selects the standby"
            assert PRIMARY in chosen, (
                f"{expr!r} no longer selects the real worker, so a stale tick "
                f"would go unrecovered"
            )

    @_NEEDS_JQ
    def test_the_fixture_is_one_the_old_filters_got_wrong(self):
        """Proves the fixture reaches the branch: the pre-fix filters select
        the standby on exactly this input."""
        for expr in PRE_FIX_FILTERS:
            assert STANDBY in _jq(expr), (
                f"the fixture no longer contains a standby that {expr!r} would "
                f"restart, so the test above proves nothing"
            )
