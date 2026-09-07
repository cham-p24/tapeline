"""The survey send must reach customers and nobody else.

This is the first broadcast written after #782, which found that the
per-category opt-out gate was decorative in BOTH previous broadcast scripts —
they passed `u.email_prefs` (an int) to `wants()`, which then returned True for
everyone including a fully opted-out user. So the opt-out assertion below is not
ceremony: this is the first send where that gate actually fires, and the guard
exists to keep it that way.

The audience rules encode decisions, not preferences, so each has its own test:

  * `re_sunset` accounts are suppressed from every non-transactional send by
    `services/lifecycle.LIFECYCLE_SUPPRESSED_TOKENS`. A survey is
    non-transactional. Including them for a 23-person list would risk the
    deliverability of the digest and trial drip for accounts that do pay.
  * The founder's own accounts and the ads contractor are not customers.
  * The token makes a second run a no-op, because "I already answered that"
    from a customer is the cheapest possible way to lose one.
"""
from __future__ import annotations

import pytest

from app.db import session_scope
from app.models import User
from app.scripts import survey_send


_seq = 0


async def _mk(session, email: str, **kw) -> User:
    """`User.id` is a String PK with no default — native auth mints "u_<uuid>"
    at signup, so a test row has to supply one."""
    global _seq
    _seq += 1
    u = User(
        id=kw.pop("id", f"u_test_{_seq}"),
        email=email,
        name=email.split("@")[0],
        tier=kw.pop("tier", "free"),
        **kw,
    )
    session.add(u)
    await session.flush()
    return u


async def test_an_ordinary_customer_is_a_recipient() -> None:
    async with session_scope() as s:
        await _mk(s, "real@example.com")
        recipients, _ = await survey_send.collect(s)
    assert [u.email for u in recipients] == ["real@example.com"]


@pytest.mark.parametrize("addr", sorted(survey_send.INTERNAL_ADDRESSES))
async def test_internal_accounts_are_excluded(addr: str) -> None:
    """The founder's two accounts and the ads contractor are not customers."""
    async with session_scope() as s:
        await _mk(s, addr)
        recipients, skipped = await survey_send.collect(s)
    assert recipients == []
    assert [r for _u, r in skipped] == ["internal"]


async def test_admins_are_excluded() -> None:
    async with session_scope() as s:
        await _mk(s, "boss@example.com", is_admin=True)
        recipients, skipped = await survey_send.collect(s)
    assert recipients == []
    assert [r for _u, r in skipped] == ["admin"]


async def test_a_sunset_account_is_suppressed_by_default() -> None:
    """`re_sunset` is terminal. The governor blocks every non-transactional
    send to these accounts, and a survey is non-transactional."""
    async with session_scope() as s:
        await _mk(s, "dormant@example.com", drip_state="re14,re24,re_sunset")
        recipients, skipped = await survey_send.collect(s)
    assert recipients == []
    assert [r for _u, r in skipped] == ["sunset"]


async def test_include_sunset_is_an_explicit_override() -> None:
    """It exists so a founder decision can reach them, and it is not the
    default. If this ever flips to default-on, the deliverability argument in
    the module docstring has to be re-made first."""
    async with session_scope() as s:
        await _mk(s, "dormant@example.com", drip_state="re_sunset")
        recipients, _ = await survey_send.collect(s, include_sunset=True)
    assert [u.email for u in recipients] == ["dormant@example.com"]


async def test_an_opted_out_account_is_excluded() -> None:
    """The regression this whole class of script got wrong until #782.

    `email_prefs = 0` is someone who has opted out of everything. Before the
    fix, `wants(u.email_prefs, ...)` returned True for exactly this user.
    """
    async with session_scope() as s:
        await _mk(s, "optout@example.com", email_prefs=0)
        recipients, skipped = await survey_send.collect(s)
    assert recipients == []
    assert [r for _u, r in skipped] == ["opted_out"]


async def test_an_undeliverable_account_is_excluded() -> None:
    from datetime import UTC, datetime

    async with session_scope() as s:
        await _mk(s, "bounced@example.com", email_undeliverable_at=datetime.now(UTC))
        recipients, skipped = await survey_send.collect(s)
    assert recipients == []
    assert [r for _u, r in skipped] == ["undeliverable"]


async def test_the_token_makes_a_second_run_a_no_op() -> None:
    async with session_scope() as s:
        await _mk(s, "done@example.com", drip_state=survey_send.SURVEY_TOKEN)
        recipients, skipped = await survey_send.collect(s)
    assert recipients == []
    assert [r for _u, r in skipped] == ["already_surveyed"]


async def test_only_restricts_to_one_address() -> None:
    """The self-test path. The first LIVE run goes to one inbox, not to N
    customers — `--limit` cannot do this because it takes the first N rows,
    which are real people."""
    async with session_scope() as s:
        await _mk(s, "a@example.com")
        await _mk(s, "b@example.com")
        recipients, _ = await survey_send.collect(s, only="b@example.com")
    assert [u.email for u in recipients] == ["b@example.com"]


async def test_dry_run_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default must be inert. A broadcast script whose default transmits is
    one fat-fingered shell history entry away from an incident."""
    sent: list[str] = []

    async def _boom(**kwargs):
        sent.append(kwargs.get("to", "?"))
        return {}

    monkeypatch.setattr("app.services.email.send_email", _boom)
    async with session_scope() as s:
        await _mk(s, "dry@example.com")

    counts = await survey_send.run(send=False, limit=None)
    assert sent == [], "a dry run transmitted email"
    assert counts["sent"] == 0
    assert counts["would_send"] >= 1


async def test_send_refuses_a_non_https_app_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard that saved the free-month send.

    This script is run by hand against the PRODUCTION database from a machine
    whose APP_URL is http://localhost:3000. A dry run cannot catch that,
    because a dry run is exactly where a wrong-but-plausible link looks fine.
    """
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "app_url", "http://localhost:3000", raising=False)
    with pytest.raises(SystemExit, match="not a public https URL"):
        await survey_send.run(send=True, limit=None)
