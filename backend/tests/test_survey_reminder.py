"""The survey reminder must reach the right people exactly once, with nobody watching.

Founder-authorised 2026-09-11: "go, one address for Waad, send Wed 16". It runs
from .github/workflows/survey-reminder.yml over `flyctl ssh`, unattended, into a
log that is world-readable on this public repo. So every property a human would
normally eyeball in a dry run is pinned here instead:

  * only people who RECEIVED the original, and none of them twice;
  * not the duplicate Waad address, not the Resend-suppressed one, not anyone
    who left their email in the form;
  * first names, the original subject, never "Re:";
  * a dropped ssh session cannot cause a double-send (per-recipient commit);
  * a send whose outcome is unknown (Resend may have it) is stamped, so a
    manual re-dispatch skips that person; one Resend never had is retried;
  * the newsletter half runs on the first run only, and only when that run
    left a trace (that table has no marker);
  * the workflow passes --quiet, and under --quiet no address reaches the
    public log — not from send_email's own `to=` lines, not from an exception
    message, not from an uncaught traceback;
  * a second run started while one is going is refused, and says so.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import pathlib
import re
import subprocess
import sys
from datetime import UTC, datetime
from html import unescape

import httpx
import pytest
from sqlalchemy import select

from app.db import session_scope
from app.models import SurveyResponse, User
from app.models.newsletter import NewsletterSubscriber
from app.scripts import survey_send as ss

WORKFLOW = pathlib.Path(__file__).resolve().parents[2] / ".github" / "workflows" / "survey-reminder.yml"
BEFORE = datetime(2026, 9, 1, tzinfo=UTC)
AFTER = datetime(2026, 9, 12, tzinfo=UTC)

_seq = 0


async def _user(s, email: str, *, got_original: bool = True, extra_tokens=(), **kw) -> User:
    """`User.id` has no default (native auth mints "u_<uuid>"), so supply one."""
    global _seq
    _seq += 1
    toks = set(extra_tokens) | ({ss.SURVEY_TOKEN} if got_original else set())
    u = User(
        id=f"u_rem_{_seq}",
        email=email,
        name=kw.pop("name", "Sam Example"),
        tier="free",
        drip_state=",".join(sorted(toks)),
        **kw,
    )
    s.add(u)
    await s.flush()
    return u


async def _sub(s, email: str, *, created: datetime = BEFORE) -> NewsletterSubscriber:
    sub = NewsletterSubscriber(
        email=email,
        status="confirmed",
        unsubscribe_token="tok_" + email.split("@")[0],
        created_at=created,
    )
    s.add(sub)
    await s.flush()
    return sub


def _toks(drip_state: str | None) -> set[str]:
    return {t for t in (drip_state or "").split(",") if t}


@pytest.fixture
def https(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "app_url", "https://tapeline.io", raising=False)


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    sent: list[dict] = []

    async def _fake(**kw):
        sent.append(kw)
        return {"id": f"re_{len(sent)}"}

    monkeypatch.setattr("app.services.email.send_email", _fake)
    return sent


# ── Greeting ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("stored", "greeting"),
    [
        ("David Eley", "David"),
        ("ELANGOVAN M", "Elangovan"),
        ("Mal", "Mal"),
        ("Rafael acevedo", "Rafael"),
        ("McKay Smith", "McKay"),
        ("The Best", "there"),
        ("Waad20rabee Ma", "there"),
        ("J", "there"),
        ("", "there"),
        (None, "there"),
    ],
)
def test_first_name(stored: str | None, greeting: str) -> None:
    """The original went out as "Hi David Eley," / "Hi ELANGOVAN M," /
    "Hi The Best,". Every stored name on the real list is one of these shapes."""
    assert ss.first_name(stored) == greeting


# ── Account audience ────────────────────────────────────────────────────────

async def test_only_people_who_received_the_original_are_reminded() -> None:
    """The 8 sunset accounts never got the original; reminding them of it
    would be a first contact that pretends to be a follow-up."""
    async with session_scope() as s:
        await _user(s, "got@example.com")
        await _user(s, "never@example.com", got_original=False)
        recipients, skipped = await ss.collect_reminder_accounts(s)
    assert [u.email for u in recipients] == ["got@example.com"]
    assert all(u.email != "never@example.com" for u, _r in skipped)


@pytest.mark.parametrize(
    ("email", "kw", "reason"),
    [
        ("done@example.com", {"extra_tokens": (ss.REMINDER_TOKEN,)}, "already_reminded"),
        ("waadrabeema@gmail.com", {}, "duplicate_person"),
        ("optout@example.com", {"email_prefs": 0}, "opted_out"),
    ],
)
async def test_account_exclusions(email: str, kw: dict, reason: str) -> None:
    async with session_scope() as s:
        await _user(s, email, **kw)
        recipients, skipped = await ss.collect_reminder_accounts(s)
    assert recipients == []
    assert [r for _u, r in skipped] == [reason]


async def test_the_other_waad_address_is_still_reminded() -> None:
    """The founder said ONE address, not none."""
    async with session_scope() as s:
        await _user(s, "waadrabeemm@gmail.com", name="Waad Rabeemm")
        await _user(s, "waadrabeema@gmail.com", name="Waad20rabee Ma")
        recipients, _ = await ss.collect_reminder_accounts(s)
    assert [u.email for u in recipients] == ["waadrabeemm@gmail.com"]


async def test_someone_who_left_their_email_in_the_form_is_not_reminded() -> None:
    """The only way the anonymous form can tell us someone answered — and the
    match must ignore case, because people type their address how they like."""
    async with session_scope() as s:
        await _user(s, "reader@example.com")
        s.add(SurveyResponse(status="using_it", contact_email="Reader@Example.com"))
        await s.flush()
        recipients, skipped = await ss.collect_reminder_accounts(s)
    assert recipients == []
    assert [r for _u, r in skipped] == ["answered"]


# ── Newsletter audience ─────────────────────────────────────────────────────

async def test_newsletter_reminder_reaches_only_pre_send_subscribers() -> None:
    async with session_scope() as s:
        await _sub(s, "early@example.com", created=BEFORE)
        await _sub(s, "late@example.com", created=AFTER)
        await _sub(s, "patelsp1@yahoo.com", created=BEFORE)
        recipients, skipped = await ss.collect_reminder_newsletter(s)
    assert [r.email for r in recipients] == ["early@example.com"]
    reasons = {x.email: r for x, r in skipped}
    assert reasons["late@example.com"] == "joined_after_original"
    assert reasons["patelsp1@yahoo.com"] == "resend_suppressed"


# ── The run ─────────────────────────────────────────────────────────────────

async def test_dry_run_sends_nothing(https, outbox: list[dict]) -> None:
    async with session_scope() as s:
        await _user(s, "dry@example.com")
        await _sub(s, "drysub@example.com")
    counts = await ss.run_reminder(send=False)
    assert outbox == [], "a dry run transmitted email"
    assert counts["would_send"] == 2


async def test_quiet_prints_no_address(capsys, https, outbox: list[dict]) -> None:
    """The workflow's log is world-readable on this public repo."""
    async with session_scope() as s:
        await _user(s, "private@example.com")
        await _sub(s, "alsoprivate@example.com")
    await ss.run_reminder(send=True, quiet=True)
    assert len(outbox) == 2
    out = capsys.readouterr().out
    assert "@" not in out, f"an address reached output the workflow publishes:\n{out}"


async def test_the_send_uses_first_names_and_the_original_subject(
    https, outbox: list[dict],
) -> None:
    async with session_scope() as s:
        await _user(s, "david@example.com", name="David Eley")
    await ss.run_reminder(send=True, quiet=True)
    [msg] = [m for m in outbox if m["to"] == "david@example.com"]
    assert msg["subject"] == "Tapeline — four questions"
    assert not msg["subject"].lower().startswith("re:")
    assert "Hi David," in msg["html"]
    assert "Hi David Eley," not in msg["html"]


async def test_a_second_run_reminds_nobody_twice(https, outbox: list[dict]) -> None:
    async with session_scope() as s:
        await _user(s, "once@example.com")
        await _sub(s, "oncesub@example.com")
    await ss.run_reminder(send=True, quiet=True)
    first = sorted(m["to"] for m in outbox)
    outbox.clear()
    await ss.run_reminder(send=True, quiet=True)
    assert first == ["once@example.com", "oncesub@example.com"]
    assert outbox == [], f"the second run re-sent to {[m['to'] for m in outbox]}"


async def test_the_newsletter_phase_runs_on_the_first_run_only(
    https, outbox: list[dict],
) -> None:
    """That table has no per-row marker, so an earlier reminder run is detected
    from the account tokens, and the newsletter half then stays off unless a
    human forces it after checking Resend."""
    async with session_scope() as s:
        await _user(s, "earlier@example.com", extra_tokens=(ss.REMINDER_TOKEN,))
        await _sub(s, "reader@example.com")
    await ss.run_reminder(send=True, quiet=True)
    assert outbox == [], "the newsletter phase re-ran after a reminder run had already started"

    await ss.run_reminder(send=True, quiet=True, force_newsletter=True)
    assert [m["to"] for m in outbox] == ["reader@example.com"]


async def test_a_killed_run_keeps_the_tokens_it_already_earned(
    https, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dropped `flyctl ssh` session, simulated.

    CancelledError is a BaseException, so nothing in the loop catches it and
    session_scope does not commit on the way out. With an end-of-run commit the
    first recipient's token would vanish although their email had gone, and the
    next run would send it again.
    """
    calls: list[str] = []

    async def _dies_on_second(**kw):
        calls.append(kw["to"])
        if len(calls) == 2:
            raise asyncio.CancelledError()
        return {"id": "re_1"}

    monkeypatch.setattr("app.services.email.send_email", _dies_on_second)
    async with session_scope() as s:
        await _user(s, "one@example.com")
        await _user(s, "two@example.com")

    with pytest.raises(asyncio.CancelledError):
        await ss.run_reminder(send=True, quiet=True)

    async with session_scope() as s:
        rows = (await s.execute(
            select(User.email, User.drip_state)
            .where(User.email.in_(["one@example.com", "two@example.com"]))
        )).all()
    reminded = {e for e, d in rows if ss.REMINDER_TOKEN in _toks(d)}
    assert reminded == {calls[0]}, (
        f"sent to {calls[0]} before the kill, but tokens persisted for {reminded}"
    )


async def test_the_token_is_appended_without_losing_other_tokens(
    https, outbox: list[dict],
) -> None:
    async with session_scope() as s:
        await _user(s, "keep@example.com", extra_tokens=("re14", "weekly_2026W37"))
    await ss.run_reminder(send=True, quiet=True)
    async with session_scope() as s:
        state = await s.scalar(select(User.drip_state).where(User.email == "keep@example.com"))
    assert _toks(state) == {ss.SURVEY_TOKEN, ss.REMINDER_TOKEN, "re14", "weekly_2026W37"}


# ── Copy ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("audience", ["account", "newsletter"])
def test_reminder_copy_stays_inside_the_rules(audience: str) -> None:
    from app.services.email import render_survey_reminder_email
    from app.services.email_design import UNSUB_PLACEHOLDER

    html = render_survey_reminder_email(
        "Sam", survey_url="https://tapeline.io/survey", audience=audience,
    )
    body = unescape(re.sub(r"<[^>]+>", " ", html.split("</style>")[-1]))
    body = body.split("Not investment advice")[0]
    for banned in (
        r"\bbuy\b", r"\bsell\b", r"\brecommend", r"you should", r"last chance",
        r"hurry", r"limited time", r"expire", r"free trial", r"\$\s?\d",
        r"\bprice\b", r"discount", r"\boffer\b", r"upgrade",
    ):
        assert not re.search(banned, body, re.I), f"{audience}: {banned!r} in the reminder"
    assert "the last time I'll ask" in body
    assert UNSUB_PLACEHOLDER in html
    if audience == "newsletter":
        assert "never made an account" in body
        assert "signed up for Tapeline" not in body


# ── The workflow ────────────────────────────────────────────────────────────

def _workflow_code() -> str:
    """The workflow with comments removed. Its header prose discusses --quiet
    at length, so a guard that could match prose would pass with the flag
    deleted from the command."""
    lines = []
    for line in WORKFLOW.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#"):
            continue
        lines.append(re.sub(r"\s+#.*$", "", line))
    return "\n".join(lines)


def test_the_workflow_runs_the_reminder_quietly() -> None:
    m = re.search(r'-C\s+"([^"]+)"', _workflow_code())
    assert m, "no `flyctl ssh console -C` command found in the workflow"
    argv = m.group(1).split()
    assert argv[:3] == ["python", "-m", "app.scripts.survey_send"], argv
    assert {"--reminder", "--send", "--quiet"} <= set(argv), (
        f"{argv} — without --quiet every recipient's address lands in a public log"
    )


def test_the_workflow_is_one_shot_and_takes_no_inputs() -> None:
    code = _workflow_code()
    assert 'cron: "7 17 16 9 *"' in code
    assert "2026-09-16T17:00:00Z" in code and "2026-09-19T00:00:00Z" in code
    assert "inputs:" not in code, "workflow_dispatch must take no inputs"


# ── Concurrency ─────────────────────────────────────────────────────────────

def test_the_reminder_holds_its_own_registered_lock() -> None:
    """Two runs at once would both read "not reminded" before either commits.

    The id must come from dblock's registry and be unique there: sharing a
    number with a real email job would make the reminder and that job block
    each other on 16 September.
    """
    from app.services import dblock

    assert ss.run_reminder._one_machine_lock_id == dblock.LOCK_SURVEY_REMINDER
    ids = [v for k, v in vars(dblock).items() if k.startswith("LOCK_") and k != "LOCK_NAMESPACE"]
    assert len(ids) == len(set(ids)), f"a lock id is reused: {sorted(ids)}"


async def test_a_run_that_loses_the_lock_sends_nothing(
    https, outbox: list[dict], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dblock is a no-op on SQLite, which is the whole test suite, so the loss
    is simulated at the one seam every lock goes through. A green that only
    ever exercised the no-op would prove nothing."""
    from app.services import dblock

    async def _lost(_session, _objid):
        return False

    monkeypatch.setattr(dblock, "try_xact_lock", _lost)
    async with session_scope() as s:
        await _user(s, "racer@example.com")
        await _sub(s, "racersub@example.com")
    result = await ss.run_reminder(send=True, quiet=True)
    assert result == {}
    assert outbox == [], "a run that lost the lock still sent email"


async def test_a_subscriber_who_joined_after_the_real_send_is_not_reminded() -> None:
    """Pins the cutoff to when the original actually went out.

    Resend's log puts every survey email at 2026-09-10 15:59-16:00 UTC. The
    cutoff used to be 2026-09-11 03:44, read off `users.updated_at`, so someone
    who joined the list overnight would have been sent a "follow-up" to an email
    they never received.
    """
    async with session_scope() as s:
        await _sub(s, "overnight@example.com", created=datetime(2026, 9, 11, 0, 0, tzinfo=UTC))
        await _sub(s, "before@example.com", created=datetime(2026, 9, 10, 15, 0, tzinfo=UTC))
        recipients, skipped = await ss.collect_reminder_newsletter(s)
    assert [r.email for r in recipients] == ["before@example.com"]
    assert {x.email: r for x, r in skipped}["overnight@example.com"] == "joined_after_original"



def _worker_send_hour(stage: str) -> int:
    """The UTC hour a worker email stage opens, read from tick()'s own source.

    Derived rather than restated so a worker that moves its send cannot leave
    this reminder silently colliding with it again.
    """
    import inspect

    from app.workers import signal_publisher as sp

    src = inspect.getsource(sp.tick)
    start = src.index(f'_set_stage("{stage}")')
    end = src.find("_set_stage(", start + 1)
    m = re.search(r"started\.hour\s*>=\s*(\d+)", src[start:end if end != -1 else None])
    assert m, f"no `started.hour >= N` gate found in the {stage} stage"
    return int(m.group(1))


def test_the_reminder_is_clear_of_the_workers_own_sends() -> None:
    """13:07 was seven minutes after the Daily Top 10 reached every newsletter
    subscriber, and the frequency governor cannot see the worker's sends from a
    fresh ssh process. Keep at least two hours from each worker email gate."""
    m = re.search(r'cron:\s*"(\d+)\s+(\d+)\s+16\s+9\s+\*"', _workflow_code())
    assert m, "reminder cron not found"
    fire_minutes = int(m.group(2)) * 60 + int(m.group(1))
    for stage in ("daily_newsletter_date", "eod_digest_date"):
        gate = _worker_send_hour(stage) * 60
        assert abs(fire_minutes - gate) >= 120, (
            f"reminder fires at {fire_minutes // 60:02d}:{fire_minutes % 60:02d} UTC, "
            f"within two hours of the worker's {stage} send at {gate // 60:02d}:00"
        )


# ── Outcome unknown: stamped, so a re-dispatch skips them ───────────────────

_REQ = httpx.Request("POST", "https://api.resend.com/emails")


def _status(code: int) -> httpx.HTTPStatusError:
    """What send_email's resp.raise_for_status() raises for this status."""
    return httpx.HTTPStatusError(
        f"HTTP {code}", request=_REQ, response=httpx.Response(code, request=_REQ),
    )


#: Errors that can arrive AFTER Resend queued the email.
OUTCOME_UNKNOWN = {
    "read_timeout": lambda: httpx.ReadTimeout("timed out", request=_REQ),
    "dropped_mid_response": lambda: httpx.RemoteProtocolError("peer closed", request=_REQ),
    "http_502_gateway": lambda: _status(502),
}

#: Errors that prove Resend never had it.
NEVER_REACHED_RESEND = {
    "connect_error": lambda: httpx.ConnectError("refused", request=_REQ),
    "http_422_rejected": lambda: _status(422),
    "raised_before_the_post": lambda: RuntimeError("render failed"),
}


async def _state(email: str) -> set[str]:
    async with session_scope() as s:
        return _toks(await s.scalar(select(User.drip_state).where(User.email == email)))


@pytest.mark.parametrize("make_error", OUTCOME_UNKNOWN.values(), ids=OUTCOME_UNKNOWN.keys())
async def test_an_unknown_outcome_is_stamped_and_a_second_run_skips_it(
    https, monkeypatch: pytest.MonkeyPatch, make_error,
) -> None:
    """The fake DELIVERS, then raises, on the first call — what a read timeout
    after Resend queued the email looks like from here. Before the fix run 1
    counted failed=1 and left no stamp, and a manual re-dispatch mailed the
    same person a second time."""
    delivered: list[str] = []

    async def _accepts_then_raises(**kw):
        delivered.append(kw["to"])
        if len(delivered) == 1:
            raise make_error()
        return {"id": "re_ok"}

    monkeypatch.setattr("app.services.email.send_email", _accepts_then_raises)
    async with session_scope() as s:
        await _user(s, "slow@example.com")

    first = await ss.run_reminder(send=True, quiet=True)
    assert (first["unknown"], first["failed"], first["accounts_sent"]) == (1, 0, 0), first
    assert ss.REMINDER_TOKEN in await _state("slow@example.com")

    await ss.run_reminder(send=True, quiet=True)
    assert delivered == ["slow@example.com"], f"delivered {delivered}"


@pytest.mark.parametrize("make_error", NEVER_REACHED_RESEND.values(), ids=NEVER_REACHED_RESEND.keys())
async def test_an_error_that_proves_resend_never_had_it_is_retried(
    https, monkeypatch: pytest.MonkeyPatch, make_error,
) -> None:
    """The other side of the line: stamping these would leave someone who was
    never reminded unreminded, with nothing in the result line saying so."""
    calls: list[str] = []

    async def _fails_once(**kw):
        calls.append(kw["to"])
        if len(calls) == 1:
            raise make_error()
        return {"id": "re_ok"}

    monkeypatch.setattr("app.services.email.send_email", _fails_once)
    async with session_scope() as s:
        await _user(s, "refused@example.com")

    first = await ss.run_reminder(send=True, quiet=True)
    assert (first["failed"], first["unknown"]) == (1, 0), first
    assert ss.REMINDER_TOKEN not in await _state("refused@example.com")

    await ss.run_reminder(send=True, quiet=True)
    assert calls == ["refused@example.com", "refused@example.com"]
    assert ss.REMINDER_TOKEN in await _state("refused@example.com")


async def test_a_run_that_stamps_no_account_does_not_mail_the_list(
    https, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run whose every account send fails leaves no token, so a re-dispatch
    still looks like a first run. If that run had mailed the newsletter list,
    the re-dispatch would mail it again."""
    sent: list[str] = []

    async def _accounts_refused(**kw):
        if kw["to"] == "down@example.com":
            raise httpx.ConnectError("refused", request=_REQ)
        sent.append(kw["to"])
        return {"id": "re_ok"}

    monkeypatch.setattr("app.services.email.send_email", _accounts_refused)
    async with session_scope() as s:
        await _user(s, "down@example.com")
        await _sub(s, "reader@example.com")

    counts = await ss.run_reminder(send=True, quiet=True)
    assert (counts["failed"], counts["newsletter_sent"]) == (1, 0), counts
    assert sent == [], f"the list was mailed by a run that left no trace: {sent}"

    await ss.run_reminder(send=True, quiet=True, force_newsletter=True)
    assert sent == ["reader@example.com"]


async def test_a_run_whose_only_stamp_is_outcome_unknown_still_mails_the_list(
    https, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An outcome-unknown stamp tells a re-run this run happened, so a re-run
    skips the list; if this run skipped it too, the list would never be
    reminded without a human."""
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
    counts = await ss.run_reminder(send=True, quiet=True)
    assert sent == ["slow@example.com", "reader@example.com"]
    assert (counts["unknown"], counts["newsletter_sent"]) == (1, 1), counts


@pytest.mark.parametrize(
    ("make_error", "key"),
    [(OUTCOME_UNKNOWN["read_timeout"], "unknown"), (NEVER_REACHED_RESEND["connect_error"], "failed")],
    ids=["unknown", "failed"],
)
async def test_a_newsletter_error_is_counted_by_what_it_means(
    https, monkeypatch: pytest.MonkeyPatch, make_error, key: str,
) -> None:
    """No per-subscriber stamp exists, so the count is the only thing that
    tells the operator whether Resend's log needs checking."""
    async def _list_send_raises(**kw):
        if kw["to"] == "reader@example.com":
            raise make_error()
        return {"id": "re_ok"}

    monkeypatch.setattr("app.services.email.send_email", _list_send_raises)
    async with session_scope() as s:
        await _user(s, "one@example.com")
        await _sub(s, "reader@example.com")
    counts = await ss.run_reminder(send=True, quiet=True)
    other = {"unknown": "failed", "failed": "unknown"}[key]
    assert (counts[key], counts[other], counts["newsletter_sent"]) == (1, 0, 0), counts


# ── --quiet: no address in any line the public log receives ─────────────────
#
# These drive `main`, not `run_reminder`, because main is where --quiet has to
# install redaction — the bug was that it did not. And they run with the ROOT
# LOGGER BARE, as it is in `python -m app.scripts.survey_send`: pytest attaches
# its own handlers to the root logger, which would swallow the WARNING lines
# that a bare interpreter prints to stderr, and make a leak invisible here.


@pytest.fixture
def run_main(monkeypatch: pytest.MonkeyPatch):
    """Call `ss.main(argv)` with the root logger as a bare interpreter has it.

    The handlers are cleared INSIDE the call, not at fixture setup: pytest adds
    its capture handlers to the root logger again at the start of each test
    phase, so clearing them during setup would leave the test body covered.
    """
    # main() installs a Windows loop policy on win32; it would outlive the test.
    monkeypatch.setattr(ss.asyncio, "set_event_loop_policy", lambda _p: None)
    root = logging.getLogger()

    def _run(argv: list[str]) -> None:
        handlers, level, hook = list(root.handlers), root.level, sys.excepthook
        root.handlers[:] = []
        root.setLevel(logging.WARNING)
        try:
            ss.main(argv)
        finally:
            root.handlers[:] = handlers
            root.setLevel(level)
            sys.excepthook = hook

    return _run


def _seed(*people: tuple[str, str]) -> None:
    """Seed ("account" | "newsletter", address) rows from a sync test."""
    async def _go() -> None:
        async with session_scope() as s:
            for kind, email in people:
                if kind == "account":
                    await _user(s, email)
                else:
                    await _sub(s, email)
    asyncio.run(_go())


def test_quiet_redacts_the_address_send_email_logs_itself(
    https, monkeypatch: pytest.MonkeyPatch, capsys, run_main,
) -> None:
    """The REAL send_email, with no Resend key: it logs
    `email.skipped reason=no_api_key ... to=<address>` at WARNING, which a bare
    interpreter prints to stderr — the workflow's public log."""
    from app.services import email

    monkeypatch.setattr(email.settings, "resend_api_key", "", raising=False)
    _seed(("account", "private@example.com"))

    run_main(["--reminder", "--send", "--quiet"])

    captured = capsys.readouterr()
    assert "email.skipped" in captured.err, captured.err  # self-test: the line was emitted
    assert "result:" in captured.out
    assert "@" not in captured.out + captured.err, (
        f"an address reached output the workflow publishes:\n{captured.out}{captured.err}"
    )


def test_quiet_redacts_addresses_in_http_errors_and_tracebacks(
    https, monkeypatch: pytest.MonkeyPatch, capsys, run_main,
) -> None:
    """The REAL send_email over a fake Resend transport. Every error carries
    the recipient's address in its message — the worst case for an exception
    that is logged with its traceback — across all three logged paths: an
    account whose outcome is unknown, an account that failed, and a newsletter
    subscriber whose outcome is unknown."""
    from app.services import email

    monkeypatch.setattr(email.settings, "resend_api_key", "re_test_not_a_real_key", raising=False)
    real_client = httpx.AsyncClient

    def _resend(request: httpx.Request) -> httpx.Response:
        to = json.loads(request.content)["to"][0]
        if to == "slow@example.com":
            raise httpx.ReadTimeout(f"read timed out sending to {to}", request=request)
        if to == "refused@example.com":
            raise httpx.ConnectError(f"connection refused for <{to}>", request=request)
        raise httpx.RemoteProtocolError(f"peer closed mid-response ({to})", request=request)

    monkeypatch.setattr(
        email.httpx, "AsyncClient",
        lambda *a, **kw: real_client(transport=httpx.MockTransport(_resend)),
    )
    _seed(
        ("account", "slow@example.com"),
        ("account", "refused@example.com"),
        ("newsletter", "reader@example.com"),
    )

    run_main(["--reminder", "--send", "--quiet"])

    captured = capsys.readouterr()
    for event in (
        "survey_reminder.send_outcome_unknown",
        "survey_reminder.send_failed",
        "survey_reminder.newsletter_outcome_unknown",
    ):
        assert event in captured.err, f"self-test: {event} was not logged\n{captured.err}"
    assert "Traceback" in captured.err  # self-test: the exception text was in the log
    assert "@" not in captured.out + captured.err, (
        f"an address reached output the workflow publishes:\n{captured.out}{captured.err}"
    )
    assert "<address>" in captured.err  # redacted, not merely absent


def test_quiet_redacts_an_uncaught_traceback() -> None:
    """A crash that escapes the run is printed by the interpreter itself, not
    by logging, so it is run for real in a child process. The child replaces
    run_reminder with one that raises an address-bearing error; it touches no
    database and sends nothing."""
    child = (
        "from app.scripts import survey_send as ss\n"
        "async def _boom(**kw):\n"
        "    raise RuntimeError('Resend rejected leak@example.com')\n"
        "ss.run_reminder = _boom\n"
        "ss.main(['--reminder', '--quiet'])\n"
    )
    env = {
        k: v for k, v in os.environ.items()
        if k not in {"RESEND_API_KEY", "STRIPE_SECRET_KEY", "META_CAPI_ACCESS_TOKEN"}
    }
    env["DATABASE_URL"] = "sqlite+aiosqlite:///./_uncaught_child_unused.db"
    env["APP_ENV"] = "development"
    proc = subprocess.run(
        [sys.executable, "-c", child],
        cwd=pathlib.Path(__file__).resolve().parents[1],
        env=env, capture_output=True, text=True, timeout=120,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode != 0, output
    assert "Resend rejected" in output, output  # self-test: the crash was reported
    assert "@" not in output, f"an uncaught traceback printed an address:\n{output}"


def test_quiet_is_refused_where_it_would_not_be_honoured(
    https, outbox: list[dict], run_main,
) -> None:
    """Only the reminder gates its per-recipient lines. The survey and
    newsletter runs print every address, so accepting --quiet there would
    promise a public log something the run does not do."""
    with pytest.raises(SystemExit) as exc:
        run_main(["--send", "--quiet"])
    assert exc.value.code == 2
    assert outbox == []


# ── A concurrent second run is refused ──────────────────────────────────────

async def test_two_runs_at_once_remind_each_person_once(
    https, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two runs genuinely overlapping. SQLite has no advisory locks, so the
    lock is given real one-holder semantics at the seam every run goes through;
    the sends yield, so each run reads "not reminded" before the other stamps.
    Without the lock both runs mail everyone."""
    from app.services import dblock

    held: set[int] = set()

    @contextlib.asynccontextmanager
    async def _one_holder(objid: int):
        if objid in held:
            yield False
            return
        held.add(objid)
        try:
            yield True
        finally:
            held.discard(objid)

    monkeypatch.setattr(dblock, "hold_xact_lock", _one_holder)

    delivered: list[str] = []

    async def _slow_send(**kw):
        for _ in range(5):
            await asyncio.sleep(0)
        delivered.append(kw["to"])
        return {"id": f"re_{len(delivered)}"}

    monkeypatch.setattr("app.services.email.send_email", _slow_send)
    async with session_scope() as s:
        await _user(s, "a@example.com")
        await _user(s, "b@example.com")
        await _sub(s, "reader@example.com")

    results = await asyncio.gather(
        ss.run_reminder(send=True, quiet=True),
        ss.run_reminder(send=True, quiet=True),
    )
    assert sorted(delivered) == ["a@example.com", "b@example.com", "reader@example.com"], delivered
    assert {} in results, f"neither run was refused: {results}"


def test_a_refused_run_says_so_in_the_log(
    https, outbox: list[dict], monkeypatch: pytest.MonkeyPatch, capsys, run_main,
) -> None:
    """The lock's loser returns {} and the decorator logs at INFO, which the
    public log does not show. Without a line of its own, a refused run's log
    would be empty."""
    from app.services import dblock

    async def _lost(_session, _objid):
        return False

    monkeypatch.setattr(dblock, "try_xact_lock", _lost)
    _seed(("account", "racer@example.com"))

    run_main(["--reminder", "--send", "--quiet"])

    out = capsys.readouterr().out
    assert outbox == []
    assert "refused: another survey reminder run holds the lock" in out, out
