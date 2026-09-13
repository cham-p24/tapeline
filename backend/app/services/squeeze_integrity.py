"""One freshness rule for every place a squeeze setup reaches a user.

Why: on 2026-09-14 production's `squeeze_setups` held 15 rows, all written at
2026-07-18 14:53:19 UTC by a `mock_feed.fetch_squeezes` tick. The only real
writer (the SPIKE INTELLIGENCE sheet tab) has never been configured, so those
invented rows were served as current setups on the public page, the free
preview, the Pro feed and the squeeze alert evaluator. A row is publishable
only if it was written after mock writes stopped (2026-07-19) AND in the last
48 hours; anything else is not a current setup and is not shown. Rows are
suppressed, not deleted — deleting production data is a separate decision.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import ColumnElement, and_

from app.models import SqueezeSetup

#: Mock squeeze rows were last written 2026-07-18T14:53:19Z. Nothing written
#: before this instant is real.
MOCK_WRITES_STOPPED_AT = datetime(2026, 7, 19, tzinfo=UTC)

#: A setup older than this is not "current", whoever wrote it.
MAX_AGE = timedelta(hours=48)


class _HasUpdatedAt(Protocol):
    @property
    def updated_at(self) -> datetime | None: ...


def _as_utc(value: datetime) -> datetime:
    # SQLite hands back naive datetimes; every stored value is UTC.
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def is_publishable(row: _HasUpdatedAt, now: datetime | None = None) -> bool:
    """True only for a row written after mock writes stopped and within MAX_AGE."""
    if row.updated_at is None:
        return False
    now = _as_utc(now) if now is not None else datetime.now(UTC)
    updated = _as_utc(row.updated_at)
    return updated >= MOCK_WRITES_STOPPED_AT and updated > now - MAX_AGE


def publishable_clause(now: datetime | None = None) -> ColumnElement[bool]:
    """SQLAlchemy predicate equivalent to is_publishable, for use in queries.

    Apply it to EVERY SqueezeSetup query whose rows (or counts) reach a user.
    """
    now = now if now is not None else datetime.now(UTC)
    return and_(
        SqueezeSetup.updated_at >= MOCK_WRITES_STOPPED_AT,
        SqueezeSetup.updated_at > now - MAX_AGE,
    )
