"""Stripe billing endpoints."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import Subscription, User
from app.services.auth import current_user_required
from app.services.billing import (
    apply_save_offer_coupon,
    create_checkout_session,
    create_portal_session,
    get_charge_disclosure,
    pause_subscription,
    resume_subscription,
    set_cancel_at_period_end,
    trial_save_offer_eligible,
)
from app.services.email_checkout import verify_checkout_token
from app.services.rate_limit import limit_strict
from app.services.tier import is_on_trial

router = APIRouter()
settings = get_settings()

# Exit-survey reason codes accepted by POST /cancel. Anything else is coerced
# to "other" so a stale frontend can't 422 a user out of cancelling.
_CANCEL_REASONS = frozenset(
    {
        "too_expensive",
        "not_using",
        "missing_feature",
        "found_alternative",
        "trial_only",
        "technical_issues",
        "other",
    }
)


# ── Card-required 14-day trial ──────────────────────────────────────────────
#
# Creating an account is email + password only and lands on FREE, and FREE is
# a working product: the top ten scored rows of any scan on live data, one
# saved screen, a five-symbol watchlist, twelve ticker pages a day. No card is
# asked for at the door. The route wall that used to stand at /app/start was
# removed in #683; `tier.must_add_card` survives it, but it now drives what we
# SAY to an account with no card, not what that account may reach. The limits
# that do the work are the free caps in services/tier, enforced server-side.
#
# STARTING the trial is a separate, deliberate act, and the card is what it
# costs. It is also what the card buys: every matching row instead of the
# first ten, a second saved screen, alerts on every channel, CSV export, the
# 200-symbol watchlist, congressional and insider filings. We open the same
# Stripe Checkout the paid flow uses, in mode=subscription with
# subscription_data.trial_end 14 days out. Stripe charges $0 today, bills the first real amount at
# trial_end, and the subscription is cancellable in one click from the
# customer portal before then. That mechanism (rather than setup-mode + a
# cron + SetupIntent → Subscription) is what keeps dunning, the portal and
# the whole existing webhook path working for trialists.
#
# TRIAL_DAYS is the single source of truth: the endpoint that SHOWS the user
# their first-charge date (GET /trial-offer) and the endpoint that SENDS the
# date to Stripe (POST /checkout) both read it, so the disclosed date cannot
# drift from the billed date.
TRIAL_DAYS = 30

# ── Floor on a NEW trial, and why it is not a preference ────────────────────
#
# We collect a card up front, so the trial ends in a real charge. The only
# thing standing between that charge and a surprised customer is the pre-charge
# warning email (services/email.render_trial_precharge_reminder_email), and that
# email does not run on a timer of ours — it rides on Stripe's
# `customer.subscription.trial_will_end`, which fires about THREE DAYS before
# the trial ends. Its own subject line says "Your trial ends in 3 days."
#
# Two places promise that warning to the customer IN WRITING:
#   * /legal/refund §4 — "we email you three days before that happens"
#   * the trial disclosure on the trial-start screen (/app/start)
#
# So a new trial shorter than the warning window would charge someone without
# the notice we told them they would get. That is the chargeback-and-complaint
# pattern the reminder exists to prevent, and on a financial product it is a
# consumer-law problem rather than a UX one.
#
# Hence: this is an invariant, not a tunable. Shortening the trial below
# MIN_TRIAL_DAYS is only safe if the pre-charge notice is first moved onto a
# mechanism we control (a scheduled send keyed on trial_ends_at) instead of
# Stripe's fixed T-3 event. Raise this floor freely; lower it only with that
# work done, and update the two copy surfaces above in the same change.
MIN_TRIAL_DAYS = 3

if TRIAL_DAYS < MIN_TRIAL_DAYS:  # pragma: no cover - import-time invariant
    raise RuntimeError(
        f"TRIAL_DAYS={TRIAL_DAYS} is below MIN_TRIAL_DAYS={MIN_TRIAL_DAYS}. "
        "A trial this short ends before Stripe's trial_will_end event can warn "
        "the customer, so they would be charged without the notice /legal/refund "
        "promises them in writing. See the comment above MIN_TRIAL_DAYS."
    )

# Why a given account may not start a trial. Machine-readable code → the plain
# sentence we're willing to show. One trial per account, and never as a
# substitute for a purchase someone has already made.
_TRIAL_INELIGIBLE_MESSAGES: dict[str, str] = {
    "lifetime": "Your account already has lifetime access — there's nothing to trial.",
    "already_trialed": "This account has already used its 14-day trial.",
    "has_billing_account": (
        "This account already has a billing history with us, so the trial "
        "doesn't apply. You can subscribe directly at any time."
    ),
    "already_paid_tier": "You're already on a paid plan.",
}


def _trial_ineligible_reason(user: User) -> str | None:
    """None when `user` may start the card-required trial; else a key of
    _TRIAL_INELIGIBLE_MESSAGES.

    One trial per account, forever. The two trial columns answer different
    questions and BOTH are checked:
      • trial_started_at — stamped by the subscription webhook the first time a
        trial actually begins. Null for accounts that never trialled.
      • trial_ends_at    — also set by every LEGACY no-card auto-trial from
        before this change. Those rows have a null trial_started_at, so without
        this second check every pre-existing user would be handed a fresh
        14-day trial on top of the one they already had.

    A user who has ever had a Stripe customer record has been through billing
    (subscriber or churned) and buys directly rather than re-trialling; the
    win-back path deliberately still lets them check out normally, just without
    a free window.
    """
    if user.is_lifetime:
        return "lifetime"
    if user.trial_started_at is not None or user.trial_ends_at is not None:
        return "already_trialed"
    if user.stripe_customer_id is not None:
        return "has_billing_account"
    if user.tier in ("pro", "premium"):
        return "already_paid_tier"
    return None


class CheckoutRequest(BaseModel):
    tier: str = "pro"                     # "pro" or "premium"
    billing_period: str = "monthly"        # "monthly" or "annual"
    # Opt-in: open this checkout as a 14-day trial instead of an immediate
    # purchase. Defaults False so every pre-existing caller (paid upgrade,
    # mid-trial card-add, win-back re-subscribe) behaves exactly as before.
    start_trial: bool = False


@router.post("/checkout", dependencies=[Depends(limit_strict)])
async def create_checkout(
    body: CheckoutRequest,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if body.tier not in ("pro", "premium"):
        raise HTTPException(400, "tier must be 'pro' or 'premium'")
    if body.billing_period not in ("monthly", "annual"):
        raise HTTPException(400, "billing_period must be 'monthly' or 'annual'")
    # Double-billing guard (mirrors the email-checkout guard below): a user
    # whose paid tier is live on Stripe already has a subscription — Checkout
    # always mints a NEW Stripe Customer + subscription, so letting a
    # subscriber through here double-bills them and the webhook can only page
    # the founder to refund it after the money moved. Keyed on paid tier AND
    # linked customer, NOT bare stripe_customer_id: churned users keep their
    # customer id (tier already dropped to "free") and must still be able to
    # check out again — the win-back path below depends on it. Trial users
    # have no stripe_customer_id, so they pass through untouched.
    if user.stripe_customer_id and user.tier in ("pro", "premium"):
        raise HTTPException(
            409,
            # Points at the SELF-SERVE portal, not "support". The portal is
            # already wired end to end (POST /api/billing/portal, with buttons
            # on /app/billing), so telling a paying subscriber to email a
            # human was sending them to a slower path that already existed —
            # and reads as "we cannot do this" rather than "here is where".
            # Whether the portal offers plan switching is a Stripe dashboard
            # setting; this message is correct either way, because cancel and
            # payment-method changes live there too.
            "You already have an active subscription. Manage or switch your "
            "plan from the billing portal on your account page.",
        )

    # Which trial_end (if any) this session carries. Exactly one of the two
    # branches can apply, and both end up as subscription_data.trial_end on the
    # SAME Stripe mechanism:
    #
    #   start_trial=True  → a NEW 14-day trial. Gated on never-trialled; a
    #     second attempt is refused here rather than quietly minting a second
    #     free window. The instant is computed once and returned to the caller
    #     so the confirmation UI states the same date Stripe was given.
    #
    #   start_trial=False → the pre-existing mid-trial card-add: forward the
    #     user's REMAINING trial so adding a card doesn't charge today and
    #     silently forfeit the free days already promised. Unchanged.
    #
    # The MIN_TRIAL_DAYS floor applies to the FIRST branch only. The second one
    # forwards a trial the user is already inside and already knows the end date
    # of; clamping it up to 3 days would silently EXTEND someone's trial past
    # the date we disclosed, which is a different lie. Its short-remainder case
    # is handled where it belongs — services/billing drops trial_end under
    # Stripe's 48h minimum rather than failing the checkout.
    trial_end: datetime | None
    if body.start_trial:
        reason = _trial_ineligible_reason(user)
        if reason is not None:
            raise HTTPException(409, _TRIAL_INELIGIBLE_MESSAGES[reason])
        trial_end = datetime.now(UTC) + timedelta(days=max(TRIAL_DAYS, MIN_TRIAL_DAYS))
    else:
        trial_end = (
            user.trial_ends_at
            if is_on_trial(user.tier, user.trial_ends_at, user.stripe_customer_id)
            else None
        )
        # SQLite (dev/tests) hands back naive datetimes for tz-aware columns;
        # stored values are UTC. Normalise so the instant we echo to the caller
        # is unambiguous. Same idiom as services/tier.is_on_trial.
        if trial_end is not None and trial_end.tzinfo is None:
            trial_end = trial_end.replace(tzinfo=UTC)

    url = await create_checkout_session(
        user_id=user.id,
        user_email=user.email,
        tier=body.tier,
        billing_period=body.billing_period,
        # Params are read by the frontend conversion analytics in /app/billing —
        # keep `checkout=success` + tier + billing_period in sync with
        # app/app/billing/page.tsx. `{CHECKOUT_SESSION_ID}` is a Stripe
        # template token (escaped as {{...}} so the f-string leaves it intact):
        # Stripe substitutes the real cs_… id on redirect, and the client uses
        # it as the GA4/Ads `transaction_id` plus a one-shot dedupe key, so
        # reloading the success URL can no longer re-fire the purchase event.
        # `trial=1` marks a $0-today trial start. app/app/billing/page.tsx:279
        # reads exactly this param (and its comment at line 87 calls it the
        # fallback when storage is blocked) to decide whether to report a
        # `purchase` or a trial conversion. It was never appended here, so a
        # card-gate trial that charges $0 today was reported to GA4/Google Ads
        # as a completed purchase at full plan value — inflating conversion
        # value and training Smart Bidding on revenue that has not happened yet.
        success_url=(
            f"{settings.app_url}/app/billing?checkout=success"
            f"&tier={body.tier}&billing_period={body.billing_period}"
            f"{'&trial=1' if body.start_trial else ''}"
            f"&session_id={{CHECKOUT_SESSION_ID}}"
        ),
        # Stripe's "back" link. Carries the tier + period the user was part-way
        # through so /app/billing can restate the choice and offer ONE resume
        # button instead of dumping them on a generic plan grid. Read by the
        # `checkout=cancelled` handler in app/app/billing/page.tsx — keep the
        # param names in sync with the success_url above.
        cancel_url=f"{settings.app_url}/app/billing?checkout=cancelled&tier={body.tier}&billing_period={body.billing_period}",
        # Pass the user's unspent referral credits; the billing service mints
        # a one-shot 100%-off coupon for that many months when > 0.
        referral_credit_months=user.referral_credit_months or 0,
        # Returning-customer 40%-off offer (day-90 win-back email). Gated
        # server-side on "actually churned" — cancelled AND already dropped to
        # free — so the ?winback=1 link can't be farmed by an active user, and
        # it mirrors exactly who receives the wb90 email. Referral credit, if
        # any, takes precedence inside create_checkout_session.
        winback=(user.tier == "free" and user.canceled_at is not None),
        # One-time 50%-off-3-months for the expired card-less trialist (the
        # cancel-intercept save offer, extended to trial expiry). Gate lives
        # in services/billing.trial_save_offer_eligible; redeemed-at is set by
        # the subscription webhook so an abandoned checkout doesn't burn it.
        trial_save_offer=trial_save_offer_eligible(user),
        # Either a brand-new 14-day trial or the remainder of an in-flight one
        # — see the branch above. Forwarded as subscription_data.trial_end, so
        # Stripe collects the card, charges nothing today, and bills the first
        # real amount on that date. The service drops it when under Stripe's
        # 48h trial_end minimum (only reachable on the mid-trial card-add
        # branch; a fresh trial is always 14 days out).
        trial_end=trial_end,
    )
    # Mark the checkout as in-flight for abandonment recovery. If the user
    # never completes, the hourly worker (run_checkout_abandonment_recovery)
    # emails a one-shot resume nudge ~1-24h later; checkout.session.completed
    # clears checkout_started_at, so a converted user is never nudged. Stripping
    # the "abandon1" token re-arms the nudge for this fresh attempt even if a
    # prior abandoned checkout already consumed it. Stamped only after the
    # session minted successfully (a Stripe error above raises before this).
    user.checkout_started_at = datetime.now(UTC)
    user.checkout_tier = body.tier
    user.checkout_billing_period = body.billing_period
    user.drip_state = ",".join(
        t for t in (user.drip_state or "").split(",") if t and t != "abandon1"
    )
    await session.commit()
    # `trial_end` is echoed back so the caller can restate the first-charge
    # date it is about to send the user to Stripe for, from the exact instant
    # Stripe was given rather than a second local "now + 14 days". Null for a
    # plain purchase. Nothing else about the response shape changed.
    return {
        "url": url,
        "trial_end": trial_end.isoformat() if trial_end else None,
        "trial_days": TRIAL_DAYS if body.start_trial else None,
    }


@router.get("/email-checkout", dependencies=[Depends(limit_strict)])
async def email_checkout(
    # Deliberately tolerant params: mail clients line-wrap and rewrite long
    # URLs, and FastAPI validation failures return raw 422 JSON BEFORE the
    # handler's graceful fallback can run. So no required params, no pattern
    # constraints — bad values are coerced/redirected inside the handler.
    token: str = Query(""),
    tier: str = Query("premium"),
    period: str = Query("monthly"),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """One-click checkout from a conversion email — no login required.

    The trial-drip emails are the only touchpoint that reaches a bounced trial
    user, and their CTA used to land behind the login wall (a password the
    user forgot two weeks ago). This endpoint verifies the signed token from
    the email and 303s straight into Stripe Checkout for that user's account.

    The token grants NO session — it can only open a checkout page bound to
    its own user (worst case for a forwarded email: someone pays FOR the
    user). Every failure path degrades to a marketing page, never an error.

    Deliberately side-effect-free besides the Stripe session: email scanners
    (Outlook SafeLinks, Gmail) prefetch GET links, so this path must NOT stamp
    checkout_started_at / re-arm the abandonment nudge the way POST /checkout
    does — a scanner prefetch would otherwise queue a spurious "finish
    checking out" email at every send.
    """
    fallback = f"{settings.app_url}/pricing?src=email_link"
    # Coerce (not reject) mangled tier/period — the token is what proves
    # identity; a truncated tier param shouldn't cost the conversion.
    if tier not in ("pro", "premium"):
        tier = "premium"
    if period not in ("monthly", "annual"):
        period = "monthly"
    user_id = verify_checkout_token(token)
    if user_id is None:
        # Missing/expired/tampered link — somewhere they can still convert.
        return RedirectResponse(fallback, status_code=303)

    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        return RedirectResponse(fallback, status_code=303)
    if user.stripe_customer_id:
        # Already has billing set up (subscribed after the email went out, or
        # an old link) — the in-app billing page is the right surface; a fresh
        # checkout here could double-subscribe them.
        return RedirectResponse(f"{settings.app_url}/app/billing", status_code=303)

    try:
        url = await create_checkout_session(
            user_id=user.id,
            user_email=user.email,
            tier=tier,
            billing_period=period,
            # PUBLIC success/cancel pages — this flow's whole premise is a
            # user with no session (forgot password), and /app/* sits behind
            # the login-wall middleware. Bouncing a PAYING customer to /signin
            # (success) or dead-ending a hesitant one (cancel) recreates the
            # exact friction this endpoint exists to remove. /checkout/success
            # fires the trial_converted + subscribe analytics events that
            # /app/billing fires for the authed flow.
            # `{CHECKOUT_SESSION_ID}` (escaped {{...}} for the f-string) is
            # substituted by Stripe — same transaction_id + reload-dedupe role
            # as the authed success_url above.
            success_url=f"{settings.app_url}/checkout/success?tier={tier}&billing_period={period}&src=email&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.app_url}/pricing?src=email_checkout_cancelled",
            referral_credit_months=user.referral_credit_months or 0,
            winback=(user.tier == "free" and user.canceled_at is not None),
            # Same trial-expiry save offer as POST /checkout — the T+0
            # "trial ended" email's one-click links land here, so the offer
            # it states must actually be attached to the session it mints.
            trial_save_offer=trial_save_offer_eligible(user),
            # Same mid-trial preservation as POST /checkout — this endpoint
            # IS the "Keep Premium — add a card" email CTA, so it's the path
            # a day-3 trial user most likely arrives through.
            trial_end=user.trial_ends_at
            if is_on_trial(user.tier, user.trial_ends_at, user.stripe_customer_id)
            else None,
            # Shrink the completable window from ~24h to Stripe's 30-min
            # minimum: each email carries TWO tier links, and the double-
            # subscribe guard above only runs at session-CREATE time — a
            # long-lived second tab must not be able to complete a second
            # subscription a day later.
            expires_in_minutes=30,
        )
    except Exception:
        # Stripe hiccup — degrade to the pricing page, never a raw 500 from an
        # email click.
        import logging

        logging.getLogger(__name__).exception(
            "billing.email_checkout_session_failed user=%s", user.id
        )
        return RedirectResponse(fallback, status_code=303)
    return RedirectResponse(url, status_code=303)


@router.post("/portal", dependencies=[Depends(limit_strict)])
async def open_portal(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not user.stripe_customer_id:
        raise HTTPException(400, "No billing account yet — subscribe first")
    url = await create_portal_session(
        customer_id=user.stripe_customer_id,
        return_url=f"{settings.app_url}/app/billing",
    )
    return {"url": url}


# ── Retention: cancel intercept (save offer + pause + one-click cancel; ─────
# ── exit survey is optional, after the cancel — never a gate) ───────────────


class PauseRequest(BaseModel):
    months: int = 1  # 1, 2, or 3


class CancelRequest(BaseModel):
    # Both optional: the one-click cancel posts an empty body (no survey gate),
    # and the optional post-cancel survey posts reason/feedback afterwards.
    # None means "not asked / not answered" — never coerced to "other", so the
    # churn dashboard only ever sees reasons a human actually chose.
    reason: str | None = None
    feedback: str | None = None


def _require_paid(user: User) -> None:
    """Cancel/pause/save only apply to a real Stripe subscription. Trial users
    (no customer id) just let the trial lapse — surface a clear 400 instead."""
    if not user.stripe_customer_id:
        raise HTTPException(400, "No paid subscription to manage yet.")


@router.get("/retention-options")
async def retention_options(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """State the cancel-intercept modal needs to decide what to offer.

    `save_offer_available` gates the one-time 50%-off-3-months card.
    `paused_until` / `canceled_at` let the modal reflect an in-flight pause
    or scheduled cancellation rather than re-offering the same actions.

    `past_due` / `subscription_status` mirror what GET /api/me exposes to the
    global DunningBanner. The billing page already fetches THIS endpoint, so
    piggy-backing the dunning state here lets the page render a failed-renewal
    panel without a second round-trip — and, more importantly, stops the "Next
    charge" tile from cheerfully quoting a renewal price to someone whose card
    just declined.
    """
    past_due = False
    sub_status: str | None = None
    if user.tier != "free":
        sub_row = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.current_period_end.desc())
            .limit(1)
        )
        sub = sub_row.scalar_one_or_none()
        if sub is not None:
            sub_status = sub.status
            past_due = sub.status in ("past_due", "unpaid")
    return {
        "has_subscription": bool(user.stripe_customer_id),
        "tier": user.tier,
        "save_offer_available": user.save_offer_redeemed_at is None,
        "paused_until": user.subscription_paused_until.isoformat()
        if user.subscription_paused_until
        else None,
        "canceled_at": user.canceled_at.isoformat() if user.canceled_at else None,
        "past_due": past_due,
        "subscription_status": sub_status,
    }


@router.get("/charge-disclosure")
async def charge_disclosure() -> dict:
    """What Stripe will actually charge — currency, and whether tax is added.

    Read by the plan cards so the hosted Checkout page can never surprise a
    user with a different currency or an unmentioned line item. Derived from
    the live Stripe Price object plus the session kwargs we send; when the
    Stripe lookup fails `currency` is null and the UI drops the currency
    sentence rather than asserting one. No auth: it describes public list
    pricing, and the pre-signup /pricing cards need it too.
    """
    return await get_charge_disclosure()


@router.get("/trial-offer")
async def trial_offer(
    user: User = Depends(current_user_required),
) -> dict:
    """The facts the trial-start screen has to state BEFORE the card is asked for.

    Every field here is a statement about what Stripe will actually do, derived
    from the same TRIAL_DAYS constant POST /checkout sends, so the date on the
    screen is the date on the subscription. The point of the endpoint is that
    the disclosure cannot be assembled client-side from a second local clock
    and quietly disagree with the charge.

      eligible / ineligible_reason / message
          Whether this account can start a trial, and — when it can't — the
          plain sentence explaining why. Declining is a normal outcome and
          leaves the user somewhere real: an account that says no keeps the
          free tier — top-ten rows on live data, one saved screen, a
          watchlist — and is not sent anywhere.
      card_required
          True, and it is about the TRIAL. There used to be a
          `free_tier_requires_card` beside it, reporting the /app/start wall
          per account; #683 removed the wall, which left the field with one
          answer (no) and a name that invited the opposite reading, so it is
          gone. A card buys the trial, never entry.
      trial_days / first_charge_at
          14, and the exact UTC instant of the FIRST charge if the trial were
          started now. Nothing is charged before it.
      amount_charged_today
          0. Stated as a number so the UI can't drift from it.
      cancel_in_one_click
          True — the subscription is cancellable from the billing page / Stripe
          portal at any point before first_charge_at.
      current_trial_ends_at
          Set once a trial is actually running, read from the subscription's
          own trial_end (written by the webhook). This is the authoritative
          date for in-app "your first charge is on ..." copy.

    No countdowns, no scarcity, nothing time-pressured: a factual date only.
    """
    reason = _trial_ineligible_reason(user)
    ends = user.trial_ends_at
    if ends is not None and ends.tzinfo is None:
        ends = ends.replace(tzinfo=UTC)
    return {
        "eligible": reason is None,
        "ineligible_reason": reason,
        "message": _TRIAL_INELIGIBLE_MESSAGES.get(reason) if reason else None,
        "trial_days": TRIAL_DAYS,
        "first_charge_at": (
            datetime.now(UTC) + timedelta(days=TRIAL_DAYS)
        ).isoformat() if reason is None else None,
        "amount_charged_today": 0,
        "cancel_in_one_click": True,
        "card_required": True,
        "current_trial_ends_at": ends.isoformat() if ends else None,
        "trial_started_at": (
            user.trial_started_at.isoformat() if user.trial_started_at else None
        ),
    }


@router.post("/save-offer", dependencies=[Depends(limit_strict)])
async def accept_save_offer(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Accept the one-time 50%-off-for-3-months retention coupon."""
    _require_paid(user)
    if user.save_offer_redeemed_at is not None:
        raise HTTPException(409, "You've already used this offer.")
    await apply_save_offer_coupon(user.stripe_customer_id)
    now = datetime.now(UTC)
    user.save_offer_redeemed_at = now
    # They're staying — wipe any in-flight cancellation + winback bookkeeping.
    user.canceled_at = None
    user.winback_state = ""
    await session.commit()

    # Transactional confirmation — fire-and-forget so a Resend hiccup never
    # 500s the save-offer accept. No List-Unsubscribe header: it's account
    # state (a billing change the user just made), not marketing.
    if user.email:
        try:
            from app.services.email import render_save_offer_accepted_email, send_email

            html = render_save_offer_accepted_email(
                user.name or "trader",
                tier=user.tier,
            )
            await send_email(
                user.email,
                "Your Tapeline discount is applied — 50% off for 3 months",
                html,
                persona="billing",
            )
        except Exception:  # email must never block the save-offer accept
            import logging

            logging.getLogger(__name__).exception(
                "billing.save_offer_email_failed user=%s", user.id
            )

    return {
        "ok": True,
        "message": "Done — your next 3 months are 50% off. Same plan, half the price.",
    }


def _pause_blocked_until(user: User) -> datetime | None:
    """The instant an in-flight pause resumes, or None if none is running.

    The 1-3 month cap in `pause_subscription` is a PER-CALL bound, not a
    lifetime one, and nothing else bounded the feature. `pause_collection` is
    set with `behavior="void"`, which voids every invoice raised during the
    pause while Stripe deliberately keeps the subscription `status="active"` —
    so the webhook's active branch leaves `user.tier` at pro/premium the whole
    time. Re-calling on day 89 simply pushed `resumes_at` 90 days further out.

    Repeat every ~89 days and you have unlimited Premium — full universe,
    congress + insider feeds, unlimited alerts, the 1,000/day API quota — with
    zero further charges. `limit_strict` is irrelevant at a 3-month cadence, and
    the account still counts as an active subscription in the admin dashboard,
    so the missing revenue never shows up anywhere.

    `retention_options` already returns `paused_until`, but only so the modal
    can render differently. That is presentation; this is enforcement.
    """
    until = user.subscription_paused_until
    if until is None:
        return None
    # Rows written before the column was tz-aware may be naive.
    if until.tzinfo is None:
        until = until.replace(tzinfo=UTC)
    return until if until > datetime.now(UTC) else None


@router.post("/pause", dependencies=[Depends(limit_strict)])
async def pause(
    body: PauseRequest,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Pause billing for 1-3 months instead of cancelling."""
    _require_paid(user)
    blocked_until = _pause_blocked_until(user)
    if blocked_until is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Your billing is already paused until "
                f"{blocked_until:%B} {blocked_until.day}, {blocked_until.year}. "
                "Resume first if you want to change it."
            ),
        )
    resumes_at = await pause_subscription(user.stripe_customer_id, body.months)
    user.subscription_paused_until = resumes_at
    user.canceled_at = None
    user.winback_state = ""
    await session.commit()
    return {"ok": True, "resumes_at": resumes_at.isoformat()}


@router.post("/resume", dependencies=[Depends(limit_strict)])
async def resume(
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Resume a paused subscription immediately."""
    _require_paid(user)
    await resume_subscription(user.stripe_customer_id)
    user.subscription_paused_until = None
    await session.commit()
    return {"ok": True}


@router.post("/cancel", dependencies=[Depends(limit_strict)])
async def cancel(
    body: CancelRequest,
    user: User = Depends(current_user_required),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Schedule cancellation at period end; the exit survey is optional and after.

    First call (no cancellation in flight): schedules the Stripe cancellation
    (cancel_at_period_end — the customer keeps their tier until the paid
    period ends), stamps canceled_at (drives the 30/60/90-day winback drip),
    re-arms winback, and sends the confirmation email. The one-click cancel
    path posts an empty body — reason/feedback are only stored if provided.

    Follow-up call (canceled_at already set): the OPTIONAL post-cancel exit
    survey. Records reason/feedback only — no Stripe round-trip (a survey
    submit must never fail on a Stripe hiccup), no second email, and the
    canceled_at winback clock is left untouched. This also makes a
    double-click on the cancel button harmless.
    """
    _require_paid(user)
    already_scheduled = user.canceled_at is not None
    period_end = None
    if not already_scheduled:
        period_end = await set_cancel_at_period_end(user.stripe_customer_id)
        user.canceled_at = datetime.now(UTC)
        user.winback_state = ""  # fresh cancellation → eligible for winback again
    if body.reason is not None:
        user.cancellation_reason = body.reason if body.reason in _CANCEL_REASONS else "other"
    feedback = (body.feedback or "").strip()
    if feedback:
        user.cancellation_feedback = feedback[:1000]
    await session.commit()

    # Transactional confirmation — fire-and-forget so a Resend hiccup never
    # 500s the cancel. No List-Unsubscribe header: it's account state, not
    # marketing. First call only — the optional survey follow-up must not
    # trigger a second "set to cancel" email.
    if user.email and not already_scheduled:
        try:
            from app.services.email import render_subscription_canceled_email, send_email

            html = render_subscription_canceled_email(
                user.name or "trader",
                tier=user.tier,
                period_end_iso=period_end.isoformat() if period_end else None,
            )
            await send_email(
                user.email,
                "Your Tapeline plan is set to cancel",
                html,
                persona="billing",
            )
        except Exception:  # email must never block the cancel
            import logging

            logging.getLogger(__name__).exception(
                "billing.cancel_email_failed user=%s", user.id
            )

    return {
        "ok": True,
        "period_end": period_end.isoformat() if period_end else None,
        # True on the survey follow-up / a double-submit — the cancellation
        # was already in flight before this request.
        "already_scheduled": already_scheduled,
    }
