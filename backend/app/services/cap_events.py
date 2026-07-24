"""record_cap_hit — durable, fire-and-forget logging of free-tier cap hits.

Called at each server-side enforcement point AT the moment a FREE user is
refused MORE of a metered resource (the 403 / 402 / limit branch). Persists one
append-only `cap_events` row so the free→paid micro-funnel can be measured and
the future free-tier-tightening decision made from data instead of intuition.

Two hard guarantees, because this runs on the hot path of the reject branch:

  1. IT NEVER BREAKS THE REQUEST. Every failure mode — a bad cap name, a write
     error, a session already in trouble — is swallowed and logged. The caller
     is about to return a 402/403 to the user; a logging hiccup must never turn
     that into a 500.

  2. IT ONLY LOGS FREE-TIER HITS. Paid tiers (pro/premium) can technically trip
     a couple of these branches too (e.g. a Pro user at their 50-ticker
     watchlist cap), but a paid user hitting a paid ceiling is NOT a free→paid
     conversion signal and would pollute the dataset. The helper refuses any
     non-free tier centrally, so call sites don't each have to guard.

Storage is server-side and durable on purpose: GA4 is a no-op in prod (the
measurement env is deliberately unset) and event tools drop low-N rows, so the
durable table — not the client beacon — is the ground truth. No cap VALUES
change here; this only records.
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cap_events import CAP_NAMES, CapEvent
from app.services.tier import Tier

logger = logging.getLogger(__name__)


async def record_cap_hit(
    session: AsyncSession,
    user_id: str,
    cap: str,
    tier: Tier | str,
) -> None:
    """Persist one free-tier cap-hit event. Fire-and-forget: never raises.

    Args:
        session:  the request's AsyncSession. Only free-tier reject branches
                  call this, and those branches carry no other pending writes,
                  so committing here flushes just this one row.
        user_id:  the free user who was refused.
        cap:      one of models.cap_events.CAP_NAMES. An unknown value is
                  dropped (logged) rather than written, so a typo can't poison
                  the dataset.
        tier:     the user's tier at hit-time. Anything other than FREE is a
                  no-op — paid ceilings aren't a conversion signal.
    """
    try:
        tier_value = tier.value if isinstance(tier, Tier) else str(tier)
        # Only free-tier hits are the free→paid signal. Refuse the rest here so
        # no call site can accidentally log a paid ceiling.
        if tier_value != Tier.FREE.value:
            return
        if cap not in CAP_NAMES:
            logger.warning("cap_hit.unknown_cap cap=%s user=%s", cap, user_id)
            return

        session.add(CapEvent(user_id=user_id, cap=cap, tier=tier_value))
        await session.commit()
    except Exception:
        # A logging failure must never break the request. Roll back so the
        # caller's session is left clean for the 402/403 it's about to raise.
        logger.exception("cap_hit.record_failed cap=%s user=%s", cap, user_id)
        try:
            await session.rollback()
        except Exception:
            logger.exception("cap_hit.rollback_failed cap=%s user=%s", cap, user_id)
