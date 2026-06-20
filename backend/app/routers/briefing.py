"""/api/briefing — preview + trigger the daily briefing email.

Preview behaviour:
- Signed-in user → renders THEIR personalised briefing (watchlist-scoped).
  Doubles as a "see what you'll get every morning" demo for the app's billing
  page or the briefing settings panel.
- Anonymous     → renders the site-wide briefing as a generic preview. Useful
  on the marketing pages to show prospects what the daily mail looks like.

Send behaviour:
- POST /send is authenticated; sends THIS user's personalised briefing right
  now to their own email. Used by the in-app "test the briefing" button.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.services.auth import current_user_optional, current_user_required
from app.services.briefing import generate_briefing_html
from app.services.rate_limit import limit_strict

router = APIRouter()


@router.get("/preview", response_class=HTMLResponse)
async def preview_briefing(
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(current_user_optional),
) -> str:
    """Public HTML preview of today's briefing — doubles as a landing-page demo.

    Signed-in viewer → personalised briefing (watchlist-scoped).
    Anonymous viewer → generic site-wide briefing.
    """
    return await generate_briefing_html(session, user)


@router.post("/send", dependencies=[Depends(limit_strict)])
async def send_test_briefing(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Send today's personalised briefing to the current user's email right now."""
    from app.services.email import send_email
    html = await generate_briefing_html(session, user)
    await send_email(user.email, "Your Tapeline briefing (test)", html, persona="alerts")
    return {"ok": True, "sent_to": user.email}
