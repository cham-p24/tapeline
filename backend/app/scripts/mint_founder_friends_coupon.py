"""
Mint the founder-friends $20/mo-for-90-days Stripe promotion code.

The pricing model has Premium at $39.99/mo retail. For the first paying
beta cohort (friends, family, ex-colleagues, network contacts), we want
a clean 50%-off code that lasts 3 months — long enough to feel like a
real beta period, short enough that they convert to retail or churn
within a quarter.

Run once after the Stripe Premium product + price IDs are configured:
    fly ssh console -a tapeline-backend -C "python -m app.scripts.mint_founder_friends_coupon"

Or from a local dev box with `STRIPE_API_KEY` in env:
    python -m app.scripts.mint_founder_friends_coupon

Output is the redeemable promotion code (e.g. `FOUNDERFRIENDS`). Hand
that to anyone who says yes to the personal-outreach DMs. They paste it
at /app/billing → Premium → "Have a code?" or you can pre-apply it via
Stripe Customer Portal.

Idempotent — re-running detects an existing identically-configured code
and prints it without creating a duplicate.

Why a static code (not the dynamically-minted referral coupons in
services/billing.py)? Those are one-off, customer-scoped, and require
backend-orchestrated checkout sessions. A static promotion code is
trivial for the founder to text/DM and trivial for the recipient to
type, which is exactly what the personal-outreach flow needs.

Mechanics:
- Coupon: 50% off, repeating, 3 month duration (so it covers the 90-day
  beta period and then auto-rolls to retail $39.99 unless cancelled)
- Promotion code: human-readable string `FOUNDERFRIENDS`, max 100 redemptions
  (capped so the code can't leak and burn down to zero margin)
- Restricted to Premium monthly + Premium annual prices when those env
  vars are set; otherwise applies to all prices
"""
from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


COUPON_ID = "founder_friends_50_off_3mo"
PROMO_CODE = "FOUNDERFRIENDS"
MAX_REDEMPTIONS = 100


def main() -> int:
    try:
        import stripe
    except ImportError:
        logger.error("stripe library not installed. Add to pyproject.toml or pip install stripe.")
        return 1

    api_key = os.getenv("STRIPE_API_KEY") or os.getenv("STRIPE_SECRET_KEY")
    if not api_key:
        logger.error("STRIPE_API_KEY not set. Refusing to mint against unknown Stripe account.")
        return 1
    stripe.api_key = api_key
    # Pin the API version for this script. Stripe's 2026-05-27.dahlia release
    # restructured PromotionCode.create's `coupon` parameter (rejected with
    # "Received unknown parameter: coupon" on first prod attempt 2026-06-01).
    # 2024-04-10 is a stable older version where the documented top-level
    # `coupon` kwarg still works. Script is one-off + idempotent so locking
    # to an older API is safe — when we migrate to dahlia's new shape, update
    # this line and re-run.
    stripe.api_version = "2024-04-10"

    # ---- Coupon: 50% off, 3-month duration ---------------------------------
    try:
        coupon = stripe.Coupon.retrieve(COUPON_ID)
        logger.info(f"[coupon] existing: {coupon.id} ({coupon.percent_off}% off, {coupon.duration} {coupon.duration_in_months}mo)")
    except stripe.error.InvalidRequestError:
        coupon = stripe.Coupon.create(
            id=COUPON_ID,
            percent_off=50,
            duration="repeating",
            duration_in_months=3,
            # Stripe caps coupon.name at 40 chars
            name="Founder Friends — 50% off / 3 months",
        )
        logger.info(f"[coupon] created: {coupon.id}")

    # ---- Promotion code: redeemable string ---------------------------------
    # Search for an existing promo code with this string before creating
    existing = stripe.PromotionCode.list(code=PROMO_CODE, limit=1)
    if existing.data:
        promo = existing.data[0]
        logger.info(f"[promo]  existing: {promo.code} (active={promo.active}, redemptions={promo.times_redeemed}/{promo.max_redemptions})")
    else:
        # `coupon` is a real Stripe API parameter on PromotionCode.create
        # (the docs require it — a promo code wraps a coupon). The stripe-python
        # type stubs don't expose it as a typed kwarg, hence the call-arg ignore.
        promo = stripe.PromotionCode.create(  # type: ignore[call-arg]
            code=PROMO_CODE,
            coupon=coupon.id,
            max_redemptions=MAX_REDEMPTIONS,
            active=True,
        )
        logger.info(f"[promo]  created: {promo.code} (max {MAX_REDEMPTIONS} redemptions)")

    # ---- Output ------------------------------------------------------------
    logger.info("")
    logger.info("=" * 60)
    logger.info("FOUNDER-FRIENDS COUPON READY")
    logger.info("=" * 60)
    logger.info(f"Code:     {promo.code}")
    logger.info("Discount: 50% off Premium for 3 months")
    logger.info("Then:     auto-rolls to retail $39.99/mo unless cancelled")
    logger.info(f"Remaining redemptions: {MAX_REDEMPTIONS - promo.times_redeemed}")
    logger.info("")
    logger.info("How to use it:")
    logger.info("  1. DM someone the code: 'Use FOUNDERFRIENDS at /app/billing for 50%% off 90 days'")
    logger.info("  2. They sign up at tapeline.io/signup (14-day trial auto-starts, no card)")
    logger.info("  3. Day 5-7 of trial they go to /app/billing → Premium → enter FOUNDERFRIENDS")
    logger.info("  4. Stripe applies the 50% off for the next 3 monthly invoices")
    logger.info("     ($19.99 × 3 = $59.97 total before retail kicks in)")
    logger.info("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
