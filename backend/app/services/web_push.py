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

import asyncio
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



# Hosts real browsers hand out as Web Push endpoints. We POST to whatever is
# stored, so an unvalidated endpoint is a server-side request forgery primitive:
# a Pro+ user could register `https://169.254.169.254/...` (cloud metadata) or an
# internal admin port and have OUR server issue that request, from inside the
# network, on every alert fire.
#
# An allowlist beats blocking private IPs: hostname->IP blocklists lose to DNS
# rebinding and to redirects, while every genuine subscription comes from one of
# these four services. An unknown browser fails closed with a clear error rather
# than silently opening a hole.
ALLOWED_PUSH_HOSTS = (
    "fcm.googleapis.com",                 # Chrome / Chromium / Android
    "updates.push.services.mozilla.com",  # Firefox
    "web.push.apple.com",                 # Safari / iOS PWA
    "notify.windows.com",                 # Edge (regional sub-domains)
)


def is_allowed_push_endpoint(url: str) -> bool:
    """True if `url` is an https endpoint at a known push service.

    Anchored on a leading dot for the sub-domain case so a lookalike such as
    "evil-notify.windows.com.attacker.tld" cannot pass.
    """
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url or "")
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    return any(host == h or host.endswith("." + h) for h in ALLOWED_PUSH_HOSTS)


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
    # Defence in depth: rows written before the subscribe-time allowlist existed
    # (or by any future path that skips it) must not turn this into an SSRF
    # egress. Validate at the point of the actual outbound request.
    if not is_allowed_push_endpoint(str(subscription.get("endpoint") or "")):
        logger.warning(
            "web_push.blocked_endpoint host_not_allowlisted endpoint=%s",
            str(subscription.get("endpoint") or "")[:80],
        )
        return False
    if not PYWEBPUSH_AVAILABLE:
        logger.warning("web_push.skipped reason=pywebpush_not_installed")
        return False
    if not _vapid_configured():
        logger.warning("web_push.skipped reason=vapid_not_configured")
        return False

    payload = json.dumps({"title": title, "body": body[:300], "url": url})

    try:
        await asyncio.to_thread(
            webpush,
            subscription_info=subscription,
            data=payload,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
            timeout=10,
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
