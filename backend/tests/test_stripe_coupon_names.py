"""Every Stripe coupon label must fit Stripe's 40-character `name` limit.

Why this file exists: on 2026-08-10 a real production checkout 502'd
(Sentry TAPELINE-BACKEND-26) because the annual trial-save coupon name was
52 characters. Stripe 400s an over-long `Coupon.name`, and every coupon in
services/billing.py is minted inside the try/except that converts a
StripeError into HTTPException(502) — so the customer clicking "keep my
plan, 50% off" got a dead checkout instead of a discount.

Four of the eight labels were over the limit at the time: both trial-save
variants, the annual win-back, and the annual cancel-intercept retention
offer. All four are revenue-RECOVERY paths, which is the worst possible
place for a silent break: the user is already leaving.

These labels are copy, so they get edited by people thinking about wording
rather than about Stripe's API contract. This test makes the limit part of
the contract instead of trivia someone has to remember.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app.services import billing
from app.services.billing import STRIPE_COUPON_NAME_MAX, _coupon_name

BILLING_SRC = Path(billing.__file__)


def _coupon_name_literals() -> list[tuple[int, str]]:
    """Every string passed to `name=_coupon_name(...)` in billing.py.

    Parsed from the AST rather than grepped so an f-string is measured with
    its placeholders filled by a worst-case stand-in, and so a new call site
    is picked up automatically instead of needing to be added to a list here.
    """
    tree = ast.parse(BILLING_SRC.read_text(encoding="utf-8"))
    found: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Name) and fn.id == "_coupon_name"):
            continue
        assert node.args, f"_coupon_name() called with no argument at line {node.lineno}"
        found.append((node.lineno, _render(node.args[0])))

    return found


def _render(node: ast.expr) -> str:
    """Flatten a str or f-string literal, standing in for placeholders.

    `referral_credit_months` is the only interpolated value; it is a month
    count, so "12" is the realistic worst case. Widen to 3 digits so the
    assertion still holds if someone ever grants a 100-month credit.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                out.append(part.value)
            else:
                out.append("999")  # worst-case placeholder
        return "".join(out)
    raise AssertionError(f"unexpected coupon-name expression: {ast.dump(node)}")


def test_every_coupon_name_call_site_is_found() -> None:
    """Guard the guard: if the call sites stop matching, this file is inert."""
    literals = _coupon_name_literals()
    assert len(literals) == 8, (
        f"expected 8 _coupon_name() call sites, found {len(literals)}. "
        "If you added or removed a coupon, update this count deliberately — "
        "it exists so the length assertions below can't silently stop running."
    )


@pytest.mark.parametrize("lineno,name", _coupon_name_literals())
def test_coupon_name_fits_stripe_limit(lineno: int, name: str) -> None:
    assert len(name) <= STRIPE_COUPON_NAME_MAX, (
        f"billing.py:{lineno} coupon name is {len(name)} chars "
        f"(Stripe's limit is {STRIPE_COUPON_NAME_MAX}): {name!r}. "
        "Stripe 400s this, which surfaces as a 502 on the customer's "
        "checkout. Shorten the label."
    )


def test_no_raw_coupon_names_bypass_the_clamp() -> None:
    """A `name=` on Coupon.create must go through _coupon_name().

    Without this, the next coupon added with a bare literal would reintroduce
    the exact 2026-08-10 outage and every test above would still pass.
    """
    src = BILLING_SRC.read_text(encoding="utf-8")
    bare = [
        (i, line.strip())
        for i, line in enumerate(src.splitlines(), start=1)
        if re.search(r"^\s*name=(?!_coupon_name\()", line)
    ]
    assert not bare, (
        "coupon name(s) not wrapped in _coupon_name(): "
        + "; ".join(f"billing.py:{i} {t}" for i, t in bare)
    )


def test_clamp_truncates_rather_than_raising() -> None:
    """The runtime backstop must fail SOFT.

    A clipped discount label is cosmetic; a raised exception here would land
    inside create_checkout_session's except-StripeError blind spot and break
    the payment anyway, which is the failure we're removing.
    """
    long = "x" * 100
    assert len(_coupon_name(long)) == STRIPE_COUPON_NAME_MAX
    assert _coupon_name("Trial save (50% off 3 months)") == "Trial save (50% off 3 months)"
