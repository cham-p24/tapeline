"""Marketing-consent writes, with provenance attached by construction.

WHY THIS MODULE EXISTS
----------------------
`users.marketing_opt_in` used to be a bare boolean written from three separate
surfaces. It recorded the answer but never the evidence: no timestamp, no
record of which screen the user was looking at.

Tapeline sends from Melbourne, so the governing regime is the **Australian
Spam Act 2003**, not the US CAN-SPAM opt-out model that most email advice is
written against. The difference that matters here: under the Spam Act the
**onus of proving consent sits with the sender**. If ACMA asks when a
particular recipient consented, `marketing_opt_in = True` is not an answer.

So consent is not a boolean assignment any more. It is a three-column write,
and this module is the only place that performs it — which is what stops a
future call site from setting the flag and forgetting the evidence.

WITHDRAWAL IS NOT THE MIRROR OF GRANT
-------------------------------------
`clear_marketing_consent()` deliberately keeps `marketing_opt_in_at` and
`marketing_opt_in_source` intact while flipping the flag to False. The record
of a past consent is not falsified by its later withdrawal, and being able to
show "consented here, withdrew there" is strictly better evidence than a row
scrubbed back to NULL.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.models import User

#: Every surface allowed to record consent. Adding one means adding it here,
#: which is the point: an unrecognised source should be a code review question,
#: not a silent string in the database.
ConsentSource = Literal[
    "signup_form",          # the marketing checkbox on /signup
    "onboarding",           # the onboarding submit on first run
    "settings",             # /app/settings/email
    "newsletter_capture",   # the public footer / landing capture box
    "backfill_unverified",  # migration 0060 — timestamp reconstructed, surface unknown
]

VALID_SOURCES: frozenset[str] = frozenset(ConsentSource.__args__)  # type: ignore[attr-defined]


def set_marketing_consent(
    user: User,
    *,
    granted: bool,
    source: str,
    at: datetime | None = None,
) -> None:
    """Record a marketing-consent decision together with its provenance.

    `granted=False` routes to `clear_marketing_consent`, so a single call site
    can pass a checkbox value straight through without branching.

    Raises ValueError on an unrecognised source — a typo must not become an
    unauditable row.
    """
    if source not in VALID_SOURCES:
        raise ValueError(
            f"Unknown consent source {source!r}. Add it to ConsentSource if it "
            f"is a real surface; known sources: {sorted(VALID_SOURCES)}"
        )

    if not granted:
        clear_marketing_consent(user)
        return

    user.marketing_opt_in = True
    user.marketing_opt_in_at = at or datetime.now(UTC)
    user.marketing_opt_in_source = source


def clear_marketing_consent(user: User) -> None:
    """Withdraw consent, preserving the record that it was once given.

    The timestamp and source are intentionally NOT cleared — see the module
    docstring. A withdrawal does not make the earlier grant untrue, and keeping
    both halves is better evidence than erasing one.
    """
    user.marketing_opt_in = False


def consent_is_provable(user: User) -> bool:
    """True when this row could actually answer 'prove they consented'.

    A row backfilled by migration 0060 returns False: its timestamp was
    reconstructed from `created_at` and its surface is unknown, which is
    exactly the situation that needs a re-permission ask rather than a
    confident send.
    """
    return bool(
        user.marketing_opt_in
        and user.marketing_opt_in_at is not None
        and user.marketing_opt_in_source not in (None, "backfill_unverified")
    )
