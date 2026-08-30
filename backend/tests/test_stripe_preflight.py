"""Guards on the Stripe shadow test.

The script talks to LIVE Stripe, so the properties worth pinning are the ones
that keep it harmless and keep it honest.

It also must not commit the very bug it exists to detect. #639 was
`stripe.Event.get(...)` raising AttributeError because a `StripeObject` is not
a dict in stripe-python >= 12 — and the first draft of this script called
`.get()` on `stripe.Price`, `stripe.Account` and a `ListObject`. mypy caught
it before it ran. This test keeps that door shut.
"""

import ast
import inspect
import textwrap

from app.scripts import stripe_preflight as pf


def _code() -> str:
    """Executable source only — comments and docstrings stripped.

    The module docstring necessarily discusses `.get()` and "no charge", so
    prose must not be able to satisfy OR break these assertions.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(pf)))
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


def test_it_never_calls_get_on_a_stripe_object():
    """The #639 shape bug, in the tool built to catch it."""
    code = _code()
    for banned in ("acct.get(", "p.get(", "sessions.get(", "newest.get(", "rec.get("):
        assert banned not in code, (
            f"{banned!r} — StripeObject has no .get() in stripe-python >= 12; "
            f"this is exactly the #639 failure mode"
        )
    assert "_f(" in code, "the safe field accessor is not being used"


def test_the_field_accessor_survives_both_shapes():
    """It has to work against a real StripeObject (subscript, no .get) and
    against the plain dicts nested fields sometimes come back as."""
    class _Obj:
        def __init__(self, d):
            self._d = d

        def __getitem__(self, k):
            return self._d[k]        # no .get, like StripeObject

    assert pf._f(_Obj({"id": "x"}), "id") == "x"
    assert pf._f({"id": "y"}, "id") == "y"
    assert pf._f(_Obj({}), "missing", "fallback") == "fallback"
    assert pf._f({}, "missing") is None


def test_it_takes_no_money():
    """A shadow test that could charge would be a very expensive mistake.

    Creating a Checkout Session mints a URL; a PaymentIntent, Charge, Refund
    or direct Customer creation would not be a shadow test at all.
    """
    code = _code()
    for banned in (
        "PaymentIntent.create",
        "Charge.create",
        "Refund.create",
        "Subscription.create",
        "Customer.create",
        "Invoice.pay",
    ):
        assert banned not in code, f"{banned} moves money or creates billing state"


def test_it_expires_the_sessions_it_creates():
    """The URLs it mints are real and completable until expired. Leaving one
    open is a live checkout link sitting in a CI log."""
    code = _code()
    assert "Session.expire" in code


def test_it_calls_the_real_checkout_path_not_a_copy():
    """#635 slipped through because a permissive mock accepted a
    wrong-but-plausible Stripe field. Re-implementing the kwargs here would
    rebuild that blind spot in a new place."""
    code = _code()
    assert "from app.services.billing import create_checkout_session" in code
    assert "create_checkout_session(" in code


def test_it_never_prints_a_whole_secret():
    """It reports LIVE vs TEST mode, which needs a few characters of the key
    and no more.

    The fixture is deliberately NOT key-shaped. An earlier version used a
    realistic-looking `sk_live_…` literal and GitHub push protection blocked
    the push — correctly. A fake credential that pattern-matches a real one is
    still a bad thing to commit to a public repo: it trains people to click
    past the warning, and no scanner can tell it is fake.
    """
    sample = "PREFIXX_notarealkey_SUFFIX_abcd"
    masked = pf._mask(sample)
    assert masked == "PREFIXX…abcd"
    assert sample not in masked
    # 11 of 31 characters survive; the rest cannot be recovered from the log.
    assert len(masked) < len(sample)

    # Short/absent values must not echo at all.
    assert pf._mask("short") == "(set)"

    code = _code()
    assert "settings.stripe_secret_key)" not in code.replace("_mask(", "")


def test_the_webhook_check_stops_at_parsing():
    """It signs a payload and runs the real parser. It must NOT dispatch the
    event — handling a fabricated `checkout.session.completed` could grant a
    tier or write an idempotency row."""
    code = _code()
    assert "parse_webhook" in code
    for banned in ("handle_event", "handle_webhook", "process_event"):
        assert banned not in code, f"{banned} would dispatch a fabricated event"
