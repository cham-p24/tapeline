"""The September product update must reach the right people exactly once, unattended.

It runs from .github/workflows/product-update-send.yml over `flyctl ssh`, with
nobody watching, into a log that is world-readable on this public repo. So every
property a human would normally eyeball in a dry run is pinned here instead:

  * a dry run sends nothing; --send stamps each recipient; a re-run is a no-op;
  * a send whose outcome is unknown (Resend may have it) is stamped, not retried;
  * the RE_ENGAGEMENT opt-out, undeliverable, sunset and Resend suppression hold;
  * newsletter-only subscribers are deduplicated against EVERY account;
  * the open-access sentence reaches account holders only;
  * the copy is the approved copy, word for word and in order, in both parts,
    with nothing added around it;
  * nothing address-shaped reaches the output under --quiet;
  * every update_send command in the workflow passes --quiet; the window step,
    run for real, opens only inside its window; nothing but the schedule or a
    manual dispatch triggers it; the send stays clear of the worker's own
    digests (read from the worker's source) and off the reminder's day;
  * a registered, unique lock stops two runs sending at once.
"""
from __future__ import annotations

import ast
import asyncio
import fnmatch
import inspect
import json
import logging
import os
import pathlib
import re
import shutil
import subprocess
from datetime import UTC, date, datetime, time, timedelta
from html import unescape

import httpx
import pytest
import yaml
from sqlalchemy import select

from app.db import session_scope
from app.models import User
from app.models.newsletter import NewsletterSubscriber
from app.scripts import survey_send as ss
from app.scripts import update_send as us
from app.services.email_prefs import DEFAULT_PREFS, EmailPref

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "product-update-send.yml"
REMINDER_WORKFLOW = ROOT / ".github" / "workflows" / "survey-reminder.yml"
WORKER = ROOT / "backend" / "app" / "workers" / "signal_publisher.py"

#: The survey reminder goes out at 13:07 UTC on this day. The update must never
#: land on the same UTC day: two emails from one small sender inside a few hours
#: is the pattern that gets the second one read as a campaign, or spam-filed.
SURVEY_REMINDER_DAY = date(2026, 9, 16)

#: The copy as approved for review, verbatim — the account-holder variant, plain
#: text, everything above the footer. The newsletter variant is this minus the
#: "And one thing that is not an improvement" paragraph. If the copy changes
#: after approval, this is where the change has to be made on purpose.
#: Reworded 2026-09-14 on the founder's "reword the email": see
#: test_the_update_repeats_none_of_the_sentences_withdrawn_on_14_september.
APPROVED_COPY = """\
Hi Sam,

A lot changed at Tapeline over the past week, and part of it went wrong in a way you should hear about from us rather than notice for yourself.

Scores were not kept up to date for most of 6 to 11 September.
From 6 September our scoring kept failing to finish its work. Three of the six factors — trend, relative strength and momentum — kept using price data from 6 September until a fix on 10 September, and nothing on the site said so. From 15:36 UTC on 9 September to 16:18 UTC on 10 September, the scanner showed numbers that were not being refreshed at all. Our monitoring restarted the machines that run scoring many times over those days, and the restarts did not fix it. The cause was our own code plus a server that could not keep up with the larger universe described below. We fixed the problems we had found in our code on 10 September, but scoring fell behind again, and on 11 September we moved it to a dedicated machine. Every automated check on it since then, up to 14 September, has passed.

Two other factors fell behind as well.
Company fundamentals and insider buying are refreshed by a separate job. It was still stalled on 13 September, two days after scoring moved to its new machine, and some readings it did fetch were lost when we released updates to the site. We made fixes on 13 and 14 September and began fetching the lost readings again. Where a stock has no reading for one of these factors, that factor counts as neutral in its score.

The scanner now covers about 11,500 stocks and ETFs.
Until 6 September, thousands of stocks and ETFs we had already scored could not appear in a scan. That is not new data we bought. It is data we already had and were not refreshing. Search for TSM, Sony or Toyota and they are there.

Crypto is in: more than 100 pairs, updated once a day.
Coins sit in their own list and are never ranked against stocks, because two of our six factors — company fundamentals and insider buying — cannot exist for a coin. Prices update daily, not live. Our data plan does not include live crypto prices, and we would rather tell you that than label a day-old number "live".

Scores moved on 7 September, mostly down.
Three columns in one of our data sources were renamed, and we read them as missing. Missing inputs are scored as neutral, which made most of the affected scores too high. We recalculated 4,112 scores and 3,233 of them went down. Scores also moved that week as the stale price data and missing factor readings described above were refreshed, so a change in a score you watch may have more than one cause.

And one thing that is not an improvement: the open-access month ended on 8 September, as scheduled. Free accounts are back to the top 10 rows per scan.

The record is still free to read, with no account: tapeline.io/scorecard

— Christian"""

ACCOUNT_ONLY_MARKER = "the open-access month ended"
SCORECARD = "https://tapeline.io/scorecard?" + us.SCORECARD_UTM

_seq = 0


async def _user(s, email: str, *, tokens=(), **kw) -> User:
    """`User.id` has no default (native auth mints "u_<uuid>"), so supply one."""
    global _seq
    _seq += 1
    u = User(
        id=f"u_upd_{_seq}",
        email=email,
        name=kw.pop("name", "Sam Example"),
        tier="free",
        drip_state=",".join(tokens),
        **kw,
    )
    s.add(u)
    await s.flush()
    return u


async def _sub(s, email: str, **kw) -> NewsletterSubscriber:
    sub = NewsletterSubscriber(
        email=email,
        status=kw.pop("status", "confirmed"),
        unsubscribe_token=kw.pop("unsubscribe_token", "tok_" + email.split("@")[0].lower()),
        **kw,
    )
    s.add(sub)
    await s.flush()
    return sub


def _toks(drip_state: str | None) -> set[str]:
    return {t for t in (drip_state or "").split(",") if t}


async def _state(email: str) -> set[str]:
    async with session_scope() as s:
        return _toks(await s.scalar(select(User.drip_state).where(User.email == email)))


@pytest.fixture
def https(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "app_url", "https://tapeline.io", raising=False)
    monkeypatch.setattr(get_settings(), "session_secret", "test-secret", raising=False)


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    sent: list[dict] = []

    async def _fake(**kw):
        sent.append(kw)
        return {"id": f"re_{len(sent)}"}

    monkeypatch.setattr("app.services.email.send_email", _fake)
    return sent


def _visible_text(html: str) -> str:
    body = html.split("</style>")[-1]
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", body)).split())


def _squash(text: str) -> str:
    return " ".join(text.split())


def _split_rendered(html: str) -> tuple[str, str]:
    """(body, unsubscribe slot) of a rendered update, proving everything else is
    exactly the shared shell.

    The chrome is derived from email_design.shell() itself, rendered around a
    sentinel, so nothing here restates its markup. Anything added above the body
    (a preheader), below the footer, or between the body and the footer's
    divider lands outside the two returned pieces and fails the prefix and
    suffix checks.
    """
    from app.services.email_design import UNSUB_PLACEHOLDER, shell

    sentinel = "TL-TEST-BODY-SENTINEL"
    head, tail = shell(sentinel).split(sentinel)
    footer_top, footer_rest = tail.split(UNSUB_PLACEHOLDER)
    assert html.startswith(head), "something was added above the body — a preheader?"
    assert html.endswith(footer_rest), "the footer below the unsubscribe line was changed"
    body, divider, slot = html[len(head): len(html) - len(footer_rest)].rpartition(footer_top)
    assert divider, "the footer's divider is missing"
    return body, slot


def _paragraph_texts(body: str) -> list[str]:
    return [
        _squash(unescape(re.sub(r"<[^>]+>", " ", inner)))
        for inner in re.findall(r"<p\b[^>]*>(.*?)</p>", body, re.S)
    ]


# ── Account audience ────────────────────────────────────────────────────────

async def test_an_ordinary_customer_is_a_recipient() -> None:
    async with session_scope() as s:
        await _user(s, "real@example.com")
        recipients, skipped = await us.collect_accounts(s)
    assert [u.email for u in recipients] == ["real@example.com"]
    assert skipped == []


@pytest.mark.parametrize(
    ("email", "kw", "reason"),
    [
        ("done@example.com", {"tokens": ("re14", us.UPDATE_TOKEN)}, "already_sent"),
        ("owner@tapeline.io", {}, "internal"),
        ("boss@example.com", {"is_admin": True}, "internal"),
        ("bounced@example.com", {"email_undeliverable_at": datetime(2026, 9, 1, tzinfo=UTC)}, "undeliverable"),
        (sorted(ss.RESEND_SUPPRESSED)[0], {}, "resend_suppressed"),
        ("dormant@example.com", {"tokens": ("re14", "re24", "re_sunset")}, "sunset"),
        # Only the RE_ENGAGEMENT bit cleared. The governor blocks email_prefs == 0
        # on its own, so a fully opted-out user would pass even with the
        # category gate deleted; this one would not.
        ("optout@example.com", {"email_prefs": int(DEFAULT_PREFS & ~EmailPref.RE_ENGAGEMENT)}, "opted_out"),
    ],
)
async def test_account_exclusions(email: str, kw: dict, reason: str) -> None:
    async with session_scope() as s:
        await _user(s, email, **kw)
        recipients, skipped = await us.collect_accounts(s)
    assert recipients == []
    assert [r for _u, r in skipped] == [reason]


async def test_an_account_whose_drip_state_cannot_take_the_token_is_skipped() -> None:
    """VARCHAR(255) on Postgres; SQLite ignores the length, so the overflow the
    stamp would hit in production is checked here at the boundary instead."""
    capacity = User.__table__.c.drip_state.type.length
    assert isinstance(capacity, int) and capacity > len(us.UPDATE_TOKEN)
    fits = "a" * (capacity - len(us.UPDATE_TOKEN) - 1)   # + "," + token == capacity
    over = "b" * (capacity - len(us.UPDATE_TOKEN))       # one character too many
    async with session_scope() as s:
        await _user(s, "fits@example.com", tokens=(fits,))
        await _user(s, "over@example.com", tokens=(over,))
        recipients, skipped = await us.collect_accounts(s)
    assert [u.email for u in recipients] == ["fits@example.com"]
    assert [(u.email, r) for u, r in skipped] == [("over@example.com", "no_room_for_token")]


async def test_already_sent_is_parsed_not_pattern_matched() -> None:
    """`_` is a LIKE wildcard. A token that only a wildcard would match must not
    count as sent — otherwise someone is silently never mailed."""
    lookalike = us.UPDATE_TOKEN.replace("_", "-")
    async with session_scope() as s:
        await _user(s, "lookalike@example.com", tokens=(lookalike, us.UPDATE_TOKEN + "_r"))
        recipients, _ = await us.collect_accounts(s)
    assert [u.email for u in recipients] == ["lookalike@example.com"]


# ── Newsletter audience ─────────────────────────────────────────────────────

async def test_newsletter_only_subscriber_is_a_recipient() -> None:
    async with session_scope() as s:
        await _sub(s, "reader@example.com")
        recipients, _ = await us.collect_newsletter_only(s)
    assert [r.email for r in recipients] == ["reader@example.com"]


async def test_a_subscriber_with_an_account_in_any_casing_is_skipped() -> None:
    async with session_scope() as s:
        await _user(s, "mixed@example.com")
        await _sub(s, "Mixed@Example.com")
        recipients, skipped = await us.collect_newsletter_only(s)
    assert recipients == []
    assert [r for _x, r in skipped] == ["has_account"]


@pytest.mark.parametrize(
    ("email", "kw", "reason"),
    [
        ("gone@example.com", {"status": "unsubscribed"}, "status_unsubscribed"),
        ("notoken@example.com", {"unsubscribe_token": ""}, "no_unsubscribe_token"),
        (sorted(ss.RESEND_SUPPRESSED)[0], {}, "resend_suppressed"),
    ],
)
async def test_newsletter_exclusions(email: str, kw: dict, reason: str) -> None:
    async with session_scope() as s:
        await _sub(s, email, **kw)
        recipients, skipped = await us.collect_newsletter_only(s)
    assert recipients == []
    assert [r for _x, r in skipped] == [reason]


async def test_an_opted_out_account_is_not_reached_through_the_list(
    https, outbox: list[dict],
) -> None:
    """Dedupe is against every account, not only the eligible ones."""
    async with session_scope() as s:
        await _user(s, "both@example.com", email_prefs=int(DEFAULT_PREFS & ~EmailPref.RE_ENGAGEMENT))
        await _sub(s, "Both@Example.com")
    await us.run(send=True, quiet=True, force_newsletter=True)
    assert outbox == [], f"sent to {[m['to'] for m in outbox]}"


# ── The run ─────────────────────────────────────────────────────────────────

async def test_dry_run_sends_and_stamps_nothing(https, outbox: list[dict]) -> None:
    async with session_scope() as s:
        await _user(s, "dry@example.com")
        await _sub(s, "drysub@example.com")
    counts = await us.run(send=False)
    assert outbox == [], "a dry run transmitted email"
    assert counts["would_send"] == 2
    assert us.UPDATE_TOKEN not in await _state("dry@example.com")


async def test_send_stamps_each_recipient(https, outbox: list[dict]) -> None:
    async with session_scope() as s:
        await _user(s, "one@example.com")
        await _user(s, "two@example.com", tokens=("re14", "weekly_2026W37"))
        await _sub(s, "list@example.com")
    counts = await us.run(send=True, quiet=True)
    assert sorted(m["to"] for m in outbox) == ["list@example.com", "one@example.com", "two@example.com"]
    assert counts["accounts_sent"] == 2 and counts["newsletter_sent"] == 1
    assert await _state("one@example.com") == {us.UPDATE_TOKEN}
    # Appended, not rewritten: other tokens survive.
    assert await _state("two@example.com") == {"re14", "weekly_2026W37", us.UPDATE_TOKEN}


async def test_a_second_run_sends_nothing(https, outbox: list[dict]) -> None:
    async with session_scope() as s:
        await _user(s, "once@example.com")
        await _sub(s, "oncesub@example.com")
    await us.run(send=True, quiet=True)
    first = sorted(m["to"] for m in outbox)
    outbox.clear()
    await us.run(send=True, quiet=True)
    assert first == ["once@example.com", "oncesub@example.com"]
    assert outbox == [], f"the second run re-sent to {[m['to'] for m in outbox]}"


async def test_a_retry_after_a_partial_failure_does_not_mail_the_list_again(
    https, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The realistic re-run: Resend cannot be reached for one account, a human
    re-dispatches the workflow, and the retry stamps that account. "This run
    stamped someone" is then true again, so only the first-run check stops the
    list being mailed a second time.

    The failure is a refused connection on purpose: Resend never had that
    email, so sending it again is the right recovery. An error that could come
    after Resend accepted it is the next test's case, and is not retried."""
    calls: list[str] = []
    fail_once = {"flaky@example.com"}

    async def _flaky(**kw):
        calls.append(kw["to"])
        if kw["to"] in fail_once:
            fail_once.discard(kw["to"])
            raise httpx.ConnectError("connection refused")
        return {"id": "re_ok"}

    monkeypatch.setattr("app.services.email.send_email", _flaky)
    async with session_scope() as s:
        await _user(s, "ok@example.com")
        await _user(s, "flaky@example.com")
        await _sub(s, "reader@example.com")

    first = await us.run(send=True, quiet=True)
    assert sorted(calls) == ["flaky@example.com", "ok@example.com", "reader@example.com"]
    assert first["failed"] == 1 and first["newsletter_sent"] == 1

    calls.clear()
    retry = await us.run(send=True, quiet=True)
    assert calls == ["flaky@example.com"], f"the retry sent to {calls}"
    assert retry["accounts_sent"] == 1 and retry["newsletter_sent"] == 0

    calls.clear()
    await us.run(send=True, quiet=True, force_newsletter=True)
    assert calls == ["reader@example.com"]


_REQ = httpx.Request("POST", "https://api.resend.com/emails")


def _status(code: int) -> httpx.HTTPStatusError:
    """What send_email's resp.raise_for_status() raises for this status."""
    return httpx.HTTPStatusError(
        f"HTTP {code}", request=_REQ, response=httpx.Response(code, request=_REQ),
    )


#: Errors that can arrive after Resend has queued the email. send_email posts
#: with timeout=10.0, then raise_for_status(), so each of these can follow an
#: accepted request.
OUTCOME_UNKNOWN = {
    "read_timeout": lambda: httpx.ReadTimeout("timed out", request=_REQ),
    "write_timeout": lambda: httpx.WriteTimeout("timed out", request=_REQ),
    "dropped_mid_response": lambda: httpx.RemoteProtocolError("server disconnected", request=_REQ),
    "reset_mid_response": lambda: httpx.ReadError("connection reset", request=_REQ),
    "http_500": lambda: _status(500),
    "http_504": lambda: _status(504),
}

#: Errors that prove Resend never had the email, so a retry must send it.
NEVER_REACHED_RESEND = {
    "connect_timeout": lambda: httpx.ConnectTimeout("timed out", request=_REQ),
    "connection_refused": lambda: httpx.ConnectError("refused", request=_REQ),
    "http_422_rejected": lambda: _status(422),
    "http_429_rate_limited": lambda: _status(429),
    "raised_before_the_post": lambda: RuntimeError("render failed"),
}


@pytest.mark.parametrize("make_error", OUTCOME_UNKNOWN.values(), ids=OUTCOME_UNKNOWN.keys())
async def test_an_error_after_resend_may_have_accepted_is_stamped_not_retried(
    https, monkeypatch: pytest.MonkeyPatch, make_error,
) -> None:
    """The reproduced double-send: the fake DELIVERS, then raises, on the first
    call. Before the fix run 1 counted failed=1 and left no stamp, and run 2 —
    the recovery the retry test above recommends — delivered it again."""
    delivered: list[str] = []

    async def _accepts_then_raises(**kw):
        delivered.append(kw["to"])
        if len(delivered) == 1:
            raise make_error()
        return {"id": "re_ok"}

    monkeypatch.setattr("app.services.email.send_email", _accepts_then_raises)
    async with session_scope() as s:
        await _user(s, "slow@example.com")

    first = await us.run(send=True, quiet=True)
    assert (first["unknown"], first["failed"], first["accounts_sent"]) == (1, 0, 0), first
    assert us.UPDATE_TOKEN in await _state("slow@example.com")

    await us.run(send=True, quiet=True)
    assert delivered == ["slow@example.com"], f"delivered {delivered}"


@pytest.mark.parametrize("make_error", NEVER_REACHED_RESEND.values(), ids=NEVER_REACHED_RESEND.keys())
async def test_an_error_that_proves_resend_never_had_it_is_retried(
    https, monkeypatch: pytest.MonkeyPatch, make_error,
) -> None:
    """The other side of the line: stamping these would mean a customer who
    was never mailed is never mailed, with the result line saying nothing."""
    calls: list[str] = []

    async def _fails_once(**kw):
        calls.append(kw["to"])
        if len(calls) == 1:
            raise make_error()
        return {"id": "re_ok"}

    monkeypatch.setattr("app.services.email.send_email", _fails_once)
    async with session_scope() as s:
        await _user(s, "refused@example.com")

    first = await us.run(send=True, quiet=True)
    assert (first["failed"], first["unknown"]) == (1, 0), first
    assert us.UPDATE_TOKEN not in await _state("refused@example.com")

    await us.run(send=True, quiet=True)
    assert calls == ["refused@example.com", "refused@example.com"]
    assert us.UPDATE_TOKEN in await _state("refused@example.com")


def test_every_httpx_error_is_classified_on_purpose() -> None:
    """Enumerated from httpx itself, not from a list kept here: an httpx
    upgrade that adds an error type fails this until someone decides whether
    it can follow an accepted request."""
    exported = [getattr(httpx, name) for name in httpx.__all__]
    errors = {c for c in exported if isinstance(c, type) and issubclass(c, Exception)}
    leaves = {c for c in errors if not any(o is not c and issubclass(o, c) for o in errors)}
    # Self-test: the enumeration reaches the classes this guard exists for.
    assert {httpx.ReadTimeout, httpx.ConnectTimeout, httpx.HTTPStatusError} <= leaves

    after_the_request = {
        httpx.ReadTimeout, httpx.WriteTimeout, httpx.ReadError, httpx.WriteError,
        httpx.CloseError, httpx.RemoteProtocolError, httpx.DecodingError,
    }
    before_resend_has_it = {
        httpx.ConnectTimeout, httpx.PoolTimeout, httpx.ConnectError,
        httpx.LocalProtocolError, httpx.UnsupportedProtocol, httpx.ProxyError,
        httpx.TooManyRedirects, httpx.InvalidURL, httpx.CookieConflict,
        httpx.StreamConsumed, httpx.StreamClosed, httpx.ResponseNotRead,
        httpx.RequestNotRead,
    }
    unclassified = leaves - after_the_request - before_resend_has_it - {httpx.HTTPStatusError}
    assert not unclassified, f"decide which side these are on: {sorted(c.__name__ for c in unclassified)}"
    # Classified by type, so an instance built without its constructor is enough.
    for cls in after_the_request:
        assert us._outcome_unknown(cls.__new__(cls)), cls.__name__
    for cls in before_resend_has_it:
        assert not us._outcome_unknown(cls.__new__(cls)), cls.__name__
    for code in (400, 401, 403, 404, 409, 422, 429, 499):
        assert not us._outcome_unknown(_status(code)), code
    for code in (500, 502, 503, 504, 599):
        assert us._outcome_unknown(_status(code)), code


async def test_a_run_whose_only_stamp_is_outcome_unknown_still_mails_the_list(
    https, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer 3 asks whether a re-run could tell this run happened. An
    outcome-unknown stamp answers yes, so a re-run would skip the list; if this
    run skipped it too, the list would never be mailed without a human."""
    sent: list[str] = []

    async def _account_times_out(**kw):
        sent.append(kw["to"])
        if kw["to"] == "slow@example.com":
            raise httpx.ReadTimeout("timed out", request=_REQ)
        return {"id": "re_ok"}

    monkeypatch.setattr("app.services.email.send_email", _account_times_out)
    async with session_scope() as s:
        await _user(s, "slow@example.com")
        await _sub(s, "reader@example.com")
    counts = await us.run(send=True, quiet=True)
    assert sent == ["slow@example.com", "reader@example.com"]
    assert (counts["unknown"], counts["newsletter_sent"]) == (1, 1), counts


@pytest.mark.parametrize(
    ("make_error", "key"),
    [(OUTCOME_UNKNOWN["read_timeout"], "unknown"), (NEVER_REACHED_RESEND["connect_timeout"], "failed")],
    ids=["unknown", "failed"],
)
async def test_a_newsletter_error_is_counted_by_what_it_means(
    https, monkeypatch: pytest.MonkeyPatch, make_error, key: str,
) -> None:
    """There is no per-subscriber stamp, so the count is the only thing that
    tells the operator whether Resend's log needs checking."""
    async def _list_send_raises(**kw):
        if kw["to"] == "reader@example.com":
            raise make_error()
        return {"id": "re_ok"}

    monkeypatch.setattr("app.services.email.send_email", _list_send_raises)
    async with session_scope() as s:
        await _user(s, "one@example.com")
        await _sub(s, "reader@example.com")
    counts = await us.run(send=True, quiet=True)
    other = {"unknown": "failed", "failed": "unknown"}[key]
    assert (counts[key], counts[other], counts["newsletter_sent"]) == (1, 0, 0), counts


async def test_a_run_that_stamps_no_account_does_not_mail_the_list(
    https, outbox: list[dict],
) -> None:
    """Without this, a run whose account phase sent nothing leaves no trace, and
    a re-run would mail every newsletter subscriber a second time."""
    async with session_scope() as s:
        await _user(s, "quiet@example.com", email_prefs=int(DEFAULT_PREFS & ~EmailPref.RE_ENGAGEMENT))
        await _sub(s, "reader@example.com")
    counts = await us.run(send=True, quiet=True)
    assert outbox == [] and counts["newsletter_sent"] == 0

    await us.run(send=True, quiet=True, force_newsletter=True)
    assert [m["to"] for m in outbox] == ["reader@example.com"]


async def test_a_killed_run_keeps_the_tokens_it_already_earned(
    https, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dropped `flyctl ssh` session, simulated. CancelledError is a
    BaseException: nothing in the loop catches it and session_scope does not
    commit on the way out, so only a per-recipient commit keeps the first token."""
    calls: list[str] = []

    async def _dies_on_second(**kw):
        calls.append(kw["to"])
        if len(calls) == 2:
            raise asyncio.CancelledError()
        return {"id": "re_1"}

    monkeypatch.setattr("app.services.email.send_email", _dies_on_second)
    async with session_scope() as s:
        await _user(s, "first@example.com")
        await _user(s, "second@example.com")

    with pytest.raises(asyncio.CancelledError):
        await us.run(send=True, quiet=True)

    stamped = {
        e for e in ("first@example.com", "second@example.com")
        if us.UPDATE_TOKEN in await _state(e)
    }
    assert stamped == {calls[0]}, f"sent to {calls[0]} before the kill, but stamped {stamped}"


async def test_a_skipped_send_is_not_stamped(https, monkeypatch: pytest.MonkeyPatch) -> None:
    """send_email returns skipped when there is no Resend key. Stamping that
    would record an email nobody received, and a real run would then skip them."""
    async def _skipped(**kw):
        return {"skipped": True, "reason": "no_api_key"}

    monkeypatch.setattr("app.services.email.send_email", _skipped)
    async with session_scope() as s:
        await _user(s, "notyet@example.com")
    counts = await us.run(send=True, quiet=True)
    assert counts["not_sent"] == 1
    assert us.UPDATE_TOKEN not in await _state("notyet@example.com")


async def test_the_send_loop_still_refuses_what_the_governor_can_see(
    https, outbox: list[dict], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In this process the governor's ledger is empty (it is per process, and
    this runs over a fresh `flyctl ssh`), so its gap and weekly cap never fire.
    What it can still see — global opt-out, undeliverable, sunset — is a second
    layer behind collect_accounts. This pins that layer: with the collection
    bypassed, the loop alone must still hold all three back."""
    async with session_scope() as s:
        await _user(s, "allout@example.com", email_prefs=0)
        await _user(s, "dead@example.com", email_undeliverable_at=datetime(2026, 9, 1, tzinfo=UTC))
        await _user(s, "dormant@example.com", tokens=("re14", "re24", "re_sunset"))
        await _user(s, "fine@example.com")

    async def _unfiltered(session):
        return list((await session.execute(select(User))).scalars().all()), []

    monkeypatch.setattr(us, "collect_accounts", _unfiltered)
    counts = await us.run(send=True, quiet=True)
    assert [m["to"] for m in outbox] == ["fine@example.com"]
    assert counts["governed"] == 3, counts


async def test_send_refuses_a_non_https_app_url(monkeypatch: pytest.MonkeyPatch, outbox) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "app_url", "http://localhost:3000", raising=False)
    monkeypatch.setattr(get_settings(), "session_secret", "test-secret", raising=False)
    with pytest.raises(SystemExit, match="not a public https URL"):
        await us.run(send=True, quiet=True)


async def test_send_refuses_without_a_signing_secret(monkeypatch: pytest.MonkeyPatch, outbox) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "app_url", "https://tapeline.io", raising=False)
    monkeypatch.setattr(get_settings(), "session_secret", "", raising=False)
    async with session_scope() as s:
        await _user(s, "nolink@example.com")
    with pytest.raises(SystemExit, match="SESSION_SECRET"):
        await us.run(send=True, quiet=True)
    assert outbox == []


# ── What each audience receives ─────────────────────────────────────────────

async def test_each_audience_gets_its_own_copy_and_opt_out(https, outbox: list[dict]) -> None:
    from app.services.email import PRODUCT_UPDATE_SUBJECT
    from app.services.email_design import UNSUB_PLACEHOLDER

    async with session_scope() as s:
        await _user(s, "david@example.com", name="David Eley")
        await _sub(s, "reader@example.com")
    await us.run(send=True, quiet=True)
    by_to = {m["to"]: m for m in outbox}
    acct, news = by_to["david@example.com"], by_to["reader@example.com"]

    for m in (acct, news):
        assert m["subject"] == PRODUCT_UPDATE_SUBJECT
        assert "/api/" in m["text"] and "unsubscribe" in m["text"].lower()

    assert "Hi David," in acct["html"] and "Hi David," in acct["text"]
    assert ACCOUNT_ONLY_MARKER in acct["html"] and ACCOUNT_ONLY_MARKER in acct["text"]
    # Account holders: the audited user-keyed path resolves the footer link.
    assert UNSUB_PLACEHOLDER in acct["html"]
    assert acct["unsubscribe_user_id"] and acct["unsubscribe_category"] == "re_engagement"

    assert "Hi there," in news["html"] and "Hi there," in news["text"]
    assert ACCOUNT_ONLY_MARKER not in news["html"], "newsletter subscribers never had a free account"
    assert ACCOUNT_ONLY_MARKER not in news["text"], "newsletter subscribers never had a free account"
    # Newsletter: the list's own link, inside the footer, plus its headers.
    assert UNSUB_PLACEHOLDER not in news["html"]
    assert "/api/newsletter/unsubscribe?token=tok_reader" in news["html"]
    assert news["html"].rstrip().endswith("</html>")
    assert "List-Unsubscribe" in news["headers"]


@pytest.mark.parametrize("audience", ["account", "newsletter"])
def test_both_parts_carry_the_approved_copy_verbatim(audience: str) -> None:
    from app.services.email import render_product_update_email, render_product_update_text

    expected = APPROVED_COPY
    if audience == "newsletter":
        blocks = [b for b in APPROVED_COPY.split("\n\n") if ACCOUNT_ONLY_MARKER not in b]
        assert len(blocks) == len(APPROVED_COPY.split("\n\n")) - 1
        expected = "\n\n".join(blocks)

    text = render_product_update_text(
        "Sam", scorecard_url=SCORECARD, audience=audience,
        unsubscribe_url="https://tapeline.io/api/unsubscribe?token=t",
    )
    assert text.split("\n\n--\n")[0] == expected

    html = render_product_update_email(
        "Sam", scorecard_url=SCORECARD, audience=audience,
        newsletter_unsubscribe_url="https://tapeline.io/api/newsletter/unsubscribe?token=t",
    )
    body, slot = _split_rendered(html)
    # EQUAL, not "contains": an added sentence, a reordered section or a block
    # moved below the sign-off all pass a containment check.
    assert _visible_text(body) == _squash(expected), f"{audience} HTML body is not the approved copy"
    assert _paragraph_texts(body) == [_squash(b) for b in expected.split("\n\n")]
    assert re.fullmatch(r"(?:\s*<p\b[^>]*>.*?</p>)*\s*", body, re.S), "the body holds more than paragraphs"
    assert "display:none" not in html, "hidden text in an email nobody approved line by line"

    from app.services.email_design import UNSUB_PLACEHOLDER

    if audience == "account":
        assert slot == UNSUB_PLACEHOLDER  # send_email resolves it for account holders
    else:
        assert _visible_text(slot) == "Unsubscribe — one click, no sign-in needed."


def test_the_section_headings_are_bold_in_html() -> None:
    """Headings are derived from the approved copy — a block whose first line
    stands alone above its body — not from the constant the renderer uses."""
    from app.services.email import render_product_update_email

    headings = [b.split("\n")[0] for b in APPROVED_COPY.split("\n\n") if "\n" in b]
    assert len(headings) == 5, headings  # self-test: the detector found the headings
    html = render_product_update_email("Sam", scorecard_url=SCORECARD, audience="account")
    for h in headings:
        assert f"<strong>{h}</strong>" in html, f"not bold: {h!r}"
    assert html.count("<strong>") == len(headings) + 1  # + the footer's "Not investment advice."


def test_the_scorecard_link_follows_app_url() -> None:
    from app.services.email import render_product_update_email

    html = render_product_update_email("Sam", scorecard_url=SCORECARD, audience="account")
    assert f'href="{SCORECARD}"' in html
    assert ">tapeline.io/scorecard</a>" in html


def test_a_typed_name_cannot_inject_markup() -> None:
    from app.services.email import render_product_update_email

    html = render_product_update_email("<b>x</b>", scorecard_url=SCORECARD, audience="account")
    assert "Hi &lt;b&gt;x&lt;/b&gt;," in html


def test_a_newsletter_copy_without_an_opt_out_is_refused() -> None:
    from app.services.email import render_product_update_email

    with pytest.raises(ValueError, match="unsubscribe"):
        render_product_update_email("there", scorecard_url=SCORECARD, audience="newsletter")


def test_the_open_access_sentence_is_still_true() -> None:
    """Both numbers in it are read from the copy and checked against
    services/tier.py. If the founder extends the promo, or retunes the free
    row cap, before this goes out, the build fails instead of the email lying."""
    from app.services.email import PRODUCT_UPDATE_ACCOUNT_ONLY
    from app.services.tier import FREE_SCANNER_ROWS, PROMO_OPEN_ACCESS_UNTIL

    day = re.search(r"ended on (\d+) (\w+)", PRODUCT_UPDATE_ACCOUNT_ONLY)
    rows = re.search(r"top (\d+) rows", PRODUCT_UPDATE_ACCOUNT_ONLY)
    assert day and rows, "the detector no longer finds the numbers in the sentence"
    assert int(day.group(1)) == PROMO_OPEN_ACCESS_UNTIL.day
    assert day.group(2) == f"{PROMO_OPEN_ACCESS_UNTIL:%B}"
    assert int(rows.group(1)) == FREE_SCANNER_ROWS


def test_the_universe_count_is_the_one_the_rest_of_the_copy_uses() -> None:
    """The heading's count is read from the copy and checked against
    services/universe.py, the number every other email and the site's
    frontend/lib/universe.ts print. #826 re-measured it the night this email
    was merged; a re-measure before the send fails the build instead of this
    email disagreeing with the site."""
    from app.services.email import PRODUCT_UPDATE_SECTIONS
    from app.services.universe import SCORED_TICKERS_IN_COPY

    counts = [
        m.group(1)
        for heading, _body in PRODUCT_UPDATE_SECTIONS
        for m in [re.search(r"covers about ([\d,]+) stocks and ETFs", heading)]
        if m
    ]
    assert len(counts) == 1, "the detector no longer finds the universe heading"
    assert int(counts[0].replace(",", "")) == SCORED_TICKERS_IN_COPY


@pytest.mark.parametrize("audience", ["account", "newsletter"])
def test_the_update_repeats_none_of_the_sentences_withdrawn_on_14_september(audience: str) -> None:
    """Checked against the pull requests and production on 2026-09-14 and
    reworded before the send:

    - "stalled several more times before recovering on its own": the cloud
      watchdog found the worker's tick stale on 30 of its 34 runs from 6 to
      11 September and restarted the worker machines each time. It never
      recovered on its own; #797, #798 and #800 (10 Sep) and the dedicated
      machine in #807 (11 Sep) fixed it.
    - "it has not stalled since 11 September": the fundamentals and insider
      refresh stalled from 11 to 13 September and lost readings on deploys
      (#822, #825, #828, #829).
    - "At the start of the month it was about 2,000": on 1 September 6,757
      tickers were scored and the refresh cap was 2,500; ~1,836 was only the
      default view, measured just before #763.
    - "the lower number is the accurate one": that week scores also moved on
      stale price bars and on the factor fixes, so no single number was.
    - "flattered most stocks": the renamed columns affected the ~4,100
      spreadsheet-based scores, not most of ~11,500.
    - "Crypto is in: 100 pairs": 110 pairs were scored on 14 September.
    - "stopped updating for about a day": three factors ran on 6 September
      price data for four days.
    """
    from app.services.email import render_product_update_email, render_product_update_text

    text = render_product_update_text(
        "Sam", scorecard_url=SCORECARD, audience=audience,
        unsubscribe_url="https://tapeline.io/api/unsubscribe?token=t",
    )
    html_body, _slot = _split_rendered(render_product_update_email(
        "Sam", scorecard_url=SCORECARD, audience=audience,
        newsletter_unsubscribe_url="https://tapeline.io/api/newsletter/unsubscribe?token=t",
    ))
    for part, content in (("text", _squash(text)), ("html", _visible_text(html_body))):
        for withdrawn in (
            r"recover\w* on its own",
            r"(?:has not|hasn't|not) stalled since",
            r"about 2,000",
            r"lower number is the accurate",
            r"flattered most",
            r"crypto is in: 100 pairs",
            r"stopped updating for about a day",
        ):
            assert not re.search(withdrawn, content, re.I), (
                f"{audience} {part} repeats a withdrawn claim: {withdrawn!r}"
            )


@pytest.mark.parametrize("audience", ["account", "newsletter"])
def test_the_update_sells_nothing(audience: str) -> None:
    """The consent basis is a relationship plus a message that promotes nothing.
    ("you should" is not banned here, unlike the survey: the copy's only use is
    "you should hear about from us", which is not advice.)"""
    from app.services.email import render_product_update_email, render_product_update_text

    text = render_product_update_text(
        "Sam", scorecard_url=SCORECARD, audience=audience, unsubscribe_url="https://x/u",
    ).split("Not investment advice")[0]
    # The HTML body is checked on its own: a line added to the HTML renderer
    # alone never reaches the text part. The footer is left out because
    # _split_rendered proves it is the shared shell's, which says "recommendation".
    html_body, _slot = _split_rendered(render_product_update_email(
        "Sam", scorecard_url=SCORECARD, audience=audience, newsletter_unsubscribe_url="https://x/u",
    ))
    for part, content in (("text", text), ("html", _visible_text(html_body))):
        for banned in (
            r"\bbuy\b", r"\bsell\b", r"\brecommend", r"last chance", r"hurry",
            r"limited time", r"expire", r"free trial", r"\$\s?\d", r"discount",
            r"\boffer\b", r"upgrade", r"beat the market", r"guarantee",
            r"\bsave\b", r"\d+\s?% off", r"act now",
        ):
            assert not re.search(banned, content, re.I), f"{audience} {part}: {banned!r} in the update"


def test_the_copy_lives_where_the_copy_linter_reads() -> None:
    """scripts/ is outside the linter's include globs. Moving the subject or the
    renderer there would take them out of its sight without any failure."""
    from app.services import email

    allow = json.loads((ROOT / "scripts" / "copy-compliance.allow.json").read_text(encoding="utf-8"))
    rel = pathlib.Path(inspect.getsourcefile(email.render_product_update_email)).resolve()
    rel = rel.relative_to(ROOT).as_posix()
    assert any(fnmatch.fnmatch(rel, g) for g in allow["include"]), rel
    assert hasattr(email, "PRODUCT_UPDATE_SUBJECT")
    assert not re.search(r"^PRODUCT_UPDATE_SUBJECT\s*=|What changed at Tapeline",
                         inspect.getsource(us), re.M)


# ── Nothing address-shaped in public output ─────────────────────────────────

async def test_quiet_prints_no_address(capsys, https, outbox: list[dict]) -> None:
    async with session_scope() as s:
        await _user(s, "private@example.com")
        await _sub(s, "alsoprivate@example.com")
    await us.run(send=True, quiet=True)
    assert len(outbox) == 2  # self-test: there were addresses to leak
    captured = capsys.readouterr()
    assert "result:" in captured.out
    assert "@" not in captured.out + captured.err, (
        f"an address reached output the workflow publishes:\n{captured.out}{captured.err}"
    )


def test_the_redacting_formatter_removes_addresses_even_from_tracebacks() -> None:
    try:
        raise RuntimeError("resend rejected <a.b+c@example.co.uk>")
    except RuntimeError:
        import sys

        exc_info = sys.exc_info()
    record = logging.LogRecord(
        "app.services.email", logging.WARNING, __file__, 1,
        "email.skipped reason=no_api_key to=%s", ("leak@example.com",), exc_info,
    )
    # Self-test: an ordinary formatter DOES leak this record.
    assert "@" in logging.Formatter("%(message)s").format(record)
    record.exc_text = None
    out = us.RedactAddresses("%(message)s").format(record)
    assert "email.skipped" in out and "<address>" in out
    assert "@" not in out, out


@pytest.fixture
def restore_root_logging():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def test_main_quiet_routes_logs_through_the_redactor(
    monkeypatch: pytest.MonkeyPatch, capsys, restore_root_logging,
) -> None:
    """send_email logs `to=` on its no-key and undeliverable paths, and a script
    with no logging configured prints WARNING+ to stderr — the public log."""
    seen: dict = {}

    async def _fake_run(**kw):
        seen.update(kw)
        logging.getLogger("app.services.email").warning(
            "email.skipped reason=no_api_key to=%s", "leak@example.com",
        )
        return {}

    monkeypatch.setattr(us, "run", _fake_run)
    monkeypatch.setattr(us.asyncio, "set_event_loop_policy", lambda _p: None)
    us.main(["--send", "--quiet"])
    err = capsys.readouterr().err
    assert seen == {"send": True, "quiet": True, "force_newsletter": False}
    assert "email.skipped" in err  # self-test: the log line did reach stderr
    assert "@" not in err, err


# ── The workflow ────────────────────────────────────────────────────────────

def _workflow_doc(raw: str | None = None) -> dict:
    """The workflow as GitHub reads it. Parsed, not pattern-matched: YAML drops
    comments, and the header prose discusses --quiet, the dates and the
    triggers at length, so a guard that could match prose would pass with any
    of them deleted from the code."""
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8") if raw is None else raw)
    # YAML 1.1 reads a bare `on:` key as the boolean True.
    if True in doc:
        doc["on"] = doc.pop(True)
    return doc


def _steps(doc: dict) -> list[dict]:
    jobs = doc["jobs"]
    assert len(jobs) == 1, f"jobs {sorted(jobs)}: a second job would run without the window step"
    (job,) = jobs.values()
    return job["steps"]


def _window_step(doc: dict) -> dict:
    (step,) = [s for s in _steps(doc) if s.get("id") == "window"]
    return step


def _update_send_commands(doc: dict) -> list[str]:
    """Every shell line, in every step of every job, that runs update_send."""
    commands = []
    for job in doc["jobs"].values():
        for step in job["steps"]:
            script = (step.get("run") or "").replace("\\\n", " ")
            commands += [
                line.strip() for line in script.splitlines()
                if "update_send" in line and not line.lstrip().startswith("#")
            ]
    return commands


def _flags(command: str) -> set[str]:
    return set(re.findall(r"(?<![\w-])--[a-z][\w-]*", command))


def _window(raw: str) -> tuple[datetime, datetime]:
    run = _window_step(_workflow_doc(raw))["run"]
    start = re.search(r'start=\$\(date -u -d "([^"]+)"', run)
    end = re.search(r'end=\$\(date -u -d "([^"]+)"', run)
    assert start and end, "no date window found in the window step"
    parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))  # noqa: E731
    return parse(start.group(1)), parse(end.group(1))


def _cron_fire(raw: str) -> datetime:
    (entry,) = _workflow_doc(raw)["on"]["schedule"]
    m = re.fullmatch(r"(\d+) (\d+) (\d+) (\d+) \*", entry["cron"])
    assert m, f"not a single-date cron: {entry['cron']!r}"
    minute, hour, dom, month = map(int, m.groups())
    return datetime(_window(raw)[0].year, month, dom, hour, minute, tzinfo=UTC)


def test_the_workflow_sends_quietly() -> None:
    commands = _update_send_commands(_workflow_doc())
    assert commands, "no update_send command found in the workflow"
    for command in commands:
        assert "--quiet" in _flags(command), (
            f"{command} — without --quiet every address lands in a public log"
        )
    sending = [c for c in commands if "--send" in _flags(c)]
    assert len(sending) == 1, f"{commands} — without --send the scheduled run is a dry run"
    assert '-C "python -m app.scripts.update_send ' in sending[0], sending[0]


def test_the_command_detector_cannot_be_fooled() -> None:
    """Self-test, on both broken shapes: the flag dropped from the real command
    while a commented-out copy still carries it, and a second step that runs
    update_send without it — which reading only the first `-C` missed."""
    raw = WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")
    real = (
        '          flyctl ssh console -a tapeline-backend \\\n'
        '            -C "python -m app.scripts.update_send --send --quiet"'
    )
    assert raw.count(real) == 1, "the detector's fixture no longer matches the workflow"

    commented = raw.replace(
        real,
        '          # flyctl ssh console -a tapeline-backend -C "python -m app.scripts.update_send --send --quiet"\n'
        + real.replace(" --quiet", ""),
    )
    assert "--quiet" in commented
    assert ["--quiet" in _flags(c) for c in _update_send_commands(_workflow_doc(commented))] == [False]

    second_step = raw.rstrip("\n") + (
        "\n\n      - name: Dry run as well\n"
        "        if: steps.window.outputs.go == 'true'\n"
        '        run: flyctl ssh console -a tapeline-backend -C "python -m app.scripts.update_send"\n'
    )
    assert ["--quiet" in _flags(c) for c in _update_send_commands(_workflow_doc(second_step))] == [True, False]


def test_only_the_schedule_or_a_manual_dispatch_can_start_it() -> None:
    """A `push` trigger would send on merge whatever the cron says, leaving the
    window as the only thing between a merge and the list."""
    on = _workflow_doc()["on"]
    assert set(on) == {"schedule", "workflow_dispatch"}, sorted(on)
    assert not on["workflow_dispatch"], "workflow_dispatch must take no inputs"
    assert len(on["schedule"]) == 1


def test_a_second_run_queues_behind_the_first_and_never_cancels_it() -> None:
    """cancel-in-progress would kill a run mid-loop by dropping its `flyctl ssh`
    session: the failure layer 1 exists to survive, not one to cause on purpose.
    Without the group, two runs overlap and only the database lock is left."""
    assert _workflow_doc()["concurrency"] == {
        "group": "product-update-send", "cancel-in-progress": False,
    }


def test_every_step_after_the_window_is_gated_by_it() -> None:
    steps = _steps(_workflow_doc())
    assert steps[0].get("id") == "window", "the window step must run before anything else"
    for step in steps[1:]:
        assert step.get("if") == "steps.window.outputs.go == 'true'", (
            f"step {step.get('name')!r} runs whether or not the window is open"
        )


def _bash() -> str:
    bash = shutil.which("bash")
    # Failed, not skipped: CI runs on Linux, where bash is always present, and a
    # skipped guard is one nobody notices has stopped guarding.
    assert bash, "bash is needed to run the workflow's window step"
    return bash


#: Stands in for `date` inside the step: a call that parses a date string goes
#: to the real GNU date, so the step's own arithmetic runs; the "now" call gets
#: FAKE_NOW. A shell function rather than a PATH stub, so it behaves the same
#: under Git Bash on Windows.
_DATE_STUB = (
    'date() { case " $* " in *" -d "*|*" --date"*) command date "$@" ;; '
    '*) echo "$FAKE_NOW" ;; esac; }\n'
)


def _run_window_step(run: str, now: datetime, tmp_path: pathlib.Path) -> str:
    output = tmp_path / f"github_output_{int(now.timestamp())}"
    output.write_text("")
    proc = subprocess.run(
        [_bash(), "-c", _DATE_STUB + run],
        env={**os.environ, "FAKE_NOW": str(int(now.timestamp())), "GITHUB_OUTPUT": output.as_posix()},
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return output.read_text().strip()


def test_the_window_step_opens_only_inside_its_window(tmp_path: pathlib.Path) -> None:
    """Runs the step's own shell, so the comparison is tested — not only the
    two date strings, which a swapped echo, a deleted condition or an inverted
    operator all leave exactly as they were. The go=true cases fall outside
    the real clock on any day but 15 Sep 2026 and the go=false ones inside it,
    so between them they also prove the stub, not the clock, decided."""
    raw = WORKFLOW.read_text(encoding="utf-8")
    run = _window_step(_workflow_doc(raw))["run"]
    start, end = _window(raw)
    fires = _cron_fire(raw)
    second = timedelta(seconds=1)
    expected = {
        start - second: "go=false",
        start: "go=true",
        fires: "go=true",
        end - second: "go=true",
        end: "go=false",
        fires.replace(year=fires.year + 1): "go=false",       # the cron has no year field
        datetime(2026, 9, 14, 13, 7, tzinfo=UTC): "go=false",  # the first draft's slot
    }
    got = {when: _run_window_step(run, when, tmp_path) for when in expected}
    assert got == expected


def test_the_window_harness_catches_swapped_outputs(tmp_path: pathlib.Path) -> None:
    """Self-test: the broken shape is the two echoes swapped, which leaves both
    date strings, all the earlier test read, untouched."""
    raw = WORKFLOW.read_text(encoding="utf-8")
    run = _window_step(_workflow_doc(raw))["run"]
    assert run.count('"go=false"') == 1 and run.count('"go=true"') == 1
    swapped = (
        run.replace('"go=false"', '"go=SWAP"')
        .replace('"go=true"', '"go=false"')
        .replace('"go=SWAP"', '"go=true"')
    )
    assert _run_window_step(swapped, _cron_fire(raw), tmp_path) == "go=false"


#: Importing one of these is what sending customer mail looks like in the worker.
CUSTOMER_MAIL_MODULES = frozenset({"app.services.email", "app.services.newsletter"})


def _customer_mail_hours(source: str) -> set[int]:
    """UTC hours from which the worker sends customer mail by the clock, read
    from its source: every `if ... <x>.hour >= N ...:` whose body imports a mail
    module, directly or through a function defined in the same file (the Daily
    Top 10 is dispatched as `_spawn(_run_daily_newsletter(...))`)."""
    tree = ast.parse(source)
    local = {
        n.name: n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    def imports_mail(node: ast.AST) -> bool:
        if isinstance(node, ast.ImportFrom) and node.module:
            names = {node.module} | {f"{node.module}.{a.name}" for a in node.names}
            return bool(names & CUSTOMER_MAIL_MODULES)
        if isinstance(node, ast.Import):
            return any(a.name in CUSTOMER_MAIL_MODULES for a in node.names)
        return False

    def sends_mail(node: ast.AST, seen: set[str]) -> bool:
        for sub in ast.walk(node):
            if imports_mail(sub):
                return True
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                name = sub.func.id
                if name in local and name not in seen:
                    seen.add(name)
                    if sends_mail(local[name], seen):
                        return True
        return False

    hours: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        gates = {
            c.comparators[0].value
            for c in ast.walk(node.test)
            if isinstance(c, ast.Compare) and len(c.ops) == 1 and isinstance(c.ops[0], ast.GtE)
            and isinstance(c.left, ast.Attribute) and c.left.attr == "hour"
            and isinstance(c.comparators[0], ast.Constant) and isinstance(c.comparators[0].value, int)
        }
        if gates and any(sends_mail(stmt, set()) for stmt in node.body):
            hours |= gates
    return hours


def test_the_mail_hour_detector_matches_the_shapes_it_must() -> None:
    """Self-test: a gate reached through a spawned local function and a gate
    with a direct import are found; a gate that mails only the founder is not."""
    synthetic = (
        "async def tick(started):\n"
        "    if started.hour >= 5 and started.weekday() < 5:\n"
        "        _spawn(_send_list(started), key='x')\n"
        "    if started.hour >= 7:\n"
        "        from app.services.growth_bot import run_daily_growth_tick\n"
        "    if iso_dow == 1 and started.hour >= 9:\n"
        "        from app.services import email\n"
        "async def _send_list(started):\n"
        "    from app.services.newsletter import run_daily_digest\n"
    )
    assert _customer_mail_hours(synthetic) == {5, 9}


#: How far EVERY moment of the window stays from the worker's customer mail —
#: the whole window, not only the cron, because the manual fallback can be
#: dispatched at any moment inside it.
WINDOW_CLEARANCE = timedelta(hours=2)

#: How far the scheduled fire stays from it. The worker's hours are 13:00 and
#: 21:00 UTC and the list is mostly US (survey-reminder.yml), so 4 hours from
#: each, at 17:00, is the most US business hours allow. Less 15 minutes,
#: because the cron sits a few minutes off :00 on purpose (Actions bunches
#: scheduled runs at the hour), and 17:07 is 3h53 from 21:00.
FIRE_CLEARANCE = timedelta(hours=4) - timedelta(minutes=15)


def test_the_send_stays_clear_of_the_workers_own_mail() -> None:
    """The first draft fired at 13:07 UTC on a Monday, 7 minutes after the
    worker starts the weekly digest and the Daily Top 10. The script cannot
    space itself from them: the governor's ledger is per process, and the
    `flyctl ssh` process this runs in starts with it empty."""
    hours = _customer_mail_hours(WORKER.read_text(encoding="utf-8"))
    # Self-test on the real worker: its 13:00 UTC sends are still found.
    assert 13 in hours, f"the detector no longer finds the worker's 13:00 UTC sends: {hours}"
    raw = WORKFLOW.read_text(encoding="utf-8")
    start, end = _window(raw)
    fires = _cron_fire(raw)
    day = start.date() - timedelta(days=1)
    while day <= end.date() + timedelta(days=1):
        for hour in sorted(hours):
            mail = datetime.combine(day, time(hour), tzinfo=UTC)
            assert mail <= start - WINDOW_CLEARANCE or mail >= end + WINDOW_CLEARANCE, (
                f"the worker sends at {mail}, within {WINDOW_CLEARANCE} of the window [{start}, {end})"
            )
            assert abs(fires - mail) >= FIRE_CLEARANCE, (
                f"the cron fires at {fires}, {abs(fires - mail)} from the worker's send at {mail}"
            )
        day += timedelta(days=1)


def test_the_window_can_never_reach_the_survey_reminder_day() -> None:
    from app.services.lifecycle import MIN_LIFECYCLE_GAP_HOURS

    raw = WORKFLOW.read_text(encoding="utf-8")
    start, end = _window(raw)
    reminder_day_starts = datetime.combine(SURVEY_REMINDER_DAY, datetime.min.time(), tzinfo=UTC)
    assert start < end
    assert end <= reminder_day_starts, f"window ends {end}, on or after the reminder's day"
    assert end < datetime(2026, 9, 16, 13, 0, tzinfo=UTC)
    if REMINDER_WORKFLOW.exists():  # deleted after the reminder goes; the constant then stands
        r_raw = REMINDER_WORKFLOW.read_text(encoding="utf-8")
        r_start, _ = _window(r_raw)
        assert r_start.date() == SURVEY_REMINDER_DAY
        assert end <= r_start
        # The gap the governor would enforce between two lifecycle emails, had
        # both gone through one process's ledger.
        gap = _cron_fire(r_raw) - _cron_fire(raw)
        assert gap >= timedelta(hours=MIN_LIFECYCLE_GAP_HOURS), f"the reminder follows only {gap} later"


def test_the_schedule_fires_inside_its_own_window() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    start, end = _window(raw)
    fires = _cron_fire(raw)
    assert start <= fires < end, f"cron fires {fires}, outside [{start}, {end})"


def test_the_workflow_is_marked_held_and_pinned() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "FOUNDER-APPROVED 2026-09-13" in raw
    assert "DELETE THIS FILE" in raw
    (uses,) = [s["uses"] for s in _steps(_workflow_doc(raw)) if "uses" in s]
    pin = re.fullmatch(r"superfly/flyctl-actions/setup-flyctl@([0-9a-f]{40})", uses)
    assert pin, f"flyctl action is not pinned to a commit SHA: {uses}"
    if REMINDER_WORKFLOW.exists():
        r_pin = re.search(r"setup-flyctl@([0-9a-f]{40})", REMINDER_WORKFLOW.read_text(encoding="utf-8"))
        assert r_pin and r_pin.group(1) == pin.group(1)


# ── Concurrency ─────────────────────────────────────────────────────────────

def test_the_update_holds_its_own_registered_lock() -> None:
    """The id must come from dblock's registry and be unique there: sharing a
    number with a real email job would make them block each other."""
    from app.services import dblock

    assert us.run._one_machine_lock_id == dblock.LOCK_PRODUCT_UPDATE
    ids = [v for k, v in vars(dblock).items() if k.startswith("LOCK_") and k != "LOCK_NAMESPACE"]
    assert len(ids) == len(set(ids)), f"a lock id is reused: {sorted(ids)}"


async def test_a_run_that_loses_the_lock_sends_nothing(
    https, outbox: list[dict], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dblock is a no-op on SQLite, so the loss is simulated at the one seam
    every lock goes through."""
    from app.services import dblock

    async def _lost(_session, _objid):
        return False

    monkeypatch.setattr(dblock, "try_xact_lock", _lost)
    async with session_scope() as s:
        await _user(s, "racer@example.com")
        await _sub(s, "racersub@example.com")
    assert await us.run(send=True, quiet=True) == {}
    assert outbox == [], "a run that lost the lock still sent email"


def test_the_update_makes_no_claim_about_the_record_that_is_false() -> None:
    """Two sentences were cut from the approved copy on 2026-09-13, after an
    integrity review verified against production that both were false:

    - "We freeze the daily Top 10 ... and never edit it": all 190 published
      rows from 18 May to 12 Jun carry score_at_flag = 100.0 (no other row
      does) — a 15 June migration overwrote them, and no restatement exists.
    - "One day is missing from the public record": four trading days are
      missing (31 Aug, 2 Sep, 4 Sep, 9 Sep), not one.

    How to tell customers about the record is the founder's decision. Until
    it is made, this email says nothing about the record's completeness or
    immutability, and this test keeps it that way."""
    from app.services.email import render_product_update_email, render_product_update_text

    for audience in ("account", "newsletter"):
        text = render_product_update_text(
            "Sam", scorecard_url=SCORECARD, audience=audience,
            unsubscribe_url="https://tapeline.io/api/unsubscribe?token=t",
        )
        html = render_product_update_email(
            "Sam", scorecard_url=SCORECARD, audience=audience,
            newsletter_unsubscribe_url=(
                "https://tapeline.io/api/newsletter/unsubscribe?token=t"
                if audience == "newsletter" else None
            ),
        )
        for part, body in (("text", text), ("html", html)):
            low = body.lower()
            for claim in ("never edit", "one day is missing", "filled in later",
                          "nothing in the public record", "append-only", "stay a gap"):
                assert claim not in low, f"{audience} {part} still claims: {claim!r}"
