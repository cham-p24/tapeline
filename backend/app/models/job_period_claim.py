"""One row per (job, period) a periodic founder job has claimed - the durable latch."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class JobPeriodClaim(Base):
    """A periodic job's claim on one period, written BEFORE the work.

    Process-memory latches are forgotten on every restart, so a job that sends
    something once a period re-ran after each deploy. The primary key is the
    claim: two processes inserting the same (job, period) cannot both succeed.

    `owner` is a random token written by whoever holds the claim now. A takeover
    writes a new one, so a run that was presumed dead can no longer complete or
    release a claim that has since passed to someone else.

    `completed_at` is NULL while the run is in flight. A claim that has sat
    incomplete for longer than the job is allowed to run was left by a process
    that died mid-run, and may be taken over; see services/job_claims.py.
    """
    __tablename__ = "job_period_claims"

    job: Mapped[str] = mapped_column(String(64), primary_key=True)
    period: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner: Mapped[str] = mapped_column(String(36), nullable=False)
    claimed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
