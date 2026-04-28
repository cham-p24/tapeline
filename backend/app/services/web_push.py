"""
Web Push notification delivery — biggest missing channel for desktop traders.

Uses the W3C Push API + VAPID. Browsers (Chrome, Firefox, Edge, and iOS Safari
with PWA install) subscribe via a Service Worker; the resulting PushSubscription
gets POSTed to /api/me/push and stored in `web_push_subscriptions`.

Implementation note:
    pywebpush handles the messy parts (VAPID JWT signing + ECIES payload
    encryption). If it isn't installed, this module degrades to a no-op so the
    rest of the alerts pipeline keeps working. Install with:
        pip install pywebpush

Set VAPID keys in .env once configured:
    VAPID_PUBLIC_KEY=<base64url-encoded uncompressed P-256 public key>
    VAPID_PRIVATE_KEY=<base64url-encoded P-256 private scalar>
    VAPID_SUBJECT=mailto:owner@tapeline.io
    NEXT_PUBLIC_VAPID_PUBLIC_KEY=<same as VAPID_PUBLIC_KEY> (frontend reads this)

Generate keys once with: python -c "from pywebpush import webpush; print(WebPusher.generate_vapid_keys())"
or use https://vapidkeys.com/.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

try:
    from pywebpush import WebPushException, webpush  # type: ignore
    PYWEBPUSH_AVAILABLE = True
except ImportError:
    PYWEBPUSH_AVAILABLE = False
    logger.info("web_push.pywebpush_not_installed run 'pip install pywebpush' to activate")


def _vapid_configured() -> bool:
    return bool(
        getattr(settings, "vapid_private_key", "")
        and getattr(settings, "vapid_public_key", "")
        and getattr(settings, "vapid_subject", "")
    )


async def send_web_push(
    subscription: dict[str, Any],
    title: str,
    body: str,
    url: str = "/app/scanner",
) -> bool:
    """
    Send a push notification to one browser subscription.

    `subscription` shape (matches what pushManager.subscribe() returns):
        {"endpoint": "...", "keys": {"p256dh": "...", "auth": "..."}}

    Returns True on success. False if pywebpush isn't installed, VAPID isn't
    configured, or the push service rejects the delivery (e.g. 410 Gone for
    expired subscriptions — caller should delete those rows).
    """
    if not PYWEBPUSH_AVAILABLE:
        logger.warning("web_push.skipped reason=pywebpush_not_installed")
        return False
    if not _vapid_configured():
        logger.warning("web_push.skipped reason=vapid_not_configured")
        return False

    payload = json.dumps({"title": title, "body": body[:300], "url": url})

    try:
        webpush(
            subscription_info=subscription,
            data=payload,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
        )
        return True
    except WebPushException as exc:
        # 410 Gone = subscription expired, caller should delete from DB
        status = getattr(exc.response, "status_code", None) if exc.response else None
        if status == 410:
            logger.info("web_push.subscription_gone delete_recommended endpoint=%s", subscription.get("endpoint", "")[:80])
        else:
            logger.warning("web_push.send_failed status=%s exc=%s", status, str(exc)[:200])
    except Exception:
        logger.exception("web_push.send_failed_exception endpoint=%s", subscription.get("endpoint", "")[:80])
    return False


def public_vapid_key() -> str:
    """Public VAPID key for the frontend to use when subscribing. May be empty."""
    return getattr(settings, "vapid_public_key", "") or ""
