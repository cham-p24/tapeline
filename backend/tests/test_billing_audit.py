"""Guards on the billing audit.

It reads live Stripe and every account's tier, so the properties worth pinning
are: it stays read-only, it never leaks a customer's email into a CI log, and
it uses the shared vendor-object accessor rather than `.get()` — which is the
#639 bug it partly exists to detect.
"""

import ast
import inspect
import textwrap

from app.scripts import billing_audit as ba
from app.services.stripe_compat import stripe_field


def _code() -> str:
    """Executable source only — comments and docstrings stripped, so the
    module's own prose about `.get()` and writes can't satisfy or break these
    assertions."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(ba)))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module))
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


#: Method names that write. A read-only audit has no legitimate use for any of
#: them on ANY receiver, so this is matched on the method rather than on
#: "session.commit" — the first version of this guard banned that exact string
#: while the audit's session variable is named `s`, so `await s.commit()`
#: passed straight through it. Watched it fail before trusting it.
WRITE_METHODS = {"commit", "add", "add_all", "delete", "flush", "merge", "execute"}

#: Stripe calls that create or move money. `execute` is in WRITE_METHODS above
#: but `session.execute(select(...))` is the audit's only read path, so it is
#: allowed there and checked separately.
MONEY_CALLS = {
    "Subscription.create", "Subscription.delete", "Subscription.modify",
    "Customer.create", "Customer.delete", "Customer.modify",
    "PaymentIntent.create", "Charge.create", "Refund.create", "Invoice.pay",
    "checkout.Session.create",
}


def test_it_is_read_only():
    """Every fix this audit could suggest moves money or changes what someone
    is entitled to. It reports; a human decides.

    Matched on the AST method name, not a receiver-qualified string.
    """
    code = _code()
    for banned in MONEY_CALLS:
        assert banned not in code, f"{banned} moves money or creates billing state"

    offenders = []
    for node in ast.walk(ast.parse(code)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        name = node.func.attr
        if name not in WRITE_METHODS:
            continue
        # The one permitted write-shaped call: session.execute(select(...)).
        if name == "execute":
            arg = node.args[0] if node.args else None
            reads = (
                isinstance(arg, ast.Call)
                and isinstance(arg.func, ast.Name)
                and arg.func.id == "select"
            )
            if reads:
                continue
        offenders.append(f".{name}(...) at line {node.lineno}")
    assert not offenders, (
        "the audit is supposed to be read-only, but writes: " + "; ".join(offenders)
    )


STRIPE_LOCALS = {"customer", "sub", "subs", "it", "p", "acct", "sessions", "event", "rec"}


def test_it_uses_the_shared_accessor_not_dot_get():
    """StripeObject has no .get() in stripe-python >= 12. That is #639, and it
    has now been written twice by accident in this codebase.

    Matched on the AST receiver, not on text: the distinction that matters is
    WHAT you call .get() on, and a substring can't see that.
    """
    code = _code()
    assert "stripe_field" in code or "_f(" in code

    offenders = []
    for node in ast.walk(ast.parse(code)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in STRIPE_LOCALS
        ):
            offenders.append(f"{node.func.value.id}.get(...) at line {node.lineno}")
    assert not offenders, (
        "AttributeError on a StripeObject — this is exactly #639: " + "; ".join(offenders)
    )


def test_that_guard_would_actually_fire():
    """The guard above is a no-op if its receiver set never matches. Prove it
    catches the real shape while leaving a plain-dict .get() alone."""
    sample = "customer.get('email')" + chr(10) + "findings.get(key, [])"
    tree = ast.parse(sample)
    hits = [
        n.func.value.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "get"
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id in STRIPE_LOCALS
    ]
    assert hits == ["customer"], "the receiver check does not discriminate"


def test_emails_are_masked():
    """This runs in GitHub Actions logs."""
    assert ba._mask_email("chamara@tapeline.io") == "ch***@tapeline.io"
    assert ba._mask_email("a@b.com") == "a***@b.com"
    assert ba._mask_email(None) == "(none)"
    assert ba._mask_email("") == "(none)"
    # The local part must never survive intact.
    assert "chamara" not in ba._mask_email("chamara@tapeline.io")


def test_paid_not_granted_is_reported_first():
    """Being charged and not receiving the product is the worst outcome here,
    and it is #639's exact signature. It must not be buried under the benign
    GRANTED_NOT_PAID rows."""
    code = _code()
    order_start = code.index("order = [")
    order_block = code[order_start:order_start + 400]
    assert order_block.index("PAID_NOT_GRANTED") < order_block.index("GRANTED_NOT_PAID")


def test_past_due_counts_as_live():
    """A past_due subscription still entitles the customer — dropping them to
    free the moment a card bounces would be the wrong repair, and would make
    the audit recommend it."""
    assert "past_due" in ba.LIVE_STATUSES
    assert "active" in ba.LIVE_STATUSES
    assert "trialing" in ba.LIVE_STATUSES
    assert "canceled" not in ba.LIVE_STATUSES


def test_price_ids_map_back_to_tiers():
    """A price id that maps to nothing would silently report TIER_MISMATCH for
    a perfectly healthy subscriber."""
    code = _code()
    for field in (
        "stripe_price_pro_monthly", "stripe_price_pro_annual",
        "stripe_price_premium_monthly", "stripe_price_premium_annual",
    ):
        assert field in code, f"{field} is not mapped back to a tier"


class _StripeLike:
    """A StripeObject stand-in: subscriptable, and deliberately no .get()."""

    def __init__(self, data):
        self._data = data

    def __getitem__(self, k):
        return self._data[k]


def test_shared_accessor_handles_both_shapes():
    assert stripe_field(_StripeLike({"id": "cus_1"}), "id") == "cus_1"
    assert stripe_field({"id": "cus_2"}, "id") == "cus_2"
    assert stripe_field(_StripeLike({}), "missing", "d") == "d"
    assert stripe_field(None, "anything", "d") == "d"
    # A present-but-None field must fall back, not return None — Stripe sends
    # explicit nulls for unset optional fields.
    assert stripe_field({"x": None}, "x", "d") == "d"


def test_shared_accessor_never_raises_on_a_get_less_object():
    """The whole point: this is what `.get()` would blow up on."""
    obj = _StripeLike({"a": 1})
    assert not hasattr(obj, "get")
    assert stripe_field(obj, "a") == 1
    assert stripe_field(obj, "nope") is None
