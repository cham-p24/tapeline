"""newsletter subscribers table + signup UTM attribution columns

Two related additions:

1) `newsletter_subscribers` — the lead-magnet table. People who aren't
   ready to sign up for a trial can give their email to get the Daily
   Top 10 picks newsletter. Lower-commitment funnel step that gets us
   into their inbox; the welcome + first daily digest are the
   conversion vehicle.

       email                — primary lookup; unique
       status               — pending | confirmed | unsubscribed
       source               — where the signup happened: 'homepage' /
                              'scorecard' / 'pricing' / 'api'. Plus the
                              utm_* triplet for paid-channel attribution.
       unsubscribe_token    — random 32-char hex; one-click unsubscribe
                              link uses this so we never expose internal ids.
       confirmed_at         — set when the user clicks the welcome email
                              CTA (or auto-confirmed on signup if we're
                              not gating with double opt-in yet — we're
                              not currently gating).
       unsubscribed_at      — set on unsubscribe click.
       last_sent_at         — bumped by the daily worker; used to skip
                              users we've already sent today's digest to
                              if the worker restarts mid-run.

2) `users.signup_utm_*` — five columns capturing the UTM triplet the user
   arrived with at signup time. Distinct from `referral_source` (which is
   self-reported during onboarding and has poor data quality): UTM is the
   ground-truth marketing attribution. Frontend captures `?utm_source=...`
   on landing, stores in localStorage (30-day TTL), and forwards on POST
   /api/auth/signup. Backend writes once at signup, never updates.

Revision ID: 0025_newsletter_and_signup_utm
Revises: 0024_email_verification
Create Date: 2026-05-20 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0025_newsletter_and_signup_utm"
down_revision: str | None = "0024_email_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---------- newsletter_subscribers ----------
    op.create_table(
        "newsletter_subscribers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(200), nullable=False, unique=True, index=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="confirmed",
        ),
        sa.Column("source", sa.String(40), nullable=True),
        sa.Column("utm_source", sa.String(80), nullable=True),
        sa.Column("utm_medium", sa.String(80), nullable=True),
        sa.Column("utm_campaign", sa.String(120), nullable=True),
        sa.Column("utm_term", sa.String(120), nullable=True),
        sa.Column("utm_content", sa.String(120), nullable=True),
        sa.Column("unsubscribe_token", sa.String(64), nullable=False, unique=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ---------- users.signup_utm_* ----------
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("signup_utm_source", sa.String(80), nullable=True))
        batch.add_column(sa.Column("signup_utm_medium", sa.String(80), nullable=True))
        batch.add_column(sa.Column("signup_utm_campaign", sa.String(120), nullable=True))
        batch.add_column(sa.Column("signup_utm_term", sa.String(120), nullable=True))
        batch.add_column(sa.Column("signup_utm_content", sa.String(120), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("signup_utm_content")
        batch.drop_column("signup_utm_term")
        batch.drop_column("signup_utm_campaign")
        batch.drop_column("signup_utm_medium")
        batch.drop_column("signup_utm_source")

    op.drop_table("newsletter_subscribers")
