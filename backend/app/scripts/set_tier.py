"""
Manually set a user's tier. The launch-day support tool.

Use cases:
- A beta user emails "I had Pro on the old version, can you grant it?"
- Comping a journalist or a launch-week supporter to Premium
- Granting lifetime to a Founder's Lifetime purchase that bypassed Stripe
- Demoting a refunded user back to free

Usage:
    python -m app.scripts.set_tier <email> <tier>
    python -m app.scripts.set_tier alice@example.com pro
    python -m app.scripts.set_tier bob@example.com premium --lifetime
    python -m app.scripts.set_tier spam@example.com free

Or remotely against the running Fly machine (no local checkout needed):
    fly ssh console -a tapeline-backend -C "python -m app.scripts.set_tier alice@example.com pro"

Always idempotent. Prints the before/after state so you have a record.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.db import session_scope
from app.models import User
from app.services.tier import Tier


async def main() -> int:
    parser = argparse.ArgumentParser(description="Set a user's tier (admin tool)")
    parser.add_argument("email", help="The user's email address")
    parser.add_argument(
        "tier",
        choices=[t.value for t in Tier],
        help="Target tier: free | pro | premium",
    )
    parser.add_argument(
        "--lifetime",
        action="store_true",
        help="Mark the user as Founder's Lifetime — they keep access permanently "
        "even if Stripe webhooks later try to downgrade them.",
    )
    parser.add_argument(
        "--clear-trial",
        action="store_true",
        help="Also clear trial_ends_at (use when promoting a paying user so the "
        "trial countdown banner stops showing).",
    )
    args = parser.parse_args()

    email = args.email.lower().strip()

    async with session_scope() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"ERROR: no user found with email {email}", file=sys.stderr)
            return 1

        before = {
            "tier": user.tier,
            "is_lifetime": getattr(user, "is_lifetime", False),
            "trial_ends_at": user.trial_ends_at.isoformat() if user.trial_ends_at else None,
        }

        user.tier = args.tier
        if args.lifetime:
            if hasattr(user, "is_lifetime"):
                user.is_lifetime = True
            else:
                print("WARN: is_lifetime column not present on this build — skipping", file=sys.stderr)
        if args.clear_trial:
            user.trial_ends_at = None

        await session.flush()

    after = {
        "tier": args.tier,
        "is_lifetime": True if args.lifetime else before["is_lifetime"],
        "trial_ends_at": None if args.clear_trial else before["trial_ends_at"],
    }
    print(f"set_tier user={email}")
    print(f"  before: {before}")
    print(f"  after:  {after}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
