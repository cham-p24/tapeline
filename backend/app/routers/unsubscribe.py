"""Public one-click unsubscribe endpoint.

Reachable at GET (browser click) and POST (Gmail/Outlook
List-Unsubscribe-Post one-click). Both verify the HMAC token + apply
the corresponding email_prefs change, then return JSON. The frontend
/unsubscribe page wraps the GET form so the user sees a confirmation
rather than a bare JSON blob.

No auth — the HMAC token IS the proof. No rate limiting either: the
operation is idempotent and the URL is only sent inside the user's own
inbox, so abuse vectors are limited to "someone read your email". The
worst case there is "your subscription is paused", which the user can
re-enable in /app/settings/email anyway.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services.unsubscribe import apply_unsubscribe, verify_token

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def unsubscribe_get(
    token: str = Query(..., min_length=8, max_length=400),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _handle(token, session)


@router.post("")
async def unsubscribe_post(
    token: str = Query(..., min_length=8, max_length=400),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """RFC 8058 one-click variant. Gmail POSTs here when the user clicks
    its native unsubscribe button. MUST resolve quickly and idempotently."""
    return await _handle(token, session)


async def _handle(token: str, session: AsyncSession) -> dict:
    verified = verify_token(token)
    if verified is None:
        # Bad token / missing secret / unknown category. We return 200 with
        # status=invalid rather than 400 so Gmail's one-click classifier
        # doesn't penalise us for "the URL errored". The frontend page
        # renders an appropriate message.
        logger.info("unsubscribe.invalid_token")
        return {"status": "invalid"}
    user_id, category = verified
    changed = await apply_unsubscribe(session, user_id, category)
    return {
        "status": "ok",
        "changed": changed,
        "category": category,
    }
