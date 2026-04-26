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


def _shell(body_html: str) -> str:
    """Wrap body content in the standard Tapeline email shell."""
    return f"""<!doctype html>
<html><body style="font-family:Inter,system-ui,sans-serif;background:#0a0a0a;color:#f4f4f5;padding:24px;margin:0;">
  <div style="max-width:560px;margin:0 auto;background:#121214;border-radius:12px;padding:32px;border:1px solid #1f1f23;">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:24px;">
      <div style="width:24px;height:8px;border-radius:999px;background:#3b82f6;"></div>
      <strong style="font-size:18px;">Tapeline</strong>
    </div>
    {body_html}
    <hr style="border:0;border-top:1px solid #1f1f23;margin:32px 0 16px;">
    <p style="color:#6b7280;font-size:11px;margin:0;">
      <strong>Not investment advice.</strong> For informational purposes only.
      <br><br>
      <a href="https://tapeline.io/app/account" style="color:#9ca3af;">Manage notifications</a>
      &nbsp;·&nbsp;
      <a href="https://tapeline.io/app/billing" style="color:#9ca3af;">Billing</a>
    </p>
  </div>
</body></html>"""


def render_welcome_email(user_name: str) -> str:
    """Day 0 — sent immediately on signup."""
    return _shell(f"""
    <h1 style="margin:0 0 12px;font-size:26px;">Welcome, {user_name}.</h1>
    <p style="color:#d1d5db;margin:0 0 16px;">Your <strong>14-day Premium trial</strong> is live. Everything's unlocked.</p>
    <p style="color:#9ca3af;margin:0 0 20px;">Three things to try in the first five minutes:</p>
    <ol style="color:#d1d5db;line-height:1.7;padding-left:20px;margin:0 0 24px;">
      <li><strong>Scanner</strong> — see every ticker scored, hover any score for the 6-factor breakdown</li>
      <li><strong>Public scorecard</strong> — every call we've ever made, with the original reasoning</li>
      <li><strong>Watchlist</strong> — add 5–10 tickers you're following, get smart alerts when scores shift</li>
    </ol>
    <a href="https://tapeline.io/app/scanner" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:500;">Open the scanner &rarr;</a>
    <p style="color:#6b7280;margin-top:24px;font-size:13px;">No card on file. We'll remind you before the trial ends.</p>
    """)


def render_trial_day3_email(user_name: str) -> str:
    """Day 3 — feature tour, what they may have missed."""
    return _shell(f"""
    <h1 style="margin:0 0 12px;font-size:24px;">{user_name}, three days in.</h1>
    <p style="color:#d1d5db;margin:0 0 16px;">If you've only been on the scanner, here's what else is in your trial:</p>
    <div style="background:#0a0a0a;border:1px solid #1f1f23;border-radius:8px;padding:18px;margin:16px 0;">
      <div style="margin-bottom:14px;">
        <strong style="color:#3b82f6;">🔥 Squeeze Watch</strong>
        <p style="color:#9ca3af;margin:4px 0 0;font-size:14px;">Bollinger Band compressions flagged before they break. Eight setups updated live.</p>
      </div>
      <div style="margin-bottom:14px;">
        <strong style="color:#3b82f6;">🏛️ Congress Trades</strong>
        <p style="color:#9ca3af;margin:4px 0 0;font-size:14px;">Politicians' disclosed buys and sells. House and Senate, by ticker.</p>
      </div>
      <div style="margin-bottom:14px;">
        <strong style="color:#3b82f6;">💼 Elite Holdings</strong>
        <p style="color:#9ca3af;margin:4px 0 0;font-size:14px;">Latest 13F positions from Buffett, Burry, Tepper, Ackman, and four more.</p>
      </div>
      <div>
        <strong style="color:#3b82f6;">📲 Telegram alerts</strong>
        <p style="color:#9ca3af;margin:4px 0 0;font-size:14px;">Hourly digest of your watchlist + market regime, delivered to your phone.</p>
      </div>
    </div>
    <a href="https://tapeline.io/app/holdings" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:500;">Try a Premium feature &rarr;</a>
    """)


def render_trial_day7_email(user_name: str) -> str:
    """Day 7 — halfway. Reminder + nudge to add a card."""
    return _shell(f"""
    <h1 style="margin:0 0 12px;font-size:24px;">Halfway through your trial, {user_name}.</h1>
    <p style="color:#d1d5db;margin:0 0 16px;">Seven days left of full Premium access.</p>
    <p style="color:#9ca3af;margin:0 0 20px;">When the trial ends, your account drops to Free — top 20 tickers, 24-hour delayed, no alerts. To keep what you have, add a card.</p>
    <div style="background:#0a0a0a;border:1px solid #1f1f23;border-radius:8px;padding:20px;margin:16px 0;">
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px;">
        <strong style="font-size:18px;">Pro</strong>
        <span style="font-size:22px;font-weight:700;">$29<span style="font-size:14px;color:#9ca3af;">/mo</span></span>
      </div>
      <p style="color:#9ca3af;margin:0;font-size:13px;">Full live scanner, squeeze, regime, watchlist, email alerts, daily briefing.</p>
    </div>
    <div style="background:#121214;border:1px solid #3b82f6;border-radius:8px;padding:20px;margin:16px 0;">
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px;">
        <strong style="font-size:18px;color:#3b82f6;">Premium</strong>
        <span style="font-size:22px;font-weight:700;">$49<span style="font-size:14px;color:#9ca3af;">/mo</span></span>
      </div>
      <p style="color:#9ca3af;margin:0;font-size:13px;">Everything in Pro + Congress + Telegram unlimited + API + elite 13F holdings.</p>
    </div>
    <a href="https://tapeline.io/app/billing" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:500;margin-top:8px;">Add a card &rarr;</a>
    <p style="color:#6b7280;margin-top:18px;font-size:13px;">7-day money back, cancel anytime in one click.</p>
    """)


def render_trial_day13_email(user_name: str) -> str:
    """Day 13 — final urgency. Trial ends tomorrow."""
    return _shell(f"""
    <h1 style="margin:0 0 12px;font-size:24px;color:#f59e0b;">Trial ends tomorrow.</h1>
    <p style="color:#d1d5db;margin:0 0 16px;">{user_name}, your Premium trial expires in less than 24 hours.</p>
    <p style="color:#9ca3af;margin:0 0 20px;">If you don't add a card, your account drops to Free at expiry — the scanner shows yesterday's data on 20 tickers, no alerts, no Telegram, no Congress feed.</p>
    <a href="https://tapeline.io/app/billing" style="display:inline-block;background:#f59e0b;color:#0a0a0a;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:600;margin-top:8px;">Keep my account active &rarr;</a>
    <p style="color:#6b7280;margin-top:24px;font-size:13px;">7-day money back. One-click cancel. No phone calls.</p>
    """)


def render_trial_ended_email(user_name: str) -> str:
    """Sent on actual downgrade — soft re-engagement."""
    return _shell(f"""
    <h1 style="margin:0 0 12px;font-size:24px;">Your trial just ended, {user_name}.</h1>
    <p style="color:#d1d5db;margin:0 0 16px;">Your account is now on the Free plan. Your watchlist and settings are intact — only the data feed changes.</p>
    <p style="color:#9ca3af;margin:0 0 20px;">If you want live data + alerts back, the door is always open:</p>
    <a href="https://tapeline.io/app/billing" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:500;">See plans &rarr;</a>
    <p style="color:#6b7280;margin-top:24px;font-size:13px;">No hard feelings if not. The public scorecard stays free for everyone, forever.</p>
    """)


# Drip orchestration — the worker hooks below. Wiring is intentionally minimal
# until Resend is configured (no API key = send_email() returns {"skipped": True}).
# When the key arrives, add this to signal_publisher.py tick():
#
#   global _last_drip_check
#   if _last_drip_check is None or (started - _last_drip_check).total_seconds() >= 86400:
#       from app.services.email import run_daily_drip
#       async with session_scope() as s:
#           await run_daily_drip(s)
#       _last_drip_check = started
#
# Note: this MVP version may double-send if the worker restarts mid-day.
# To guard against that, add a `drip_state` JSON column to User and check it
# before each send. That's a one-line migration but waits until Resend lands.

async def run_daily_drip(session) -> dict[str, int]:
    """
    Send the day-3, day-7, day-13 emails to users whose trial-end date
    matches the corresponding window. Returns counts per stage.

    Day calculation: trial is 14 days, so:
      - Day 3 email: trial_ends_at is between (now+10d, now+11d)
      - Day 7 email: trial_ends_at is between (now+6d,  now+7d)
      - Day 13 email: trial_ends_at is between (now+0d, now+1d)
    """
    from datetime import UTC, datetime, timedelta
    from sqlalchemy import select
    from app.models import User

    now = datetime.now(UTC)
    counts = {"day3": 0, "day7": 0, "day13": 0}

    windows = [
        ("day3",  now + timedelta(days=10), now + timedelta(days=11), render_trial_day3_email),
        ("day7",  now + timedelta(days=6),  now + timedelta(days=7),  render_trial_day7_email),
        ("day13", now,                       now + timedelta(days=1),  render_trial_day13_email),
    ]
    for label, lower, upper, renderer in windows:
        result = await session.execute(
            select(User).where(
                User.trial_ends_at.isnot(None),
                User.trial_ends_at >= lower,
                User.trial_ends_at < upper,
                User.tier.in_(["pro", "premium"]),
                User.stripe_customer_id.is_(None),
            )
        )
        users = result.scalars().all()
        for user in users:
            html = renderer(user.name or "trader")
            subject_map = {
                "day3":  "Tapeline — three days in",
                "day7":  "Tapeline — halfway through your trial",
                "day13": "Tapeline — your trial ends tomorrow",
            }
            try:
                await send_email(user.email, subject_map[label], html)
                counts[label] += 1
            except Exception:
                logger.exception("drip.send_failed user=%s stage=%s", user.id, label)

    return counts
