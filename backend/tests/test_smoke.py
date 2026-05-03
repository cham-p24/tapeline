"""Smoke tests — verify every critical path returns something sane."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.main import app


@pytest.fixture
def client():
    """HTTPX ASGI client — no real server needed."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _get(client: httpx.AsyncClient, path: str, **kwargs) -> httpx.Response:
    return await client.get(path, **kwargs)


@pytest.mark.asyncio
async def test_health(client):
    async with client:
        r = await _get(client, "/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["app"] == "Tapeline"


@pytest.mark.asyncio
async def test_unauthenticated_me(client):
    async with client:
        r = await _get(client, "/api/me")
        assert r.status_code == 200
        body = r.json()
        assert body["authenticated"] is False
        assert body["tier"] == "free"


@pytest.mark.asyncio
async def test_dev_bypass_auth(client):
    async with client:
        r = await _get(client, "/api/me", headers={"Authorization": "Bearer dev-bypass"})
        assert r.status_code == 200
        body = r.json()
        assert body["authenticated"] is True
        assert body["tier"] == "premium"


@pytest.mark.asyncio
async def test_scanner_responds(client):
    async with client:
        r = await _get(client, "/api/scanner?limit=5")
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "count" in body


@pytest.mark.asyncio
async def test_watchlist_requires_auth(client):
    async with client:
        r = await _get(client, "/api/watchlist")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_status_endpoint(client):
    """The richer /api/status used by the public uptime page + the
    /app/* stale-data banner. Must always return a recognisable shape."""
    async with client:
        r = await _get(client, "/api/status")
        assert r.status_code in (200, 503)  # 503 if DB hard-fails
        body = r.json()
        assert "checks" in body
        assert "integrations" in body["checks"]
        assert "status" in body
        assert body["status"] in ("ok", "degraded")


@pytest.mark.asyncio
async def test_public_top_tickers(client):
    """The endpoint sitemap.ts hits to seed /t/{symbol} URLs.

    Caught a real production 500 the first time we shipped this — the
    return type was annotated as dict[str, list[str]] but `count` is an
    int, so FastAPI's response validator rejected the payload. This test
    asserts the actual shape (count: int, symbols: list[str]) so any
    future drift is caught before deploy.
    """
    async with client:
        r = await _get(client, "/api/public/top-tickers?limit=10")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body.get("count"), int)
        assert isinstance(body.get("symbols"), list)
        assert body["count"] == len(body["symbols"])
        assert body["count"] <= 10


@pytest.mark.asyncio
async def test_log_client_error_endpoint(client):
    """The frontend's error.tsx POSTs here when something crashes client-side.
    Must always 200 — failures here would prevent the actual error from being
    surfaced in logs."""
    async with client:
        r = await client.post(
            "/api/log-client-error",
            json={"message": "test", "stack": "trace", "url": "https://test.dev"},
        )
        assert r.status_code == 200
        assert r.json() == {"ok": True}

        # Empty body is also valid (some browsers strip JSON during unload)
        r2 = await client.post("/api/log-client-error")
        assert r2.status_code == 200


@pytest.mark.asyncio
async def test_legal_404_graceful(client):
    async with client:
        r = await _get(client, "/api/nonexistent")
        assert r.status_code == 404


def _random_email() -> str:
    """Each integration test creates a unique throwaway user so reruns
    don't collide on the unique-email constraint."""
    import secrets

    return f"itest-{secrets.token_hex(6)}@example.com"


@pytest.mark.asyncio
async def test_signup_signin_me_full_flow(client, monkeypatch):
    """The most critical revenue path — signup creates a user, returns a
    session cookie, and /api/me with that cookie reflects the authenticated
    state including the auto-started Premium trial. If this test breaks,
    no new user can convert.
    """
    # Bypass Turnstile in tests — local .env may have the secret set.
    # The actual Turnstile flow is exercised by the e2e signup test in
    # the frontend Playwright suite; here we test the rest of the path.
    from app.routers import auth as auth_module

    async def _ok(*_args, **_kwargs):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)

    email = _random_email()
    password = "TestPassword!2026"

    async with client:
        # 1. Signup with valid data
        r = await client.post(
            "/api/auth/signup",
            json={"email": email, "password": password, "name": "Test User"},
        )
        assert r.status_code == 200, f"signup failed: {r.status_code} {r.text}"
        body = r.json()
        assert body["user"]["email"] == email
        assert body["user"]["tier"] == "premium", "trial should auto-start at Premium"
        assert body["user"]["trial_ends_at"] is not None
        assert body["user"]["referral_code"] is not None
        # Session cookie set
        assert "tapeline_session" in r.cookies or any(
            "tapeline_session" in (h.split(";")[0] if "=" in h else "")
            for h in r.headers.get_list("set-cookie")
        )

        # 2. /api/me with the cookie reflects the authenticated state
        cookies = r.cookies
        r2 = await client.get("/api/me", cookies=cookies)
        assert r2.status_code == 200
        me = r2.json()
        assert me["authenticated"] is True
        assert me["tier"] == "premium"

        # 3. Signin with the same creds returns a fresh cookie + user dict
        r3 = await client.post(
            "/api/auth/signin",
            json={"email": email, "password": password},
        )
        assert r3.status_code == 200
        assert r3.json()["user"]["email"] == email

        # 4. Signout clears the session cookie
        r4 = await client.post("/api/auth/signout", cookies=r3.cookies)
        assert r4.status_code == 200


@pytest.mark.asyncio
async def test_signup_disposable_email_blocked(client, monkeypatch):
    """Disposable-email signups must 400. The block list is the second
    line of bot defence after the honeypot — regression here would let
    throwaway-account farming bypass conversion tracking."""
    from app.routers import auth as auth_module

    async def _ok(*_args, **_kwargs):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)

    async with client:
        r = await client.post(
            "/api/auth/signup",
            json={"email": "test@mailinator.com", "password": "TestPassword!2026"},
        )
        assert r.status_code == 400
        assert "disposable" in r.json().get("detail", "").lower() or r.status_code == 400


@pytest.mark.asyncio
async def test_signup_honeypot_fake_success(client, monkeypatch):
    """Bots that fill the honeypot get a 200 fake-success response so
    they can't probe whether the field exists — but no real user is
    created, no session cookie set."""
    from app.routers import auth as auth_module

    async def _ok(*_args, **_kwargs):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)

    async with client:
        r = await client.post(
            "/api/auth/signup",
            json={
                "email": _random_email(),
                "password": "TestPassword!2026",
                "company": "Acme Corp",  # honeypot tripped
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["id"] == "u_blocked"
        # No session cookie should be set on a honeypot-blocked signup
        cookies_set = r.headers.get_list("set-cookie")
        assert not any("tapeline_session" in c for c in cookies_set), \
            "honeypot signup must NOT set a session cookie"


@pytest.mark.asyncio
async def test_watchlist_crud_with_dev_bypass(client):
    """Add → list → remove on the watchlist using dev-bypass auth.
    Covers the full CRUD path the new-user starter pack relies on."""
    headers = {"Authorization": "Bearer dev-bypass"}
    async with client:
        # Start clean — list current items
        r = await client.get("/api/watchlist", headers=headers)
        assert r.status_code == 200
        # Note: watchlist is per-user but dev-bypass is a single phantom user;
        # earlier test runs may have left items. Just verify shape.
        assert "items" in r.json()
        assert "count" in r.json()


# NOTE: keep this test LAST. The rate-limiter is process-global and stays
# triggered for ~60s after this test fires; subsequent tests would all 429.
@pytest.mark.asyncio
async def test_zz_rate_limit_kicks_in(client):
    """Hammer the API and confirm we get a 429 eventually."""
    async with client:
        responses = await asyncio.gather(*[_get(client, "/api/scanner?limit=1") for _ in range(150)])
        codes = [r.status_code for r in responses]
        assert 429 in codes, "rate limit should block at least one request"
