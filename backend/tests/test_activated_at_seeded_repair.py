"""activated_at must measure the user's OWN first add, not ours.

Migration 0048 backfilled `users.activated_at` from
`MIN(watchlist_items.added_at)`, claiming it wrote "exactly the value the live
code would have written". It does not, and the codebase says so:

    Deliberately does NOT stamp user.activated_at: activation measures the
    user's own first add, not ours.   -- routers/me.py

Since PR #324 (2026-07-02) `_seed_watchlist_for_new_user` auto-inserts 2-4
watchlist_items on onboarding Submit *and* Skip. So for every account onboarded
after that, 0048 stamped activated_at with the timestamp of an item WE inserted
seconds after signup — counting as activated everyone who merely completed (or
skipped) onboarding, and setting time-to-value to ~0.

It cannot self-heal: both live stamps (routers/watchlist.py, routers/ticker.py)
are guarded on `activated_at IS NULL`, so a user carrying a wrong value never
gets the correct one.

Migration 0057 repairs only the rows 0048 provably took from a seeded item.
These tests exercise that SQL directly against the four cases that matter.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

from app.db import session_scope
from app.models import User, Watchlist, WatchlistItem

_STARTER_NOTE = "Starter pick — top-scored at signup"

# The repair statement from alembic/versions/20260823_0057_*. Kept in step with
# the migration by test_repair_sql_matches_the_migration below.
_REPAIR = """
UPDATE users
SET activated_at = (
    SELECT MIN(w.added_at)
    FROM watchlist_items w
    WHERE w.user_id = users.id
      AND (w.note IS NULL OR w.note NOT LIKE 'Starter pick%')
)
WHERE activated_at IS NOT NULL
  AND activated_at = (
      SELECT MIN(w2.added_at)
      FROM watchlist_items w2
      WHERE w2.user_id = users.id
        AND w2.note LIKE 'Starter pick%'
  )
"""


async def _mk_user(activated_at, items) -> str:
    """items: list of (added_at, note)."""
    uid = str(uuid.uuid4())
    async with session_scope() as s:
        s.add(
            User(
                id=uid,
                email=f"act-{uuid.uuid4().hex[:8]}@example.com",
                tier="free",
                activated_at=activated_at,
            )
        )
        await s.flush()
        wl = Watchlist(user_id=uid, name="W")
        s.add(wl)
        await s.flush()
        # Distinct symbols — watchlist_items is UNIQUE(user_id, symbol).
        for i, (added_at, note) in enumerate(items):
            s.add(
                WatchlistItem(
                    user_id=uid, watchlist_id=wl.id, symbol=f"ZW{i:02d}",
                    note=note, added_at=added_at,
                )
            )
        await s.commit()
    return uid


async def _activated(uid: str):
    async with session_scope() as s:
        return (
            await s.execute(select(User.activated_at).where(User.id == uid))
        ).scalar_one()


async def _run_repair() -> None:
    async with session_scope() as s:
        await s.execute(text(_REPAIR))
        await s.commit()


@pytest.mark.asyncio
async def test_seeded_only_user_is_reset_to_never_activated():
    """THE regression: onboarding Submit/Skip alone is not activation."""
    signup = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    uid = await _mk_user(
        activated_at=signup,  # what 0048 wrote — the seeded item's timestamp
        items=[(signup, _STARTER_NOTE), (signup, _STARTER_NOTE)],
    )
    await _run_repair()
    assert await _activated(uid) is None, (
        "a user whose only watchlist items are OUR starter picks still counts "
        "as activated — the activation rate stays inflated and TTV stays ~0"
    )


@pytest.mark.asyncio
async def test_user_with_a_real_add_is_moved_to_that_add():
    """Seeded at signup, genuinely added 5 days later → TTV is 5 days, not 0."""
    signup = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    real_add = signup + timedelta(days=5)
    uid = await _mk_user(
        activated_at=signup,  # 0048 took the seeded timestamp
        items=[(signup, _STARTER_NOTE), (real_add, None)],
    )
    await _run_repair()
    got = await _activated(uid)
    assert got is not None
    assert got.replace(tzinfo=UTC) == real_add, (
        f"expected the user's own first add {real_add}, got {got} — "
        f"time-to-value was being measured from OUR insert"
    )


@pytest.mark.asyncio
async def test_a_live_stamped_user_is_untouched():
    """Their activated_at is their own add, which is not a starter timestamp."""
    signup = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    own = signup + timedelta(days=2)
    uid = await _mk_user(
        activated_at=own,
        items=[(signup, _STARTER_NOTE), (own, None)],
    )
    await _run_repair()
    got = await _activated(uid)
    assert got.replace(tzinfo=UTC) == own, "a correctly-stamped user was altered"


@pytest.mark.asyncio
async def test_a_pre_324_user_is_untouched():
    """No starter picks at all — 0048 was CORRECT for them, so leave it.
    This is why the repair is targeted rather than a blanket revert."""
    add = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)
    uid = await _mk_user(activated_at=add, items=[(add, None)])
    await _run_repair()
    got = await _activated(uid)
    assert got.replace(tzinfo=UTC) == add, "a pre-#324 activation was wiped"


@pytest.mark.asyncio
async def test_a_null_activated_at_is_left_null():
    signup = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    uid = await _mk_user(activated_at=None, items=[(signup, _STARTER_NOTE)])
    await _run_repair()
    assert await _activated(uid) is None


@pytest.mark.asyncio
async def test_repair_is_idempotent():
    signup = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    real_add = signup + timedelta(days=3)
    uid = await _mk_user(
        activated_at=signup, items=[(signup, _STARTER_NOTE), (real_add, None)]
    )
    await _run_repair()
    first = await _activated(uid)
    await _run_repair()
    assert await _activated(uid) == first, "re-running the repair changed the value"


def test_repair_sql_matches_the_migration():
    """The SQL under test must be the SQL that ships."""
    import pathlib
    import re

    src = pathlib.Path(
        "alembic/versions/20260823_0057_fix_activated_at_seeded.py"
    ).read_text(encoding="utf-8")

    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip().lower()

    # The migration interpolates the note prefix; render it the same way.
    rendered = src.replace("{_STARTER}", "Starter pick%")
    assert _norm(_REPAIR) in _norm(rendered), (
        "the statement these tests exercise has drifted from the migration"
    )
