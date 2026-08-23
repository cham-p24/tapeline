"""Make alert_events.rule_id nullable so non-rule alert emails can be counted.

Watchlist smart-alert emails (`services/alerts.evaluate_watchlist_alerts`) are a
second, independent email path: they never called `_fire`, never called
`_email_cap_reached`, and never created an `AlertEvent` row at all. So those
sends were neither capped nor counted, and they did not consume the rule-driven
budget either — the `email_alerts_per_day` cap (Pro = 10) simply did not apply
to them. The cap's own docstring records that it exists because "a noisy rule
set could bill zero and email without limit"; that fix never reached this path.

The cap is metered off delivered `AlertEvent` rows, deliberately so there is "no
separate counter to drift out of sync". To put watchlist sends on that same
meter they need an AlertEvent row — but `rule_id` was NOT NULL with an FK to
`alert_rules.id`, and a watchlist alert has no rule.

Making it nullable is the smallest change that keeps one meter:
  * `_email_cap_reached` and `/api/usage` count by user + channel + delivered,
    so they pick the new rows up with no change.
  * The only query that filters on rule_id is the rule-deletion cleanup in
    routers/alerts.py, and a NULL row correctly does not match it — a watchlist
    event is not tied to any rule and must survive that rule's deletion.

Revision ID kept short: alembic_version.version_num is VARCHAR(32).

Revision ID: 0055_alert_event_rule_null
Revises: 0054_signup_fbclid
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0055_alert_event_rule_null"
down_revision: str | None = "0054_signup_fbclid"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("alert_events") as batch:
        batch.alter_column(
            "rule_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    # Non-rule rows cannot satisfy a NOT NULL constraint; drop them first so the
    # downgrade is actually runnable rather than failing halfway.
    op.execute(sa.text("DELETE FROM alert_events WHERE rule_id IS NULL"))
    with op.batch_alter_table("alert_events") as batch:
        batch.alter_column(
            "rule_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
