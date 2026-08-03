"""Tests for the public embeddable score badge (/api/public/badge/{symbol})."""
from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from app.main import app
from app.services.badge import render_score_badge


@pytest.fixture
def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# --- pure renderer ---------------------------------------------------------

def test_render_is_wellformed_svg_with_score_and_band() -> None:
    svg = render_score_badge("NVDA", "NVIDIA Corp", 82.0, None)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert "NVDA" in svg
    assert "82" in svg
    assert "STRONG SETUP" in svg  # 70–84 band label, derived from score


def test_render_prefers_stored_signal_label() -> None:
    svg = render_score_badge("AAPL", "Apple", 90.0, "HIGH CONVICTION")
    assert "HIGH CONVICTION" in svg
    assert "90" in svg


def test_render_handles_unscored_symbol_gracefully() -> None:
    svg = render_score_badge("ZZZZ", None, None, None)
    assert svg.startswith("<svg")
    assert "no score" in svg
    assert "—" in svg  # em dash placeholder


def test_render_escapes_xml_metacharacters() -> None:
    svg = render_score_badge("A&B", None, 50.0, "NEUTRAL")
    assert "&amp;" in svg
    # the raw, unescaped ampersand sequence must never reach the output
    assert "A&B" not in svg


def test_render_floors_score_to_stay_consistent_with_band() -> None:
    # 69.7 must display "69" (CONSTRUCTIVE band), never round up to "70" —
    # which would read "70 · CONSTRUCTIVE" and contradict the published band
    # (score >= 70 is STRONG SETUP). Number and label must always agree.
    svg = render_score_badge("NVDA", None, 69.7, "CONSTRUCTIVE")
    assert "69 · CONSTRUCTIVE" in svg
    assert "70 ·" not in svg


# --- endpoint --------------------------------------------------------------

@pytest.mark.asyncio
async def test_badge_endpoint_unknown_symbol_still_returns_svg(
    client: httpx.AsyncClient,
) -> None:
    async with client:
        r = await client.get("/api/public/badge/NOSUCHTICKER.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.text.startswith("<svg")
    assert "no score" in r.text
    # embeddable anywhere + cacheable
    assert r.headers["access-control-allow-origin"] == "*"
    assert "max-age" in r.headers["cache-control"]


@pytest.mark.asyncio
async def test_badge_endpoint_reflects_a_scored_ticker(
    client: httpx.AsyncClient,
) -> None:
    from sqlalchemy import delete

    from app.db import session_scope
    from app.models import Ticker

    async with session_scope() as session:
        await session.execute(delete(Ticker).where(Ticker.symbol == "TSTBDG"))
        session.add(
            Ticker(
                symbol="TSTBDG",
                name="Test Badge Co",
                asset_class="equity",
                score=78.0,
                signal="STRONG SETUP",
                updated_at=datetime.now(UTC),
            )
        )
        await session.commit()

    # lowercase in the URL should normalise to the stored symbol
    async with client:
        r = await client.get("/api/public/badge/tstbdg")
    assert r.status_code == 200
    assert "TSTBDG" in r.text
    assert "78" in r.text
    assert "STRONG SETUP" in r.text
