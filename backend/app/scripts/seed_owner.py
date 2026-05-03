"""
Seed the owner/admin account.

Run once after migrations:
    python -m app.scripts.seed_owner

Idempotent — safe to re-run.
Reads OWNER_EMAIL and OWNER_PASSWORD from env, or prompts.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

from sqlalchemy import select

from app.db import session_scope
from app.models import User
from app.services.session import hash_password


DEFAULT_EMAIL = "owner@tapeline.io"
DEFAULT_PASSWORD = "TapelineOwner!2026"  # Replace after first login


async def main() -> None:
    email = os.getenv("OWNER_EMAIL", DEFAULT_EMAIL).lower().strip()
    password = os.getenv("OWNER_PASSWORD", DEFAULT_PASSWORD)
    name = os.getenv("OWNER_NAME", "Owner")

    async with session_scope() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            # Upgrade existing user to admin + premium + reset password
            user.is_admin = True
            user.tier = "premium"
            user.password_hash = hash_password(password)
            print(f"  [updated] existing user -> admin + premium: {email}")
        else:
            user = User(
                id=f"u_owner_{uuid.uuid4().hex[:12]}",
                email=email,
                name=name,
                tier="premium",
                is_admin=True,
                password_hash=hash_password(password),
            )
            session.add(user)
            print(f"  [created] owner account: {email}")

    print()
    print("=" * 60)
    print("OWNER LOGIN")
    print("=" * 60)
    print(f"  URL:      http://localhost:3000/signin")
    print(f"  Email:    {email}")
    print(f"  Password: {password}")
    print("=" * 60)
    print("  Tier:     premium (full access to every feature)")
    print(f"  Admin:    yes (can access /app/admin)")
    print("=" * 60)
    print()
    print("CHANGE THE PASSWORD after first login:")
    print("  Set OWNER_PASSWORD env var and re-run this script.")


if __name__ == "__main__":
    # Windows + psycopg async needs SelectorEventLoop (ProactorEventLoop is the
    # default on Windows but psycopg explicitly errors on it). No-op on Linux/macOS.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
