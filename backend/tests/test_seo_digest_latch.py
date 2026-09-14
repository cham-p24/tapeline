"""The weekly SEO digest runs once a week - across restarts, machines, and off the tick.

MEASURED IN PRODUCTION, 2026-09-14 (Monday)
-------------------------------------------
The digest ran inline in the tick behind a process-memory token. Every restart
forgets that token, so the first tick after a Monday deploy ran the digest
again, inside the tick, and its link audit outlasted the watchdog:

    18:49:43 ERROR tick.timeout elapsed=240.1s limit=240s consecutive=1
             stage=seo_digest_token

Four minutes without a price pass, on the day the per-minute refresh was being
measured. Had the audit finished, every Monday deploy would also have re-sent
the founder's digest.

Now the claim lives in `job_period_claims` (written before the work, completed
after it), and the digest runs detached. Each test was watched failing against
the mutation named in its docstring.
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import textwrap
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import session_scope
from app.models import JobPeriodClaim
from app.services import job_claims
from app.services.job_claims import ClaimStatus, claim_period, complete_period, release_period
from app.workers import signal_publisher as sp

# NO pytestmark: pytest.ini sets asyncio_mode = auto.

JOB = "test_job"
WEEK = "seo_2026W38"


@pytest.fixture(autouse=True)
def _fresh_process_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts as a freshly booted worker would."""
    monkeypatch.setattr(sp, "_last_seo_digest_token", None)
    monkeypatch.setattr(sp, "_seo_digest_retry_after", None)


@pytest.fixture
def digest(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Stand-in for seo_health.run_weekly_digest: records each send."""
    sends: list[str] = []

    async def _send(_session) -> bool:
        sends.append("sent")
        return True

    monkeypatch.setattr("app.services.seo_health.run_weekly_digest", _send)
    return sends


# =============================================================================
# 1. The claim.
# =============================================================================


async def test_a_period_is_claimed_once_and_then_done() -> None:
    """Mutation: a claim that does not persist (every caller CLAIMED)."""
    assert await claim_period(JOB, WEEK) is ClaimStatus.CLAIMED
    assert await claim_period(JOB, WEEK) is ClaimStatus.BUSY
    await complete_period(JOB, WEEK)
    assert await claim_period(JOB, WEEK) is ClaimStatus.DONE


async def test_two_processes_cannot_both_claim_a_period() -> None:
    """The standby worker can be started by the watchdog while the primary
    lives. Both reaching the Monday stage must still send one digest. The
    primary key is the arbiter: exactly one INSERT wins, and the second row is
    refused by the database itself - which is what holds across two machines,
    where no in-process lock reaches. Mutation: a claim that never persists."""
    results = await asyncio.gather(*(claim_period(JOB, WEEK) for _ in range(4)))
    assert results.count(ClaimStatus.CLAIMED) == 1, results

    # The mechanism itself: the database refuses a second claim row.
    with pytest.raises(IntegrityError):
        async with session_scope() as s:
            s.add(JobPeriodClaim(job=JOB, period=WEEK))


async def test_an_abandoned_claim_is_taken_over_only_once_stale() -> None:
    """A deploy mid-digest leaves an incomplete claim. It must not cost the
    week, but a run still in flight must not be doubled. Mutations: no
    takeover; takeover of a fresh claim."""
    now = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)
    stale = job_claims.STALE_CLAIM_AFTER

    assert await claim_period(JOB, WEEK, now=now - stale + timedelta(minutes=1)) is ClaimStatus.CLAIMED
    assert await claim_period(JOB, WEEK, now=now) is ClaimStatus.BUSY, "a fresh run was taken over"

    later = now + timedelta(minutes=2)
    assert await claim_period(JOB, WEEK, now=later) is ClaimStatus.CLAIMED, "an abandoned run was never retried"
    assert await claim_period(JOB, WEEK, now=later) is ClaimStatus.BUSY, "two takeovers of one claim"


async def test_a_completed_claim_is_never_released() -> None:
    """Releasing finished work would re-send it. Mutation: release without the
    completed_at IS NULL guard."""
    assert await claim_period(JOB, WEEK) is ClaimStatus.CLAIMED
    await complete_period(JOB, WEEK)
    await release_period(JOB, WEEK)
    assert await claim_period(JOB, WEEK) is ClaimStatus.DONE


# =============================================================================
# 2. The digest job.
# =============================================================================


async def test_a_restart_after_the_send_does_not_send_again(digest: list[str]) -> None:
    """The regression, as a sequence: a worker sends the week's digest, the
    process restarts (its memory is gone), and the new process reaches the same
    Monday stage. Mutation: completing nothing, or ignoring DONE."""
    await sp._run_weekly_seo_digest(WEEK, None)
    assert digest == ["sent"]

    # The restart: a new process, with none of the old one's memory.
    sp._last_seo_digest_token = None
    sp._seo_digest_retry_after = None
    await sp._run_weekly_seo_digest(WEEK, None)

    assert digest == ["sent"], "a Monday restart re-sent the founder's digest"
    async with session_scope() as s:
        row = await s.scalar(select(JobPeriodClaim).where(
            JobPeriodClaim.job == sp.SEO_DIGEST_JOB, JobPeriodClaim.period == WEEK,
        ))
    assert row is not None and row.completed_at is not None


async def test_a_caught_failure_releases_the_claim_and_backs_off_an_hour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient Telegram or database error must retry this week, but not
    every minute. Mutations: not releasing the claim; no backoff."""
    async def _boom(_session) -> bool:
        raise RuntimeError("telegram 502")

    monkeypatch.setattr("app.services.seo_health.run_weekly_digest", _boom)
    sp._last_seo_digest_token = WEEK  # what the tick stamps before dispatch

    before = datetime.now(UTC)
    await sp._run_weekly_seo_digest(WEEK, None)

    assert sp._last_seo_digest_token is None, "the token was not rolled back"
    assert sp._seo_digest_retry_after is not None
    assert sp._seo_digest_retry_after >= before + sp.SEO_DIGEST_RETRY_AFTER - timedelta(seconds=5)
    assert await claim_period(sp.SEO_DIGEST_JOB, WEEK) is ClaimStatus.CLAIMED, (
        "the failed run's claim was left behind, so the week can never retry"
    )


async def test_a_run_in_flight_elsewhere_is_not_doubled(digest: list[str]) -> None:
    """The standby or a previous process holds a fresh claim. This process must
    not send, and must ask again later rather than give up the week. Mutation:
    treating BUSY like CLAIMED."""
    assert await claim_period(sp.SEO_DIGEST_JOB, WEEK) is ClaimStatus.CLAIMED
    sp._last_seo_digest_token = WEEK

    await sp._run_weekly_seo_digest(WEEK, None)

    assert digest == []
    assert sp._last_seo_digest_token is None, "BUSY gave up the week in this process"
    assert sp._seo_digest_retry_after is not None


# =============================================================================
# 3. Off the tick.
# =============================================================================


def _tick_code() -> str:
    tree = ast.parse(textwrap.dedent(inspect.getsource(sp.tick)))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module))
            and body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_the_tick_dispatches_the_digest_instead_of_awaiting_it() -> None:
    """Awaited inline, its link audit held every price pass behind it until
    the watchdog killed the tick. Mutation: awaiting it in the tick."""
    code = _tick_code()
    assert "_spawn(_run_weekly_seo_digest(seo_digest_token, _seo_prev), key='seo_digest')" in code
    assert "run_weekly_digest(" not in code.replace("_run_weekly_seo_digest(", "")


def test_the_tick_respects_the_backoff() -> None:
    """Mutation: dispatching again every minute after a failure."""
    assert "_seo_digest_retry_after is None or started >= _seo_digest_retry_after" in _tick_code()
