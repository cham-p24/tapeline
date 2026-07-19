"""security: session revocation epoch + TOTP replay guard

Backs three verified auth findings that all needed schema:

1) `users.session_epoch` — session JWTs were unrevocable. `verify_session_token`
   checked only the signature, `exp` and `purpose`, with no database lookup, so
   a captured cookie stayed valid for its full 30 days. Neither signout (which
   only called `delete_cookie`, i.e. clears the *browser's* copy) nor a
   password reset could evict it — the security-receipt email told the user
   their password had changed while the attacker's session kept working.
   The epoch is embedded in the token at issue and compared on verify; bumping
   the column invalidates every token minted before the bump.

   Defaults to 0, and a token with NO epoch claim is treated as 0, so this
   migration does NOT sign existing users out on deploy. Revocation applies
   from the first bump onward.

2) `users.totp_last_step` — TOTP codes were replayable. `verify_totp` used
   `valid_window=1` and recorded nothing, so one 6-digit code stayed valid for
   ~90s and could be submitted repeatedly, including after the legitimate owner
   had already signed in with it. Storing the highest accepted time-step and
   refusing anything <= it restores the one-time property.

   Nullable: NULL means "this account has never completed a TOTP challenge",
   which is different from step 0 and must not reject a first login.

Recovery-code hashing (the fourth finding) needs no schema change — bcrypt
hashes are 60 chars and `mfa_recovery_codes.code_hash` is already String(64).

Revision ID: 0040_session_revocation
Revises: 0039_gclid_and_activation
Create Date: 2026-07-19 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0040_session_revocation"
down_revision: str | None = "0039_gclid_and_activation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "session_epoch",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch.add_column(
            sa.Column("totp_last_step", sa.BigInteger(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("totp_last_step")
        batch.drop_column("session_epoch")
