"""Guards on the pre-charge notice check, plus its grading logic.

The check reads live Stripe and the webhook dedup table on a schedule and can
page the founder, so three properties are worth pinning: it stays read-only, it
never leaks a customer email into a world-readable CI log, and it grades
findings correctly — an alarm that cannot distinguish "Stripe never sent it"
from "we dropped it" sends someone to fix the wrong system.

The grading tests execute `render` and `gather` rather than reading the source.
`gather` is driven through injected fakes shaped like the real vendor objects,
because the shape is where this codebase keeps getting caught (#639, #635, and
the dahlia `current_period_end` move that this very script has to work around).
"""
from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from app.scripts import check_precharge_notices as cpn


def _code() -> str:
    """Executable source only — docstrings stripped, so the module's prose
    about writes cannot satisfy or break these assertions."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(cpn)))
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


WRITE_METHODS = {"commit", "add", "add_all", "delete", "flush", "merge", "execute"}

def _is_select(arg: ast.expr | None) -> bool:
    """True when `arg` is a SELECT, including builder-chained forms.

    `session.execute(...)` is write-shaped, so it is banned by default and
    allowed back only for reads. The obvious version of this check —
    `arg.func` is a Name called "select" — sees `select(X)` and misses
    `select(X).where(Y)`, whose func is an Attribute. That would reject the
    read this module actually performs while still waving through a genuine
    write, so the chain is unwrapped to its root call first.
    """
    while isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute):
        arg = arg.func.value
    return (
        isinstance(arg, ast.Call)
        and isinstance(arg.func, ast.Name)
        and arg.func.id == "select"
    )


MONEY_CALLS = {
    "Subscription.create", "Subscription.delete", "Subscription.modify",
    "Customer.create", "Customer.delete", "Customer.modify",
    "PaymentIntent.create", "Charge.create", "Refund.create", "Invoice.pay",
    "checkout.Session.create", "WebhookEndpoint.modify", "WebhookEndpoint.create",
}


def test_it_is_read_only():
    """A monitor that can change billing state is a liability, not a monitor.

    `WebhookEndpoint.modify` is in the banned set deliberately: the temptation
    with this particular check is to have it "fix" a missing subscription by
    enabling the event itself. It reports; a human decides.
    """
    code = _code()
    for banned in MONEY_CALLS:
        assert banned not in code, f"{banned} changes billing state"

    offenders = []
    for node in ast.walk(ast.parse(code)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        name = node.func.attr
        if name not in WRITE_METHODS:
            continue
        if name == "execute" and _is_select(node.args[0] if node.args else None):
            continue
        offenders.append(f".{name}(...) at line {node.lineno}")
    assert not offenders, (
        "the check must stay read-only, but writes: " + "; ".join(offenders)
    )


def test_it_never_reads_a_customer_email():
    """Output lands in a public repo's Actions log. Stripe ids are enough."""
    code = _code()
    assert '"email"' not in code and "'email'" not in code
    assert "User.email" not in code


def test_it_uses_the_shared_accessor_not_dot_get():
    """StripeObject has no `.get()` in stripe-python >= 12 — that is #639, and
    it has been written twice by accident in this codebase already."""
    code = _code()
    assert "stripe_field" in code

    stripe_locals = {"sub", "subs", "e", "events", "it", "obj", "event"}
    offenders = [
        f"{n.func.value.id}.get(...) at line {n.lineno}"
        for n in ast.walk(ast.parse(code))
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "get"
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id in stripe_locals
    ]
    assert not offenders, "AttributeError on a StripeObject (#639): " + "; ".join(offenders)


def test_lookback_cannot_exceed_stripe_event_retention(monkeypatch):
    """Stripe keeps events 30 days. A longer lookback reads "no event" for
    every old renewal and cries wolf on every run, forever."""
    assert cpn.LOOKBACK_DAYS <= 21


# ── the dahlia field move ────────────────────────────────────────────────────

def test_period_end_is_read_off_the_subscription_item():
    """On 2026-08-26.dahlia `current_period_end` is on the ITEM. Reading only
    the subscription returns None for every live sub and the check inspects
    nothing while reporting success."""
    sub = {"id": "sub_x", "items": {"data": [{"current_period_end": 1789361715}]}}
    assert cpn._period_end(sub) == 1789361715


def test_period_end_still_reads_the_legacy_top_level_field():
    assert cpn._period_end({"id": "s", "current_period_end": 123}) == 123


def test_period_end_is_none_when_absent():
    assert cpn._period_end({"id": "s", "items": {"data": []}}) is None


# ── grading ──────────────────────────────────────────────────────────────────

def _sub(sub_id, cust, end_ts, *, status="active", cancel=False):
    return {
        "id": sub_id, "customer": cust, "status": status,
        "cancel_at_period_end": cancel,
        "items": {"data": [{"current_period_end": end_ts}]},
    }


def _event(evt_id, evt_type, cust, created):
    return {"id": evt_id, "type": evt_type, "created": created,
            "data": {"object": {"customer": cust}}}


@pytest.fixture
def wire(monkeypatch):
    """Drive gather() with injected Stripe + DB state."""
    def _install(*, subs, events, recorded):
        class _List:
            def __init__(self, data): self.data = data
            def __getitem__(self, k): return {"data": self.data}[k]

        def _sub_list(**kw):
            return _List(subs)

        def _evt_list(**kw):
            # `type` is Stripe's kwarg name; taken from **kw so the fake does
            # not shadow the builtin.
            wanted = kw["type"]
            return _List([e for e in events if e["type"] == wanted])

        monkeypatch.setattr(cpn.stripe.Subscription, "list", _sub_list)
        monkeypatch.setattr(cpn.stripe.Event, "list", _evt_list)

        async def _rec():
            return set(recorded)

        monkeypatch.setattr(cpn, "_recorded_event_ids", _rec)
    return _install


def _now():
    import time
    return int(time.time())


@pytest.mark.asyncio
async def test_charged_with_no_notice_is_missed(wire):
    """The finding that matters: a renewal already happened and nothing warned
    the customer."""
    past = _now() - 3 * cpn.DAY
    wire(subs=[_sub("sub_1", "cus_1", past)], events=[], recorded=[])
    d = await cpn.gather()
    assert [r["sub"] for r in d["missed"]] == ["sub_1"]
    assert not d["dropped"] and not d["healthy"]
    subject, text, alert = cpn.render(d)
    assert alert is True
    assert "MISSED" in text
    assert "ALERT" in subject


@pytest.mark.asyncio
async def test_emitted_but_not_recorded_is_dropped(wire):
    """Stripe sent it, we never processed it — a different system to fix, so
    it must not be graded the same as MISSED."""
    past = _now() - 2 * cpn.DAY
    wire(
        subs=[_sub("sub_1", "cus_1", past)],
        events=[_event("evt_a", "invoice.upcoming", "cus_1", past - cpn.DAY)],
        recorded=[],                      # never landed in our dedup table
    )
    d = await cpn.gather()
    assert [r["sub"] for r in d["dropped"]] == ["sub_1"]
    assert not d["missed"]
    _, text, alert = cpn.render(d)
    assert alert is True
    assert "DROPPED" in text
    assert "enabled_events" in text       # points at the right fix


@pytest.mark.asyncio
async def test_emitted_and_recorded_is_healthy_and_silent(wire):
    past = _now() - 2 * cpn.DAY
    wire(
        subs=[_sub("sub_1", "cus_1", past)],
        events=[_event("evt_a", "invoice.upcoming", "cus_1", past - cpn.DAY)],
        recorded=["evt_a"],
    )
    d = await cpn.gather()
    assert [r["sub"] for r in d["healthy"]] == ["sub_1"]
    _, _, alert = cpn.render(d)
    assert alert is False


@pytest.mark.asyncio
async def test_future_renewal_without_a_notice_is_only_pending(wire):
    """Stripe's lead time is days. A renewal 4 days out with no notice yet is
    normal — alarming here would fire on every healthy subscription."""
    soon = _now() + 4 * cpn.DAY
    wire(subs=[_sub("sub_1", "cus_1", soon)], events=[], recorded=[])
    d = await cpn.gather()
    assert [r["sub"] for r in d["pending"]] == ["sub_1"]
    assert not d["missed"]
    _, _, alert = cpn.render(d)
    assert alert is False


@pytest.mark.asyncio
async def test_trial_will_end_counts_as_a_notice(wire):
    """The first charge is covered by the other leg. A converting trial that
    got trial_will_end has been told, and must not read as MISSED."""
    past = _now() - 2 * cpn.DAY
    wire(
        subs=[_sub("sub_1", "cus_1", past, status="trialing")],
        events=[_event("evt_t", "customer.subscription.trial_will_end", "cus_1", past - cpn.DAY)],
        recorded=["evt_t"],
    )
    d = await cpn.gather()
    assert [r["sub"] for r in d["healthy"]] == ["sub_1"]


@pytest.mark.asyncio
async def test_cancelling_subscription_is_owed_no_notice(wire):
    """No charge is coming, so silence is correct, not a miss."""
    past = _now() - 2 * cpn.DAY
    wire(subs=[_sub("sub_1", "cus_1", past, cancel=True)], events=[], recorded=[])
    d = await cpn.gather()
    assert not d["missed"] and not d["pending"] and not d["healthy"]


@pytest.mark.asyncio
async def test_dead_subscription_is_ignored(wire):
    past = _now() - 2 * cpn.DAY
    wire(subs=[_sub("sub_1", "cus_1", past, status="canceled")], events=[], recorded=[])
    d = await cpn.gather()
    assert not d["missed"]


@pytest.mark.asyncio
async def test_renewal_far_outside_the_window_is_not_inspected(wire):
    """Both directions: a renewal 300 days out and one 200 days past are both
    outside anything this check can say something useful about."""
    wire(
        subs=[
            _sub("sub_far", "cus_1", _now() + 300 * cpn.DAY),
            _sub("sub_old", "cus_2", _now() - 200 * cpn.DAY),
        ],
        events=[], recorded=[],
    )
    d = await cpn.gather()
    assert not any((d["missed"], d["dropped"], d["pending"], d["healthy"]))
    _, text, alert = cpn.render(d)
    assert alert is False
    assert "Nothing to verify" in text


@pytest.mark.asyncio
async def test_a_notice_for_a_different_customer_does_not_count(wire):
    """Grading is per customer. A neighbour's notice must not silence ours."""
    past = _now() - 2 * cpn.DAY
    wire(
        subs=[_sub("sub_1", "cus_1", past)],
        events=[_event("evt_a", "invoice.upcoming", "cus_OTHER", past - cpn.DAY)],
        recorded=["evt_a"],
    )
    d = await cpn.gather()
    assert [r["sub"] for r in d["missed"]] == ["sub_1"]


@pytest.mark.asyncio
async def test_a_stale_notice_from_a_previous_cycle_does_not_count(wire):
    """A monthly subscriber has an invoice.upcoming from LAST month. It says
    nothing about whether this month's charge was announced."""
    past = _now() - 2 * cpn.DAY
    wire(
        subs=[_sub("sub_1", "cus_1", past)],
        events=[_event("evt_old", "invoice.upcoming", "cus_1", past - 40 * cpn.DAY)],
        recorded=["evt_old"],
    )
    d = await cpn.gather()
    assert [r["sub"] for r in d["missed"]] == ["sub_1"], "stale notice was counted"


def test_the_readonly_guard_understands_chained_selects():
    """The allowance above must accept a real read and still reject a real
    write — a guard that waves everything through is worse than none."""
    assert _is_select(ast.parse("select(X).where(Y).order_by(Z)", mode="eval").body)
    assert _is_select(ast.parse("select(X)", mode="eval").body)
    assert not _is_select(ast.parse("delete(X).where(Y)", mode="eval").body)
    assert not _is_select(ast.parse("text('UPDATE t SET x=1')", mode="eval").body)
    assert not _is_select(None)
