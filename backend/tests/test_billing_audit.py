"""Guards on the billing audit.

It reads live Stripe and every account's tier, so the properties worth pinning
are: it stays read-only, it never leaks a customer's email or Stripe id into
its public CI log, and it uses the shared vendor-object accessor rather than
`.get()` — which is the #639 bug it partly exists to detect.
"""

import ast
import inspect
import json
import logging
import re
import textwrap
from urllib.parse import parse_qs, urlparse

import pytest
import stripe

import app.db as _db
from app.models import User
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


class _Sub:
    """A StripeObject-shaped subscription: subscriptable, no .get()."""

    def __init__(self, data):
        self._d = data

    def __getitem__(self, k):
        return self._d[k]


def test_the_audit_reports_cancellations():
    """The gap this closes.

    On 2026-09-03 this script printed "No discrepancies. Every account's local
    tier agrees with Stripe." while THREE of five customers — including the only
    one who had ever paid — had cancel_at_period_end set. Every word of that
    output was true and it told the founder the opposite of what was happening.

    A cancellation is not a discrepancy: local tier and Stripe agree perfectly,
    because the person IS still entitled until the period ends. So no existing
    finding category could ever have caught it, and adding one would have been
    wrong. It needs its own section.
    """
    code = _code()
    assert "cancel_at_period_end" in code, "the audit still cannot see a cancellation"
    assert "CANCELLING" in code, "cancellations are not reported as their own section"


def test_cancellation_reporting_is_not_a_finding():
    """It must not be shoved into `findings`. Nothing is broken, so a
    reconciliation failure would be a false alarm — and the founder would learn
    to ignore it."""
    code = _code()
    for wrong in ('findings["CANCELLING"]', 'findings["CHURN"]', 'findings["CANCELLED"]'):
        assert wrong not in code, "a cancellation is not a data discrepancy"


def test_it_reads_the_period_end_from_both_shapes():
    """current_period_end moved off the Subscription onto the subscription ITEM
    in Stripe API 2025-04-30.basil — the exact shape change behind #639. An
    audit that only reads the old location prints "date unknown" for every
    cancelling customer on the current API version."""
    code = _code()
    # Precise, because the loose version was VACUOUS: `"items" in code` is
    # satisfied by the unrelated price-item loop that derives stripe_tier, so
    # deleting the fallback left the test green. Watched it stay green against
    # the mutation, which is the only reason this is written out longhand.
    assert code.count("current_period_end") >= 2, (
        "only one read of current_period_end — the subscription-level and the "
        "item-level shapes are both needed (API 2025-04-30.basil moved it)"
    )
    assert "items[0]" in code, "the item-level fallback is missing"


def test_the_accessor_survives_a_subscription_without_get():
    """The churn read goes through the shared accessor, not .get()."""
    sub = _Sub({"cancel_at_period_end": True, "status": "active"})
    assert not hasattr(sub, "get")
    assert stripe_field(sub, "cancel_at_period_end") is True
    assert stripe_field(sub, "cancel_at", None) is None


# ---------------------------------------------------------------------------
# The log is PUBLIC. This job runs as a GitHub Action on a public repository,
# so anything it prints is world-readable. Masking the email was never enough:
# the 14 Sep 2026 run printed every customer's raw Stripe id 5 times over —
# 4 times per customer from stripe-python's own INFO request logging
# ("Request to Stripe api ... url=.../v1/customers/cus_...") and once more from
# the audit's own per-account line, plus again on each PAST_DUE finding.
# ---------------------------------------------------------------------------

#: Fake, test-only ids. Shaped like real ones so the library routes them and
#: the leak pattern below would catch them.
ORPHAN = "cus_TESTorphan000001"
DELETED = "cus_TESTdeleted00002"
PAST_DUE = "cus_TESTpastdue00003"
DUP_A = "cus_TESTdupeA0000004"
DUP_B = "cus_TESTdupeB0000005"
ALL_IDS = (ORPHAN, DELETED, PAST_DUE, DUP_A, DUP_B)


class _FakeStripeHTTP(stripe.HTTPClient):
    """Canned Stripe API. Going through the real library's request path is the
    point: stripe-python's own INFO logging of each request URL is one of the
    two ways a raw customer id reached the public log."""

    name = "fake"

    def request(self, method, url, headers, post_data=None, *, _usage=None):
        u = urlparse(url)
        q = parse_qs(u.query)
        hdrs = {"request-id": "req_test"}
        if u.path.startswith("/v1/customers/"):
            cid = u.path.rsplit("/", 1)[-1]
            if cid == ORPHAN:
                err = {
                    "error": {
                        "type": "invalid_request_error",
                        "code": "resource_missing",
                        "param": "id",
                        "message": f"No such customer: '{cid}'",
                    }
                }
                return json.dumps(err), 404, hdrs
            if cid == DELETED:
                return json.dumps({"id": cid, "object": "customer", "deleted": True}), 200, hdrs
            email = "dupe@example.com" if cid in (DUP_A, DUP_B) else "late@example.com"
            return json.dumps({"id": cid, "object": "customer", "email": email}), 200, hdrs
        if u.path == "/v1/subscriptions":
            cid = q.get("customer", [""])[0]
            data = []
            if cid == PAST_DUE:
                data = [{
                    "id": "sub_TESTpastdue0001",
                    "object": "subscription",
                    "status": "past_due",
                    "cancel_at_period_end": False,
                    "items": {"object": "list", "data": []},
                }]
            body = {"object": "list", "data": data, "has_more": False, "url": "/v1/subscriptions"}
            return json.dumps(body), 200, hdrs
        if u.path == "/v1/invoices":
            body = {"object": "list", "data": [], "has_more": False, "url": "/v1/invoices"}
            return json.dumps(body), 200, hdrs
        return json.dumps({"error": {"type": "api_error", "message": "unrouted"}}), 500, hdrs


async def _seed_customers() -> None:
    async with _db.SessionLocal() as s:
        for i, cid in enumerate(ALL_IDS):
            s.add(User(
                id=f"u{i}", email=f"acct{i}@example.com", tier="free",
                password_hash="x", stripe_customer_id=cid,
            ))
        await s.commit()


async def _run_audit_capturing(monkeypatch, caplog) -> str:
    await _seed_customers()
    monkeypatch.setattr(ba.settings, "stripe_secret_key", "sk_test_fake", raising=False)
    monkeypatch.setattr(stripe, "api_key", None)
    monkeypatch.setattr(stripe, "default_http_client", _FakeStripeHTTP())
    monkeypatch.setattr(stripe, "max_network_retries", 0)
    # Production runs the module as a script, where `logging.basicConfig(
    # level=INFO)` puts an INFO handler on the root logger. Mirror that.
    caplog.set_level(logging.INFO)
    await ba._main()
    # Every record from every logger, as it would print — the stripe library's
    # own request lines included.
    return "\n".join(r.getMessage() for r in caplog.records)


async def test_the_public_log_carries_no_raw_customer_id(monkeypatch, caplog):
    text = await _run_audit_capturing(monkeypatch, caplog)
    # The run really exercised every path that used to print an id — the
    # per-account line, ORPHAN (both kinds), PAST_DUE, PAID_NOT_GRANTED and
    # DUPLICATE_CUSTOMER — otherwise a clean log would prove nothing.
    for section in ("ORPHAN_CUSTOMER", "PAST_DUE", "PAID_NOT_GRANTED", "DUPLICATE_CUSTOMER"):
        assert re.search(rf"^{section}\s+[1-9]", text, re.M), f"{section} was not exercised"
    leaked = sorted({cid for cid in ALL_IDS if cid in text})
    assert not leaked, f"raw Stripe customer ids in the public log: {leaked}"
    assert not re.search(r"cus_[A-Za-z0-9]{6,}", text), "a raw customer id shape survived"


async def test_findings_still_name_the_account_by_a_stable_hash(monkeypatch, caplog):
    """Hashing must not make the report useless: each finding still carries a
    handle the operator can match against the database, and it is the same
    handle every week."""
    text = await _run_audit_capturing(monkeypatch, caplog)
    assert ba._mask_stripe_id(PAST_DUE) in text
    assert ba._mask_stripe_id(ORPHAN) in text
    assert ba._mask_stripe_id(DUP_A) in text and ba._mask_stripe_id(DUP_B) in text


def test_stripe_library_request_logging_is_silenced(caplog):
    """stripe-python logs every request URL — which embeds the customer id —
    at INFO on the `stripe` logger. Under the script's INFO root handler that
    went straight into the public log."""
    caplog.set_level(logging.INFO)
    logging.getLogger("stripe").info(
        "message='Request to Stripe api' method=get "
        "url=https://api.stripe.com/v1/customers/cus_TESTlogline00001"
    )
    assert "cus_TESTlogline00001" not in caplog.text


def test_customer_id_mask_is_stable_one_way_and_distinct():
    a = ba._mask_stripe_id(PAST_DUE)
    assert a == ba._mask_stripe_id(PAST_DUE), "must be stable across runs"
    assert PAST_DUE not in a and PAST_DUE[4:] not in a
    assert a != ba._mask_stripe_id(ORPHAN)
    assert ba._mask_stripe_id(None) == "(none)"
    assert ba._mask_stripe_id("") == "(none)"
    # Free text (an exception message quotes the id it failed on) is scrubbed.
    scrubbed = ba._scrub(f"No such customer: '{ORPHAN}'")
    assert ORPHAN not in scrubbed and ba._mask_stripe_id(ORPHAN) in scrubbed


def test_a_crash_does_not_print_a_raw_customer_id(monkeypatch, caplog):
    """An uncaught Stripe error is printed by Python as a traceback whose
    message can quote the customer id it failed on. The entry point scrubs it
    and still exits non-zero, so the Actions run still goes red."""
    crash_id = "cus_TESTcrash0000001"

    async def _boom() -> None:
        raise RuntimeError(f"Request req_test: No such customer: '{crash_id}'")

    monkeypatch.setattr(ba, "_main", _boom)
    caplog.set_level(logging.INFO)
    with pytest.raises(SystemExit) as exit_:
        ba.main()
    assert exit_.value.code == 1
    assert crash_id not in caplog.text
    assert ba._mask_stripe_id(crash_id) in caplog.text
