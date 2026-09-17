"""A failed Telegram send must not print the chat id or the bot token.

stale-link-audit.yml and seo-weekly-digest.yml run code that calls
telegram.send_message over `flyctl ssh console`, so everything it logs lands in
GitHub Actions run logs on a PUBLIC repository. Until this test,
`telegram.send_failed` printed `chat=<the founder's chat id>` and up to 200
characters of Telegram's raw response body on every non-200, for example a
Markdown parse 400.

Also pins the delivery classification the weekly digest relies on to avoid a
double send: a 4xx is REFUSED (nothing delivered), a 5xx is UNCERTAIN.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

import httpx
import pytest

from app.services import telegram
from app.services.telegram import SendStatus

CHAT_ID = "987654321"
TOKEN = "123456789:AAFakeBotTokenForTestsOnly_xyz"


def _answer(status: int, body: dict) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)
    return handler


@pytest.fixture
def telegram_answers(monkeypatch: pytest.MonkeyPatch):
    """Route telegram's AsyncClient through a MockTransport answering `handler`."""
    monkeypatch.setattr(telegram.settings, "telegram_bot_token", TOKEN)
    real_client = httpx.AsyncClient

    def install(handler: Callable[[httpx.Request], httpx.Response]) -> None:
        monkeypatch.setattr(
            telegram.httpx, "AsyncClient",
            lambda *a, **kw: real_client(*a, transport=httpx.MockTransport(handler), **kw),
        )
    return install


def _telegram_log(caplog: pytest.LogCaptureFixture) -> str:
    # This module's records only. httpx logs the request URL, token included, at
    # INFO; the scripts that run in Actions keep httpx at WARNING, and
    # test_seo_digest_latch pins that for the digest.
    return "\n".join(r.getMessage() for r in caplog.records if r.name == telegram.__name__)


# Telegram's own error text can carry the ids it could not use.
_ECHOING_BODY = {
    "ok": False,
    "error_code": 400,
    "description": (
        f"Bad Request: chat {CHAT_ID} not found for bot {TOKEN} (bot id "
        f"{TOKEN.split(':')[0]}, reply to message 1234567); "
        "can't parse entities: Can't find end of the entity starting at byte offset 42"
    ),
}


@pytest.mark.parametrize("call", ["send_message", "send_message_status", "send_message_with_id"])
async def test_a_failed_send_logs_the_status_but_not_the_chat_id_or_token(
    telegram_answers, caplog: pytest.LogCaptureFixture, call: str,
) -> None:
    """Mutations: `chat=%s` with the chat id; the raw body logged; the
    description logged without scrubbing."""
    telegram_answers(_answer(400, _ECHOING_BODY))
    with caplog.at_level(logging.DEBUG):
        await getattr(telegram, call)(CHAT_ID, "*unclosed")

    logged = _telegram_log(caplog)
    assert "status=400" in logged, logged
    assert f"chat={telegram.REDACTED}" in logged
    assert CHAT_ID not in logged, "the chat id reached a public log"
    assert TOKEN not in logged and TOKEN.split(":")[0] not in logged, "the bot token reached a public log"
    # Still diagnosable: the part of Telegram's reason that identifies nothing.
    assert "can't parse entities" in logged


async def test_a_non_json_error_body_is_not_logged_raw(
    telegram_answers, caplog: pytest.LogCaptureFixture,
) -> None:
    """Mutation: falling back to r.text when the body is not JSON."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text=f"<html>upstream for chat {CHAT_ID} failed</html>")

    telegram_answers(handler)
    with caplog.at_level(logging.DEBUG):
        assert await telegram.send_message_status(CHAT_ID, "x") is SendStatus.UNCERTAIN
    logged = _telegram_log(caplog)
    assert "status=502" in logged
    assert CHAT_ID not in logged


@pytest.mark.parametrize(("status", "expected"), [
    (200, SendStatus.DELIVERED),
    (400, SendStatus.REFUSED),
    (403, SendStatus.REFUSED),
    (429, SendStatus.REFUSED),
    (500, SendStatus.UNCERTAIN),
    (502, SendStatus.UNCERTAIN),
])
async def test_delivery_is_classified_by_status(
    telegram_answers, status: int, expected: SendStatus,
) -> None:
    """Mutation: a 5xx reported as REFUSED, which lets the weekly digest release
    a week Telegram may already have delivered."""
    telegram_answers(_answer(status, {"ok": status == 200, "result": {"message_id": 1}}))
    assert await telegram.send_message_status(CHAT_ID, "x") is expected
    assert await telegram.send_message(CHAT_ID, "x") is (expected is SendStatus.DELIVERED)


async def test_no_token_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telegram.settings, "telegram_bot_token", "")
    assert await telegram.send_message_status(CHAT_ID, "x") is SendStatus.SKIPPED
    assert await telegram.send_message(CHAT_ID, "x") is False
