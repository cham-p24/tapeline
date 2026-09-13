"""The newsletter welcome email must not overclaim about the public record.

Integrity wave approved 2026-09-14 (ticket T-07). The welcome said the digest
carried "the same public numbers anyone can see on tapeline.io/scorecard".
It does not: the public record shows each list 7 days after the session, and
the record's stored values were corrected on 2026-06-15 (scores capped) and
2026-08-25 (prices restated). The email now describes the record separately
and names both corrections.

The email is rendered through the real `_send_welcome` with `send_email`
captured, so the assertion is on what a subscriber would receive.
"""
from __future__ import annotations

import re

import pytest

from app.services import newsletter

BANNED = [
    r"never edited",
    r"no edits",
    r"no hindsight edit",
    r"original reasoning",
    r"plain-English reasoning",
    r"same numbers",
    r"same public numbers",
    r"same day, no edits",
    r"exactly what was published",
    r"congress",
    r"squeeze",
    r"beat the market",
]


@pytest.fixture
def captured(monkeypatch):
    sent: list[dict] = []

    async def fake_send_email(**kwargs):
        sent.append(kwargs)
        return {"skipped": False}

    monkeypatch.setattr(newsletter, "send_email", fake_send_email)
    return sent


@pytest.mark.asyncio
async def test_welcome_email_makes_no_banned_record_claim(captured):
    await newsletter._send_welcome(email="reader@example.com", token="t" * 64)
    assert len(captured) == 1
    for part in ("html", "text", "subject"):
        body = captured[0][part]
        for pat in BANNED:
            assert not re.search(pat, body, re.IGNORECASE), (
                f"welcome {part} contains banned record claim {pat!r}"
            )


@pytest.mark.asyncio
async def test_welcome_email_names_both_corrections_and_the_delay(captured):
    await newsletter._send_welcome(email="reader@example.com", token="t" * 64)
    for part in ("html", "text"):
        body = captured[0][part]
        assert "not re-ranked or deleted" in body
        assert "25 August 2026" in body
        assert "15 June 2026" in body
        assert "18 May to 12 June" in body
        assert "7 days after the session" in body
