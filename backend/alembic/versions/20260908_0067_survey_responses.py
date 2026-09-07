"""survey_responses — the September 2026 customer survey.

Deliberately UNLINKED to any user row. The survey URL is the same for everyone,
and the email tells respondents the link does not identify them; a per-recipient
token would make that sentence false. `contact_email` is separate, optional, and
supplied by the respondent as a visible act if they want a reply or a call.

Nothing is lost by not segmenting: at ~6 expected responses from 23 reachable
people, no two groups are separable below a 75-point gap (see
docs/growth/SURVEY_METHODOLOGY.md). The instrument is a recruiting device, not a
measurement one.

No FK anywhere, same posture as cap_events and scan_logs: a survey response must
never block a user row from being deleted. Erasure is not needed here either —
there is no identifier to erase unless the respondent typed one in, and
services/account_purge.py has nothing to join on by construction.

Revision ID: 0067_survey_responses
Revises: 0066_factor_stamps
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0067_survey_responses"
down_revision = "0066_factor_stamps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "survey_responses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "survey_key", sa.String(length=40), nullable=False,
            server_default="2026_09",
        ),
        sa.Column("status", sa.String(length=60), nullable=True),
        sa.Column("trigger_story", sa.Text(), nullable=True),
        sa.Column("friction", sa.Text(), nullable=True),
        sa.Column(
            "wants_call", sa.Boolean(), nullable=False, server_default=sa.false(),
        ),
        sa.Column("contact_email", sa.String(length=320), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index(
        "ix_survey_responses_survey_key", "survey_responses", ["survey_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_survey_responses_survey_key", table_name="survey_responses")
    op.drop_table("survey_responses")
