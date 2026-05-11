"""POST /api/contact — public contact form relay.

Posts from the marketing /contact page land here, get validated, and are
forwarded as email to support@tapeline.io via Resend. Inbound to support@
is then routed via Cloudflare Email Routing to the founder's Gmail.

No auth required — this is the public "talk to a human" surface. Rate
limited per IP to keep the spam floor down.
"""
from __future__ import annotations

import html as _html
import logging
import re
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from app.services.email import send_email

router = APIRouter()
logger = logging.getLogger(__name__)

_EMAIL_RX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Sliding-window rate limit: at most 5 submissions per IP per 10 minutes.
_RATE_LIMIT_MAX = 5
_RATE_LIMIT_WINDOW_SEC = 600
_recent_by_ip: dict[str, deque[float]] = defaultdict(deque)


class ContactMessage(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    subject: str | None = Field(None, max_length=200)
    message: str = Field(..., min_length=8, max_length=5000)
    # Honeypot — bots fill every field. Real humans never see this.
    website: str | None = Field(None, max_length=200)


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


@router.post("")
async def submit_contact(body: ContactMessage, request: Request) -> dict:
    if body.website:
        logger.info("contact.honeypot_triggered ip=%s", _client_ip(request))
        return {"ok": True}  # quietly accept so bots don't probe

    ip = _client_ip(request)
    if _rate_limited(ip):
        raise HTTPException(429, "Too many messages from your IP. Try again later.")

    subject = (body.subject or "Contact form — no subject").strip()[:180]
    safe_name = _html.escape(body.name.strip())
    safe_email = _html.escape(body.email)
    safe_subject = _html.escape(subject)
    safe_msg_html = _html.escape(body.message.strip()).replace("\n", "<br>")

    html = f"""<!doctype html><html><body style="font-family:Inter,system-ui,sans-serif;background:#0a0a0a;color:#f4f4f5;padding:24px;margin:0;">
  <div style="max-width:560px;margin:0 auto;background:#121214;border-radius:12px;padding:32px;border:1px solid #1f1f23;">
    <div style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#9ca3af;margin-bottom:8px;">Contact form</div>
    <h1 style="margin:0 0 16px;font-size:18px;">{safe_subject}</h1>
    <table style="width:100%;font-size:14px;border-collapse:collapse;">
      <tr><td style="padding:6px 0;color:#9ca3af;width:80px;">From</td><td style="padding:6px 0;">{safe_name} &lt;{safe_email}&gt;</td></tr>
      <tr><td style="padding:6px 0;color:#9ca3af;">IP</td><td style="padding:6px 0;font-family:'JetBrains Mono',monospace;font-size:12px;">{ip}</td></tr>
    </table>
    <div style="margin-top:20px;padding-top:16px;border-top:1px solid #1f1f23;line-height:1.55;">{safe_msg_html}</div>
    <p style="margin-top:24px;color:#6b7280;font-size:12px;">Reply directly to {safe_email} to respond.</p>
  </div></body></html>"""

    text = (
        f"Tapeline contact form\n"
        f"Subject: {subject}\n"
        f"From: {body.name} <{body.email}>\n"
        f"IP: {ip}\n\n"
        f"{body.message.strip()}\n\n"
        f"---\nReply directly to {body.email} to respond.\n"
    )

    try:
        await send_email(
            to="support@tapeline.io",
            subject=f"[Contact] {subject}",
            html=html,
            text=text,
        )
    except Exception as err:
        logger.exception("contact.send_failed ip=%s from=%s", ip, body.email)
        raise HTTPException(
            502,
            "Could not deliver right now — please email support@tapeline.io directly.",
        ) from err

    logger.info("contact.submitted ip=%s from=%s subject=%s", ip, body.email, subject[:60])
    return {"ok": True}
