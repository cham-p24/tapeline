"""Two billing paths that only fire when something goes slightly wrong.

Both are invisible on the happy path, which is why both shipped broken.

1. A TRIAL WHOSE FIRST CHARGE IS DECLINED. Stripe retries for days, so this is
   an ordinary outcome, not an edge case. It broke two things:
     * the dunning email called it "your last payment" and "the renewal
       charge" — to someone who had never paid Tapeline anything and never
       renewed anything. Since the card-required trial is the normal route to
       paid, that was the MOST LIKELY reader of this email;
     * the receipt and the founder revenue alert hung off
       `prior_status == "trialing"`, but the real sequence is
       trialing -> past_due -> active, so by the time it reached active the
       prior status was past_due and neither fired. The sale completed; the
       customer got nothing and the founder was never told.

2. DUNNING RECOVERY on an established subscription is also past_due -> active,
   and must NOT be mistaken for a new sale. A naive fix ("prior_status in
   (trialing, past_due)") would send a fresh receipt and ping the founder about
   new revenue every time a long-standing subscriber's card recovered.

UPDATE 2026-09-14: the "ever been active" latch that replaced prior_status was
itself premature — Stripe sets a converting trial active about an hour before
it charges, so "You're in" went out ahead of declined first charges. The
receipt and alert now wait for the first invoice with money on it; see
test_paid_welcome_waits_for_money.py.
"""

from datetime import UTC, datetime, timedelta

from app.services.email import render_payment_failed_email


class TestDeclinedChargeWording:
    """The email must never assert a renewal or a previous payment it cannot
    know happened."""

    def test_first_charge_says_first_charge_not_renewal(self):
        html = render_payment_failed_email("Sam", tier="premium", first_charge=True)
        assert "first charge" in html.lower()
        # The three false claims, in the exact shapes the old copy used.
        assert "renewal charge" not in html.lower()
        assert "last payment" not in html.lower()
        assert "your renewal" not in html.lower()

    def test_first_charge_names_the_trial_so_the_email_makes_sense(self):
        html = render_payment_failed_email("Sam", tier="premium", first_charge=True)
        assert "trial ended" in html.lower()

    def test_renewal_wording_is_true_for_both_and_asserts_neither(self):
        """The default must be safe for a caller that cannot tell which it is:
        accurate for a renewal AND for a first charge."""
        html = render_payment_failed_email("Sam", tier="pro")
        assert "didn't go through" in html
        # Never claims a prior payment or a renewal it has not established.
        assert "last payment" not in html.lower()
        assert "renewal charge" not in html.lower()

    def test_default_is_the_safe_branch(self):
        """A caller that forgets the flag must under-claim, not over-claim."""
        assert render_payment_failed_email("Sam", tier="pro") == \
            render_payment_failed_email("Sam", tier="pro", first_charge=False)

    def test_final_attempt_urgency_survives_both_branches(self):
        for first in (True, False):
            html = render_payment_failed_email(
                "Sam", tier="pro", attempt_count=4,
                final_attempt=True, first_charge=first,
            )
            assert "last automatic retry" in html.lower()

    def test_preheader_matches_the_branch(self):
        first = render_payment_failed_email("Sam", tier="pro", first_charge=True)
        renew = render_payment_failed_email("Sam", tier="pro")
        assert "first charge was declined" in first
        assert "first charge was declined" not in renew


class TestFirstChargeDetection:
    """The caller's signal. Stripe cannot tell us directly — a trial converting
    carries billing_reason "subscription_cycle", same as any renewal — but the
    first charge lands ON trial_ends_at by construction."""

    @staticmethod
    def _is_first_charge(trial_ends_at, now):
        # Mirrors routers/webhooks.py. Kept here so the boundary is asserted
        # even though the production copy is inline.
        if trial_ends_at is None:
            return False
        ends = trial_ends_at
        if ends.tzinfo is None:
            ends = ends.replace(tzinfo=UTC)
        return timedelta(0) <= (now - ends) <= timedelta(days=14)

    def test_a_trial_that_just_ended_is_a_first_charge(self):
        now = datetime(2026, 9, 12, tzinfo=UTC)
        assert self._is_first_charge(now - timedelta(hours=2), now) is True
        assert self._is_first_charge(now - timedelta(days=6), now) is True

    def test_a_long_standing_subscriber_is_not(self):
        now = datetime(2026, 9, 12, tzinfo=UTC)
        assert self._is_first_charge(now - timedelta(days=90), now) is False

    def test_a_trial_still_running_is_not(self):
        """A future trial_ends_at means no charge has been attempted yet."""
        now = datetime(2026, 9, 12, tzinfo=UTC)
        assert self._is_first_charge(now + timedelta(days=3), now) is False

    def test_an_account_that_never_trialled_is_not(self):
        assert self._is_first_charge(None, datetime(2026, 9, 12, tzinfo=UTC)) is False

    def test_a_naive_timestamp_does_not_raise(self):
        """Postgres can return one; a TypeError inside a webhook handler would
        500 the delivery and lose the email entirely."""
        now = datetime(2026, 9, 12, tzinfo=UTC)
        assert self._is_first_charge(datetime(2026, 9, 10), now) is True


class TestPaidStartLatch:
    """The welcome + founder alert answer "is this the subscription's first
    invoice with money on it", not "has its status ever been active".

    `active` is not money: at the end of a card-required trial Stripe sets the
    subscription active about an hour BEFORE it charges, and on 2026-09-12 and
    2026-09-14 that sent "You're in" ahead of a first charge that was declined.
    The trigger is now `invoice.payment_succeeded`. The behavioural cases run
    through the real signed webhook in test_paid_welcome_waits_for_money.py;
    this class keeps the decision table readable.
    """

    @staticmethod
    def _fires(amount_paid, billing_reason, latch_already_claimed, earlier_paid_invoice):
        # The shape of the production condition in _welcome_on_first_paid_invoice.
        if amount_paid <= 0 or latch_already_claimed:
            return False
        if billing_reason == "subscription_create":
            return True
        return earlier_paid_invoice is False

    def test_a_direct_paid_checkout_fires(self):
        assert self._fires(999, "subscription_create", False, None) is True

    def test_trial_converting_via_a_declined_first_attempt_fires_at_the_charge(self):
        """trialing -> active -> payment_failed -> past_due -> paid. The old
        prior_status check missed the eventual sale; the "ever active" latch
        announced it before the decline. Nothing until the money, then once."""
        assert self._fires(0, "subscription_cycle", False, False) is False  # the decline
        assert self._fires(1999, "subscription_cycle", False, False) is True

    def test_dunning_recovery_on_an_established_sub_does_not_fire(self):
        """past_due -> paid on an old subscription: the latch was claimed long
        ago, or Stripe's history shows it paid before. This is the error a naive
        fix introduces: a fresh receipt and a founder NEW-SALE alert every time
        an old subscriber's card recovers. (The founder still gets a separate
        payment-received note, which never calls itself a new subscription —
        test_founder_told_of_paid_started_subscription.py.)"""
        assert self._fires(1999, "subscription_cycle", True, None) is False
        assert self._fires(1999, "subscription_cycle", False, True) is False

    def test_a_redelivery_does_not_double_send(self):
        assert self._fires(1999, "subscription_cycle", True, False) is False

    def test_a_zero_dollar_invoice_never_fires_it(self):
        """A trial start or a 100%-off referral month."""
        assert self._fires(0, "subscription_create", False, None) is False

    def test_unknown_history_does_not_fire(self):
        assert self._fires(1999, "subscription_cycle", False, None) is False


class TestProductionActuallyUsesTheLatch:
    """The two classes above model the LOGIC; they re-implement it, so they
    would keep passing if production drifted. These check the real module.

    Source, comments and docstrings stripped — this file and webhooks.py both
    discuss `prior_status` at length in prose, and prose must not be able to
    satisfy or break the assertion.
    """

    @staticmethod
    def _code() -> str:
        import ast
        import inspect
        import textwrap

        from app.routers import webhooks

        tree = ast.parse(textwrap.dedent(inspect.getsource(webhooks)))
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if (
                isinstance(
                    node,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module),
                )
                and body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
        return ast.unparse(tree)

    def test_prior_status_is_gone_from_executable_code(self):
        """It was the bug: a trial converting through a declined first attempt
        arrives at active with prior_status == "past_due"."""
        assert "prior_status" not in self._code()

    def test_the_paid_start_latch_is_present(self):
        code = self._code()
        assert "paid_start:" in code
        assert "_welcome_on_first_paid_invoice" in code

    def test_the_welcome_and_alert_are_sent_only_from_the_paid_invoice_path(self):
        """A call-site check on the AST, not a text search: the welcome email
        and the founder alert may be called from `_welcome_on_first_paid_invoice`
        and nowhere else, and that helper may be awaited only from the
        invoice.payment_succeeded branch. Putting either back on a subscription
        status re-creates the "You're in" before the charge."""
        import ast
        import inspect
        import textwrap

        from app.routers import webhooks

        tree = ast.parse(textwrap.dedent(inspect.getsource(webhooks)))

        def _callee(node: ast.Call) -> str | None:
            return getattr(node.func, "id", getattr(node.func, "attr", None))

        funcs = {
            n.name: n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        helper = funcs["_welcome_on_first_paid_invoice"]
        for name in ("render_subscription_started_email", "notify_founder_new_subscription"):
            everywhere = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _callee(n) == name]
            in_helper = [n for n in ast.walk(helper) if isinstance(n, ast.Call) and _callee(n) == name]
            assert in_helper, f"{name} is no longer sent from the paid-invoice helper"
            assert len(everywhere) == len(in_helper), (
                f"{name} is called outside _welcome_on_first_paid_invoice"
            )

        # The helper is called exactly once in the whole module, and that call
        # sits in the BODY of the `evt_type == "invoice.payment_succeeded"`
        # branch. Decided from each call's own ancestors: the nearest enclosing
        # `evt_type` test must be that one, with the call in its body. (The
        # earlier version only looked inside branches compared against a
        # string constant, so a call dropped into the subscription branch —
        # `evt_type in (<tuple>)` — was never seen and the check still passed.)
        parents: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node

        def _is_evt_type_test(node: ast.AST) -> bool:
            return (
                isinstance(node, ast.If)
                and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "evt_type"
            )

        def _enclosing_branch(call: ast.Call) -> str:
            child: ast.AST = call
            node = parents.get(call)
            while node is not None:
                if _is_evt_type_test(node):
                    test = node.test
                    assert isinstance(test, ast.Compare)
                    in_body = any(child is stmt for stmt in node.body)
                    if (
                        in_body
                        and len(test.ops) == 1
                        and isinstance(test.ops[0], ast.Eq)
                        and isinstance(test.comparators[0], ast.Constant)
                    ):
                        return str(test.comparators[0].value)
                    return f"not in the body of a single-event branch ({ast.unparse(test)})"
                child, node = node, parents.get(node)
            return "outside any evt_type branch"

        calls = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and _callee(n) == "_welcome_on_first_paid_invoice"
        ]
        assert [_enclosing_branch(c) for c in calls] == ["invoice.payment_succeeded"], [
            _enclosing_branch(c) for c in calls
        ]

    def test_the_failed_payment_email_is_told_which_kind_of_charge(self):
        """Matched on the AST keyword argument, not on the text "first_charge=".

        The text version was VACUOUS: it passed with the keyword deleted,
        because a logger format string elsewhere in the module contains
        "first_charge=%s". Watched it stay green against the mutation, which is
        the only reason this is an AST walk.
        """
        import ast
        import inspect
        import textwrap

        from app.routers import webhooks

        tree = ast.parse(textwrap.dedent(inspect.getsource(webhooks)))
        passed = [
            kw.arg
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", getattr(node.func, "attr", None))
            == "render_payment_failed_email"
            for kw in node.keywords
        ]
        assert passed, "render_payment_failed_email is never called"
        assert "first_charge" in passed, (
            "the caller does not tell the email whether this is a first charge, "
            "so a trialist gets the renewal wording"
        )
