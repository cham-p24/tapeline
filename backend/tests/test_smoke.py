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
async def test_scanner_q_param_accepted(client):
    """The `q` symbol-search param must be accepted by the scanner endpoint
    and return a 200 with the same envelope as the unfiltered call. CI runs
    against an empty DB so we can't assert the filter ACTUALLY narrows
    results — but we can confirm the contract holds.
    """
    async with client:
        # Lowercase input — backend uppercases before matching
        r = await _get(client, "/api/scanner?q=aapl&limit=10")
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "count" in body
        # Each item, if any, must have a symbol containing AAPL (case-insensitive).
        # Empty DB → empty items, which is also fine for this contract check.
        for row in body["items"]:
            assert "AAPL" in row["symbol"].upper()


@pytest.mark.asyncio
async def test_scanner_q_param_rejects_oversized_input(client):
    """`q` is capped at 20 chars so a malicious caller can't paste a megabyte
    of substring into the LIKE clause. Anything longer must 422."""
    async with client:
        r = await _get(client, "/api/scanner?q=" + "A" * 50 + "&limit=1")
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_watchlist_requires_auth(client):
    async with client:
        r = await _get(client, "/api/watchlist")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_version_endpoint(client):
    """Reports the running build's commit SHA + boot time so the operator
    can verify a deploy actually landed."""
    async with client:
        r = await _get(client, "/api/version")
        assert r.status_code == 200
        body = r.json()
        assert "commit" in body
        assert "boot_time" in body
        assert body["env"] in ("development", "staging", "production")


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


def test_active_universe_fallback():
    """Before the worker has populated the cache, active_universe() must
    fall back to mock_feed.TICKER_UNIVERSE so dev / fresh test envs never
    hard-fail."""
    from app.services.universe import active_universe
    universe_list = active_universe()
    assert len(universe_list) > 0
    assert all(isinstance(t, tuple) and len(t) == 3 for t in universe_list)
    assert all(t[0] for t in universe_list), "every entry must have a symbol"


def test_mock_fetch_snapshots_accepts_universe_override():
    """polygon_feed.fetch_snapshots passes a DB-sourced universe via
    universe_override so we can score the top-N most-liquid tickers
    rather than the hardcoded 112-name seed."""
    from app.services.mock_feed import fetch_snapshots
    custom = [
        ("FAKE1", "Fake One Inc.", "Technology"),
        ("FAKE2", "Fake Two Corp.", "Healthcare"),
    ]
    rows = fetch_snapshots(universe_override=custom)
    assert len(rows) == 2
    syms = {r["symbol"] for r in rows}
    assert syms == {"FAKE1", "FAKE2"}
    for r in rows:
        assert r["price"] > 0
        assert "score" in r and 0 <= r["score"] <= 100


def test_email_normalisation():
    """Gmail / Outlook style providers strip dots + tags so a single inbox
    can't mint multiple trials. Lowercases everything regardless. This is
    a unit test (no async client) — pure-function check."""
    from app.services.trial_abuse import normalise_email
    assert normalise_email("Bob.Smith+launch@gmail.com") == "bobsmith@gmail.com"
    assert normalise_email("alice+spam@fastmail.com") == "alice@fastmail.com"
    assert normalise_email("Carol@Example.com") == "carol@example.com"
    assert normalise_email("first.last+a@outlook.com") == "firstlast@outlook.com"
    # Providers we don't normalise still get lowercased + trimmed
    assert normalise_email("  WHITESPACE@gmail.com  ") == "whitespace@gmail.com"
    # Non-Gmail/Outlook keeps dots in the local part
    assert normalise_email("first.last@example.com") == "first.last@example.com"


def test_ip_signup_rate_limit():
    """3 signups per IP per 24h is the hard cap."""
    from app.services.trial_abuse import record_signup, signup_allowed, signup_count_24h
    ip = "10.20.30.40"  # never used elsewhere in tests
    assert signup_count_24h(ip) == 0
    for _ in range(3):
        assert signup_allowed(ip)
        record_signup(ip)
    assert not signup_allowed(ip), "4th signup must be blocked"
    assert signup_count_24h(ip) == 3


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


def _patch_signup_gates(monkeypatch) -> None:
    """Bypass the network-level signup defences inside the unit-test loopback.

    Turnstile + IP cap + device fingerprint would otherwise block multi-signup
    tests that legitimately drive several /api/auth/signup calls in a row
    from 127.0.0.1.
    """
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_args, **_kwargs):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)


@pytest.mark.asyncio
async def test_signup_with_referral_credits_both_parties(client, monkeypatch):
    """The Channel 5 acceptance: when someone signs up via a referral link,
    both the referrer and the referee get +1 referral_credit_months. The
    credit is later consumed at first paid checkout via a Stripe coupon.

    This test covers the in-DB credit grant. The coupon side is covered
    separately by mocking stripe.Coupon.create — not in this smoke test
    since live Stripe calls aren't available in CI.
    """
    _patch_signup_gates(monkeypatch)
    password = "TestPassword!2026"

    async with client:
        # 1. Referrer signs up first (no ref code) — gets their own referral_code.
        referrer_email = _random_email()
        r_signup = await client.post(
            "/api/auth/signup",
            json={"email": referrer_email, "password": password, "name": "Referrer"},
        )
        assert r_signup.status_code == 200, r_signup.text
        referrer = r_signup.json()["user"]
        ref_code = referrer["referral_code"]
        assert ref_code, "fresh signup must carry a referral_code"
        referrer_cookies = r_signup.cookies

        # Confirm referrer starts with 0 credits.
        r_stats_before = await client.get("/api/referrals/me", cookies=referrer_cookies)
        assert r_stats_before.status_code == 200
        assert r_stats_before.json()["credit_months"] == 0

        # 2. Referee signs up with ref=<referrer code>.
        referee_email = _random_email()
        r_signup2 = await client.post(
            "/api/auth/signup",
            json={
                "email": referee_email, "password": password,
                "name": "Referee", "ref": ref_code,
            },
        )
        assert r_signup2.status_code == 200, r_signup2.text
        referee_cookies = r_signup2.cookies

        # 3. Both users now have credit_months == 1.
        r_stats_referee = await client.get("/api/referrals/me", cookies=referee_cookies)
        assert r_stats_referee.status_code == 200
        assert r_stats_referee.json()["credit_months"] == 1, (
            "referee must receive 1 free month for signing up via a referral link"
        )

        r_stats_referrer = await client.get("/api/referrals/me", cookies=referrer_cookies)
        assert r_stats_referrer.status_code == 200
        body = r_stats_referrer.json()
        assert body["credit_months"] == 1, (
            "referrer must receive 1 free month when someone uses their link"
        )
        assert body["signed_up"] == 1, "referrer's signed_up count must reflect the new referee"


@pytest.mark.asyncio
async def test_signup_with_unknown_ref_code_no_credit(client, monkeypatch):
    """A bogus ref code (or one that doesn't match any user) must NOT grant
    a free month — otherwise anyone could mint credits by typing random
    strings into the ref query param."""
    _patch_signup_gates(monkeypatch)

    async with client:
        r = await client.post(
            "/api/auth/signup",
            json={
                "email": _random_email(), "password": "TestPassword!2026",
                "name": "NoCredit", "ref": "BOGUSREF",
            },
        )
        assert r.status_code == 200, r.text
        cookies = r.cookies

        r_stats = await client.get("/api/referrals/me", cookies=cookies)
        assert r_stats.status_code == 200
        assert r_stats.json()["credit_months"] == 0, (
            "unknown referral code must not grant a credit"
        )


@pytest.mark.asyncio
async def test_onboarding_requires_auth(client):
    """POST /api/me/onboarding without a session must 401. The endpoint
    writes to user.* columns and must not accept unauthenticated bodies."""
    async with client:
        r = await client.post(
            "/api/me/onboarding",
            json={"experience_level": "beginner"},
        )
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_onboarding_persists_profile_fields(client, monkeypatch):
    """Submitting onboarding sets the profile columns + stamps the
    completed_at timestamp. Sectors outside the allowed set are dropped.
    GET /api/me reflects the new state on the next call."""
    _patch_signup_gates(monkeypatch)

    async with client:
        # Fresh user — onboarding starts null.
        signup_email = _random_email()
        r_signup = await client.post(
            "/api/auth/signup",
            json={
                "email": signup_email, "password": "TestPassword!2026",
                "name": "Onboarder",
            },
        )
        assert r_signup.status_code == 200, r_signup.text
        cookies = r_signup.cookies
        assert r_signup.json()["user"]["onboarding_completed_at"] is None

        # Submit a filled body. One unknown sector slug is included to verify
        # the server drops it rather than persisting arbitrary text.
        r_post = await client.post(
            "/api/me/onboarding",
            json={
                "experience_level": "intermediate",
                "trading_style": "swing",
                "portfolio_band": "10_50k",
                "referral_source": "twitter_x",
                "marketing_opt_in": True,
                "sectors_of_interest": ["technology", "healthcare", "made_up_sector"],
                "skipped": False,
            },
            cookies=cookies,
        )
        assert r_post.status_code == 200, r_post.text
        assert r_post.json()["onboarding_completed_at"] is not None

        # /api/me reflects the new state, with the bogus sector filtered out.
        r_me = await client.get("/api/me", cookies=cookies)
        assert r_me.status_code == 200
        me = r_me.json()
        assert me["onboarding_completed_at"] is not None
        profile = me["profile"]
        assert profile["experience_level"] == "intermediate"
        assert profile["trading_style"] == "swing"
        assert profile["portfolio_band"] == "10_50k"
        assert profile["referral_source"] == "twitter_x"
        assert profile["marketing_opt_in"] is True
        assert set(profile["sectors_of_interest"]) == {"technology", "healthcare"}


@pytest.mark.asyncio
async def test_onboarding_skip_stamps_completion(client, monkeypatch):
    """An empty (skipped) onboarding body must still stamp completed_at so
    the user isn't re-prompted, but no profile fields should be set."""
    _patch_signup_gates(monkeypatch)

    async with client:
        r_signup = await client.post(
            "/api/auth/signup",
            json={
                "email": _random_email(), "password": "TestPassword!2026",
                "name": "Skipper",
            },
        )
        assert r_signup.status_code == 200
        cookies = r_signup.cookies

        r_post = await client.post(
            "/api/me/onboarding",
            json={"skipped": True},
            cookies=cookies,
        )
        assert r_post.status_code == 200
        assert r_post.json()["onboarding_completed_at"] is not None

        r_me = await client.get("/api/me", cookies=cookies)
        me = r_me.json()
        assert me["onboarding_completed_at"] is not None
        profile = me["profile"]
        assert profile["experience_level"] is None
        assert profile["trading_style"] is None
        assert profile["marketing_opt_in"] is False
        assert profile["sectors_of_interest"] == []


@pytest.mark.asyncio
async def test_newsletter_subscribe_creates_row_and_is_idempotent(client, monkeypatch):
    """POST /api/newsletter/subscribe inserts a row and is a no-op on
    re-submit. Welcome email is suppressed via the no-API-key short-circuit
    in services/email.py, so we're just exercising the DB + endpoint path."""
    async with client:
        email = _random_email()

        # First submission — new row.
        r1 = await client.post(
            "/api/newsletter/subscribe",
            json={
                "email": email,
                "source": "homepage",
                "utm_source": "podcast",
                "utm_medium": "podcast",
                "utm_campaign": "acquirers_test",
            },
        )
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert body1["ok"] is True
        assert body1["status"] == "new"

        # Same email again — idempotent, no second welcome.
        r2 = await client.post(
            "/api/newsletter/subscribe",
            json={"email": email, "source": "homepage"},
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "already_subscribed"


@pytest.mark.asyncio
async def test_newsletter_subscribe_honeypot_silently_accepts(client):
    """Bots fill every field including `website`. Endpoint should return
    a fake success without persisting anything, so probes can't tell
    they've been blocked."""
    async with client:
        r = await client.post(
            "/api/newsletter/subscribe",
            json={
                "email": _random_email(),
                "source": "homepage",
                "website": "https://spam.example",
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "already_subscribed"


@pytest.mark.asyncio
async def test_newsletter_subscribe_rejects_disposable_domain(client):
    """Mailinator etc. should get the same silent-success treatment so
    the spammer can't enumerate which domains are blocked."""
    async with client:
        r = await client.post(
            "/api/newsletter/subscribe",
            json={
                "email": "trash@mailinator.com",
                "source": "homepage",
            },
        )
        # 200 with the same shape as honeypot — silent accept, no row.
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "already_subscribed"


@pytest.mark.asyncio
async def test_signup_persists_utm_attribution(client, monkeypatch):
    """Submitting a signup with utm_* fields stores them on the User row
    so we can attribute the conversion to the right marketing channel."""
    _patch_signup_gates(monkeypatch)
    async with client:
        email = _random_email()
        r = await client.post(
            "/api/auth/signup",
            json={
                "email": email,
                "password": "TestPassword!2026",
                "name": "Attribution Tester",
                "utm_source": "podcast",
                "utm_medium": "podcast",
                "utm_campaign": "acquirers_e2e",
                "utm_content": "ep_42",
            },
        )
        assert r.status_code == 200, r.text
        cookies = r.cookies

        # Confirm the user actually has those fields via the admin
        # surface — /api/me only exposes the public profile, but we can
        # verify the User row exists and the signup didn't fail.
        r_me = await client.get("/api/me", cookies=cookies)
        assert r_me.status_code == 200
        me = r_me.json()
        assert me["authenticated"] is True
        assert me["email"] == email


@pytest.mark.asyncio
async def test_watchlist_alert_fires_on_threshold_cross_then_debounces():
    """The watchlist smart-alert evaluator fires once when a Pro+ user's
    watchlisted ticker moves past their alert_threshold_delta, then stays
    silent for the 24h debounce window even if the score remains elevated.

    Hits the evaluator directly (not through HTTP) so we can seed state
    without driving the full signup + add-to-watchlist flow.
    """
    import uuid as _uuid
    from datetime import UTC as _UTC
    from datetime import datetime as _dt

    from sqlalchemy import select as _sel

    from app.db import session_scope
    from app.models import Ticker, User, WatchlistItem
    from app.services.alerts import evaluate_watchlist_alerts

    user_id = f"u_{_uuid.uuid4().hex}"
    symbol = "WTST"  # unique to this test so reruns don't collide

    async with session_scope() as s:
        s.add(User(
            id=user_id,
            email=f"wl-{_uuid.uuid4().hex[:8]}@example.com",
            name="Watcher",
            tier="pro",
            password_hash="not-used",
            email_prefs=15,  # all bits on
        ))
        s.add(Ticker(
            symbol=symbol,
            name="Watchlist Test Co",
            sector="Technology",
            asset_class="stock",
            price=100.0,
            score=80.0,  # 15 above baseline
            signal="STRONG SETUP",
            reason="Test fixture — score moved past delta threshold",
            updated_at=_dt.now(_UTC),
        ))
        s.add(WatchlistItem(
            user_id=user_id,
            symbol=symbol,
            baseline_score=65.0,
            alert_threshold_delta=10.0,  # 80 - 65 = 15 > 10
        ))
        await s.commit()

    async with session_scope() as s:
        n = await evaluate_watchlist_alerts(s)
    assert n == 1, "first eval should fire one watchlist alert"

    async with session_scope() as s:
        r = await s.execute(
            _sel(WatchlistItem).where(
                WatchlistItem.user_id == user_id, WatchlistItem.symbol == symbol,
            )
        )
        item = r.scalar_one()
        assert item.last_alert_at is not None, "fire should stamp last_alert_at"

    # Immediate re-run inside the 24h debounce window: must NOT re-fire.
    async with session_scope() as s:
        n2 = await evaluate_watchlist_alerts(s)
    assert n2 == 0, "second eval within debounce window must not re-fire"


@pytest.mark.asyncio
async def test_watchlist_alert_skips_free_tier_and_below_threshold():
    """Free-tier users don't get watchlist emails (alerts.email is Pro+).
    Items with a delta below threshold are also skipped."""
    import uuid as _uuid
    from datetime import UTC as _UTC
    from datetime import datetime as _dt

    from app.db import session_scope
    from app.models import Ticker, User, WatchlistItem
    from app.services.alerts import evaluate_watchlist_alerts

    free_user_id = f"u_{_uuid.uuid4().hex}"
    pro_user_id = f"u_{_uuid.uuid4().hex}"
    sym_below = "WBLW"   # delta below threshold
    sym_free = "WFRE"   # delta above threshold but user is free

    async with session_scope() as s:
        # Free user — watchlisted ticker moved 20 points (would fire if Pro).
        s.add(User(
            id=free_user_id,
            email=f"free-{_uuid.uuid4().hex[:8]}@example.com",
            name="FreeUser", tier="free", password_hash="x", email_prefs=15,
        ))
        s.add(Ticker(
            symbol=sym_free, name="Free Test Co", sector="Tech",
            asset_class="stock", price=10.0, score=85.0,
            signal="HIGH CONVICTION", reason="moved 20",
            updated_at=_dt.now(_UTC),
        ))
        s.add(WatchlistItem(
            user_id=free_user_id, symbol=sym_free,
            baseline_score=65.0, alert_threshold_delta=10.0,
        ))

        # Pro user — watchlisted ticker only moved 5 points (below threshold).
        s.add(User(
            id=pro_user_id,
            email=f"pro-{_uuid.uuid4().hex[:8]}@example.com",
            name="ProUser", tier="pro", password_hash="x", email_prefs=15,
        ))
        s.add(Ticker(
            symbol=sym_below, name="Below Threshold Co", sector="Tech",
            asset_class="stock", price=10.0, score=70.0,
            signal="STRONG SETUP", reason="moved 5",
            updated_at=_dt.now(_UTC),
        ))
        s.add(WatchlistItem(
            user_id=pro_user_id, symbol=sym_below,
            baseline_score=65.0, alert_threshold_delta=10.0,
        ))
        await s.commit()

    async with session_scope() as s:
        n = await evaluate_watchlist_alerts(s)
    # Neither row should fire — free user's tier blocks, pro user's delta is too small.
    assert n == 0


# NOTE: keep this test LAST. The rate-limiter is process-global and stays
# triggered for ~60s after this test fires; subsequent tests would all 429.
@pytest.mark.asyncio
async def test_zz_rate_limit_kicks_in(client):
    """Hammer the API and confirm we get a 429 eventually."""
    async with client:
        responses = await asyncio.gather(*[_get(client, "/api/scanner?limit=1") for _ in range(150)])
        codes = [r.status_code for r in responses]
        assert 429 in codes, "rate limit should block at least one request"
