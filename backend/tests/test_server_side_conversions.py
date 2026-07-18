"""Server-side conversion pipeline — GA4 Measurement Protocol + OAuth attribution.

Three verified leaks, closed:

  A) The `purchase` conversion existed ONLY as a client-side beacon on the
     Stripe redirect-return page (/app/billing?checkout=success). Closed tabs,
     failed redirects and ad-blockers (high prevalence in a trader audience)
     lost it outright. The Stripe webhook sees every charge, so it now fires
     the conversion server-side — once per subscription, with the Stripe
     checkout-session id as transaction_id so GA4 de-dupes against the client
     beacon rather than double-counting.

  B) `sign_up` likewise had no server-side record — a blocked client made a
     real account invisible to GA4/Ads. The OAuth callback now reports it.

  C) OAuth signups (the designed-PRIMARY signup path) stored NO UTM/gclid
     attribution, so channel ROI was uncomputable for most signups. The
     values now ride the same short-lived cookie as the `?next=` intent and
     land on the User row exactly as the email path writes them.

No network anywhere: `analytics.httpx` is stubbed, and the OAuth provider
round-trip is faked the same way test_oauth_intent_carry.py does it.
"""
from __future__ import annotations

import uuid as _uuid
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode

import httpx
import pytest
from sqlalchemy import select

import app.routers.oauth as oauth_module
import app.services.analytics as analytics
from app.db import session_scope
from app.main import app
from app.models import StripeWebhookEvent, User
from app.routers.webhooks import _send_purchase_conversion


# ── stubs ────────────────────────────────────────────────────────────────────

class _Recorder:
    """Stand-in for the `httpx` surface analytics.send_event touches.

    Records every GA4 POST so tests can assert on the payload without a
    network call.
    """

    def __init__(self, status_code: int = 204):
        self.calls: list[dict] = []
        self._status = status_code

    def AsyncClient(self, *a, **k):  # noqa: N802 — mirrors httpx's name
        recorder = self

        class _Resp:
            status_code = recorder._status

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, params=None, json=None, **k):
                recorder.calls.append({"url": url, "params": params, "json": json})
                return _Resp()

        return _Client()


@pytest.fixture
def ga4_configured(monkeypatch):
    """GA4 credentials present + transport stubbed. Yields the recorder."""
    monkeypatch.setenv("GA4_MEASUREMENT_ID", "G-TESTID123")
    monkeypatch.setenv("GA4_API_SECRET", "test-secret")
    rec = _Recorder()
    monkeypatch.setattr(analytics, "httpx", rec)
    return rec


@pytest.fixture
def ga4_unset(monkeypatch):
    """No GA4 credentials — the state in dev, CI, and prod until the operator
    sets the Fly secrets. Transport is still stubbed so a regression that
    ignored the gate would be caught by the recorder rather than by a real
    outbound request."""
    monkeypatch.delenv("GA4_MEASUREMENT_ID", raising=False)
    monkeypatch.delenv("GA4_API_SECRET", raising=False)
    rec = _Recorder()
    monkeypatch.setattr(analytics, "httpx", rec)
    return rec


# ── A1: the MP client no-ops cleanly when env is unset ──────────────────────

def test_not_configured_without_env(ga4_unset):
    assert analytics.is_configured() is False


def test_configured_requires_both_vars(monkeypatch):
    monkeypatch.setenv("GA4_MEASUREMENT_ID", "G-ONLYID")
    monkeypatch.delenv("GA4_API_SECRET", raising=False)
    assert analytics.is_configured() is False

    monkeypatch.delenv("GA4_MEASUREMENT_ID", raising=False)
    monkeypatch.setenv("GA4_API_SECRET", "only-secret")
    assert analytics.is_configured() is False


def test_blank_env_counts_as_unset(monkeypatch):
    """Fly secrets set to an empty string must not be treated as configured."""
    monkeypatch.setenv("GA4_MEASUREMENT_ID", "   ")
    monkeypatch.setenv("GA4_API_SECRET", "   ")
    assert analytics.is_configured() is False


@pytest.mark.asyncio
async def test_send_event_is_silent_noop_when_unset(ga4_unset):
    """No exception, no request, False return — never blocks the caller."""
    ok = await analytics.send_event(name="sign_up", client_id="1.2", params={})
    assert ok is False
    assert ga4_unset.calls == []


@pytest.mark.asyncio
async def test_track_helpers_noop_when_unset(ga4_unset):
    assert await analytics.track_purchase(
        user_id="u_1", transaction_id="cs_1", value=99.0,
    ) is False
    assert await analytics.track_sign_up(user_id="u_1", method="google") is False
    assert ga4_unset.calls == []


@pytest.mark.asyncio
async def test_send_event_never_raises_on_transport_error(monkeypatch):
    """A GA4 outage must not surface to the Stripe webhook / OAuth callback."""
    monkeypatch.setenv("GA4_MEASUREMENT_ID", "G-TESTID123")
    monkeypatch.setenv("GA4_API_SECRET", "test-secret")

    class _Boom:
        def AsyncClient(self, *a, **k):  # noqa: N802
            raise RuntimeError("network down")

    monkeypatch.setattr(analytics, "httpx", _Boom())
    assert await analytics.send_event(name="purchase", client_id="1.2") is False


@pytest.mark.asyncio
async def test_send_event_returns_false_on_non_2xx(monkeypatch):
    monkeypatch.setenv("GA4_MEASUREMENT_ID", "G-TESTID123")
    monkeypatch.setenv("GA4_API_SECRET", "test-secret")
    monkeypatch.setattr(analytics, "httpx", _Recorder(status_code=400))
    assert await analytics.send_event(name="purchase", client_id="1.2") is False


def test_synthetic_client_id_is_stable_and_ga4_shaped():
    a = analytics.synthetic_client_id("u_abc")
    assert a == analytics.synthetic_client_id("u_abc"), "must be deterministic"
    assert a != analytics.synthetic_client_id("u_xyz")
    left, _, right = a.partition(".")
    assert left.isdigit() and right.isdigit(), f"not GA4-shaped: {a}"


@pytest.mark.asyncio
async def test_send_event_payload_shape(ga4_configured):
    await analytics.send_event(
        name="sign_up", params={"method": "google"},
        client_id="123.456", user_id="u_9",
    )
    assert len(ga4_configured.calls) == 1
    call = ga4_configured.calls[0]
    assert call["url"] == analytics.GA4_ENDPOINT
    assert call["params"] == {
        "measurement_id": "G-TESTID123", "api_secret": "test-secret",
    }
    body = call["json"]
    assert body["client_id"] == "123.456"
    assert body["user_id"] == "u_9"
    assert body["events"] == [{"name": "sign_up", "params": {"method": "google"}}]


# ── A2: purchase fires once per subscription, with the Stripe id ────────────

def _checkout_obj(session_id: str, subscription_id: str) -> dict:
    """Minimal checkout.session.completed data.object."""
    return {
        "id": session_id,
        "subscription": subscription_id,
        "amount_total": 27900,  # minor units — $279.00
        "currency": "usd",
    }


@pytest.mark.asyncio
async def test_purchase_fires_once_per_subscription(ga4_configured):
    sub_id = f"sub_{_uuid.uuid4().hex[:16]}"
    obj = _checkout_obj(f"cs_{_uuid.uuid4().hex[:16]}", sub_id)

    async with session_scope() as s:
        await _send_purchase_conversion(
            s, user_id="u_conv", obj=obj, tier="premium", billing_period="annual",
        )
        # A SECOND checkout.session.completed for the same subscription (the
        # duplicate-tab case the webhook explicitly handles) must not send a
        # second conversion.
        await _send_purchase_conversion(
            s, user_id="u_conv",
            obj=_checkout_obj(f"cs_{_uuid.uuid4().hex[:16]}", sub_id),
            tier="premium", billing_period="annual",
        )

    assert len(ga4_configured.calls) == 1, "conversion double-counted"

    event = ga4_configured.calls[0]["json"]["events"][0]
    assert event["name"] == "purchase"
    # transaction_id is the Stripe checkout-session id — the same id a client
    # beacon carries, which is how GA4 de-dupes the two reports of one sale.
    assert event["params"]["transaction_id"] == obj["id"]
    assert event["params"]["value"] == 279.0, "amount_total is in minor units"
    assert event["params"]["currency"] == "USD"
    assert event["params"]["tier"] == "premium"
    assert event["params"]["billing_period"] == "annual"
    assert ga4_configured.calls[0]["json"]["user_id"] == "u_conv"

    async with session_scope() as s:
        latch = (await s.execute(
            select(StripeWebhookEvent).where(
                StripeWebhookEvent.id == f"ga4_purchase:{sub_id}"
            )
        )).scalar_one()
        await s.delete(latch)
        await s.commit()


@pytest.mark.asyncio
async def test_purchase_noop_and_no_latch_when_ga4_unset(ga4_unset):
    """Unconfigured must leave no trace — importantly no latch row, so
    turning GA4 on later doesn't find every subscription pre-suppressed."""
    sub_id = f"sub_{_uuid.uuid4().hex[:16]}"
    async with session_scope() as s:
        await _send_purchase_conversion(
            s, user_id="u_noop", obj=_checkout_obj("cs_noop", sub_id),
        )
    assert ga4_unset.calls == []

    async with session_scope() as s:
        latch = (await s.execute(
            select(StripeWebhookEvent).where(
                StripeWebhookEvent.id == f"ga4_purchase:{sub_id}"
            )
        )).scalar_one_or_none()
        assert latch is None


@pytest.mark.asyncio
async def test_purchase_survives_analytics_failure(monkeypatch, ga4_configured):
    """The money path must complete even if the conversion send explodes."""
    async def _boom(**kwargs):
        raise RuntimeError("ga4 exploded")

    monkeypatch.setattr(analytics, "track_purchase", _boom)
    sub_id = f"sub_{_uuid.uuid4().hex[:16]}"
    async with session_scope() as s:
        # Must not raise.
        await _send_purchase_conversion(
            s, user_id="u_boom", obj=_checkout_obj("cs_boom", sub_id),
        )
        latch = (await s.execute(
            select(StripeWebhookEvent).where(
                StripeWebhookEvent.id == f"ga4_purchase:{sub_id}"
            )
        )).scalar_one_or_none()
        if latch is not None:
            await s.delete(latch)
            await s.commit()


# ── C: OAuth new-user persists utm/gclid ────────────────────────────────────

@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def google_configured(monkeypatch):
    monkeypatch.setattr(oauth_module.settings, "oauth_google_client_id", "test-cid")
    monkeypatch.setattr(oauth_module.settings, "oauth_google_client_secret", "test-secret")


def _fake_httpx(email: str) -> SimpleNamespace:
    """Canned provider round-trip — mirrors test_oauth_intent_carry.py."""

    class _Resp:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = 200
            self.text = ""

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **k):
            return _Resp({"access_token": "fake-token", "id_token": None})

        async def get(self, url, **k):
            return _Resp({"email": email, "name": "Attribution Tester"})

    return SimpleNamespace(AsyncClient=_Client)


ATTR = {
    "utm_source": "google",
    "utm_medium": "cpc",
    "utm_campaign": "finviz-alternative",
    "utm_term": "stock screener",
    "utm_content": "ad-b",
    "gclid": "TeSt-GcLiD-123",
}


def test_clean_attribution_filters_and_truncates():
    cleaned = oauth_module._clean_attribution({
        "utm_source": "  google  ",
        "utm_campaign": "c" * 500,       # over the 120-char column
        "gclid": "g" * 500,              # over the 200-char column
        "next": "/app/billing",          # not an attribution field
        "utm_medium": "cp\nc",           # control char — header-injection shape
        "utm_term": "",                  # empty is dropped, not stored as ""
    })
    assert cleaned["utm_source"] == "google"
    assert len(cleaned["utm_campaign"]) == 120
    assert len(cleaned["gclid"]) == 200
    assert "next" not in cleaned
    assert "utm_medium" not in cleaned
    assert "utm_term" not in cleaned


@pytest.mark.asyncio
async def test_start_stashes_attribution_cookie(client, google_configured):
    async with client:
        r = await client.get("/api/auth/oauth/google/start", params=ATTR)
    assert r.status_code == 307
    attr_cookies = [
        c for c in r.headers.get_list("set-cookie")
        if c.startswith("oauth_attr_google=")
    ]
    assert len(attr_cookies) == 1, "attribution must ride one cookie"
    cookie = attr_cookies[0]
    assert "HttpOnly" in cookie
    assert "Max-Age=600" in cookie, "attribution cookie must be short-lived"


@pytest.mark.asyncio
async def test_start_sets_no_attribution_cookie_for_untagged_traffic(
    client, google_configured,
):
    async with client:
        r = await client.get("/api/auth/oauth/google/start")
    assert not any(
        c.startswith("oauth_attr_google=")
        for c in r.headers.get_list("set-cookie")
    )


@pytest.mark.asyncio
async def test_oauth_new_user_persists_utm_and_gclid(
    client, google_configured, monkeypatch, ga4_configured,
):
    """The core fix: an OAuth signup off a paid click is now attributable,
    exactly as the email path already was."""
    email = f"oauth_attr_{_uuid.uuid4().hex}@example.com"
    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(email))

    async with client:
        r = await client.get(
            "/api/auth/oauth/google/callback",
            params={"code": "fake-code", "state": "st"},
            headers={"cookie": f"oauth_state_google=st; oauth_attr_google={urlencode(ATTR)}"},
        )
    assert r.status_code == 307

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        assert row.signup_utm_source == "google"
        assert row.signup_utm_medium == "cpc"
        assert row.signup_utm_campaign == "finviz-alternative"
        assert row.signup_utm_term == "stock screener"
        assert row.signup_utm_content == "ad-b"
        assert row.signup_gclid == "TeSt-GcLiD-123"
        user_id = row.id
        await s.delete(row)
        await s.commit()

    # …and the signup is now visible server-side too (finding B).
    sign_ups = [
        c for c in ga4_configured.calls
        if c["json"]["events"][0]["name"] == "sign_up"
    ]
    assert len(sign_ups) == 1
    assert sign_ups[0]["json"]["events"][0]["params"]["method"] == "google"
    assert sign_ups[0]["json"]["user_id"] == user_id

    # One-shot cookie is cleared once consumed.
    assert any(
        c.startswith("oauth_attr_google=")
        and ('=""' in c or "Max-Age=0" in c or "01 Jan 1970" in c)
        for c in r.headers.get_list("set-cookie")
    ), "oauth_attr cookie must be deleted after use"


@pytest.mark.asyncio
async def test_oauth_new_user_without_attribution_stays_null(
    client, google_configured, monkeypatch, ga4_unset,
):
    """Direct/untagged traffic — the common case — must not blow up or write
    empty strings into the columns."""
    email = f"oauth_direct_{_uuid.uuid4().hex}@example.com"
    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(email))

    async with client:
        r = await client.get(
            "/api/auth/oauth/google/callback",
            params={"code": "fake-code", "state": "st"},
            headers={"cookie": "oauth_state_google=st"},
        )
    assert r.status_code == 307

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        assert row.signup_utm_source is None
        assert row.signup_gclid is None
        await s.delete(row)
        await s.commit()


@pytest.mark.asyncio
async def test_oauth_tampered_attribution_cookie_is_truncated_not_trusted(
    client, google_configured, monkeypatch, ga4_unset,
):
    """The cookie is client-writable. An over-long value must be truncated to
    the column width rather than raising a DB error mid-signup."""
    email = f"oauth_tamper_attr_{_uuid.uuid4().hex}@example.com"
    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(email))
    evil = urlencode({"utm_source": "s" * 400, "gclid": "g" * 900})

    async with client:
        r = await client.get(
            "/api/auth/oauth/google/callback",
            params={"code": "fake-code", "state": "st"},
            headers={"cookie": f"oauth_state_google=st; oauth_attr_google={evil}"},
        )
    assert r.status_code == 307

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.email == email))).scalar_one()
        assert len(row.signup_utm_source) == 80
        assert len(row.signup_gclid) == 200
        await s.delete(row)
        await s.commit()


@pytest.mark.asyncio
async def test_returning_oauth_user_attribution_is_not_overwritten(
    client, google_configured, monkeypatch, ga4_configured,
):
    """Write-once-at-signup, same contract as the email path: a later OAuth
    sign-IN off a different campaign must not rewrite first-touch credit, and
    must not fire a second sign_up conversion."""
    uid = f"oauth_ret_attr_{_uuid.uuid4().hex}"
    email = f"{uid}@example.com"
    async with session_scope() as s:
        s.add(User(id=uid, email=email, name="Returning", tier="free",
                   password_hash="not-used", signup_utm_source="podcast"))
        await s.commit()
    monkeypatch.setattr(oauth_module, "httpx", _fake_httpx(email))

    async with client:
        r = await client.get(
            "/api/auth/oauth/google/callback",
            params={"code": "fake-code", "state": "st"},
            headers={"cookie": f"oauth_state_google=st; oauth_attr_google={urlencode(ATTR)}"},
        )
    assert r.status_code == 307

    async with session_scope() as s:
        row = (await s.execute(select(User).where(User.id == uid))).scalar_one()
        assert row.signup_utm_source == "podcast", "first-touch credit was clobbered"
        await s.delete(row)
        await s.commit()

    assert not [
        c for c in ga4_configured.calls
        if c["json"]["events"][0]["name"] == "sign_up"
    ], "sign_up must fire only for genuinely new users"


@pytest.mark.asyncio
async def test_start_carries_both_next_and_attribution(client, google_configured):
    """The `?next=` intent carry (PR #2xx) and attribution must coexist —
    neither may clobber the other on the /start URL."""
    async with client:
        r = await client.get(
            "/api/auth/oauth/google/start",
            params={**ATTR, "next": "/app/billing?intent=premium"},
        )
    set_cookies = r.headers.get_list("set-cookie")
    assert any(c.startswith("oauth_next_google=") for c in set_cookies)
    attr = [c for c in set_cookies if c.startswith("oauth_attr_google=")]
    assert len(attr) == 1
    stored = parse_qs(attr[0].split(";")[0].split("=", 1)[1])
    assert stored["utm_source"] == ["google"]
    assert "next" not in stored
