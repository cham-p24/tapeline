"""GDPR-compliance endpoints: data export + account deletion."""
from __future__ import annotations

import io
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import AlertEvent, AlertRule, ApiKey, Subscription, User, WatchlistItem
from app.services.auth import current_user_required

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/export")
async def export_my_data(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
):
    """Return a JSON bundle of everything we hold about the user. GDPR Art. 15."""
    wl = (await session.execute(select(WatchlistItem).where(WatchlistItem.user_id == user.id))).scalars().all()
    rules = (await session.execute(select(AlertRule).where(AlertRule.user_id == user.id))).scalars().all()
    events = (await session.execute(select(AlertEvent).where(AlertEvent.user_id == user.id))).scalars().all()
    subs = (await session.execute(select(Subscription).where(Subscription.user_id == user.id))).scalars().all()

    bundle = {
        "exported_at": user.updated_at.isoformat(),
        "user": {"id": user.id, "email": user.email, "name": user.name, "tier": user.tier, "created_at": user.created_at.isoformat()},
        "watchlist": [{"symbol": w.symbol, "note": w.note, "baseline_score": w.baseline_score, "added_at": w.added_at.isoformat()} for w in wl],
        "alert_rules": [{"name": r.name, "rule_type": r.rule_type, "symbol": r.symbol, "threshold": r.threshold, "channel": r.channel, "created_at": r.created_at.isoformat()} for r in rules],
        "alert_events": [{"symbol": e.symbol, "message": e.message, "channel": e.channel, "delivered": e.delivered, "created_at": e.created_at.isoformat()} for e in events],
        "subscriptions": [{"id": s.id, "status": s.status, "tier": s.tier, "current_period_end": s.current_period_end.isoformat()} for s in subs],
    }

    # GDPR Art. 15 confirmation — fire-and-forget so a Resend hiccup never
    # breaks the export download. Account-state notification (can't opt out):
    # persona "default", no List-Unsubscribe.
    if user.email:
        try:
            from app.services.email import render_gdpr_confirmation_email, send_email

            html = render_gdpr_confirmation_email(user.name or "trader", kind="export")
            await send_email(
                user.email,
                "Your Tapeline data export is ready",
                html,
                persona="default",
            )
        except Exception:  # confirmation must never block the export
            logger.exception("account.export_confirmation_email_failed user=%s", user.id)

    buf = io.BytesIO(json.dumps(bundle, indent=2).encode("utf-8"))
    return StreamingResponse(
        buf,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=tapeline_{user.id}.json"},
    )


@router.delete("")
async def delete_my_account(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Hard-delete all user data. GDPR Art. 17."""
    user_id = user.id
    # Capture identity BEFORE deletion — once the User row is gone we can't
    # render or address the confirmation. This is the LAST email the account
    # ever receives, so we send it up front and swallow any failure (a Resend
    # hiccup must never block an erasure request).
    user_email = user.email
    user_name = user.name or "trader"
    if user_email:
        try:
            from app.services.email import render_gdpr_confirmation_email, send_email

            html = render_gdpr_confirmation_email(user_name, kind="deletion")
            await send_email(
                user_email,
                "Your Tapeline account has been deleted",
                html,
                persona="default",
                # The undeliverable check runs a separate DB query against the
                # User row — fine here since we send before the deletes land.
            )
        except Exception:  # confirmation must never block the erasure
            logger.exception("account.deletion_confirmation_email_failed user=%s", user_id)

    # Cascade delete user-owned rows
    await session.execute(delete(AlertEvent).where(AlertEvent.user_id == user_id))
    await session.execute(delete(AlertRule).where(AlertRule.user_id == user_id))
    await session.execute(delete(WatchlistItem).where(WatchlistItem.user_id == user_id))
    await session.execute(delete(Subscription).where(Subscription.user_id == user_id))
    await session.execute(delete(ApiKey).where(ApiKey.user_id == user_id))
    await session.execute(delete(User).where(User.id == user_id))
    await session.commit()
    logger.info("account.deleted user=%s", user_id)
    # NOTE: Clerk user deletion should also be triggered from the frontend via Clerk SDK
    return {"ok": True, "deleted_user_id": user_id}
