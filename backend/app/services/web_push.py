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
import enum
import json
import logging
from typing import Any
from urllib.parse import urlparse

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


class PushStatus(enum.Enum):
    """What one push service said about one browser subscription.

    DELIVERED  the push service accepted the message.
    GONE       the push service answered 404 or 410: the subscription no longer
               exists and never will again. The caller deletes the row. It is
               not a delivery.
    FAILED     anything else: a 5xx, a 429, a timeout, a 403 on the VAPID
               signature, the module not configured. The row stays, and the
               caller treats the send as failed.
    """

    DELIVERED = "delivered"
    GONE = "gone"
    FAILED = "failed"

    def __bool__(self) -> bool:
        # This function used to return a bool. A caller still written as
        # `if await send_web_push(...)` must not read GONE or FAILED as a
        # success, and both would be truthy by default.
        return self is PushStatus.DELIVERED


# The push service's own word that a subscription is dead. RFC 8030 section 7.3
# says 404 or 410 for an expired subscription, and Apple, FCM and Mozilla all
# answer one of the two once the browser has unsubscribed or rotated it.
GONE_HTTP_STATUSES = frozenset({404, 410})


def _endpoint_host(endpoint: str) -> str:
    """The push service host, for logs. The rest of the URL identifies the
    subscription itself, so it never goes in a log line."""
    try:
        return (urlparse(endpoint).hostname or "").lower() or "-"
    except ValueError:
        return "-"


def _scrub(text: str, endpoint: str) -> str:
    """`text` with the endpoint URL and its path removed.

    requests and urllib3 put the request URL (or just its path) into their
    exception messages, and the path is the subscription token.
    """
    if endpoint:
        text = text.replace(endpoint, "<endpoint>")
        try:
            path = urlparse(endpoint).path
        except ValueError:
            path = ""
        if len(path) > 1:
            text = text.replace(path, "<path>")
    return text


async def send_web_push(
    subscription: dict[str, Any],
    title: str,
    body: str,
    url: str = "/app/scanner",
) -> PushStatus:
    """
    Send a push notification to one browser subscription.

    `subscription` shape (matches what pushManager.subscribe() returns):
        {"endpoint": "...", "keys": {"p256dh": "...", "auth": "..."}}

    Returns PushStatus.DELIVERED on success, PushStatus.GONE when the push
    service says the subscription no longer exists (404 or 410: the caller
    must delete the row), and PushStatus.FAILED for everything else, including
    pywebpush not installed and VAPID not configured. Every outcome of a real
    send is logged as `web_push.send_result` with the HTTP status code and the
    push service host, never the endpoint URL.
    """
    endpoint = str(subscription.get("endpoint") or "")
    host = _endpoint_host(endpoint)
    # Defence in depth: rows written before the subscribe-time allowlist existed
    # (or by any future path that skips it) must not turn this into an SSRF
    # egress. Validate at the point of the actual outbound request.
    if not is_allowed_push_endpoint(endpoint):
        logger.warning("web_push.blocked_endpoint host_not_allowlisted host=%s", host)
        return PushStatus.FAILED
    if not PYWEBPUSH_AVAILABLE:
        logger.warning("web_push.skipped reason=pywebpush_not_installed")
        return PushStatus.FAILED
    if not _vapid_configured():
        logger.warning("web_push.skipped reason=vapid_not_configured")
        return PushStatus.FAILED

    payload = json.dumps({"title": title, "body": body[:300], "url": url})

    try:
        response = await asyncio.to_thread(
            webpush,
            subscription_info=subscription,
            data=payload,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
            timeout=10,
        )
    except WebPushException as exc:
        # `is not None`, never a plain truth test: a requests.Response is falsy
        # for every 4xx and 5xx (Response.__bool__ is `.ok`), so the old
        # `... if exc.response else None` read every refusal as status None.
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None) if response is not None else None
        if status in GONE_HTTP_STATUSES:
            logger.info(
                "web_push.send_result outcome=gone http_status=%s host=%s", status, host,
            )
            return PushStatus.GONE
        logger.warning(
            "web_push.send_result outcome=failed http_status=%s host=%s error=%s",
            status, host, _scrub(str(getattr(exc, "message", exc)), endpoint)[:200],
        )
        return PushStatus.FAILED
    except Exception as exc:
        # A timeout or a connection error: no HTTP status to read. Logged
        # without the traceback, because the request URL is in it.
        logger.warning(
            "web_push.send_result outcome=failed http_status=None host=%s error=%s: %s",
            host, type(exc).__name__, _scrub(str(exc), endpoint)[:200],
        )
        return PushStatus.FAILED

    logger.info(
        "web_push.send_result outcome=delivered http_status=%s host=%s",
        getattr(response, "status_code", None), host,
    )
    return PushStatus.DELIVERED


def public_vapid_key() -> str:
    """Public VAPID key for the frontend to use when subscribing. May be empty."""
    return getattr(settings, "vapid_public_key", "") or ""
