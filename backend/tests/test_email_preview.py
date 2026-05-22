"""Admin email-preview endpoint contract.

Three things to lock in:
  1. The list endpoint enumerates every renderer (admin guard works)
  2. The render endpoint returns valid HTML with the design-system invariants
  3. theme=light / dark force the dark-mode media query to never / always match
"""
from __future__ import annotations

import uuid as _uuid

import httpx
import pytest

from app.main import app


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _make_admin_cookies(client: httpx.AsyncClient, monkeypatch) -> dict:
    """Create a fresh signed-up user, then flip is_admin to True so admin
    endpoints accept them. Returns the session cookies."""
    from sqlalchemy import select

    from app.db import session_scope
    from app.models import User
    from app.routers import auth as auth_module
    from app.services import trial_abuse

    async def _ok(*_a, **_k):
        return True

    monkeypatch.setattr(auth_module, "verify_turnstile", _ok)
    monkeypatch.setattr(trial_abuse, "signup_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(trial_abuse, "fingerprint_allowed", lambda *_a, **_k: True)

    email = f"admin-{_uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "TestPassword!2026", "name": "Admin"},
    )
    assert r.status_code == 200, r.text
    cookies = r.cookies

    # Promote to admin via the DB — there's no signup-time admin flag.
    async with session_scope() as s:
        u = (await s.execute(select(User).where(User.email == email))).scalar_one()
        u.is_admin = True
        await s.commit()
    return cookies


@pytest.mark.asyncio
async def test_email_preview_requires_admin(client):
    """Anonymous and non-admin users both get 401."""
    async with client:
        r = await client.get("/api/admin/email-preview")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_email_preview_lists_every_renderer(client, monkeypatch):
    """The list endpoint should return at least the 15 emails we ship.
    The exact count is allowed to grow (new variants), but never shrink
    silently — if it drops below 15, a renderer fell out of the index."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        r = await client.get("/api/admin/email-preview", cookies=cookies)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body and "count" in body
        assert body["count"] == len(body["items"])
        assert body["count"] >= 15, (
            f"expected at least 15 email previews, got {body['count']}"
        )
        # Sanity: every item has both fields
        for it in body["items"]:
            assert "name" in it and "description" in it
            assert it["name"]
            assert it["description"]


@pytest.mark.asyncio
async def test_email_preview_renders_html_with_design_invariants(client, monkeypatch):
    """A picked email renders as HTML and carries the design-system markers."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        r = await client.get(
            "/api/admin/email-preview/welcome_with_picks", cookies=cookies,
        )
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
        html = r.text
        assert "<!doctype html>" in html.lower()
        assert "Tapeline" in html
        assert "Not investment advice" in html


@pytest.mark.asyncio
async def test_email_preview_theme_light_disables_dark_block(client, monkeypatch):
    """theme=light should rewrite the dark-mode media query to one that
    never matches (max-width: 0px), so the email always paints light."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        r = await client.get(
            "/api/admin/email-preview/welcome_fallback?theme=light",
            cookies=cookies,
        )
        assert r.status_code == 200
        html = r.text
        assert "@media (prefers-color-scheme: dark)" not in html
        assert "@media (max-width: 0px)" in html


@pytest.mark.asyncio
async def test_email_preview_theme_dark_forces_dark_block(client, monkeypatch):
    """theme=dark rewrites the dark-mode media query to @media all so the
    dark CSS overrides always apply, regardless of OS theme."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        r = await client.get(
            "/api/admin/email-preview/welcome_fallback?theme=dark",
            cookies=cookies,
        )
        assert r.status_code == 200
        html = r.text
        assert "@media (prefers-color-scheme: dark)" not in html
        assert "@media all" in html


@pytest.mark.asyncio
async def test_email_preview_unknown_name_404(client, monkeypatch):
    """An unknown email name returns 404 with a helpful message."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        r = await client.get(
            "/api/admin/email-preview/this_does_not_exist", cookies=cookies,
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_email_preview_rejects_invalid_theme(client, monkeypatch):
    """Theme is constrained to auto/light/dark via Query pattern. Anything
    else must 422 — no silent fallback."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        r = await client.get(
            "/api/admin/email-preview/welcome_fallback?theme=neon",
            cookies=cookies,
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_send_to_me_requires_admin(client):
    """POST /api/admin/email-preview/{name}/send is admin-only — same gate
    as the GET endpoints."""
    async with client:
        r = await client.post("/api/admin/email-preview/welcome_fallback/send")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_send_to_me_skips_when_no_api_key(client, monkeypatch):
    """In test/dev with no RESEND_API_KEY, send_email returns skipped.
    The endpoint surfaces that as status='skipped' (not an error) so the
    UI can show a clear 'Resend not configured' message instead of failing."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        r = await client.post(
            "/api/admin/email-preview/welcome_fallback/send",
            cookies=cookies,
        )
        assert r.status_code == 200
        body = r.json()
        # In a fresh test env Resend isn't configured so we expect skipped.
        # If a developer has RESEND_API_KEY exported in their shell while
        # running tests locally, we'd see status="sent" instead — accept
        # either since both prove the endpoint wired up.
        assert body["status"] in ("sent", "skipped")
        if body["status"] == "skipped":
            assert body["reason"] == "no_api_key"


@pytest.mark.asyncio
async def test_send_to_me_unknown_name_404(client, monkeypatch):
    """Same 404 path as the GET render — name must be a known variant."""
    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        r = await client.post(
            "/api/admin/email-preview/this_does_not_exist/send",
            cookies=cookies,
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_send_to_me_picks_persona_by_name(client, monkeypatch):
    """The endpoint's persona heuristic dispatches by name prefix so the
    From: header matches the kind of email being previewed. We can verify
    this by mocking send_email and asserting on the persona arg.
    """
    from unittest.mock import AsyncMock, patch

    cases = [
        ("welcome_fallback",                  "default"),
        ("email_verification",                "default"),
        ("subscription_started_pro_monthly",  "billing"),
        ("payment_failed_first",              "billing"),
        ("alert_rule",                        "alerts"),
        ("watchlist_alert",                   "alerts"),
        ("digest_with_items",                 "alerts"),
        ("weekly_newsletter",                 "alerts"),
        ("day13",                             "sales"),
        ("re_engagement",                     "sales"),
    ]

    async with client:
        cookies = await _make_admin_cookies(client, monkeypatch)
        for preview_name, expected_persona in cases:
            mock_send = AsyncMock(return_value={"id": "stub"})  # not skipped
            # admin.py does `from app.services.email import send_email`
            # at call time — so the live reference lives on
            # app.services.email, not on the admin module.
            with patch("app.services.email.send_email", new=mock_send):
                r = await client.post(
                    f"/api/admin/email-preview/{preview_name}/send",
                    cookies=cookies,
                )
            assert r.status_code == 200, (preview_name, r.text)
            body = r.json()
            assert body.get("status") == "sent", (preview_name, body)
            assert body["persona"] == expected_persona, (preview_name, body)
            # Mock should have been invoked exactly once per preview
            assert mock_send.await_count == 1, preview_name
            persona_kw = mock_send.call_args.kwargs.get("persona")
            assert persona_kw == expected_persona, (preview_name, persona_kw)
