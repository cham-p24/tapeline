"""/api/briefing — preview + trigger the daily briefing email."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.services.auth import current_user_optional, current_user_required
from app.services.briefing import generate_briefing_html

router = APIRouter()


@router.get("/preview", response_class=HTMLResponse)
async def preview_briefing(
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(current_user_optional),
) -> str:
    """Public HTML preview of today's briefing — doubles as a landing-page demo."""
    name = (user.name if user else None) or "trader"
    return await generate_briefing_html(session, name)


@router.post("/send")
async def send_test_briefing(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Send today's briefing to the current user's email right now."""
    from app.services.email import send_email
    html = await generate_briefing_html(session, user.name or "trader")
    await send_email(user.email, "Your Tapeline briefing (test)", html)
    return {"ok": True, "sent_to": user.email}
