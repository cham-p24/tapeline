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

  - **The money event happens off-session.** The 30-day trial's first charge
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
`client_ip_address` and `client_user_agent`, which Meta also requires
unhashed. `test_meta_capi.py` guards this both ways: raw email must never
appear on the wire, and fbc/fbp must appear on it verbatim.

Browser keys on events with no browser (blueprint P1-P3, 2026-09-17)
-------------------------------------------------------------------
StartTrial, Purchase and Subscribe fire from Stripe webhooks, where the
request is Stripe's: its IP address and user agent describe Stripe, never the
buyer, so they are never read there. Instead `remember_browser()` stores the
LATEST values seen on the requests the visitor's own browser sends straight to
api.tapeline.io (email signup, the OAuth callback, POST /api/billing/checkout
— each verified to bypass the Next.js /api rewrite in production on
2026-09-17), and `stored_match_keys()` reads them back for those events.
Nothing is stored while Meta is not configured: the values have no other use.
The IP address and user agent also wait for their own switch,
`META_CAPI_SEND_IP_UA` (off by default — see `client_ip_ua_enabled`).

GO-LIVE CHECKLIST (none of this is done by shipping this file)
--------------------------------------------------------------
1. Create the Meta pixel; copy its id.
2. Events Manager → Conversions API → generate an access token.
3. `fly secrets set META_PIXEL_ID=... META_CAPI_ACCESS_TOKEN=... -a tapeline-backend`
4. **Verify before spending**: set `META_CAPI_TEST_EVENT_CODE` to the code from
   Events Manager → Test Events, trigger a signup, and watch the event arrive.
   Unset it afterwards — test events do not count toward optimisation.
5. **Update the privacy policy** to name Meta as a sub-processor and describe
   what is sent (hashed email, hashed user id, event value, and — since
   2026-09-17 — the browser's IP address and user agent, the `_fbp`/`_fbc`
   values, and that the latest IP/user agent are stored). This is a legal
   prerequisite, not a nicety — do not enable the secrets before it ships.
   `app/legal/privacy/page.tsx` carries it; change it with any new field.
6. Australian advertisers targeting financial products face a separate Meta
   verification regime (`docs/META_ADS_DECISION.md` §3). That is a founder +
   lawyer step, not an engineering one.

Env vars:
    META_PIXEL_ID=<numeric pixel id>
    META_CAPI_ACCESS_TOKEN=<Events Manager CAPI token>
    META_CAPI_TEST_EVENT_CODE=<optional, verification only — unset in prod>
    META_CAPI_SEND_IP_UA=<1 to capture, store and send the browser's IP address
        and user agent; off by default — see client_ip_ua_enabled()>
"""
from __future__ import annotations

import hashlib
import ipaddress
import logging
import os
import re
import time
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Pinned Graph API version. Meta deprecates versions on a schedule; pinning
# means an upstream default change can never silently alter payload handling.
#
# The pin is only safe if someone notices when it goes stale, and nobody did:
# v21.0 sat here from #542 until 2026-09-04, by which point Meta was returning
# `x-ad-api-version-warning: You are calling a deprecated version of the Ads
# API` on EVERY live call. The warning was in the response headers the whole
# time and nothing read them.
#
# Verified against the live endpoint on 2026-09-04 (empty `data` array, so no
# event is recorded), from the production machine:
#
#   for v in v21.0 v22.0 v23.0 v24.0 v25.0; do
#     curl -s -D- -o/dev/null -X POST #       "https://graph.facebook.com/$v/<PIXEL_ID>/events" #       -H "Authorization: Bearer $META_CAPI_ACCESS_TOKEN" #       -H 'Content-Type: application/json' -d '{"data":[]}' #       | grep -i 'x-ad-api-version-warning\|facebook-api-version'
#   done
#
#   v21.0 v22.0 v23.0 -> deprecated warning
#   v24.0 v25.0       -> no warning
#
# A bogus version (v99.0) is served as v20.0 and errors with "Unknown path
# components", so an echoed `facebook-api-version` really does confirm the
# version exists — that control is what makes the result above meaningful.
#
# v24.0 rather than v25.0: one step back from newest is the conservative pin for
# a money path, and both are current. `test_graph_api_version_is_not_deprecated`
# fails if this is ever set back into the known-deprecated range.
GRAPH_API_VERSION = "v24.0"

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


def source_url(path: str | None) -> str | None:
    """Absolute page URL for `event_source_url`, or None if one cannot be built.

    Meta wants the URL of the page an event happened on whenever
    `action_source` is `website`, and it is one of the inputs to Event Match
    Quality. Every call site omitted it until 2026-09-04, so the field was
    defined and consumed here but never actually populated in production.

    `path` is a site-relative path (e.g. the `signup_landing_path` recorded on
    the user row). A protocol-relative value is flattened to `/` rather than
    joined, so a stored path can never redirect the reported source to another
    origin.
    """
    from app.config import get_settings

    base = (get_settings().app_url or "").rstrip("/")
    if not base:
        return None
    candidate = (path or "/").strip() or "/"
    if not candidate.startswith("/"):
        candidate = "/" + candidate
    if candidate.startswith("//"):
        candidate = "/"
    return f"{base}{candidate}"


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

    The cost of that choice, stated plainly: `click_time` is only as good as
    what the caller can offer. `remember_browser` passes the instant the
    browser reports capturing the click; the signup-time fallback is the
    account's `created_at`, and first-touch capture holds an fbclid for up to
    30 days, so on a delayed signup that can trail the real click by as much.
    Meta documents falling back to observation time when the true click time
    is unavailable, and matches primarily on the fbclid itself, so an
    approximate timestamp degrades nothing; an absent or malformed `_fbc`
    would. `remember_browser` does read the timestamp back, though
    (`click_time_ms`), to order two clicks — so a proxy stamp there means a
    replacement decision made on a proxy.

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


# Column widths on `users` (migration 0073). A value that does not fit is
# dropped, never truncated: a truncated cookie or user agent matches nothing.
FBP_MAX = 200
FBC_MAX = 500
CLIENT_IP_MAX = 45
CLIENT_USER_AGENT_MAX = 1024
_FBCLID_MAX = 200  # users.signup_fbclid, and what lib/utm.ts stores

# `fb.<subdomain index>.<creation ms>.<token>` — the shape the pixel writes
# for both `_fbp` and `_fbc`. Anything else is not a Meta cookie.
_BROWSER_ID_RE = re.compile(r'^fb\.[0-9]\.[0-9]{10,16}\.[^\s;,"\\]+$')
_CLICK_ID_RE = re.compile(r'^[^\s;,"\\]+$')


def browser_id(value: str | None, *, max_len: int) -> str | None:
    """A `_fbp` or `_fbc` cookie value as Meta's pixel writes it, else None.

    These arrive in a request body the browser controls, and are stored and
    later sent to Meta verbatim, so anything not shaped like the pixel's own
    value is dropped rather than repaired."""
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or len(candidate) > max_len or not candidate.isascii():
        return None
    return candidate if _BROWSER_ID_RE.match(candidate) else None


def client_ip_ua_enabled() -> bool:
    """Is sending the browser's IP address and user agent switched on?

    Separate from `is_configured()` and OFF unless `META_CAPI_SEND_IP_UA` is
    set to 1/true. Storing an IP address and user agent on the account, and
    sending them to Meta, is a new category of data: the privacy policy's
    "Changes to this policy" section promises account holders a heads-up
    email 14 days before a change like that takes effect, and no customer
    email goes out without the founder's yes. So the code ships dark and the
    switch is flipped once that notice has run. `_fbp`/`_fbc` are not behind
    it: the policy already discloses those cookies and that Meta receives
    them, and `fbp`/`fbc` were already sent on CompleteRegistration.

    Read at call time; while off nothing is captured, stored or sent, and
    values stored while it was on stop being sent the moment it is turned off.
    """
    return (os.getenv("META_CAPI_SEND_IP_UA") or "").strip().lower() in {"1", "true", "yes", "on"}


# Address ranges that can only ever be an internal hop, never a visitor:
# RFC1918, carrier-grade NAT, and IPv6 unique-local — which is where Fly's own
# private 6PN network (fdaa::/16) lives. Listed explicitly rather than using
# `is_private`, whose definition also covers the documentation ranges (192.0.2,
# 198.51.100, 203.0.113) that are a normal, public-shaped address to test with.
_PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("fc00::/7"),
)


def client_context(request: Any) -> tuple[str | None, str | None]:
    """(client_ip_address, client_user_agent) of the browser behind `request`.

    ONLY for a request the visitor's browser sends straight to the API: the
    email signup POST, the OAuth callback (a top-level navigation from the
    provider) and POST /api/billing/checkout. Never for a Stripe webhook,
    whose IP address and user agent are Stripe's.

    The IP comes from `rate_limit.client_ip`, which reads `Fly-Client-IP` —
    set by Fly's proxy from the real TCP peer, so a client cannot forge it.
    A loopback, unspecified, link-local or multicast address (local dev, the
    ASGI test client) is not a visitor and is dropped, as is a user agent that
    is empty, overlong or carries control characters, and so is an address
    from a private range (`_PRIVATE_NETWORKS`). In production `Fly-Client-IP`
    is always the public peer, so that last one is defence in depth: it means
    a future deployment behind a proxy, or a reader of the header that falls
    back to the socket, stores nothing rather than storing an address that
    identifies no visitor and would only ever dilute Meta's matching."""
    ip: str | None = None
    try:
        from app.services.rate_limit import client_ip

        addr = ipaddress.ip_address(client_ip(request).strip())
        if not (
            addr.is_loopback or addr.is_unspecified or addr.is_link_local
            or addr.is_multicast or addr.is_reserved
            or any(addr in net for net in _PRIVATE_NETWORKS if net.version == addr.version)
        ):
            ip = str(addr)
    except (ValueError, AttributeError, TypeError):
        ip = None
    ua: str | None = None
    try:
        raw_ua = (request.headers.get("user-agent") or "").strip()
        if (
            raw_ua
            and len(raw_ua) <= CLIENT_USER_AGENT_MAX
            and not any(ord(c) < 0x20 or ord(c) == 0x7F for c in raw_ua)
        ):
            ua = raw_ua
    except AttributeError:
        ua = None
    return (ip if ip and len(ip) <= CLIENT_IP_MAX else None), ua


def click_time_ms(value: str | None) -> int | None:
    """The click instant inside an `fb.<n>.<ms>.<token>` value, or None.

    Every stored `fbc` carries the time of the click it describes — the
    pixel's cookie because Meta wrote it there, ours because `fbc_value`
    builds it that way. That field is the only thing that can order two
    clicks, so it is parsed rather than trusted by arrival order."""
    if not isinstance(value, str):
        return None
    parts = value.split(".")
    if len(parts) < 4 or not parts[2].isdigit():
        return None
    return int(parts[2])


# A capture time the browser reports has to be a plausible wall-clock instant:
# after 2001 (when 13-digit epoch ms began) and no more than a day ahead of us,
# which allows for a skewed client clock without letting one park a click in
# the future where nothing could ever replace it.
_CLICK_MS_FLOOR = 1_000_000_000_000
_CLICK_MS_SKEW_ALLOWANCE = 86_400_000


def _reported_click_ms(raw: Any) -> int | None:
    """When the browser says it first saw a bare `fbclid`, in epoch ms."""
    if not isinstance(raw, int) or isinstance(raw, bool):
        return None
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    if raw < _CLICK_MS_FLOOR or raw > now_ms + _CLICK_MS_SKEW_ALLOWANCE:
        return None
    return raw


def remember_browser(
    user: Any,
    request: Any | None = None,
    *,
    fbp: str | None = None,
    fbc: str | None = None,
    fbclid: str | None = None,
    fbclid_at: int | None = None,
) -> None:
    """Store the latest browser match keys on `user` (the caller commits).

    * IP address and user agent are replaced TOGETHER from `request`, so the
      pair always describes one browser — the most recent one.
    * `fbp` replaces the stored value only when a valid one arrived: a
      browser with the pixel blocked sends none, and the older value still
      identifies this person's other browser.
    * `fbc` (P3): Meta wants the LATEST click, and "arrived most recently" is
      not the same thing. The two browser-side captures disagree by design —
      `lib/utm.ts` holds the FIRST click for 30 days, while the pixel's `_fbc`
      cookie follows the latest — and Safari caps a script-written cookie at
      7 days, so a later request routinely carries the older stored click and
      no cookie at all. So a stored click is replaced only by one that can be
      shown to be newer, comparing the click instants the values carry:
      - an `_fbc` cookie arrives with its own timestamp and is preferred over
        any bare `fbclid` in the same request, but still has to be at least as
        recent as what is stored;
      - a bare `fbclid` is stamped with `fbclid_at`, when the browser saw it,
        and may replace a stored click only when that is later. With nothing
        stored it is taken as-is (falling back to now, which Meta documents,
        when the browser sent no time).
      `signup_fbclid` — first-touch, and a different question — is never
      written here and never replaces a stored click.

    No-op while Meta is not configured — the values have no other use — and
    the IP address and user agent additionally wait for
    `client_ip_ua_enabled()`. Never raises: this sits on the signup and
    checkout paths."""
    if not is_configured():
        return
    try:
        if request is not None and client_ip_ua_enabled():
            user.meta_client_ip, user.meta_client_user_agent = client_context(request)
        fbp_value = browser_id(fbp, max_len=FBP_MAX)
        if fbp_value:
            user.meta_fbp = fbp_value
        stored = getattr(user, "meta_fbc", None) or ""
        stored_ms = click_time_ms(stored)
        fbc_cookie = browser_id(fbc, max_len=FBC_MAX)
        if fbc_cookie:
            cookie_ms = click_time_ms(fbc_cookie)
            if stored_ms is None or (cookie_ms is not None and cookie_ms >= stored_ms):
                user.meta_fbc = fbc_cookie
            return
        click = fbclid.strip() if isinstance(fbclid, str) else ""
        if not (
            click
            and len(click) <= _FBCLID_MAX
            and click.isascii()
            and _CLICK_ID_RE.match(click)
            and click != (getattr(user, "signup_fbclid", None) or "")
            and not stored.endswith(f".{click}")
        ):
            return
        seen_ms = _reported_click_ms(fbclid_at)
        if stored and (seen_ms is None or stored_ms is None or seen_ms <= stored_ms):
            # Nothing here shows this click is the later one. Keeping what we
            # have is the safe half of the trade: a stale click id matches the
            # wrong ad, a missing one only costs match quality.
            return
        seen = datetime.fromtimestamp(seen_ms / 1000, UTC) if seen_ms is not None else None
        newer = fbc_value(click, seen)
        if newer and len(newer) <= FBC_MAX:
            user.meta_fbc = newer
    except Exception:
        logger.exception("meta_capi.remember_browser_failed")


def stored_match_keys(user: Any) -> dict[str, str | None]:
    """The browser keys an event with no browser present can carry.

    For StartTrial, Purchase and Subscribe, which fire from Stripe webhooks.
    `fbc` is the most recent click id stored by `remember_browser`, falling
    back to the first-touch `signup_fbclid` stamped with the account's
    creation time. Keyword-compatible with every `track_*` helper. The IP
    address and user agent are included only while `client_ip_ua_enabled()`."""
    ip_ua = client_ip_ua_enabled()
    return {
        "fbc": getattr(user, "meta_fbc", None) or fbc_value(
            getattr(user, "signup_fbclid", None), getattr(user, "created_at", None),
        ),
        "fbp": getattr(user, "meta_fbp", None),
        "client_ip_address": getattr(user, "meta_client_ip", None) if ip_ua else None,
        "client_user_agent": getattr(user, "meta_client_user_agent", None) if ip_ua else None,
    }


async def send_event(
    *,
    event_name: str,
    event_id: str,
    email: str | None = None,
    user_id: str | None = None,
    fbc: str | None = None,
    fbp: str | None = None,
    client_ip_address: str | None = None,
    client_user_agent: str | None = None,
    custom_data: dict[str, Any] | None = None,
    event_source_url: str | None = None,
    action_source: str = "website",
) -> bool:
    """POST one event to the Conversions API.

    `fbc` is Meta's click identifier in `fb.1.<ms>.<fbclid>` form (build it
    with `fbc_value`); `fbp` is the `_fbp` first-party browser cookie the
    pixel writes. `client_ip_address` and `client_user_agent` are the
    browser's (see `client_context`). All four are OPTIONAL and all four go on
    the wire UNHASHED — see the PII section of the module docstring. They are
    the EMQ upgrade that costs no new PII (docs/PAID_ADS_METRICS_BIBLE.md §7.1).

    Returns True if Meta accepted the payload, False on any no-op or failure.
    Never raises — the return value is informational only.
    """
    creds = _credentials()
    if creds is None:
        # Silent in dev (the common case until the operator sets the secrets),
        # LOUD in production.
        #
        # This line cost real money. On 2026-08-31 a signup that arrived from a
        # paid Meta ad produced no CompleteRegistration, because the process
        # serving it had no META_* in its environment. At debug level the app
        # said nothing, Meta reported no error, and the only visible symptom was
        # an ad account optimising toward a conversion it had never once
        # observed - which is what a ~5x CPM buys you. The event is gone; the
        # silence is what made it unfindable.
        if (os.getenv("APP_ENV") or "").lower() == "production":
            logger.warning(
                "meta_capi.unconfigured event=%s - META_PIXEL_ID/"
                "META_CAPI_ACCESS_TOKEN missing in THIS process. Ad conversion "
                "not reported. Check every machine, not just one: "
                "fly ssh console --machine <id> -C 'printenv META_PIXEL_ID'",
                event_name,
            )
        else:
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
    # Same rule: plain strings, verbatim. Meta requires client_user_agent on
    # website events and matches both against what its pixel saw.
    if client_ip_address:
        user_data["client_ip_address"] = client_ip_address
    if client_user_agent:
        user_data["client_user_agent"] = client_user_agent

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
                headers={"Authorization": f"Bearer {token}"},
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
    fbc: str | None = None,
    fbp: str | None = None,
    client_ip_address: str | None = None,
    client_user_agent: str | None = None,
    event_source_url: str | None = None,
) -> bool:
    """`StartTrial` — the card-required trial began.

    This is the event a Meta campaign should OPTIMISE toward: it is the
    earliest high-intent signal that has any chance of reaching the ~50
    events/ad-set/week that smart bidding needs. `Purchase` is for reporting.

    Value stays unset (blueprint P6): a trial has earned nothing yet, and a
    plan price here would put unearned revenue into ROAS columns.
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
        fbc=fbc,
        fbp=fbp,
        client_ip_address=client_ip_address,
        client_user_agent=client_user_agent,
        event_source_url=event_source_url,
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
    fbc: str | None = None,
    fbp: str | None = None,
    client_ip_address: str | None = None,
    client_user_agent: str | None = None,
    event_source_url: str | None = None,
) -> bool:
    """`Purchase` — a DIRECT paid checkout completed, with money taken at
    checkout.

    Not a trial checkout: that charges $0 and is StartTrial's (the webhook
    skips it, blueprint P4). A trial's first real charge, about 30 days later
    with no browser involved, is `track_subscribe`.

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
        fbc=fbc,
        fbp=fbp,
        client_ip_address=client_ip_address,
        client_user_agent=client_user_agent,
        event_source_url=event_source_url,
    )


async def track_subscribe(
    *,
    user_id: str,
    subscription_id: str,
    email: str | None = None,
    value: float | None = None,
    currency: str = "USD",
    fbc: str | None = None,
    fbp: str | None = None,
    client_ip_address: str | None = None,
    client_user_agent: str | None = None,
) -> bool:
    """`Subscribe` — the first REAL charge of a subscription that began as a
    trial (blueprint P5).

    Stripe takes that charge on its own at trial end, so no browser and no
    page are involved: `action_source` is `system_generated` (Meta's own
    example for the value is an auto-pay subscription charge) and there is no
    `event_source_url`. It lands 30 days or more after the click, outside
    every click window, so it cannot feed optimisation; it is for reporting,
    audiences and the fbclid -> account -> Stripe join.

    `value` is what the invoice actually charged, not the plan's price: a
    referral, win-back or save-offer coupon changes it. `event_id` derives
    from the subscription id, hashed, so no raw Stripe id reaches Meta (which
    is also why Meta's optional `subscription_id` parameter is not sent).
    """
    custom: dict[str, Any] = {"currency": currency}
    if value is not None:
        custom["value"] = value
    return await send_event(
        event_name="Subscribe",
        event_id=event_id_for("subscribe", subscription_id),
        email=email,
        user_id=user_id,
        custom_data=custom,
        fbc=fbc,
        fbp=fbp,
        client_ip_address=client_ip_address,
        client_user_agent=client_user_agent,
        action_source="system_generated",
    )


async def track_complete_registration(*, user_id: str, email: str | None = None,
                                      method: str = "email",
                                      fbc: str | None = None,
                                      fbp: str | None = None,
                                      client_ip_address: str | None = None,
                                      client_user_agent: str | None = None,
                                      event_source_url: str | None = None) -> bool:
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
        client_ip_address=client_ip_address,
        client_user_agent=client_user_agent,
        custom_data={"content_name": method},
        event_source_url=event_source_url,
    )
