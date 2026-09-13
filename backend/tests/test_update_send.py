"""The September product update must reach the right people exactly once, unattended.

It runs from .github/workflows/product-update-send.yml over `flyctl ssh`, with
nobody watching, into a log that is world-readable on this public repo. So every
property a human would normally eyeball in a dry run is pinned here instead:

  * a dry run sends nothing; --send stamps each recipient; a re-run is a no-op;
  * the RE_ENGAGEMENT opt-out, undeliverable, sunset and Resend suppression hold;
  * newsletter-only subscribers are deduplicated against EVERY account;
  * the open-access sentence reaches account holders only;
  * the copy is the approved copy, word for word, in both parts;
  * nothing address-shaped reaches the output under --quiet;
  * the workflow passes --send --quiet, and cannot fire on the reminder's day;
  * a registered, unique lock stops two runs sending at once.
"""
from __future__ import annotations

import asyncio
import fnmatch
import inspect
import json
import logging
import pathlib
import re
from datetime import UTC, date, datetime
from html import unescape

import pytest
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

#: The survey reminder goes out at 13:07 UTC on this day. The update must never
#: land on the same UTC day: two emails from one small sender inside a few hours
#: is the pattern that gets the second one read as a campaign, or spam-filed.
SURVEY_REMINDER_DAY = date(2026, 9, 16)

#: The copy as approved for review, verbatim — the account-holder variant, plain
#: text, everything above the footer. The newsletter variant is this minus the
#: "And one thing that is not an improvement" paragraph. If the copy changes
#: after approval, this is where the change has to be made on purpose.
APPROVED_COPY = """\
Hi Sam,

A lot changed at Tapeline over the past week, and part of it went wrong in a way you should hear about from us rather than notice for yourself.

Scores and prices stopped updating for about a day.
From 15:36 UTC on 9 September to 16:18 UTC on 10 September, the scanner kept showing numbers that were not being refreshed. Over the following day it stalled several more times before recovering on its own. The cause was our own code plus a server that could not keep up with the larger universe described below. Both are fixed: scoring now runs on a dedicated machine, and it has not stalled since 11 September.

One day is missing from the public record, permanently.
We freeze the daily Top 10 after the US close and never edit it. On 9 September that step did not run, so there is no Top 10 for that day. We could have rebuilt one after the fact, but a record is only worth trusting if nothing in it was filled in later. So there is a gap, and it will stay a gap.

The scanner now covers about 11,500 stocks and ETFs.
At the start of the month it was about 2,000. That is not new data we bought. It is data we already had and were not refreshing. Search for TSM, Sony or Toyota and they are there.

Crypto is in: 100 pairs, updated once a day.
Coins sit in their own list and are never ranked against stocks, because two of our six factors — company fundamentals and insider buying — cannot exist for a coin. Prices update daily, not live. Our data plan does not include live crypto prices, and we would rather tell you that than label a day-old number "live".

Scores moved on 7 September, mostly down.
A renamed column in one of our data sources meant some inputs went missing, and a missing input was being scored as neutral, which flattered most stocks. We recalculated 4,112 scores and 3,233 of them went down. If a score you watch dropped that week, the lower number is the accurate one. Nothing in the public record was changed.

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
    """The realistic re-run: Resend fails one account, a human re-dispatches the
    workflow, and the retry stamps that account. "This run stamped someone" is
    then true again, so only the first-run check stops the list being mailed a
    second time."""
    calls: list[str] = []
    fail_once = {"flaky@example.com"}

    async def _flaky(**kw):
        calls.append(kw["to"])
        if kw["to"] in fail_once:
            fail_once.discard(kw["to"])
            raise RuntimeError("resend 503")
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
    visible = _visible_text(html)
    for block in expected.split("\n\n"):
        assert _squash(block) in visible, f"{audience} HTML is missing: {block[:60]!r}"


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


@pytest.mark.parametrize("audience", ["account", "newsletter"])
def test_the_update_sells_nothing(audience: str) -> None:
    """The consent basis is a relationship plus a message that promotes nothing.
    ("you should" is not banned here, unlike the survey: the copy's only use is
    "you should hear about from us", which is not advice.)"""
    from app.services.email import render_product_update_text

    text = render_product_update_text(
        "Sam", scorecard_url=SCORECARD, audience=audience, unsubscribe_url="https://x/u",
    ).split("Not investment advice")[0]
    for banned in (
        r"\bbuy\b", r"\bsell\b", r"\brecommend", r"last chance", r"hurry",
        r"limited time", r"expire", r"free trial", r"\$\s?\d", r"discount",
        r"\boffer\b", r"upgrade", r"beat the market", r"guarantee",
    ):
        assert not re.search(banned, text, re.I), f"{audience}: {banned!r} in the update"


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

def _workflow_code(raw: str) -> str:
    """The workflow with comments removed. Its header prose discusses --quiet
    and the dates at length, so a guard that could match prose would pass with
    the flag or the window deleted from the code."""
    lines = []
    for line in raw.splitlines():
        if line.lstrip().startswith("#"):
            continue
        lines.append(re.sub(r"\s+#.*$", "", line))
    return "\n".join(lines)


def _command_argv(raw: str) -> list[str]:
    m = re.search(r'-C\s+"([^"]+)"', _workflow_code(raw))
    assert m, "no `flyctl ssh console -C` command found in the workflow"
    return m.group(1).split()


def _window(raw: str) -> tuple[datetime, datetime]:
    code = _workflow_code(raw)
    start = re.search(r'start=\$\(date -u -d "([^"]+)"', code)
    end = re.search(r'end=\$\(date -u -d "([^"]+)"', code)
    assert start and end, "no date window found in the workflow code"
    parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))  # noqa: E731
    return parse(start.group(1)), parse(end.group(1))


def test_the_workflow_sends_quietly() -> None:
    argv = _command_argv(WORKFLOW.read_text(encoding="utf-8"))
    assert argv[:3] == ["python", "-m", "app.scripts.update_send"], argv
    assert "--send" in argv, f"{argv} — without --send the scheduled run is a dry run"
    assert "--quiet" in argv, f"{argv} — without --quiet every address lands in a public log"


def test_the_comment_stripper_cannot_be_fooled_by_prose() -> None:
    """Self-test: the broken shape is the flag removed from the real command
    while a commented-out copy of the old command still carries it."""
    raw = WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")
    real = '          flyctl ssh console -a tapeline-backend \\\n            -C "python -m app.scripts.update_send --send --quiet"'
    assert raw.count(real) == 1, "the detector's fixture no longer matches the workflow"
    broken = raw.replace(
        real,
        '          # flyctl ssh console -a tapeline-backend -C "python -m app.scripts.update_send --send --quiet"\n'
        + real.replace(" --quiet", ""),
    )
    assert "--quiet" in broken
    assert "--quiet" not in _command_argv(broken)


def test_the_window_can_never_reach_the_survey_reminder_day() -> None:
    start, end = _window(WORKFLOW.read_text(encoding="utf-8"))
    reminder_day_starts = datetime.combine(SURVEY_REMINDER_DAY, datetime.min.time(), tzinfo=UTC)
    assert start < end
    assert end <= reminder_day_starts, f"window ends {end}, on or after the reminder's day"
    assert end < datetime(2026, 9, 16, 13, 0, tzinfo=UTC)
    if REMINDER_WORKFLOW.exists():  # deleted after the reminder goes; the constant then stands
        r_start, _ = _window(REMINDER_WORKFLOW.read_text(encoding="utf-8"))
        assert r_start.date() == SURVEY_REMINDER_DAY
        assert end <= r_start


def test_the_schedule_fires_inside_its_own_window() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    code = _workflow_code(raw)
    m = re.search(r'cron:\s*"(\d+) (\d+) (\d+) (\d+) \*"', code)
    assert m, "no single-date cron found"
    minute, hour, dom, month = map(int, m.groups())
    start, end = _window(raw)
    fires = datetime(start.year, month, dom, hour, minute, tzinfo=UTC)
    assert start <= fires < end, f"cron fires {fires}, outside [{start}, {end})"
    assert "inputs:" not in code, "workflow_dispatch must take no inputs"


def test_the_workflow_is_marked_held_and_pinned() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "HELD PENDING FOUNDER APPROVAL" in raw
    assert "DELETE THIS FILE" in raw
    pin = re.search(r"uses:\s*superfly/flyctl-actions/setup-flyctl@([0-9a-f]{40})\b", _workflow_code(raw))
    assert pin, "flyctl action is not pinned to a commit SHA"
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
