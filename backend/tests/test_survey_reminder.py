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
  * the newsletter half runs on the first run only (that table has no marker);
  * the workflow passes --quiet, so no address reaches the public log.
"""
from __future__ import annotations

import asyncio
import pathlib
import re
from datetime import UTC, datetime
from html import unescape

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
    assert 'cron: "7 13 16 9 *"' in code
    assert "2026-09-16T13:00:00Z" in code and "2026-09-19T00:00:00Z" in code
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

