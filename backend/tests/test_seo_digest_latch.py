"""The weekly SEO digest: sent once a week, from outside the worker, never
holding a database session across its crawl.

WHAT PRODUCTION SHOWED
----------------------
* 2026-09-14 18:45Z. The digest ran inline in the worker tick behind a
  process-memory token. Every deploy forgot the token, and the first Monday
  tick after it ran the digest again until the watchdog killed the tick:
  `tick.timeout elapsed=240.1s stage=seo_digest_token`, four minutes with no
  price pass.
* 2026-09-07 to 09-12. The daily link audit, the same crawl run from Actions,
  failed on every run with "received 2 results from command 'COMMIT'". It read
  the owner row, crawled for 6 to 14 minutes with that transaction open, and
  production Postgres (idle_in_transaction_session_timeout = 5min) killed the
  connection underneath it. The digest was built the same way.

Now the digest runs daily from .github/workflows/seo-weekly-digest.yml, claims
the ISO week in job_period_claims before it crawls, and opens no session while
the crawl runs. Each test was watched failing against the mutation named in its
docstring.
"""
from __future__ import annotations

import asyncio
import logging
import pathlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db import session_scope
from app.models import JobPeriodClaim
from app.services import job_claims, seo_health
from app.services.job_claims import ClaimStatus, claim_period, complete_period, release_period
from app.services.seo_health import DigestOutcome

# NO pytestmark: pytest.ini sets asyncio_mode = auto.

JOB = "test_job"
WEEK = "2026W39"
STALE = job_claims.STALE_CLAIM_AFTER

#: Monday of ISO week 2026-W39, the first week the claim governs.
MONDAY_10 = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)

_REPO = pathlib.Path(__file__).resolve().parents[2]


# =============================================================================
# 1. The claim.
# =============================================================================


async def test_a_period_is_claimed_once_and_then_done() -> None:
    """Mutation: a claim that does not persist (every caller CLAIMED)."""
    first = await claim_period(JOB, WEEK)
    assert first.status is ClaimStatus.CLAIMED
    assert (await claim_period(JOB, WEEK)).status is ClaimStatus.BUSY
    assert await complete_period(first)
    assert (await claim_period(JOB, WEEK)).status is ClaimStatus.DONE


async def test_two_runs_cannot_both_claim_a_period() -> None:
    """A manual re-run can overlap a scheduled one. The primary key is the
    arbiter: exactly one INSERT wins, and the database refuses the second row.
    Mutation: a claim that never persists."""
    results = await asyncio.gather(*(claim_period(JOB, WEEK) for _ in range(4)))
    assert [r.status for r in results].count(ClaimStatus.CLAIMED) == 1, results

    with pytest.raises(IntegrityError):
        async with session_scope() as s:
            s.add(JobPeriodClaim(job=JOB, period=WEEK, owner="someone-else"))


async def test_an_abandoned_claim_is_taken_over_only_once_stale() -> None:
    """A deploy mid-crawl leaves an incomplete claim. It must not cost the week,
    but a run still in flight must not be doubled. Mutations: no takeover;
    takeover of a fresh claim."""
    t0 = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)

    assert (await claim_period(JOB, WEEK, now=t0)).status is ClaimStatus.CLAIMED
    for fresh in (timedelta(minutes=1), STALE - timedelta(minutes=1)):
        assert (await claim_period(JOB, WEEK, now=t0 + fresh)).status is ClaimStatus.BUSY, (
            f"a run claimed {fresh} ago was taken over"
        )

    later = t0 + STALE + timedelta(minutes=1)
    assert (await claim_period(JOB, WEEK, now=later)).status is ClaimStatus.CLAIMED, (
        "an abandoned run was never retried"
    )
    assert (await claim_period(JOB, WEEK, now=later)).status is ClaimStatus.BUSY, "two takeovers of one claim"


async def test_a_completed_claim_is_never_taken_over() -> None:
    """A run long after the send finds the week done, however old the claim.
    Mutation: the takeover UPDATE without `completed_at IS NULL`, which would
    re-send any week whose digest went out more than STALE_CLAIM_AFTER ago."""
    sent_at = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
    claim = await claim_period(JOB, WEEK, now=sent_at)
    assert await complete_period(claim, now=sent_at)

    much_later = sent_at + STALE + timedelta(minutes=31)
    assert (await claim_period(JOB, WEEK, now=much_later)).status is ClaimStatus.DONE


async def test_a_completed_claim_is_never_released() -> None:
    """Releasing finished work would re-send it. Mutation: release without the
    completed_at IS NULL guard."""
    claim = await claim_period(JOB, WEEK)
    assert await complete_period(claim)
    assert not await release_period(claim)
    assert (await claim_period(JOB, WEEK)).status is ClaimStatus.DONE


async def test_a_run_presumed_dead_cannot_touch_the_claim_that_replaced_it() -> None:
    """Run A stalls past the stale window and B takes the week over. A then
    fails, or finishes. Neither may reach B's claim: releasing it would let a
    third run claim the week while B is still sending. Mutations: release or
    complete without the owner filter."""
    t0 = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
    a = await claim_period(JOB, WEEK, now=t0)
    b = await claim_period(JOB, WEEK, now=t0 + STALE + timedelta(minutes=1))
    assert a.status is b.status is ClaimStatus.CLAIMED
    assert a.owner != b.owner

    assert not await release_period(a), "the stale run deleted the claim that replaced it"
    c = await claim_period(JOB, WEEK, now=t0 + STALE + timedelta(minutes=2))
    assert c.status is ClaimStatus.BUSY, "a third run claimed a week that is still in flight"

    assert not await complete_period(a), "the stale run completed someone else's claim"
    assert await complete_period(b)
    assert (await claim_period(JOB, WEEK)).status is ClaimStatus.DONE


async def test_only_a_claim_this_caller_won_can_be_completed_or_released() -> None:
    """Mutation: _owned_by accepting a claim with no owner, which would match
    every incomplete row for the period."""
    await claim_period(JOB, WEEK)
    busy = await claim_period(JOB, WEEK)
    assert busy.status is ClaimStatus.BUSY
    with pytest.raises(ValueError):
        await release_period(busy)
    with pytest.raises(ValueError):
        await complete_period(busy)


# =============================================================================
# 2. The digest job.
# =============================================================================


class _Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class _Digest:
    """Stand-ins for the network: the crawl, Telegram, and the owner lookup."""

    def __init__(self, clock: _Clock) -> None:
        self.clock = clock
        self.crawls = 0
        self.sends: list[str] = []
        self.send_result: bool | Exception = True
        self.crawl_error: Exception | None = None
        self.crawl_minutes = 0
        self.open_scopes = 0
        self.scopes_open_during_crawl: list[int] = []
        self.chat_id: str | None = "founder-chat"

    async def crawl(self) -> dict:
        self.crawls += 1
        self.scopes_open_during_crawl.append(self.open_scopes)
        if self.crawl_error is not None:
            raise self.crawl_error
        self.clock.now += timedelta(minutes=self.crawl_minutes)
        return {"checked": 3, "healthy": 2, "broken": [{"url": "https://tapeline.io/x", "status": 404}]}

    async def send(self, chat_id: str, text_: str) -> bool:
        if isinstance(self.send_result, Exception):
            raise self.send_result
        self.sends.append(text_)
        return self.send_result

    async def owner_chat_id(self, session) -> str | None:
        # A real query, so the lookup's session holds a transaction exactly as
        # the production lookup does.
        await session.execute(text("SELECT 1"))
        return self.chat_id


@pytest.fixture
def clock() -> _Clock:
    return _Clock(MONDAY_10)


@pytest.fixture
def digest(monkeypatch: pytest.MonkeyPatch, clock: _Clock) -> _Digest:
    d = _Digest(clock)
    real_scope = seo_health.session_scope

    @asynccontextmanager
    async def _counted_scope() -> AsyncIterator:
        d.open_scopes += 1
        try:
            async with real_scope() as s:
                yield s
        finally:
            d.open_scopes -= 1

    monkeypatch.setattr(seo_health, "session_scope", _counted_scope)
    monkeypatch.setattr(seo_health, "run_stale_link_audit", d.crawl)
    monkeypatch.setattr(seo_health, "send_message", d.send)
    monkeypatch.setattr(seo_health, "_owner_chat_id", d.owner_chat_id)
    monkeypatch.setattr(seo_health.settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(seo_health, "COMPLETE_RETRY_SECONDS", 0.0)
    return d


async def _run(clock: _Clock) -> DigestOutcome:
    return await asyncio.wait_for(seo_health.run_weekly_digest(clock=clock), timeout=10)


async def _row() -> JobPeriodClaim | None:
    async with session_scope() as s:
        return await s.scalar(select(JobPeriodClaim).where(
            JobPeriodClaim.job == seo_health.DIGEST_JOB, JobPeriodClaim.period == WEEK,
        ))


async def test_the_digest_is_sent_once_a_week(digest: _Digest, clock: _Clock) -> None:
    """The regression, as a sequence: the week's digest goes out, then the next
    day's run, or a manual re-run, finds the week done. It must not crawl the
    site again either. Mutations: ignoring DONE; crawling before the claim."""
    assert await _run(clock) is DigestOutcome.SENT
    assert (digest.crawls, len(digest.sends)) == (1, 1)
    row = await _row()
    assert row is not None and row.completed_at is not None

    clock.now += timedelta(days=1)
    assert await _run(clock) is DigestOutcome.ALREADY_SENT
    assert (digest.crawls, len(digest.sends)) == (1, 1), "a later run crawled or sent again"


async def test_a_run_long_after_the_send_does_not_send_again(digest: _Digest, clock: _Clock) -> None:
    """Mutation: the takeover UPDATE without `completed_at IS NULL`."""
    assert await _run(clock) is DigestOutcome.SENT
    clock.now += STALE + timedelta(minutes=31)
    assert await _run(clock) is DigestOutcome.ALREADY_SENT
    assert len(digest.sends) == 1


async def test_nothing_is_sent_before_monday_nine(digest: _Digest, clock: _Clock) -> None:
    """Mutation: the 09:00 gate dropped (hour >= 0)."""
    clock.now = datetime(2026, 9, 21, 8, 59, tzinfo=UTC)
    assert await _run(clock) is DigestOutcome.NOT_YET
    assert (digest.crawls, digest.sends, await _row()) == (0, [], None)

    clock.now = datetime(2026, 9, 21, 9, 0, tzinfo=UTC)
    assert await _run(clock) is DigestOutcome.SENT


@pytest.mark.parametrize("when", [
    datetime(2026, 9, 22, 3, 0, tzinfo=UTC),    # Tuesday
    datetime(2026, 9, 27, 23, 30, tzinfo=UTC),  # Sunday, still ISO week 39
])
async def test_a_later_day_of_the_week_sends_a_missed_digest(
    digest: _Digest, clock: _Clock, when: datetime,
) -> None:
    """A Monday run lost to a deploy, or started too late by Actions, must not
    cost the week. Mutation: gating on Monday only."""
    clock.now = when
    assert await _run(clock) is DigestOutcome.SENT


async def test_a_week_before_the_first_claimed_week_is_never_sent(digest: _Digest, clock: _Clock) -> None:
    """The worker may already have sent 2026-W38 from memory, leaving no row.
    Mutation: dropping the FIRST_CLAIMED_WEEK check."""
    clock.now = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
    assert await _run(clock) is DigestOutcome.NOT_YET
    assert digest.crawls == 0


async def test_no_session_is_open_while_the_site_is_crawled(digest: _Digest, clock: _Clock) -> None:
    """MUST-FIX 1. Postgres kills a transaction left idle for 5 minutes, and the
    crawl takes longer. Mutation: crawling inside the session that renders."""
    assert await _run(clock) is DigestOutcome.SENT
    assert digest.scopes_open_during_crawl == [0], (
        f"{digest.scopes_open_during_crawl[0]} database session(s) were open during the crawl"
    )


async def test_a_telegram_refusal_releases_the_week(digest: _Digest, clock: _Clock) -> None:
    """send_message returns False on a Telegram non-200 rather than raising.
    That is nothing sent, so the next run must retry. Mutation: treating a
    False send as done."""
    digest.send_result = False
    assert await _run(clock) is DigestOutcome.FAILED
    assert await _row() is None, "a refused send marked the week done"

    digest.send_result = True
    clock.now += timedelta(days=1)
    assert await _run(clock) is DigestOutcome.SENT


@pytest.mark.parametrize("where", ["crawl", "send"])
async def test_an_error_before_the_send_completes_releases_the_week(
    digest: _Digest, clock: _Clock, where: str,
) -> None:
    """Mutation: no release in the except path."""
    if where == "crawl":
        digest.crawl_error = RuntimeError("sitemap unreachable")
    else:
        digest.send_result = RuntimeError("telegram connect timeout")
    assert await _run(clock) is DigestOutcome.FAILED
    assert await _row() is None
    assert digest.sends == []


async def test_a_sent_digest_is_never_released_when_recording_fails(
    digest: _Digest, clock: _Clock, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The database fails after Telegram accepted the digest. Releasing the week
    would send it again on the next run. Mutation: releasing after a failed
    complete."""
    async def _broken_complete(claim, *, now=None) -> bool:
        raise RuntimeError("connection dropped")

    monkeypatch.setattr(seo_health, "complete_period", _broken_complete)
    assert await _run(clock) is DigestOutcome.SENT_UNRECORDED
    row = await _row()
    assert row is not None and row.completed_at is None, "the sent week was released"

    assert await _run(clock) is DigestOutcome.IN_FLIGHT
    assert len(digest.sends) == 1


async def test_recording_a_sent_digest_is_retried(
    digest: _Digest, clock: _Clock, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: a single attempt at complete_period."""
    real = seo_health.complete_period
    calls = 0

    async def _flaky_complete(claim, *, now=None) -> bool:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("connection dropped")
        return await real(claim, now=now)

    monkeypatch.setattr(seo_health, "complete_period", _flaky_complete)
    assert await _run(clock) is DigestOutcome.SENT
    row = await _row()
    assert row is not None and row.completed_at is not None


async def test_a_run_in_flight_elsewhere_is_not_doubled(digest: _Digest, clock: _Clock) -> None:
    """A scheduled run and a manual re-run overlap. Mutations: treating BUSY
    like CLAIMED; a stale window so short that a live run counts as dead."""
    elsewhere = clock.now - timedelta(minutes=5)
    assert (await claim_period(seo_health.DIGEST_JOB, WEEK, now=elsewhere)).status is ClaimStatus.CLAIMED
    assert await _run(clock) is DigestOutcome.IN_FLIGHT
    assert (digest.crawls, digest.sends) == (0, [])


async def test_a_run_that_overruns_its_budget_sends_nothing(digest: _Digest, clock: _Clock) -> None:
    """Past the budget, another run may take the week over and send. So a slow
    run must not send. Mutation: no deadline check before the send."""
    digest.crawl_minutes = int(seo_health.DIGEST_BUDGET.total_seconds() // 60) + 1
    assert await _run(clock) is DigestOutcome.FAILED
    assert digest.sends == []
    assert await _row() is None


async def test_a_hung_crawl_is_cut_off_at_the_budget(
    digest: _Digest, clock: _Clock, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation: awaiting the crawl without a timeout."""
    async def _hang() -> dict:
        await asyncio.sleep(60)
        return {}

    monkeypatch.setattr(seo_health, "run_stale_link_audit", _hang)
    monkeypatch.setattr(seo_health, "DIGEST_BUDGET", timedelta(milliseconds=200))
    assert await _run(clock) is DigestOutcome.FAILED
    assert digest.sends == []


def test_the_budget_ends_before_a_takeover_is_possible() -> None:
    """Mutation: a budget at or past the stale window."""
    assert STALE - timedelta(minutes=10) >= seo_health.DIGEST_BUDGET


@pytest.mark.parametrize("missing", ["token", "chat_id"])
async def test_no_recipient_claims_and_crawls_nothing(
    digest: _Digest, clock: _Clock, monkeypatch: pytest.MonkeyPatch, missing: str,
) -> None:
    """Mutations: checking the recipient after the claim or the crawl."""
    if missing == "token":
        monkeypatch.setattr(seo_health.settings, "telegram_bot_token", "")
    else:
        digest.chat_id = None
    assert await _run(clock) is DigestOutcome.NO_RECIPIENT
    assert (digest.crawls, await _row()) == (0, None)


# =============================================================================
# 3. Where it runs.
# =============================================================================


@pytest.mark.parametrize(("outcome", "code"), [
    (DigestOutcome.SENT, 0),
    (DigestOutcome.ALREADY_SENT, 0),
    (DigestOutcome.IN_FLIGHT, 0),
    (DigestOutcome.NOT_YET, 0),
    (DigestOutcome.NO_RECIPIENT, 0),
    (DigestOutcome.FAILED, 1),
    (DigestOutcome.SENT_UNRECORDED, 1),
])
async def test_the_script_turns_the_run_red_only_when_it_needs_a_look(
    monkeypatch: pytest.MonkeyPatch, outcome: DigestOutcome, code: int,
) -> None:
    """Mutation: a failed run exiting 0, which leaves the workflow green."""
    from app.scripts import seo_weekly_digest as script

    async def _fixed() -> DigestOutcome:
        return outcome

    monkeypatch.setattr(script, "run_weekly_digest", _fixed)
    assert await script.main() == code


def test_the_script_keeps_the_bot_token_out_of_the_public_log() -> None:
    """The Telegram URL carries the bot token and httpx logs request URLs at
    INFO, into Actions logs on a public repository. Mutation: configuring INFO
    logging without quieting httpx."""
    from app.scripts import seo_weekly_digest as script

    root = logging.getLogger()
    saved = (root.level, list(root.handlers))
    names = ("httpx", "httpcore")
    saved_levels = {n: logging.getLogger(n).level for n in names}
    try:
        script.configure_logging()
        for name in names:
            assert logging.getLogger(name).level >= logging.WARNING, f"{name} logs at INFO"
    finally:
        root.setLevel(saved[0])
        root.handlers[:] = saved[1]
        for n, level in saved_levels.items():
            logging.getLogger(n).setLevel(level)


def test_the_workflow_runs_it_daily_and_never_beside_the_other_crawl() -> None:
    """Mutations: a Monday-only schedule (a lost Monday run loses the week); a
    concurrency group the daily audit does not share; a job timeout inside the
    digest's own budget."""
    import re

    wf = (_REPO / ".github" / "workflows" / "seo-weekly-digest.yml").read_text(encoding="utf-8")
    audit = (_REPO / ".github" / "workflows" / "stale-link-audit.yml").read_text(encoding="utf-8")

    assert "python -m app.scripts.seo_weekly_digest" in wf
    assert re.search(r'cron:\s*"\d+ \d+ \* \* \*"', wf), "the digest is not scheduled daily"
    assert re.search(r"group:\s*sitemap-crawl\b", wf)
    assert re.search(r"group:\s*sitemap-crawl\b", audit), "the daily audit can crawl beside the digest"
    minutes = int(re.search(r"timeout-minutes:\s*(\d+)", wf).group(1))  # type: ignore[union-attr]
    assert minutes > seo_health.DIGEST_BUDGET.total_seconds() / 60


# =============================================================================
# 4. The daily audit shares the crawl, and had the same session bug.
# =============================================================================


async def test_the_daily_audit_holds_no_transaction_across_its_crawl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every stale-link-audit run from 2026-09-07 to 09-12 failed at its final
    COMMIT, after Postgres killed the transaction the owner lookup had left
    open across the crawl. Mutation: removing the commit before the crawl."""
    held: list[bool] = []

    async def _owner(session) -> str:
        await session.execute(text("SELECT 1"))
        return "founder-chat"

    async with session_scope() as session:
        async def _crawl() -> dict:
            held.append(session.in_transaction())
            return {"checked": 1, "healthy": 1, "broken": []}

        monkeypatch.setattr(seo_health, "_owner_chat_id", _owner)
        monkeypatch.setattr(seo_health, "run_stale_link_audit", _crawl)
        assert await seo_health.run_stale_audit_alert(session) is False

    assert held == [False], "the audit's session was mid-transaction for the whole crawl"
