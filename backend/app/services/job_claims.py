"""Durable once-per-period claims for periodic founder jobs.

Usage, for a job that must run once per period across restarts and machines:

    claim = await claim_period(job, period)
    if claim.status is ClaimStatus.CLAIMED:
        ... the work, finished before claim.claimed_at + STALE_CLAIM_AFTER ...
        await complete_period(claim)        # or release_period(claim) to retry
    elif claim.status is ClaimStatus.DONE:
        ...                                 # nothing to do this period
    else:  # BUSY
        ...                                 # another run is in flight

The claim is written BEFORE the work, as an INSERT on the (job, period) primary
key, so two runs cannot both win. A claim with no `completed_at` older than
`STALE_CLAIM_AFTER` was left by a run that died, and is taken over by a
conditional UPDATE, which again only one caller can win.

A takeover writes a new `owner`, and complete and release only touch a row that
still carries the caller's owner. So a run that outlived its window cannot
finish or delete the claim of the run that took over from it. The window is
only safe if the job never acts after it: a job that sends must stop before
`claimed_at + STALE_CLAIM_AFTER`, because from then on another run may send.
"""
from __future__ import annotations

import enum
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.db import session_scope
from app.models import JobPeriodClaim

logger = logging.getLogger(__name__)

#: How long an incomplete claim is trusted to still be running. The SEO digest,
#: the only user, crawls the whole sitemap: 11,982 URLs, and the daily audit's
#: crawls took 4 to 14 minutes between 2026-09-06 and 09-12. The job stops
#: well inside this (seo_health.DIGEST_BUDGET), so a takeover never overlaps a
#: run that can still send.
STALE_CLAIM_AFTER = timedelta(hours=1)


class ClaimStatus(enum.Enum):
    CLAIMED = "claimed"   # this caller owns the period and must do the work
    DONE = "done"         # the period's work already completed
    BUSY = "busy"         # another caller's run is in flight (and not stale)


@dataclass(frozen=True)
class Claim:
    job: str
    period: str
    status: ClaimStatus
    #: Set only when CLAIMED: the token this caller wrote, and when.
    owner: str | None = None
    claimed_at: datetime | None = None


async def claim_period(job: str, period: str, *, now: datetime | None = None) -> Claim:
    """Claim (job, period) before doing its work. Never raises IntegrityError."""
    now = now or datetime.now(UTC)
    owner = str(uuid.uuid4())
    try:
        async with session_scope() as session:
            session.add(JobPeriodClaim(job=job, period=period, owner=owner, claimed_at=now))
        return Claim(job, period, ClaimStatus.CLAIMED, owner, now)
    except IntegrityError:
        pass

    # Someone holds it. Take it over only if it was abandoned mid-run.
    async with session_scope() as session:
        taken = await session.execute(
            update(JobPeriodClaim)
            .where(
                JobPeriodClaim.job == job,
                JobPeriodClaim.period == period,
                JobPeriodClaim.completed_at.is_(None),
                JobPeriodClaim.claimed_at < now - STALE_CLAIM_AFTER,
            )
            .values(owner=owner, claimed_at=now)
        )
        if taken.rowcount == 1:  # type: ignore[attr-defined]
            logger.warning("job_claim.reclaimed_stale job=%s period=%s", job, period)
            return Claim(job, period, ClaimStatus.CLAIMED, owner, now)
        completed = await session.scalar(
            select(JobPeriodClaim.completed_at).where(
                JobPeriodClaim.job == job, JobPeriodClaim.period == period,
            )
        )
    status = ClaimStatus.DONE if completed is not None else ClaimStatus.BUSY
    return Claim(job, period, status)


def _owned_by(claim: Claim):  # type: ignore[no-untyped-def]
    if claim.owner is None:
        raise ValueError(f"{claim.job}/{claim.period} was not claimed by this caller")
    return (
        JobPeriodClaim.job == claim.job,
        JobPeriodClaim.period == claim.period,
        JobPeriodClaim.owner == claim.owner,
        JobPeriodClaim.completed_at.is_(None),
    )


async def complete_period(claim: Claim, *, now: datetime | None = None) -> bool:
    """Mark the period's work done. After this no caller will run it again.

    False when the claim is no longer this caller's (it was taken over).
    """
    async with session_scope() as session:
        done = await session.execute(
            update(JobPeriodClaim)
            .where(*_owned_by(claim))
            .values(completed_at=now or datetime.now(UTC))
        )
    return done.rowcount == 1  # type: ignore[attr-defined]


async def release_period(claim: Claim) -> bool:
    """Give an incomplete claim back after a CAUGHT failure, so it can retry.

    A completed claim is never released, because that would re-run finished
    work, and neither is a claim another run has taken over.
    """
    async with session_scope() as session:
        gone = await session.execute(delete(JobPeriodClaim).where(*_owned_by(claim)))
    return gone.rowcount == 1  # type: ignore[attr-defined]
