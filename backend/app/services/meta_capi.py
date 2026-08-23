"""
Server-side conversion pipeline — Meta Conversions API (CAPI).

Why this exists
---------------
Before any money is spent on Meta, Meta has to be able to *learn*. An ad
account optimising toward a conversion it cannot observe is the mistake that
produced A$951 of Google clicks and zero signups (`PAID_MARKETING_PLAYBOOK.md`
§2: the campaign ran Maximize Clicks with no conversion import, so the account
could only ever see clicks). This module is the half that makes a Meta test
readable at all.

Browser-only pixel events are not sufficient here, for three reasons specific
to Tapeline:

  - **The money event happens off-session.** The 14-day trial's first charge
    arrives via a Stripe webhook two weeks after the click, with no browser
    involved. A pixel can never see it.
  - **The audience blocks trackers.** Self-directed traders run ad-blockers
    and tracking protection well above web average; a browser-only `Purchase`
    beacon loses a material share of real conversions.
  - **iOS/ATT.** Client-side signal loss on Meta specifically is the reason
    CAPI exists as a product.

So: the pixel reports what the browser sees, this module reports what the
server knows, and the two are stitched by a shared `event_id`.

Contract (identical posture to `services/analytics.py`)
-------------------------------------------------------
  - Fully env-gated on `META_PIXEL_ID` + `META_CAPI_ACCESS_TOKEN`. With
    either unset every function is a silent no-op — the state in dev, CI, and
    production until the operator sets the Fly secrets.
  - **Never raises.** Callers sit on the money path (Stripe webhook) and the
    signup path. An analytics hiccup must never fail a charge sync or cost
    someone their account.
  - Short timeout, fire-and-forget. Meta ingestion is best-effort; a webhook
    is not held open waiting on it.

Deduplication
-------------
Meta de-duplicates a browser event and a server event that share BOTH
`event_name` and `event_id` (within ~48h). Every helper here derives its
`event_id` deterministically from a stable id (Stripe subscription id, user
id) so the browser pixel can compute the identical value. Send both; Meta
keeps one. Sending only the server event is also correct — dedup is an
optimisation, not a requirement.

Which event to optimise toward
------------------------------
**`StartTrial`, not `Purchase`.** Smart bidding needs roughly 50 events per
ad set per week to leave the learning phase; at Tapeline's volume `Purchase`
will not reach that for a long time, while `StartTrial` plausibly can. Feed
Meta both — optimise the campaign toward `StartTrial` and use `Purchase` for
reporting and value. This is the same reasoning that puts trial signup as the
primary Google conversion in `PAID_MARKETING_PLAYBOOK.md` §1 item 5.

PII handling
------------
Meta requires hashed identifiers for match quality. Every *PII* field in
`user_data` is SHA-256 of a normalised value (lower-cased, trimmed) — Meta's
documented Advanced Matching format. Raw email never leaves this process.
`external_id` is a hash of Tapeline's own opaque user id, so it is not
reversible to a person even by Meta.

**`fbc` and `fbp` are the documented exceptions and must be sent UNHASHED.**
They are Meta's own click/browser identifiers — opaque tokens Meta issued
itself, carrying no personal data of ours to protect — and Meta matches them
by exact string. Hashing them produces NO error: the payload is accepted, the
identifier simply never matches anything, and the account ends up with a
permanently mediocre match rate that looks like bad luck. The same applies to
IP and user-agent if those are ever added. `test_meta_capi.py` guards this
both ways: raw email must never appear on the wire, and fbc/fbp must appear
on it verbatim.

GO-LIVE CHECKLIST (none of this is done by shipping this file)
--------------------------------------------------------------
1. Create the Meta pixel; copy its id.
2. Events Manager → Conversions API → generate an access token.
3. `fly secrets set META_PIXEL_ID=... META_CAPI_ACCESS_TOKEN=... -a tapeline-backend`
4. **Verify before spending**: set `META_CAPI_TEST_EVENT_CODE` to the code from
   Events Manager → Test Events, trigger a signup, and watch the event arrive.
   Unset it afterwards — test events do not count toward optimisation.
5. **Update the privacy policy** to name Meta as a sub-processor and describe
   what is sent (hashed email, hashed user id, event value). This is a legal
   prerequisite, not a nicety — do not enable the secrets before it ships.
6. Australian advertisers targeting financial products face a separate Meta
   verification regime (`docs/META_ADS_DECISION.md` §3). That is a founder +
   lawyer step, not an engineering one.

Env vars:
    META_PIXEL_ID=<numeric pixel id>
    META_CAPI_ACCESS_TOKEN=<Events Manager CAPI token>
    META_CAPI_TEST_EVENT_CODE=<optional, verification only — unset in prod>
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Pinned Graph API version. Meta deprecates versions on a schedule; pinning
# means an upstream default change can never silently alter payload handling.
GRAPH_API_VERSION = "v21.0"

# Best-effort, inline on the Stripe webhook. Two seconds mirrors the GA4
# service and stays far under Stripe's webhook timeout.
_TIMEOUT_SECONDS = 2.0


def _credentials() -> tuple[str, str] | None:
    """(pixel_id, access_token) if BOTH are configured, else None.

    Read at call time, not import time, so config changes need no restart and
    tests can monkeypatch os.environ.
    """
    pixel_id = (os.getenv("META_PIXEL_ID") or "").strip()
    token = (os.getenv("META_CAPI_ACCESS_TOKEN") or "").strip()
    if not pixel_id or not token:
        return None
    return pixel_id, token


def is_configured() -> bool:
    """True when Meta CAPI credentials are present."""
    return _credentials() is not None


def hash_pii(value: str | None) -> str | None:
    """SHA-256 of a normalised value, per Meta's Advanced Matching spec.

    Normalisation is lower-case + strip, which is what Meta hashes on their
    side; any mismatch in normalisation silently destroys match rate rather
    than erroring, so it is worth being exact. Returns None for empty input so
    callers can omit the key entirely rather than send an empty hash.
    """
    if not value:
        return None
    normalised = value.strip().lower()
    if not normalised:
        return None
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def fbc_value(fbclid: str | None, click_time: datetime | None = None) -> str | None:
    """Build Meta's `_fbc` wire value from a raw fbclid, or None.

    FORMAT MATTERS. Meta expects `fb.<subdomain_index>.<creation_ms>.<fbclid>`
    and rejects a bare fbclid outright — the version prefix and the timestamp
    are not decoration. We always emit subdomain index 1 (tapeline.io is the
    domain the cookie would belong to) and milliseconds since the epoch.

    WHERE THE FORMAT IS BUILT, and why here rather than at capture. The
    browser knows the exact instant it saw the fbclid, so constructing the
    string in `lib/utm.ts` would be marginally more accurate. It is built here
    instead so that ONE function owns the format for every event — the
    registration sent seconds after signup and, later, a StartTrial or
    Purchase fired from a Stripe webhook days afterwards, where no browser is
    involved and only the stored fbclid survives. A second construction site
    is a second thing to get wrong silently.

    The cost of that choice, stated plainly: `click_time` is the caller's best
    available proxy for the click (in practice the account's `created_at`),
    and first-touch capture holds an fbclid for up to 30 days — so on a
    delayed signup the timestamp can trail the real click by that much. Meta
    documents falling back to observation time when the true click time is
    unavailable, and matches primarily on the fbclid itself, so an approximate
    timestamp degrades nothing; an absent or malformed `_fbc` would.

    Returns None for an empty fbclid so callers can omit the key entirely.
    """
    if not fbclid:
        return None
    token = fbclid.strip()
    if not token:
        return None
    when = click_time or datetime.now(UTC)
    # A naive datetime from SQLite reads as UTC here; the value is a cookie
    # creation stamp, not an audited timestamp, so this is safe.
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return f"fb.1.{int(when.timestamp() * 1000)}.{token}"


def event_id_for(kind: str, stable_id: str) -> str:
    """Deterministic `event_id` shared by the browser pixel and this module.

    Meta de-duplicates on (event_name, event_id). Deriving the id from a
    stable identifier — a Stripe subscription id, a user id — means the two
    sides agree without passing anything between them. Hashed so a Stripe id
    is never exposed in a browser payload.
    """
    digest = hashlib.sha256(f"tapeline:{kind}:{stable_id}".encode()).hexdigest()
    return f"{kind}.{digest[:32]}"


async def send_event(
    *,
    event_name: str,
    event_id: str,
    email: str | None = None,
    user_id: str | None = None,
    fbc: str | None = None,
    fbp: str | None = None,
    custom_data: dict[str, Any] | None = None,
    event_source_url: str | None = None,
    action_source: str = "website",
) -> bool:
    """POST one event to the Conversions API.

    `fbc` is Meta's click identifier in `fb.1.<ms>.<fbclid>` form (build it
    with `fbc_value`); `fbp` is the `_fbp` first-party browser cookie the
    pixel writes. Both are OPTIONAL and both go on the wire UNHASHED — see
    the PII section of the module docstring. They are the EMQ upgrade that
    costs no new PII (docs/PAID_ADS_METRICS_BIBLE.md §7.1).

    Returns True if Meta accepted the payload, False on any no-op or failure.
    Never raises — the return value is informational only.
    """
    creds = _credentials()
    if creds is None:
        # Silent no-op: the common case until the operator sets the secrets.
        logger.debug("meta_capi.unconfigured event=%s", event_name)
        return False
    pixel_id, token = creds

    # Meta wants each identifier as a list of hashes.
    user_data: dict[str, Any] = {}
    hashed_email = hash_pii(email)
    if hashed_email:
        user_data["em"] = [hashed_email]
    hashed_uid = hash_pii(user_id)
    if hashed_uid:
        user_data["external_id"] = [hashed_uid]
    # NOT hashed, and not lists. `fbc`/`fbp` are Meta's own opaque tokens,
    # matched by exact string — hashing them is accepted silently and matches
    # nothing, which is worse than omitting them because it looks like it
    # worked. Do not "tidy" these into hash_pii().
    if fbc:
        user_data["fbc"] = fbc
    if fbp:
        user_data["fbp"] = fbp

    event: dict[str, Any] = {
        "event_name": event_name,
        "event_time": int(time.time()),
        "event_id": event_id,
        "action_source": action_source,
        "user_data": user_data,
    }
    if event_source_url:
        event["event_source_url"] = event_source_url
    if custom_data:
        event["custom_data"] = custom_data

    payload: dict[str, Any] = {"data": [event]}
    # Present only while verifying in Events Manager. Test events are excluded
    # from optimisation, so leaving this set in production would quietly stop
    # the campaign learning — hence the explicit warning below.
    test_code = (os.getenv("META_CAPI_TEST_EVENT_CODE") or "").strip()
    if test_code:
        payload["test_event_code"] = test_code
        logger.warning(
            "meta_capi.test_mode event=%s code=%s — events are NOT counted for "
            "optimisation while META_CAPI_TEST_EVENT_CODE is set",
            event_name, test_code,
        )

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                f"https://graph.facebook.com/{GRAPH_API_VERSION}/{pixel_id}/events",
                params={"access_token": token},
                json=payload,
            )
        if resp.status_code >= 300:
            # Meta returns a JSON error body with a useful message; log it at
            # warning so a misconfigured token surfaces without failing a charge.
            logger.warning(
                "meta_capi.rejected event=%s status=%s body=%s",
                event_name, resp.status_code, resp.text[:400],
            )
            return False
        logger.info("meta_capi.sent event=%s id=%s", event_name, event_id)
        return True
    except Exception:
        logger.exception("meta_capi.send_failed event=%s", event_name)
        return False


async def track_start_trial(
    *,
    user_id: str,
    email: str | None = None,
    value: float | None = None,
    currency: str = "USD",
) -> bool:
    """`StartTrial` — the card-required trial began.

    This is the event a Meta campaign should OPTIMISE toward: it is the
    earliest high-intent signal that has any chance of reaching the ~50
    events/ad-set/week that smart bidding needs. `Purchase` is for reporting.
    """
    custom: dict[str, Any] = {"currency": currency}
    if value is not None:
        custom["value"] = value
    return await send_event(
        event_name="StartTrial",
        event_id=event_id_for("trial", user_id),
        email=email,
        user_id=user_id,
        custom_data=custom,
    )


async def track_purchase(
    *,
    user_id: str,
    transaction_id: str,
    email: str | None = None,
    value: float | None = None,
    currency: str = "USD",
    tier: str | None = None,
    billing_period: str | None = None,
) -> bool:
    """`Purchase` — the first real charge succeeded.

    `transaction_id` MUST be the Stripe id the browser beacon would use for
    the same checkout, so the derived `event_id` matches and Meta counts the
    sale once rather than twice.
    """
    custom: dict[str, Any] = {"currency": currency}
    if value is not None:
        custom["value"] = value
    if tier:
        custom["content_name"] = tier
    if billing_period:
        custom["content_category"] = billing_period
    return await send_event(
        event_name="Purchase",
        event_id=event_id_for("purchase", transaction_id),
        email=email,
        user_id=user_id,
        custom_data=custom,
    )


async def track_complete_registration(*, user_id: str, email: str | None = None,
                                      method: str = "email",
                                      fbc: str | None = None,
                                      fbp: str | None = None) -> bool:
    """`CompleteRegistration` — an account was created (no card yet).

    Lower intent than StartTrial now that the trial is card-required (#536).

    The pre-existing note here — "reported, NOT the optimisation target" —
    reads backwards against the campaign plan that has since been written, and
    is corrected rather than left standing: `PAID_ADS_METRICS_BIBLE.md` §7.2
    makes this the ad set's optimisation event *precisely because* the
    card-required trial is scarce, and Meta needs ~50 events/week to leave
    learning. Which event a campaign optimises toward is an Ads Manager
    setting, not a code path — all three still flow from here regardless.

    That is why `fbc`/`fbp` matter most on this event: match quality on the
    OPTIMISATION event is what the delivery model learns from.
    """
    return await send_event(
        event_name="CompleteRegistration",
        event_id=event_id_for("signup", user_id),
        email=email,
        user_id=user_id,
        fbc=fbc,
        fbp=fbp,
        custom_data={"content_name": method},
    )
