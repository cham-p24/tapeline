"""When we email a card-required trialist before their first charge.

ONE number, shared by the thing that SENDS the notice and the copy that
PROMISES it.

`run_trial_precharge_drip` (services/email.py) runs once a day and selects
trials whose `trial_ends_at` falls inside
(now + PRECHARGE_NOTICE_DAYS - 1 days, now + PRECHARGE_NOTICE_DAYS + 1 days).
On a daily cadence the first run that catches a trial is 7 to 8 days before
the charge; the extra day on the near side only matters if a run is missed.
Stripe's `customer.subscription.trial_will_end` (about 3 days out) is a
backstop that stands down once this notice has been sent.

Why 7: Visa requires a reminder at least 7 days before a trial converts, and
Mastercard requires one between 3 and 7 days before. 7 is the only number
that satisfies both (see tests/test_precharge_notice_is_seven_days.py).

Why this module exists (integrity fix T-09, founder-approved 2026-09-14):
the sending moved from 3 days to 7, and the copy on /app/start, /signup,
/legal/refund and in two emails kept saying "three days before". Copy that
states the timing must read PRECHARGE_NOTICE_DAYS (or, on the frontend,
lib/trial.ts `PRECHARGE_NOTICE_DAYS`, pinned to this value by
tests/test_precharge_notice_copy_matches_drip.py).

A leaf module with no imports, so services and routers can both use it
without an import cycle.
"""
from __future__ import annotations

PRECHARGE_NOTICE_DAYS = 7

# The drip's selection window, in days from now. Kept beside the constant so
# the window cannot be widened or moved without the copy's number moving too.
PRECHARGE_WINDOW_LOWER_DAYS = PRECHARGE_NOTICE_DAYS - 1
PRECHARGE_WINDOW_UPPER_DAYS = PRECHARGE_NOTICE_DAYS + 1


def precharge_notice_phrase() -> str:
    """The timing as customer-facing copy: "about 7 days before".

    "About" because the daily run sends 7 to 8 days out, not at an exact hour.
    """
    return f"about {PRECHARGE_NOTICE_DAYS} days before"
