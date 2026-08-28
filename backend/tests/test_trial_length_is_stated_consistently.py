"""What we SAY the trial is must equal what Stripe DOES.

`TRIAL_DAYS` in app/routers/billing.py sets `subscription_data.trial_end` on
the Checkout session — it decides the day the customer's card is actually
charged. The frontend has its own copy in lib/trial.ts, because the number has
to appear in rendered text.

Two constants for one promise is a drift hazard, and a worse one than the
prices lib/pricing.ts guards: advertising "14-day" while Stripe is told 30 (or
the reverse) means the first charge lands on a different day than the one we
put in writing on the card wall, in the signup copy, and in the pre-charge
email. That is a billing surprise, and this product's entire pitch is that it
does not misstate things.

Before this, the length was hardcoded as the literal "14-day" in thirteen
separate strings on the signup page alone, so changing the trial meant finding
every one and missing none.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.routers.billing import MIN_TRIAL_DAYS, TRIAL_DAYS

_FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def _strip_comments(src: str) -> str:
    """Rendered copy only — comments are documentation, not claims.

    A line-prefix filter is not enough: these files carry JSX block comments
    ({/* ... */}) whose continuation lines start with ordinary words, and one
    of them is the standing PROHIBITION on saying "no credit card". Scanning
    that as if it were copy would fail the file for containing the very rule
    that keeps it honest.
    """
    out = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)  # /* */ and {/* */}
    out = re.sub(r"^\s*//.*$", " ", out, flags=re.M)  # // line comments
    return out


def _frontend_trial_days() -> int:
    src = (_FRONTEND / "lib" / "trial.ts").read_text(encoding="utf-8")
    m = re.search(r"export const TRIAL_DAYS\s*=\s*(\d+)\s*;", src)
    assert m, "lib/trial.ts no longer exports a literal TRIAL_DAYS"
    return int(m.group(1))


def test_the_advertised_length_matches_the_charged_length():
    frontend = _frontend_trial_days()
    assert frontend == TRIAL_DAYS, (
        f"the site advertises a {frontend}-day trial while Stripe is told "
        f"{TRIAL_DAYS} days. Whichever is wrong, a customer is charged on a "
        f"different day than the one we put in writing. Change both, or neither."
    )


def test_the_length_still_clears_the_pre_charge_notice_floor():
    """A trial shorter than the notice period is a promise we cannot keep.

    We commit to emailing three days before the first charge (the
    `customer.subscription.trial_will_end` branch). MIN_TRIAL_DAYS exists so a
    trial can never be shorter than its own warning.
    """
    assert TRIAL_DAYS >= MIN_TRIAL_DAYS


def test_the_copy_interpolates_rather_than_hardcoding_the_number():
    """Guards the fix, not just the values.

    Re-hardcoding "14-day" into a string is exactly how the two constants drift
    apart: they keep matching each other while the rendered text quietly says
    something else.
    """
    signup = (_FRONTEND / "app" / "signup" / "page.tsx").read_text(encoding="utf-8")
    literal = re.findall(r"\d+-day (?:Premium )?trial", _strip_comments(signup))
    assert not literal, (
        f"signup copy hardcodes the trial length again: {literal}. Interpolate "
        f"TRIAL_LENGTH_LABEL from lib/trial.ts so one edit changes every surface."
    )


def test_the_card_wall_reads_the_constant_too():
    wall = (_FRONTEND / "app" / "app" / "start" / "page.tsx").read_text(encoding="utf-8")
    assert "TRIAL_DAYS" in wall, "the card wall stopped reading the constant"
    assert not re.findall(r"\d+-day", _strip_comments(wall)), (
        "the card wall hardcodes a trial length; it must interpolate TRIAL_DAYS"
    )


def test_the_trial_is_never_advertised_as_needing_no_card():
    """The trial takes a card. Copy may not imply otherwise.

    Scoped to the marketing cliché "no credit card", NOT to the words "no
    card" generally — because the card wall says something true with those
    words: the public record and today's picks are open to everyone "with no
    account and no card". That sentence is the honest way out of the gate and
    must not be broken by a blunter rule than the one we actually mean.

    Pinned because "no credit card required" is the single most tempting phrase
    to add to a trial CTA, and here it would be a lie about when someone gets
    charged.
    """
    for name in ("app/app/start/page.tsx", "app/signup/page.tsx"):
        src = _strip_comments((_FRONTEND / name).read_text(encoding="utf-8"))
        assert not re.search(r"no\s+credit\s+card", src, re.I), (
            f"{name} advertises 'no credit card' — the trial requires one"
        )
