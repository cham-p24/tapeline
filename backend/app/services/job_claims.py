"""Durable once-per-period claims for periodic worker jobs.

Usage, for a job that must run once per period across restarts and machines:

    status = await claim_period(job, period)
    if status is ClaimStatus.CLAIMED:
        try:
            ... the work ...
            await complete_period(job, period)
        except Exception:
            await release_period(job, period)   # a caught failure retries
    elif status is ClaimStatus.DONE:
        ...                                      # nothing to do this period
    else:  # BUSY
        ...                                      # another run is in flight

The claim is written BEFORE the work, as an INSERT on the (job, period) primary
key, so two processes - the worker and a standby the watchdog started - cannot
both win. A claim with no `completed_at` older than `STALE_CLAIM_AFTER` was
left by a process that died mid-run, and is taken over by a conditional UPDATE,
which again only one caller can win.
"""
from __future__ import annotations

import enum
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.db import session_scope
from app.models import JobPeriodClaim

logger = logging.getLogger(__name__)

#: How long an incomplete claim is trusted to still be running. Well above the
#: slowest job using this (the SEO digest's link audit runs a few minutes).
STALE_CLAIM_AFTER = timedelta(minutes=30)


class ClaimStatus(enum.Enum):
    CLAIMED = "claimed"   # this caller owns the period and must do the work
    DONE = "done"         # the period's work already completed
    BUSY = "busy"         # another caller's run is in flight (and not stale)


async def claim_period(job: str, period: str, *, now: datetime | None = None) -> ClaimStatus:
    """Claim (job, period) before doing its work. Never raises IntegrityError."""
    now = now or datetime.now(UTC)
    try:
        async with session_scope() as session:
            session.add(JobPeriodClaim(job=job, period=period, claimed_at=now))
        return ClaimStatus.CLAIMED
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
            .values(claimed_at=now)
        )
        if taken.rowcount == 1:  # type: ignore[attr-defined]
            logger.warning("job_claim.reclaimed_stale job=%s period=%s", job, period)
            return ClaimStatus.CLAIMED
        completed = await session.scalar(
            select(JobPeriodClaim.completed_at).where(
                JobPeriodClaim.job == job, JobPeriodClaim.period == period,
            )
        )
    return ClaimStatus.DONE if completed is not None else ClaimStatus.BUSY


async def complete_period(job: str, period: str, *, now: datetime | None = None) -> None:
    """Mark the period's work done. After this no caller will run it again."""
    async with session_scope() as session:
        await session.execute(
            update(JobPeriodClaim)
            .where(JobPeriodClaim.job == job, JobPeriodClaim.period == period)
            .values(completed_at=now or datetime.now(UTC))
        )


async def release_period(job: str, period: str) -> None:
    """Give an incomplete claim back after a CAUGHT failure, so it can retry.

    A completed claim is never released: that would re-send finished work.
    """
    async with session_scope() as session:
        await session.execute(
            delete(JobPeriodClaim).where(
                JobPeriodClaim.job == job,
                JobPeriodClaim.period == period,
                JobPeriodClaim.completed_at.is_(None),
            )
        )
