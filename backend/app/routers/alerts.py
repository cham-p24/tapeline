"""Alert rule CRUD for authenticated users."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import AlertEvent, AlertRule, User
from app.services.auth import current_user_required
from app.services.tier import Tier, effective_limit, has_feature

router = APIRouter()


class AlertRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    rule_type: str = Field(..., pattern="^(score|squeeze|regime|congress|news)$")
    symbol: str | None = Field(None, max_length=20)
    threshold: float | None = None
    channel: str = Field("email", pattern="^(email|telegram|web_push)$")


@router.get("/rules")
async def list_rules(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.execute(
        select(AlertRule).where(AlertRule.user_id == user.id).order_by(desc(AlertRule.created_at))
    )
    rules = result.scalars().all()
    return {"count": len(rules), "items": [_rule_to_dict(r) for r in rules]}


@router.post("/rules")
async def create_rule(
    body: AlertRuleCreate,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    # Feature gate: Telegram = Premium-only, email = Pro+, web_push = Free+
    # (the free "alert taste" channel — see tier.FREE_WEB_PUSH_ALERTS).
    # Discord + SMS channels were retired 2026-05-04.
    feature = (
        "alerts.telegram" if body.channel == "telegram"
        else "alerts.web_push" if body.channel == "web_push"
        else "alerts.email"
    )
    if not has_feature(Tier(user.tier), feature):
        raise HTTPException(
            403,
            f"{feature} requires a higher tier. Upgrade at /app/billing",
        )

    # Web-push count cap. Web push is the one channel a FREE user may create
    # rules on (the activation "taste"), but only up to a SMALL allowance —
    # tier.web_push_alerts (Free=FREE_WEB_PUSH_ALERTS=2, paid=effectively
    # unlimited). Enforced server-side because a forked/old client can't be
    # trusted. effective_limit keeps this correct under trial-state Premium
    # too (which sits at the paid cap). email/telegram are already fully
    # gated by has_feature above, so this cap only needs to guard web_push.
    if body.channel == "web_push":
        cap = effective_limit(user, "web_push_alerts")
        existing_q = await session.execute(
            select(func.count())
            .select_from(AlertRule)
            .where(AlertRule.user_id == user.id, AlertRule.channel == "web_push")
        )
        current = existing_q.scalar() or 0
        if cap is not None and current >= cap:
            tier = Tier(user.tier).value
            raise HTTPException(
                403,
                f"Free web-push alert limit reached ({cap} on {tier}). "
                f"Upgrade for 10 alerts/day plus Telegram at /app/billing.",
            )

    rule = AlertRule(
        user_id=user.id,
        name=body.name,
        rule_type=body.rule_type,
        symbol=body.symbol,
        threshold=body.threshold,
        channel=body.channel,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return _rule_to_dict(rule)


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.execute(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == user.id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(404, "Rule not found")
    await session.delete(rule)
    await session.commit()
    return {"ok": True}


@router.get("/events")
async def list_events(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
    limit: int = 50,
) -> dict:
    result = await session.execute(
        select(AlertEvent)
        .where(AlertEvent.user_id == user.id)
        .order_by(desc(AlertEvent.created_at))
        .limit(limit)
    )
    events = result.scalars().all()
    return {
        "count": len(events),
        "items": [
            {
                "id": e.id,
                "rule_id": e.rule_id,
                "symbol": e.symbol,
                "message": e.message,
                "channel": e.channel,
                "delivered": e.delivered,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }


def _rule_to_dict(r: AlertRule) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "rule_type": r.rule_type,
        "symbol": r.symbol,
        "threshold": r.threshold,
        "channel": r.channel,
        "enabled": r.enabled,
        "last_fired_at": r.last_fired_at.isoformat() if r.last_fired_at else None,
        "created_at": r.created_at.isoformat(),
    }
