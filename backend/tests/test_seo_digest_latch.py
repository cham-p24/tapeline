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

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db import session_scope
from app.models import JobPeriodClaim
from app.services import job_claims, seo_health
from app.services.job_claims import ClaimStatus, claim_period, complete_period, release_period
from app.services.seo_health import DigestOutcome
from app.services.telegram import SendStatus

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
        self.send_attempts = 0
        self.send_result: SendStatus | Exception = SendStatus.DELIVERED
        self.crawl_error: Exception | None = None
        self.crawl_result: dict = {
            "checked": 3, "healthy": 2, "broken": [{"url": "https://tapeline.io/x", "status": 404}],
        }
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
        return self.crawl_result

    async def send(self, chat_id: str, text_: str) -> SendStatus:
        self.send_attempts += 1
        if isinstance(self.send_result, Exception):
            raise self.send_result
        if self.send_result is SendStatus.DELIVERED:
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
    monkeypatch.setattr(seo_health, "send_message_status", d.send)
    monkeypatch.setattr(seo_health, "_owner_chat_id", d.owner_chat_id)
    monkeypatch.setattr(seo_health.settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(seo_health, "COMPLETE_RETRY_SECONDS", 0.0)
    return d


async def _run(clock: _Clock) -> DigestOutcome:
    return await asyncio.wait_for(seo_health.run_weekly_digest(clock=clock), timeout=10)


async def _row(period: str = WEEK) -> JobPeriodClaim | None:
    async with session_scope() as s:
        return await s.scalar(select(JobPeriodClaim).where(
            JobPeriodClaim.job == seo_health.DIGEST_JOB, JobPeriodClaim.period == period,
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


@pytest.mark.parametrize(("when", "period"), [
    (datetime(2026, 12, 28, 10, 0, tzinfo=UTC), "2026W53"),  # Monday; 2026 has 53 ISO weeks
    (datetime(2027, 1, 1, 10, 0, tzinfo=UTC), "2026W53"),    # Friday: calendar 2027, ISO 2026
    (datetime(2027, 1, 4, 10, 0, tzinfo=UTC), "2027W01"),    # Monday: week 1 < 39, but 2027 > 2026
    (datetime(2027, 12, 27, 10, 0, tzinfo=UTC), "2027W52"),  # calendar and ISO year agree
    (datetime(2029, 12, 31, 10, 0, tzinfo=UTC), "2030W01"),  # Monday: calendar 2029, ISO 2030
])
async def test_the_week_is_the_iso_week_across_a_year_boundary(
    digest: _Digest, clock: _Clock, when: datetime, period: str,
) -> None:
    """Mutations: the calendar year in the period key (2027-01-01 would become
    2027W53, a second digest for ISO week 2026-W53); a first-week gate on the
    week number alone (2027-W01 to W38 would never send); the header week read
    from the wall clock instead of the claimed period."""
    clock.now = when
    assert await _run(clock) is DigestOutcome.SENT
    assert await _row(period) is not None, f"not recorded under {period}"
    year, week = period.split("W")
    assert f"week {year}-W{week}" in digest.sends[0], digest.sends[0].splitlines()[0]


async def test_one_iso_week_spanning_new_year_is_sent_once(digest: _Digest, clock: _Clock) -> None:
    """Mutation: the calendar year in the period key."""
    clock.now = datetime(2026, 12, 28, 10, 0, tzinfo=UTC)
    assert await _run(clock) is DigestOutcome.SENT
    clock.now = datetime(2027, 1, 2, 10, 0, tzinfo=UTC)
    assert await _run(clock) is DigestOutcome.ALREADY_SENT
    assert len(digest.sends) == 1


async def test_the_header_names_the_claimed_week_not_the_render_time(
    digest: _Digest, clock: _Clock,
) -> None:
    """A run claimed late on Sunday of W39 that renders after midnight UTC must
    still say W39, the week it is recorded under. Mutation: the header week
    taken from the clock at render time."""
    clock.now = datetime(2026, 9, 27, 23, 50, tzinfo=UTC)
    digest.crawl_minutes = 20
    assert await _run(clock) is DigestOutcome.SENT
    assert "week 2026-W39" in digest.sends[0]
    assert await _row("2026W39") is not None


async def test_no_session_is_open_while_the_site_is_crawled(digest: _Digest, clock: _Clock) -> None:
    """MUST-FIX 1. Postgres kills a transaction left idle for 5 minutes, and the
    crawl takes longer. Mutation: crawling inside the session that renders."""
    assert await _run(clock) is DigestOutcome.SENT
    assert digest.scopes_open_during_crawl == [0], (
        f"{digest.scopes_open_during_crawl[0]} database session(s) were open during the crawl"
    )


async def test_a_telegram_refusal_releases_the_week(digest: _Digest, clock: _Clock) -> None:
    """A Telegram 4xx is REFUSED rather than raised. That is nothing sent, so
    the next run must retry. Mutation: treating a refused send as done."""
    digest.send_result = SendStatus.REFUSED
    assert await _run(clock) is DigestOutcome.FAILED
    assert await _row() is None, "a refused send marked the week done"

    digest.send_result = SendStatus.DELIVERED
    clock.now += timedelta(days=1)
    assert await _run(clock) is DigestOutcome.SENT


@pytest.mark.parametrize("where", ["crawl", "connect_error", "connect_timeout", "pool_timeout"])
async def test_an_error_before_telegram_has_the_digest_releases_the_week(
    digest: _Digest, clock: _Clock, where: str,
) -> None:
    """A crawl error, or a send that never opened a connection: nothing can
    have been delivered, so the next run must retry. Mutations: no release in
    the except path; classifying a connect failure as an unknown delivery."""
    if where == "crawl":
        digest.crawl_error = RuntimeError("crawl exploded")
    elif where == "connect_error":
        digest.send_result = httpx.ConnectError("x")
    elif where == "connect_timeout":
        digest.send_result = httpx.ConnectTimeout("x")
    else:
        digest.send_result = httpx.PoolTimeout("x")
    assert await _run(clock) is DigestOutcome.FAILED
    assert await _row() is None
    assert digest.sends == []

    digest.crawl_error = None
    digest.send_result = SendStatus.DELIVERED
    clock.now += timedelta(days=1)
    assert await _run(clock) is DigestOutcome.SENT


@pytest.mark.parametrize("result", [
    httpx.ReadTimeout("x"),
    httpx.WriteTimeout("x"),
    httpx.ReadError("x"),
    httpx.WriteError("x"),
    httpx.RemoteProtocolError("x"),
    RuntimeError("anything else the send raises"),
    SendStatus.UNCERTAIN,   # a Telegram 5xx
], ids=lambda r: getattr(r, "value", type(r).__name__))
async def test_a_send_that_may_have_delivered_keeps_the_week(
    digest: _Digest, clock: _Clock, result: SendStatus | Exception,
) -> None:
    """Telegram accepted the digest and the response read timed out, or a 5xx
    came back after it took the request. Releasing the week would send it again
    the next day: the double send #831 fixed for the survey reminder. The week
    is recorded as sent and the run goes red for a person to check Telegram.
    Mutations: releasing on any send exception; treating a 5xx as a refusal;
    leaving the claim incomplete (taken over, and re-sent, an hour later)."""
    digest.send_result = result
    assert await _run(clock) is DigestOutcome.SEND_UNKNOWN
    row = await _row()
    assert row is not None, "an uncertain send released the week"
    assert row.completed_at is not None, "an uncertain send can be taken over and re-sent"

    digest.send_result = SendStatus.DELIVERED
    for later in (STALE + timedelta(minutes=1), timedelta(days=1)):
        clock.now = MONDAY_10 + later
        assert await _run(clock) is DigestOutcome.ALREADY_SENT
    assert digest.send_attempts == 1, "the week was sent a second time"


async def test_an_uncertain_send_says_to_check_telegram_before_a_re_dispatch(
    digest: _Digest, clock: _Clock, caplog: pytest.LogCaptureFixture,
) -> None:
    """Mutation: the send_unknown log line dropped, or not naming the week."""
    digest.send_result = httpx.ReadTimeout("x")
    with caplog.at_level(logging.INFO, logger=seo_health.__name__):
        assert await _run(clock) is DigestOutcome.SEND_UNKNOWN
    unknown = [r.getMessage() for r in caplog.records if "seo_digest.send_unknown" in r.getMessage()]
    assert any("Check the founder's Telegram" in m and WEEK in m for m in unknown), unknown
    assert all("founder-chat" not in r.getMessage() for r in caplog.records)


async def test_an_unreadable_sitemap_is_not_reported_as_a_healthy_site(
    digest: _Digest, clock: _Clock,
) -> None:
    """run_stale_link_audit returns checked 0, broken [] when it cannot fetch the
    sitemap. Sending that is "0 URLs, 0 broken" about a site nobody checked, and
    marks the week done so it is never retried. Mutation: no sitemap check."""
    digest.crawl_result = {
        "checked": 0, "healthy": 0, "broken": [], "note": "sitemap_unavailable",
    }
    assert await _run(clock) is DigestOutcome.SITEMAP_UNAVAILABLE
    assert (digest.send_attempts, await _row()) == (0, None)

    digest.crawl_result = {"checked": 3, "healthy": 3, "broken": []}
    clock.now += timedelta(days=1)
    assert await _run(clock) is DigestOutcome.SENT


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


async def test_in_flight_says_whose_claim_it_is_and_when_it_can_be_taken_over(
    digest: _Digest, clock: _Clock, caplog: pytest.LogCaptureFixture,
) -> None:
    """A re-dispatch soon after a run killed by a deploy shows green IN_FLIGHT
    while nothing runs. The log must say how old the claim is, whose, and when
    a run can take it over. Mutations: no detail; the age or the takeover time
    computed from the wrong end; the full owner token printed."""
    elsewhere = clock.now - timedelta(minutes=25)
    held = await claim_period(seo_health.DIGEST_JOB, WEEK, now=elsewhere)
    assert held.owner is not None

    with caplog.at_level(logging.INFO, logger=seo_health.__name__):
        assert await _run(clock) is DigestOutcome.IN_FLIGHT
    lines = [r.getMessage() for r in caplog.records if "seo_digest.in_flight" in r.getMessage()]
    assert len(lines) == 1, lines
    line = lines[0]
    assert f"owner={held.owner[:8]}..." in line
    assert held.owner not in line, "the full owner token was printed"
    assert f"claimed_at={elsewhere.isoformat()}" in line
    assert "age=25m" in line
    assert f"retryable_after={(elsewhere + STALE).isoformat()}" in line
    assert "founder-chat" not in line


async def test_a_busy_claim_carries_the_holder_but_cannot_be_used_to_finish_it() -> None:
    """Mutation: returning the holder's token as `owner`, which would let a
    BUSY caller complete or release someone else's claim."""
    t0 = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
    held = await claim_period(JOB, WEEK, now=t0)
    busy = await claim_period(JOB, WEEK, now=t0 + timedelta(minutes=7))
    assert busy.status is ClaimStatus.BUSY
    assert (busy.owner, busy.claimed_at) == (None, None)
    assert busy.held_by == held.owner
    assert busy.held_since == t0
    assert busy.retryable_after() == t0 + STALE


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
    (DigestOutcome.SEND_UNKNOWN, 1),
    (DigestOutcome.SITEMAP_UNAVAILABLE, 1),
])
async def test_the_script_turns_the_run_red_only_when_it_needs_a_look(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
    outcome: DigestOutcome, code: int,
) -> None:
    """Mutations: a failed run exiting 0, which leaves the workflow green; a red
    run with no annotation saying what to do."""
    from app.scripts import seo_weekly_digest as script

    async def _fixed() -> DigestOutcome:
        return outcome

    monkeypatch.setattr(script, "run_weekly_digest", _fixed)
    assert await script.main() == code
    out = capsys.readouterr().out
    assert f"seo_digest.outcome={outcome.value}" in out
    if code:
        assert "::error title=" in out, "a red run gives no reason in the Actions UI"


def test_every_red_outcome_is_annotated() -> None:
    """Mutation: a red outcome added without an annotation saying what to do."""
    from app.scripts import seo_weekly_digest as script

    for outcome in script._RED:
        assert script.ANNOTATIONS[outcome].startswith("::error "), outcome
    assert "Telegram BEFORE re-dispatching" in script.ANNOTATIONS[DigestOutcome.SEND_UNKNOWN]
    assert script.ANNOTATIONS[DigestOutcome.IN_FLIGHT].startswith("::notice ")


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


@pytest.mark.parametrize("name", ["seo-weekly-digest.yml", "stale-link-audit.yml"])
def test_both_crawls_are_pinned_to_the_worker_and_warn_that_cron_runs_late(name: str) -> None:
    """Mutations: an unpinned `flyctl ssh console`, which may land on an api
    machine; the header note that Actions starts crons hours late removed."""
    import re

    wf = (_REPO / ".github" / "workflows" / name).read_text(encoding="utf-8")
    consoles = re.findall(r"flyctl ssh console[^\n]*", wf)
    consoles = [c for c in consoles if " -a " in c]
    assert consoles, f"{name} no longer runs over flyctl ssh"
    for line in consoles:
        assert re.search(r"\s-g worker\b", line), f"{name}: not pinned to the worker: {line}"
    assert re.search(r"1\s*(?:#\s*)?to 7 hours", wf), f"{name}: the late-cron note is gone"


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


async def test_the_daily_audit_does_not_call_an_unreadable_sitemap_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The audit returned False ("no broken URLs") when it had checked nothing,
    so the workflow stayed green through a sitemap outage. Mutations: no
    sitemap check; the workflow not turning SitemapUnavailableError into exit 1."""
    sends: list[str] = []

    async def _owner(session) -> str:
        return "founder-chat"

    async def _crawl() -> dict:
        return {"checked": 0, "healthy": 0, "broken": [], "note": "sitemap_unavailable"}

    async def _send(chat_id: str, text_: str) -> bool:
        sends.append(text_)
        return True

    monkeypatch.setattr(seo_health, "_owner_chat_id", _owner)
    monkeypatch.setattr(seo_health, "run_stale_link_audit", _crawl)
    monkeypatch.setattr(seo_health, "send_message", _send)
    async with session_scope() as session:
        with pytest.raises(seo_health.SitemapUnavailableError):
            await seo_health.run_stale_audit_alert(session)
    assert sends == []

    wf = (_REPO / ".github" / "workflows" / "stale-link-audit.yml").read_text(encoding="utf-8")
    assert "except SitemapUnavailableError" in wf
    assert "return 1" in wf and "sys.exit(asyncio.run(main()))" in wf
