"""
Server-side conversion pipeline — GA4 Measurement Protocol.

Why this exists
---------------
Tapeline's conversions were, until now, *only* client-side beacons:

  - `purchase` / `subscribe` fired from `/app/billing?checkout=success`, i.e.
    a redirect-return page. Anything that stops that page from executing —
    the customer closing the tab at Stripe, a failed redirect, or (very
    common in a trader audience) an ad-blocker or tracking-protection
    setting — loses the conversion outright. Meanwhile the Stripe webhook
    reliably sees *every* charge, server-side, with no client involved.
  - `sign_up` had no server-side record at all, so a blocked or crashed
    client made a real account creation invisible to GA4.

This module is the server-side half. It posts events straight to GA4's
Measurement Protocol from the backend, where no browser can drop them.

Deliberately NOT here: the Google Ads **offline conversion upload**. See
`docs/AUTONOMY.md` ("Decided against — server-side conversion upload"):
`UploadClickConversions` fails for any developer token with no prior upload
history, and Tapeline's Ads account is brand new. That half stays
client-side (`lib/gtag.ts`) until/unless the Data Manager API is wired up.

Contract
--------
Every function here is **fire-and-forget and non-fatal**:

  - Fully env-gated on `GA4_MEASUREMENT_ID` + `GA4_API_SECRET`. With either
    unset this module is a silent no-op — which is the state in dev, in CI,
    and in prod until the operator sets them on Fly.
  - Never raises. Callers sit on the money path (Stripe webhook) and the
    signup path (OAuth callback); an analytics hiccup must never fail a
    charge sync or lose a customer their account.
  - Short timeout. GA4 ingestion is best-effort; we will not hold a webhook
    open waiting on it.

Env vars (set on Fly for this to actually transmit):
    GA4_MEASUREMENT_ID=G-XXXXXXXXXX   (the web stream's measurement ID)
    GA4_API_SECRET=<secret>           (Admin → Data Streams → Measurement
                                       Protocol API secrets → Create)
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GA4_ENDPOINT = "https://www.google-analytics.com/mp/collect"

# GA4 ingestion is best-effort and sits inline on the Stripe webhook / OAuth
# callback. Two seconds is generous for a fire-and-forget POST and still far
# under Stripe's webhook timeout.
_TIMEOUT_SECONDS = 2.0


def _credentials() -> tuple[str, str] | None:
    """(measurement_id, api_secret) if BOTH are configured, else None.

    Read from the environment at call time rather than import time so the
    module picks up config without a process restart, and so tests can
    monkeypatch os.environ.
    """
    measurement_id = (os.getenv("GA4_MEASUREMENT_ID") or "").strip()
    api_secret = (os.getenv("GA4_API_SECRET") or "").strip()
    if not measurement_id or not api_secret:
        return None
    return measurement_id, api_secret


def is_configured() -> bool:
    """True when GA4 Measurement Protocol credentials are present."""
    return _credentials() is not None


def synthetic_client_id(seed: str) -> str:
    """A stable, GA4-shaped pseudonymous `client_id` derived from `seed`.

    The Measurement Protocol requires a `client_id`, but a webhook has no
    browser and therefore no `_ga` cookie to read. We derive a deterministic
    stand-in from the user id so all server-side events for one user share a
    client_id (GA4 stitches them by `user_id` anyway).

    Shape mirrors a real GA4 client id ("<random>.<timestamp>") so GA4's
    validator accepts it. It is a one-way hash of an internal opaque id — no
    PII and not reversible to an email address.
    """
    digest = hashlib.sha256(f"tapeline:{seed}".encode()).hexdigest()
    return f"{int(digest[:8], 16)}.{int(digest[8:16], 16)}"


async def send_event(
    *,
    name: str,
    params: dict[str, Any] | None = None,
    client_id: str,
    user_id: str | None = None,
) -> bool:
    """POST one event to the GA4 Measurement Protocol.

    Returns True if GA4 accepted the payload, False on any no-op or failure.
    Never raises — callers treat the return value as informational only.
    """
    creds = _credentials()
    if creds is None:
        # Silent no-op: the overwhelmingly common case (dev, CI, and prod
        # until the operator sets the Fly secrets). Debug-level so it can be
        # confirmed when wiring up, without spamming production logs.
        logger.debug("analytics.ga4_unconfigured event=%s", name)
        return False
    measurement_id, api_secret = creds

    payload: dict[str, Any] = {
        "client_id": client_id,
        # non_personalized_ads=False keeps these events usable for the ads
        # audience/ROAS reporting they exist to feed.
        "non_personalized_ads": False,
        "events": [{"name": name, "params": params or {}}],
    }
    if user_id:
        payload["user_id"] = user_id

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                GA4_ENDPOINT,
                params={"measurement_id": measurement_id, "api_secret": api_secret},
                json=payload,
            )
        # GA4 answers 2xx (usually 204) for accepted payloads and never
        # reports validation errors on the production endpoint — a 2xx is
        # the only signal available here.
        if resp.status_code >= 300:
            logger.warning(
                "analytics.ga4_rejected event=%s status=%s", name, resp.status_code,
            )
            return False
        logger.info("analytics.ga4_sent event=%s user=%s", name, user_id or "-")
        return True
    except Exception:
        # Non-fatal by contract: the caller is a Stripe webhook or an OAuth
        # signup. Log and move on.
        logger.exception("analytics.ga4_send_failed event=%s", name)
        return False


async def track_purchase(
    *,
    user_id: str,
    transaction_id: str,
    value: float | None = None,
    currency: str = "USD",
    tier: str | None = None,
    billing_period: str | None = None,
) -> bool:
    """Server-side `purchase` conversion, fired from the Stripe webhook.

    `transaction_id` MUST be the Stripe id the client-side beacon would use
    for the same checkout. GA4 de-duplicates `purchase` events sharing a
    transaction_id, so a customer whose success page *did* execute is
    counted once, not twice.
    """
    params: dict[str, Any] = {"transaction_id": transaction_id, "currency": currency}
    if value is not None:
        params["value"] = value
    if tier:
        params["tier"] = tier
    if billing_period:
        params["billing_period"] = billing_period
    return await send_event(
        name="purchase",
        params=params,
        client_id=synthetic_client_id(user_id),
        user_id=user_id,
    )


async def track_sign_up(*, user_id: str, method: str) -> bool:
    """Server-side `sign_up` conversion, keyed on our own user id.

    `method` is the signup path ("google" / "microsoft" / "apple"), matching
    the `method` param the client-side sign_up beacon sends.
    """
    return await send_event(
        name="sign_up",
        params={"method": method},
        client_id=synthetic_client_id(user_id),
        user_id=user_id,
    )
