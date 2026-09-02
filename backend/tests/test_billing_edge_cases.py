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
    """`is_paid_start` must answer "has this subscription EVER been active",
    not "what was its status a moment ago"."""

    @staticmethod
    def _fires(status, latch_already_claimed):
        # The shape of the production condition.
        return status == "active" and not latch_already_claimed

    def test_trial_converting_cleanly_fires(self):
        assert self._fires("active", False) is True

    def test_trial_converting_via_a_declined_first_attempt_still_fires(self):
        """trialing -> past_due -> active. The old prior_status check missed
        this entirely: the sale completed and nobody was told."""
        # past_due did not claim the latch, because it is not active.
        assert self._fires("past_due", False) is False
        # …so when the retry succeeds, the latch is still free and it fires.
        assert self._fires("active", False) is True

    def test_dunning_recovery_on_an_established_sub_does_not_fire(self):
        """Also past_due -> active, but the latch was claimed long ago. This is
        the error a naive fix introduces: a fresh receipt and a founder revenue
        ping every time an old subscriber's card recovers."""
        assert self._fires("active", True) is False

    def test_a_redelivery_does_not_double_send(self):
        assert self._fires("active", True) is False

    def test_a_trial_start_never_fires_it(self):
        assert self._fires("trialing", False) is False


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
        assert "is_paid_start" in code

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
