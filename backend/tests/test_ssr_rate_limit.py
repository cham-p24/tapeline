"""SSR must not be rate-limited into 500s by its own success.

Server-side rendering funnels EVERY page render for the whole site through one
Fly egress IP, so all of it shares limit_api's per-IP 120/min bucket. A single
ticker page fans out to ~3 upstream calls, so ~40 cold renders a minute drains
it — after which the backend 429s its own frontend and
frontend/app/t/[symbol]/page.tsx converts that into HTTP 500.

Observed in production: the weekly SEO audit reported "1534 URLs returning
non-2xx/3xx" while every one of those pages served 200 to a normal visitor
moments later — the crawl had broken them itself. Googlebot walking the
~8,400-page ticker sitemap hits the same wall, which is a deindexing risk on
the site's biggest crawl surface.

main.py already exempted /api/embed/ for this exact one-shared-IP reason; these
tests cover closing the same gap for the SSR reads.
"""
from __future__ import annotations

import httpx
import pytest

from app.main import _is_trusted_ssr, app
from app.services import rate_limit as rl

TOKEN = "test-ssr-token-abc123"


class _Req:
    def __init__(self, headers: dict):
        self.headers = headers


@pytest.fixture(autouse=True)
def _fresh_limiter():
    """limit_api buckets are process-global; isolate each test."""
    rl.limiter._buckets.clear() if hasattr(rl.limiter, "_buckets") else None
    yield
    rl.limiter._buckets.clear() if hasattr(rl.limiter, "_buckets") else None


# ── the trust check itself ───────────────────────────────────────────────────

def test_unset_token_never_exempts(monkeypatch):
    """A missing secret must degrade to TODAY's behaviour (everything limited),
    never to an open door."""
    monkeypatch.setattr("app.main.settings.internal_ssr_token", "")
    assert _is_trusted_ssr(_Req({"x-tapeline-internal": "anything"})) is False
    assert _is_trusted_ssr(_Req({})) is False


def test_only_the_exact_token_exempts(monkeypatch):
    monkeypatch.setattr("app.main.settings.internal_ssr_token", TOKEN)
    assert _is_trusted_ssr(_Req({"x-tapeline-internal": TOKEN})) is True
    assert _is_trusted_ssr(_Req({"x-tapeline-internal": TOKEN + "x"})) is False
    assert _is_trusted_ssr(_Req({"x-tapeline-internal": ""})) is False
    assert _is_trusted_ssr(_Req({})) is False


def test_token_is_not_a_public_env_var():
    """It must never be NEXT_PUBLIC_*, which Next inlines into browser bundles —
    a browser-readable token would let anyone bypass the rate limit."""
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "app" / "config.py").read_text(
        encoding="utf-8"
    )
    assert "NEXT_PUBLIC_INTERNAL_SSR" not in src
    frontend = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "ssrHeaders.ts"
    if frontend.exists():
        ts = frontend.read_text(encoding="utf-8")
        assert "NEXT_PUBLIC_INTERNAL_SSR_TOKEN" not in ts
        assert "process.env.INTERNAL_SSR_TOKEN" in ts


# ── end-to-end through the real middleware ───────────────────────────────────

@pytest.mark.asyncio
async def test_ssr_token_survives_a_burst_that_429s_an_anonymous_client(monkeypatch):
    """THE REGRESSION. Drive more requests than the per-IP cap allows:
    an anonymous client gets 429s; our own SSR does not."""
    monkeypatch.setattr("app.main.settings.internal_ssr_token", TOKEN)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # NOTE: /api/health* is deliberately exempt from the middleware, so it
        # cannot demonstrate anything here — use a genuinely limited path.
        PATH = "/api/status"

        anon_429 = 0
        for _ in range(200):
            r = await c.get(PATH, headers={"cf-connecting-ip": "9.9.9.9"})
            if r.status_code == 429:
                anon_429 += 1

        # Same source IP, now presenting our SSR token: must never be limited,
        # even though that IP's bucket is already drained by the loop above.
        ssr_429 = 0
        for _ in range(200):
            r = await c.get(
                PATH,
                headers={"cf-connecting-ip": "9.9.9.9", "x-tapeline-internal": TOKEN},
            )
            if r.status_code == 429:
                ssr_429 += 1

    # Guard against a vacuous pass: if the limiter never fired for the
    # anonymous client, the SSR assertion below proves nothing.
    assert anon_429 > 0, (
        "the per-IP limiter must actually engage for an anonymous client, "
        "otherwise this test cannot demonstrate the exemption"
    )
    assert ssr_429 == 0, "our own SSR must never be rate-limited into 500s"


@pytest.mark.asyncio
async def test_a_forged_token_is_still_rate_limited(monkeypatch):
    """The exemption must not be reachable by guessing the header name."""
    monkeypatch.setattr("app.main.settings.internal_ssr_token", TOKEN)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        seen_429 = False
        for _ in range(200):
            r = await c.get(
                "/api/scanner",
                headers={"cf-connecting-ip": "8.8.4.4", "x-tapeline-internal": "wrong"},
            )
            if r.status_code == 429:
                seen_429 = True
                break
    assert seen_429, "a wrong token must NOT bypass the per-IP limit"
