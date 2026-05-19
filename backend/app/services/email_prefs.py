"""Per-user email preferences bitmask.

The User.email_prefs integer column holds a bitmask of which
non-transactional email categories the user wants to receive. The bits
are defined here as module-level constants and combined via OR.

Transactional emails (welcome, payment-failed, referral) are not gated
by this field — they're account-state notifications, not marketing, and
the user can't opt out of them.

Usage:

    from app.services.email_prefs import EmailPref, wants

    if not wants(user, EmailPref.RE_ENGAGEMENT):
        continue   # skip this user this round

The `categories_for_ui()` helper returns the per-bit metadata that the
frontend settings page uses to render the toggles and explanatory copy.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntFlag
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import User


class EmailPref(IntFlag):
    """Bits of users.email_prefs. Default = all five set (= 31).

    `WEEKLY_NEWSLETTER` was added in migration 0023 — the bit is set by
    default on new signups, but real delivery is gated by *both* this bit
    AND `User.marketing_opt_in` (the explicit GDPR consent flag captured
    on the onboarding step). So a user who skips onboarding sees the
    toggle on at /app/settings/email, but won't receive the newsletter
    until they tick the marketing-opt-in checkbox there or re-run
    onboarding. The decoupling is intentional — `email_prefs` is "do you
    want this category, day-to-day"; `marketing_opt_in` is "do I have
    explicit consent on file".
    """

    TRIAL_DRIP = 1
    RE_ENGAGEMENT = 2
    DAILY_DIGEST = 4
    ALERT_EMAILS = 8
    WEEKLY_NEWSLETTER = 16


DEFAULT_PREFS: int = int(
    EmailPref.TRIAL_DRIP
    | EmailPref.RE_ENGAGEMENT
    | EmailPref.DAILY_DIGEST
    | EmailPref.ALERT_EMAILS
    | EmailPref.WEEKLY_NEWSLETTER
)


def wants(user: User, category: EmailPref) -> bool:
    """True if the user opts in to this email category.

    Defensive default: if `user.email_prefs` is unset (e.g. an in-memory
    User created in tests without the DB-side default firing), assume
    opted in. Better to send a relevant email than to silently suppress
    because of a column-default oddity.
    """
    prefs = getattr(user, "email_prefs", None)
    if prefs is None:
        return True
    return bool(int(prefs) & int(category))


@dataclass(frozen=True)
class PrefCategory:
    key: str         # frontend toggle key (also used in the API contract)
    bit: int         # bit value
    label: str       # display label on the settings UI
    description: str # one-line explanation shown next to the toggle


def categories_for_ui() -> list[PrefCategory]:
    """Authoritative list of toggleable email categories.

    Drives both the frontend settings page render AND the GET/POST
    /api/user/email-prefs API contract — keeping these in one place
    means the UI and API can't drift.
    """
    return [
        PrefCategory(
            key="trial_drip",
            bit=int(EmailPref.TRIAL_DRIP),
            label="Trial reminders",
            description="The six emails sent during your 14-day Premium trial.",
        ),
        PrefCategory(
            key="re_engagement",
            bit=int(EmailPref.RE_ENGAGEMENT),
            label="Come-back note",
            description="One founder-signed nudge if you don't open Tapeline for 14 days. Never sent more than once.",
        ),
        PrefCategory(
            key="daily_digest",
            bit=int(EmailPref.DAILY_DIGEST),
            label="End-of-day watchlist digest",
            description="A summary of your watchlist's score moves after every US market close (Pro+).",
        ),
        PrefCategory(
            key="alert_emails",
            bit=int(EmailPref.ALERT_EMAILS),
            label="Alert emails",
            description="The score / squeeze / regime / news rules you set up on /app/alerts. Disabling this disables ALL email alerts but doesn't touch Telegram or browser push.",
        ),
        PrefCategory(
            key="weekly_newsletter",
            bit=int(EmailPref.WEEKLY_NEWSLETTER),
            label="Weekly market digest",
            description="One email every Monday — top score movers of the week, current market regime, scorecard hit rate, latest headlines. Requires you to have ticked marketing-opt-in at onboarding (or here, when we add the consent toggle).",
        ),
    ]


def prefs_to_dict(prefs_int: int) -> dict[str, bool]:
    """Convert the integer bitmask to a {key: bool} dict for the API
    response. The frontend uses the dict shape directly to render the
    toggles."""
    return {cat.key: bool(prefs_int & cat.bit) for cat in categories_for_ui()}


def dict_to_prefs(d: dict[str, bool]) -> int:
    """Convert a {key: bool} dict (e.g. POST body) back to the integer
    bitmask. Unknown keys are silently dropped — the categories list is
    the source of truth, not the client.
    """
    out = 0
    for cat in categories_for_ui():
        if d.get(cat.key, False):
            out |= cat.bit
    return out
