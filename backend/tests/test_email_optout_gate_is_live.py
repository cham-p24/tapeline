"""The per-category opt-out gate must actually fire in the broadcast scripts.

MEASURED 2026-09-07, while scoping a customer survey send
---------------------------------------------------------
`email_prefs.wants(user, category)` takes the USER. Both ad-hoc broadcast
scripts passed the prefs INT instead:

    scripts/catchup_send.py:133      wants(u.email_prefs, EmailPref.TRIAL_DRIP)
    scripts/free_month_offer.py:115  wants(u.email_prefs, EmailPref.TRIAL_DRIP)

`wants()` read the category off the argument with `getattr(user, "email_prefs",
None)` and treated `None` as "opted in" — a deliberate default for in-memory
User stubs whose column default has not fired. On an int that default is always
taken: `getattr(15, "email_prefs", None) is None` → True. So the branch read as
an opt-out check, type-checked at a glance, and returned True for every user
alive. The gate was decorative in both scripts.

WHAT IT DID AND DID NOT COST
----------------------------
Checked against production before fixing: every one of the 34 accounts has the
TRIAL_DRIP bit set, so no user had exercised the opt-out this gate reads, and
no past send actually overrode one. This was a latent defect, not a breach.

It mattered because the NEXT broadcast was going to be cloned from one of these
two scripts, and because the fix changes the failure mode: a primitive argument
now raises in a dry run instead of mailing everyone in a live one.

Every other call site in the codebase — twenty of them across services/email.py,
services/alerts.py and routers/admin.py — passed the User correctly. Only the two
ad-hoc scripts got it wrong, which is the argument for the type guard: the
careful path was already right, and the rushed one is where the money is.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from app.services.email_prefs import EmailPref, wants

REPO = pathlib.Path(__file__).resolve().parents[1] / "app"


class _User:
    """Duck-typed stand-in. wants() must keep accepting these — the defensive
    `prefs is None` default exists for exactly this shape."""

    def __init__(self, prefs: int | None) -> None:
        self.email_prefs = prefs


def test_an_opted_out_user_is_refused() -> None:
    assert wants(_User(0), EmailPref.TRIAL_DRIP) is False
    assert wants(_User(int(EmailPref.RE_ENGAGEMENT)), EmailPref.TRIAL_DRIP) is False


def test_an_opted_in_user_is_allowed() -> None:
    assert wants(_User(31), EmailPref.TRIAL_DRIP) is True
    assert wants(_User(int(EmailPref.TRIAL_DRIP)), EmailPref.TRIAL_DRIP) is True


def test_an_unset_prefs_column_still_defaults_to_opted_in() -> None:
    """The original defensive default, preserved. A None column is a DB-default
    oddity, not a choice the user made."""
    assert wants(_User(None), EmailPref.TRIAL_DRIP) is True


@pytest.mark.parametrize("bad", [0, 15, 31, True, 1.0, "31", b"31", None])
def test_passing_the_prefs_int_raises_instead_of_failing_open(bad: object) -> None:
    """The whole bug in one assertion.

    Before the fix every one of these returned True — including 0, a user who
    had opted out of everything. Returning True for `0` is the precise shape of
    "the gate is decorative".
    """
    with pytest.raises(TypeError, match=r"not .*email_prefs"):
        wants(bad, EmailPref.TRIAL_DRIP)  # type: ignore[arg-type]


def _wants_call_args() -> list[tuple[str, int, str]]:
    """Every wants() call in app/, as (file, line, first-arg source).

    AST, not grep: the docstrings and comments around this fix quote the broken
    call verbatim, and a text scan cannot tell the explanation from the defect.
    """
    out: list[tuple[str, int, str]] = []
    for path in REPO.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == "wants"
                and node.args
            ):
                out.append((
                    str(path.relative_to(REPO)).replace("\\", "/"),
                    node.lineno,
                    ast.unparse(node.args[0]),
                ))
    return out


def test_no_call_site_passes_the_prefs_attribute() -> None:
    """The type guard catches this at runtime; this catches it at review time,
    before a dry run is ever executed."""
    calls = _wants_call_args()
    assert len(calls) > 15, (
        f"only found {len(calls)} wants() calls — the AST walk is not reaching "
        f"the codebase, so this guard would pass vacuously"
    )
    offenders = [
        f"{f}:{ln} — wants({arg}, ...)"
        for f, ln, arg in calls
        if arg.endswith(".email_prefs") or arg == "email_prefs"
    ]
    assert offenders == [], (
        "a wants() call passes the prefs value instead of the user: "
        + "; ".join(offenders)
        + ". That reads as an opt-out check and enforces nothing."
    )
