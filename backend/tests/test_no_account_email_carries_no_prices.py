"""The free daily Top 10 email carries no vendor market data.

Anyone can join this list without an account (POST /api/newsletter/subscribe
has no auth), and our market-data plan covers personal use only. So the email
shows the score, the label and the one-line reason, and nothing from the price
feed: no price, close, daily move or volume. The founder chose this on
2026-09-19 (option "a"), before an ad started promoting the list.

The renderer has never printed a price, but `run_daily_digest` used to select
`Ticker.price` and `Ticker.change_pct_1d` into every pick. One template edit
would have put them in front of every subscriber. These tests pin both halves:
what the picks may carry, and what actually goes out.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

# Distinctive values, so a match can only come from these rows.
_PRICE = 987.65
_CLOSE = 987.64
_MOVE = 4.321
_VOLUME = 1_234_567
_AVG_VOLUME = 7_654_321

_VENDOR_STRINGS = (
    "987.65", "987.64", "987.6", "4.321", "4.32",
    "1234567", "1,234,567", "7654321", "7,654,321",
)

# What a pick handed to the renderer may hold. Nothing here comes from the
# price feed.
_ALLOWED_PICK_KEYS = {"symbol", "name", "score", "signal", "reason"}


async def _seed() -> None:
    from app.db import session_scope
    from app.models import NewsletterSubscriber, Ticker

    now = datetime.now(UTC)
    async with session_scope() as s:
        for i in range(3):
            s.add(Ticker(
                symbol=f"NOPX{i}", name=f"No Price {i}", sector="Tech",
                asset_class="equity", score=99.0 - i, signal="HIGH CONVICTION",
                reason="trend factor in the top band of its score",
                price=_PRICE, day_close=_CLOSE, change_pct_1d=_MOVE,
                volume=_VOLUME, avg_volume_30d=_AVG_VOLUME,
                confidence_pct=80.0, sub_trend=90.0, sub_rs=90.0,
                sub_momentum=90.0, sub_macro=75.0, updated_at=now,
                is_leveraged=False,
            ))
        s.add(NewsletterSubscriber(
            email=f"noprice-{uuid.uuid4().hex[:8]}@example.com",
            status="confirmed", source="homepage",
            unsubscribe_token=f"t_{uuid.uuid4().hex[:12]}",
        ))


@pytest.mark.asyncio
async def test_the_digest_picks_carry_no_vendor_fields(monkeypatch):
    from app.db import session_scope
    from app.services import newsletter

    await _seed()
    seen: list[list[dict]] = []
    real_render = newsletter._render_daily_digest

    def _spy(*, picks, **kwargs):
        seen.append(picks)
        return real_render(picks=picks, **kwargs)

    async def _no_send(**_k):
        return {"id": "test"}

    monkeypatch.setattr(newsletter, "_render_daily_digest", _spy)
    monkeypatch.setattr(newsletter, "send_email", _no_send)
    async with session_scope() as s:
        await newsletter.run_daily_digest(s)

    assert seen and seen[0], "no digest was rendered, so this proves nothing"
    extra = {k for p in seen[0] for k in p} - _ALLOWED_PICK_KEYS
    assert not extra, (
        f"the no-account digest's picks carry {sorted(extra)}; a pick may hold "
        f"only {sorted(_ALLOWED_PICK_KEYS)}, never price-feed data"
    )


@pytest.mark.asyncio
async def test_the_sent_digest_shows_no_price_move_or_volume(monkeypatch):
    from app.db import session_scope
    from app.services import newsletter

    await _seed()
    sent: list[dict] = []

    async def _capture(**kwargs):
        sent.append(kwargs)
        return {"id": "test"}

    monkeypatch.setattr(newsletter, "send_email", _capture)
    async with session_scope() as s:
        await newsletter.run_daily_digest(s)

    assert sent, "no digest was sent, so this proves nothing"
    msg = sent[0]
    body = " ".join(str(msg.get(k, "")) for k in ("subject", "html", "text"))
    assert "NOPX0" in body, "the seeded picks are not in the email, so this proves nothing"
    leaked = [v for v in _VENDOR_STRINGS if v in body]
    assert not leaked, f"the no-account digest shows vendor market data: {leaked}"
