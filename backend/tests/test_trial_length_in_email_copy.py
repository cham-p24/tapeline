"""Email copy must never state a trial length that contradicts TRIAL_DAYS.

WHY THIS EXISTS
---------------
The trial moved from 14 days to 30 on 2026-09-05 (#737). The constant moved and
the checkout moved with it, but two rendered emails kept a hardcoded "14 days":

  * ``render_free_trial_invite_email`` said, in ONE sentence, "The trial runs 30
    days ... the first charge lands 14 days later". It contradicted itself about
    the date money leaves a card.
  * ``render_trial_started_email`` opened "everything is unlocked for the next 14
    days" while the card block immediately below it printed the real Stripe
    charge date. The two disagreed by sixteen days.

This is the same defect class as #742 (the site advertising two trial lengths at
once) and #751 (the Meta ad still saying 14-day), and it is the most expensive
one to get wrong: a wrong first-charge date on a financial product is a
chargeback and a complaint, not a typo.

WHAT THIS PINS
--------------
A rendered email may state a trial duration in days only if that number is
TRIAL_DAYS. Any other bare "N days"/"N-day" adjacent to trial or charge language
fails. Stating the exact DATE instead of a duration is always allowed and is
preferred — a date derived from the user's own subscription cannot drift when
the constant changes, which matters because trials created before 2026-09-05 are
still running on 14 days and their real end date lives in Stripe.
"""

from __future__ import annotations

import re

import pytest

from app.routers.billing import TRIAL_DAYS
from app.services.email import (
    render_free_trial_invite_email,
    render_trial_started_email,
)

# "14 days", "14-day", "for the next 14 days" — a bare duration in days.
_DURATION = re.compile(r"(\d{1,3})\s*[-‑– ]?\s*days?\b", re.IGNORECASE)

# Tags out, entities in, so we match the words a reader actually sees.
_TAGS = re.compile(r"<[^>]+>")


def _visible_text(html: str) -> str:
    return _TAGS.sub(" ", html).replace("&nbsp;", " ")


def _durations_near_money(html: str) -> list[int]:
    """Every "N days" that sits in a sentence about the trial or the charge.

    Scoped to money/trial sentences on purpose: unrelated copy may legitimately
    say "30 days" for the refund window or "3 days" for the pre-charge notice,
    and those are their own constants.
    """
    text = _visible_text(html)
    found: list[int] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        low = sentence.lower()
        if not ("trial" in low or "charge" in low or "unlocked" in low):
            continue
        # The pre-charge notice ("we email you three days before") and the
        # money-back window are separate promises with their own constants.
        if "before that date" in low or "money back" in low or "refund" in low:
            continue
        for m in _DURATION.finditer(sentence):
            found.append(int(m.group(1)))
    return found


def test_trial_invite_email_states_only_the_real_trial_length() -> None:
    html = render_free_trial_invite_email("Sam")
    stated = _durations_near_money(html)
    wrong = [d for d in stated if d != TRIAL_DAYS]
    assert not wrong, (
        f"render_free_trial_invite_email states {wrong} day(s) in trial/charge "
        f"copy, but TRIAL_DAYS is {TRIAL_DAYS}. A wrong first-charge duration "
        f"on a card-required trial is a money claim, not a typo."
    )


def test_trial_started_email_states_only_the_real_trial_length() -> None:
    html = render_trial_started_email(
        "Sam",
        tier="premium",
        amount_label="$19.99",
        charge_date_label="5 October 2026",
    )
    stated = _durations_near_money(html)
    wrong = [d for d in stated if d != TRIAL_DAYS]
    assert not wrong, (
        f"render_trial_started_email states {wrong} day(s) in trial/charge copy, "
        f"but TRIAL_DAYS is {TRIAL_DAYS}. This email already receives the exact "
        f"charge date — state that, not a duration that can drift."
    )


def test_trial_started_email_still_shows_the_exact_charge_date() -> None:
    """The duration may go; the exact date must not.

    Guards the fix against being 'simplified' into removing the date too. The
    date is what the reader needs and what Stripe will actually act on.
    """
    html = render_trial_started_email(
        "Sam",
        tier="premium",
        amount_label="$19.99",
        charge_date_label="5 October 2026",
    )
    assert "5 October 2026" in _visible_text(html)
    assert "$19.99" in _visible_text(html)


@pytest.mark.parametrize("open_access", [False, True])
def test_trial_invite_email_length_is_right_in_both_promo_states(
    open_access: bool,
) -> None:
    """The invite branches on the open-access promo; both branches must agree."""
    html = render_free_trial_invite_email(
        "Sam", open_access=open_access, open_access_until="7 September 2026",
    )
    wrong = [d for d in _durations_near_money(html) if d != TRIAL_DAYS]
    assert not wrong, f"open_access={open_access} states {wrong}, want {TRIAL_DAYS}"
