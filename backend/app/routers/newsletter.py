"""POST /api/newsletter/subscribe  ·  GET /api/newsletter/unsubscribe

The lead-magnet capture endpoint. Visitors who aren't ready to start a
14-day trial can drop their email here to get the daily Top 10 digest.
Lower-commitment funnel step than /signup; once we have their email
we can re-engage via the daily send and the trial CTA inside it.

Public, no auth. Honeypot + IP rate limit keep the spam floor down.
"""
from __future__ import annotations

import logging
import re
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.services.newsletter import subscribe, unsubscribe_by_token

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

# Sliding-window rate limit — at most 5 subscribe requests per IP per
# 10 minutes. Keeps drive-by spam from poisoning the list without
# punishing households on shared IPs.
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW_SEC = 600
_recent_by_ip: dict[str, deque[float]] = defaultdict(deque)

# Light disposable-email screen — same set as bot_protection.py uses for
# signup, kept inline here to avoid the wider auth-flow import surface.
# A real disposable hits the welcome email's open metric anyway, but
# this knocks off the worst offenders cheaply.
_DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "10minutemail.com",
    "throwawaymail.com", "yopmail.com", "trashmail.com", "getnada.com",
    "spam4.me", "mohmal.com", "dispostable.com",
}
_DOMAIN_RX = re.compile(r"@([^@\s]+)$")


def _client_ip(request: Request) -> str:
    return (
        request.headers.get("cf-connecting-ip")
        or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "0.0.0.0")
    )


def _rate_limited(ip: str) -> bool:
    now = time.monotonic()
    bucket = _recent_by_ip[ip]
    while bucket and now - bucket[0] > _RATE_LIMIT_WINDOW_SEC:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT_MAX:
        return True
    bucket.append(now)
    return False


class SubscribeBody(BaseModel):
    email: EmailStr
    # Free-form surface name — 'homepage' / 'scorecard' / 'pricing' / 'api'.
    source: str | None = Field(None, max_length=40)
    # Marketing UTMs the frontend captured on landing and persisted to
    # localStorage. Pass-through to the DB row so we know which channel
    # converted them.
    utm_source: str | None = Field(None, max_length=80)
    utm_medium: str | None = Field(None, max_length=80)
    utm_campaign: str | None = Field(None, max_length=120)
    utm_term: str | None = Field(None, max_length=120)
    utm_content: str | None = Field(None, max_length=120)
    # Honeypot — invisible to humans, bots fill it. Submission tripping
    # this is silently accepted (no row written) so spammers can't probe.
    website: str | None = Field(None, max_length=200)


@router.post("/subscribe")
async def subscribe_endpoint(
    body: SubscribeBody,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    if body.website:
        logger.info("newsletter.honeypot_triggered ip=%s", _client_ip(request))
        return {"ok": True, "status": "already_subscribed"}

    ip = _client_ip(request)
    if _rate_limited(ip):
        raise HTTPException(429, "Too many requests. Try again in a few minutes.")

    domain_match = _DOMAIN_RX.search(body.email)
    if domain_match and domain_match.group(1).lower() in _DISPOSABLE_DOMAINS:
        logger.info("newsletter.disposable_rejected ip=%s domain=%s", ip, domain_match.group(1))
        # Don't surface "we rejected your domain" — pretend it worked, so
        # the spammer doesn't probe for which domains are blocked.
        return {"ok": True, "status": "already_subscribed"}

    try:
        result = await subscribe(
            session,
            email=body.email,
            source=body.source,
            utm_source=body.utm_source,
            utm_medium=body.utm_medium,
            utm_campaign=body.utm_campaign,
            utm_term=body.utm_term,
            utm_content=body.utm_content,
        )
    except Exception as err:
        logger.exception("newsletter.subscribe_failed email=%s ip=%s", body.email, ip)
        raise HTTPException(
            500, "Could not subscribe right now. Try again shortly.",
        ) from err

    return result


@router.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe_endpoint(
    token: str,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """One-click unsubscribe handler.

    Renders a confirmation page (no JS required) — important for email
    clients that pre-fetch links via "link safety scanning"; we don't
    want a pre-fetch to silently unsubscribe someone. The actual
    unsubscribe happens on form submit below.

    For now we make this a simple GET that flips the flag immediately,
    matching the lowest-friction posture. If we later see false-positive
    unsubscribes from pre-fetchers, swap to a POST-confirm flow.
    """
    ok = await unsubscribe_by_token(session, token)
    if not ok:
        return HTMLResponse(
            content=_unsub_page(
                title="Link expired",
                body=(
                    "This unsubscribe link is invalid or has already been used. "
                    'If you keep getting the digest, email '
                    '<a href="mailto:support@tapeline.io" style="color:#fb923c;">'
                    'support@tapeline.io</a> and we&rsquo;ll handle it manually.'
                ),
            ),
            status_code=404,
        )
    return HTMLResponse(
        content=_unsub_page(
            title="You're unsubscribed",
            body=(
                "You won&rsquo;t receive the Tapeline daily Top 10 again. "
                "The public scorecard is still available at "
                '<a href="https://tapeline.io/scorecard" style="color:#fb923c;">'
                "tapeline.io/scorecard</a> any time."
            ),
        ),
    )


def _unsub_page(*, title: str, body: str) -> str:
    return f"""<!doctype html><html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Tapeline</title>
</head><body style="font-family:Inter,system-ui,sans-serif;background:#0a0a0a;color:#f4f4f5;margin:0;padding:48px 24px;">
  <div style="max-width:480px;margin:0 auto;background:#121214;border-radius:12px;padding:32px;border:1px solid #1f1f23;text-align:center;">
    <h1 style="margin:0 0 16px;font-size:22px;font-weight:600;">{title}</h1>
    <p style="margin:0;line-height:1.6;color:#d4d4d8;">{body}</p>
    <a href="https://tapeline.io" style="display:inline-block;margin-top:24px;color:#9ca3af;font-size:13px;">&larr; tapeline.io</a>
  </div>
</body></html>"""
