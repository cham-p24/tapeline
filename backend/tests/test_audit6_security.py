"""Round-6 audit — security fixes.

1. Rate-limit bucket key was attacker-chosen. `_client_key` returned
   "tok:" + the last 20 chars of the *unvalidated* Authorization header, so
   `Authorization: Bearer <random>` minted a fresh empty bucket per request and
   rotating it made limit_api (120/min) and limit_strict (10/min) unenforceable.
   One header opted any scraper out of rate limiting entirely.

2. Web Push endpoint was an SSRF sink. The backend POSTs to whatever endpoint a
   Pro+ user registers, and it was validated only for length — so an internal
   address (cloud metadata, a private admin port) would be requested by OUR
   server, from inside the network, on every alert fire.
"""
from __future__ import annotations

import httpx
import pytest

from app.services.rate_limit import _client_key, client_ip
from app.services.web_push import is_allowed_push_endpoint


class _Req:
    def __init__(self, headers: dict, host: str = "1.2.3.4"):
        self.headers = headers
        self.client = type("C", (), {"host": host})()


# ── 1. rate-limit bucket key ────────────────────────────────────────────────

def test_bucket_key_ignores_the_authorization_header():
    """THE REGRESSION: a rotating bearer must NOT produce distinct buckets."""
    base = {"Fly-Client-IP": "9.9.9.9"}
    k1 = _client_key(_Req({**base, "Authorization": "Bearer aaaaaaaaaaaaaaaaaaaaaaaa"}))
    k2 = _client_key(_Req({**base, "Authorization": "Bearer bbbbbbbbbbbbbbbbbbbbbbbb"}))
    k3 = _client_key(_Req(base))
    assert k1 == k2 == k3, (
        "rotating an unvalidated Authorization header must not mint new buckets"
    )
    assert k1 == "ip:9.9.9.9"


def test_bucket_key_still_separates_genuinely_different_clients():
    """The fix must not collapse everyone into one bucket."""
    a = _client_key(_Req({"Fly-Client-IP": "9.9.9.9"}))
    b = _client_key(_Req({"Fly-Client-IP": "8.8.8.8"}))
    assert a != b


def test_bucket_key_uses_the_unforgeable_fly_header():
    """Forged cf-connecting-ip / XFF must not move the key when on Fly."""
    k = _client_key(_Req({
        "Fly-Client-IP": "9.9.9.9",
        "cf-connecting-ip": "1.1.1.1",
        "X-Forwarded-For": "2.2.2.2",
    }))
    assert k == "ip:9.9.9.9"
    assert client_ip(_Req({"Fly-Client-IP": "9.9.9.9", "cf-connecting-ip": "1.1.1.1"})) == "9.9.9.9"


@pytest.mark.asyncio
async def test_rotating_bearer_no_longer_evades_the_limiter():
    """End-to-end through the real middleware: a rotating bearer from one IP
    must still hit 429."""
    from app.main import app
    from app.services import rate_limit as rl

    if hasattr(rl.limiter, "_buckets"):
        rl.limiter._buckets.clear()

    transport = httpx.ASGITransport(app=app)
    saw_429 = False
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        for i in range(200):
            r = await c.get("/api/status", headers={
                "Fly-Client-IP": "7.7.7.7",
                "Authorization": f"Bearer rotating-token-{i:04d}",
            })
            if r.status_code == 429:
                saw_429 = True
                break
    assert saw_429, "a rotating bearer must no longer bypass the rate limit"


# ── 2. Web Push SSRF ────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "https://fcm.googleapis.com/fcm/send/abc123",
    "https://updates.push.services.mozilla.com/wpush/v2/xyz",
    "https://web.push.apple.com/QABC123",
    "https://par02p.notify.windows.com/w/?token=abc",   # regional sub-domain
])
def test_real_push_endpoints_are_accepted(url):
    assert is_allowed_push_endpoint(url) is True


@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data/",          # cloud metadata
    "https://169.254.169.254/latest/meta-data/",
    "http://127.0.0.1:8080/admin",                       # loopback
    "https://10.0.0.5/internal",                         # private range
    "http://fcm.googleapis.com/fcm/send/abc",            # http downgrade
    "https://evil.com/fcm.googleapis.com",               # path lookalike
    "https://notify.windows.com.attacker.tld/x",         # suffix lookalike
    "https://fcm.googleapis.com.attacker.tld/x",         # suffix lookalike
    "",
    "not-a-url",
])
def test_ssrf_targets_are_rejected(url):
    assert is_allowed_push_endpoint(url) is False, f"{url!r} must be rejected"


@pytest.mark.asyncio
async def test_send_web_push_refuses_a_non_allowlisted_stored_row():
    """Defence in depth: rows written before the allowlist existed must not be
    POSTed to."""
    from app.services.web_push import send_web_push

    ok = await send_web_push(
        {"endpoint": "http://169.254.169.254/latest/meta-data/",
         "keys": {"p256dh": "x", "auth": "y"}},
        title="t", body="b",
    )
    assert ok is False
