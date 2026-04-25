"""Email delivery via Resend."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

RESEND_API = "https://api.resend.com"


async def send_email(to: str, subject: str, html: str, text: str | None = None) -> dict[str, Any]:
    """Send a single email. Returns the Resend response or raises."""
    if not settings.resend_api_key:
        logger.warning("email.skipped reason=no_api_key to=%s subject=%s", to, subject)
        return {"skipped": True}

    payload = {
        "from": f"Tapeline <{settings.email_from}>",
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{RESEND_API}/emails",
            json=payload,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()


def render_alert_email(user_name: str, rule_name: str, symbol: str, score: float, message: str) -> str:
    """Render an alert email. Minimal branded HTML."""
    return f"""<!doctype html>
<html><body style="font-family:Inter,system-ui,sans-serif;background:#0a0a0a;color:#f4f4f5;padding:24px;">
  <div style="max-width:560px;margin:0 auto;background:#121214;border-radius:12px;padding:32px;border:1px solid #1f1f23;">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:24px;">
      <div style="width:24px;height:8px;border-radius:999px;background:#3b82f6;"></div>
      <strong style="font-size:18px;">Tapeline</strong>
    </div>
    <h1 style="margin:0 0 8px;font-size:22px;">Alert: {rule_name}</h1>
    <p style="color:#9ca3af;margin:0 0 24px;">Hi {user_name}, one of your rules just triggered.</p>

    <div style="background:#0a0a0a;border-radius:8px;padding:20px;border:1px solid #1f1f23;">
      <div style="font-size:32px;font-weight:700;font-family:'JetBrains Mono',monospace;">{symbol}</div>
      <div style="margin-top:4px;color:#10b981;font-weight:500;">Score: {score:.1f}</div>
      <div style="margin-top:12px;color:#f4f4f5;">{message}</div>
    </div>

    <a href="https://tapeline.io/app/scanner" style="display:inline-block;margin-top:24px;background:#3b82f6;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none;font-weight:500;">Open dashboard &rarr;</a>

    <hr style="border:0;border-top:1px solid #1f1f23;margin:32px 0 16px;">
    <p style="color:#9ca3af;font-size:12px;margin:0;">
      <strong>Not investment advice.</strong> For informational purposes only. You're receiving this because you set up an alert at tapeline.io.
      <br><br>
      <a href="https://tapeline.io/app/alerts" style="color:#9ca3af;">Manage alerts</a>
    </p>
  </div>
</body></html>"""


def render_welcome_email(user_name: str) -> str:
    return f"""<!doctype html>
<html><body style="font-family:Inter,system-ui,sans-serif;background:#0a0a0a;color:#f4f4f5;padding:24px;">
  <div style="max-width:560px;margin:0 auto;background:#121214;border-radius:12px;padding:32px;border:1px solid #1f1f23;">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:24px;">
      <div style="width:24px;height:8px;border-radius:999px;background:#3b82f6;"></div>
      <strong style="font-size:18px;">Tapeline</strong>
    </div>
    <h1>Welcome, {user_name}.</h1>
    <p style="color:#9ca3af;">Your 14-day Pro trial is active. Here's how to get the most out of it:</p>
    <ul>
      <li><strong>Scanner</strong> — filter by score, sector, or signal. Updates every 60 seconds.</li>
      <li><strong>Squeeze Watch</strong> — BB compressions flagged before breakout.</li>
      <li><strong>Alerts</strong> — set thresholds, we email when they cross.</li>
    </ul>
    <a href="https://tapeline.io/app/scanner" style="display:inline-block;margin-top:16px;background:#3b82f6;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none;font-weight:500;">Open Tapeline &rarr;</a>
  </div>
</body></html>"""
