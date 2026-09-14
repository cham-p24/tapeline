"""Data freshness: what copy and API fields are allowed to SAY about data age.

ONE place, mirrored by frontend/lib/freshness.ts and pinned to it by
tests/test_freshness_constants_agree.py.

Why this module exists (integrity wave, founder-approved 14 Sep 2026). The
site, the emails, the MCP server text and the `data_delayed_minutes` API field
all said the data was live, real-time, not delayed, or refreshed in under 60
seconds. Measured during the US session on Mon 14 Sep 2026:

* The price vendor plan is 15-minute delayed. At 13:59 UTC the AAPL snapshot's
  `updated` was 899 s old and its newest minute bar 961 s old, with no
  lastTrade / lastQuote keys (not entitled). A second session measured 15.0
  minutes for SPY, AAPL, NVDA and MSFT at 13:41 UTC. `/api/scanner` returned
  `data_delayed_minutes: 0` for every tier.
* A worker pass rewrites every covered stock and ETF. Passes landed 69.7 to
  74.3 s apart in steady state, 98 s across a deploy and ~6 minutes across a
  restart: the tick's run time plus a 60-second sleep.
* Only ~38 of ~11,546 scores changed in 2.5 minutes while ~4,161 prices did.
  Score inputs are daily readings.

Copy that states data age must read these constants. Never write "real-time",
"live data", "not delayed", "sub-60s" or "every minute" about the data;
scripts/lint-copy-compliance.mjs blocks it on the scanned surfaces.

A leaf module with no imports, so services and routers can both use it.
"""
from __future__ import annotations

# Vendor price delay (Massive / Polygon Stocks Starter plan), in minutes.
PRICE_DELAY_MINUTES = 15

PRICE_DELAY_PHRASE = f"delayed about {PRICE_DELAY_MINUTES} minutes"
PRICE_DELAY_NOTE = f"Prices {PRICE_DELAY_PHRASE}"

# Held across every steady-state pass measured on 14 Sep 2026.
PASS_INTERVAL_SECONDS_LOW = 70
PASS_INTERVAL_SECONDS_HIGH = 80
PASS_CADENCE_PHRASE = (
    f"about every {PASS_INTERVAL_SECONDS_LOW}-{PASS_INTERVAL_SECONDS_HIGH} seconds"
)

PRICE_FRESHNESS_SENTENCE = (
    f"Prices are {PRICE_DELAY_PHRASE}. Tapeline re-reads them for every covered "
    f"stock and ETF {PASS_CADENCE_PHRASE} during US market hours, and less often "
    "around deploys."
)

SCORE_CADENCE_SENTENCE = (
    "Scores are recalculated on each pass, but most of their inputs (daily price "
    "bars, fundamentals, SEC Form 4 filings and the macro regime) are daily "
    "readings, so a score usually changes about once a day."
)


def data_delayed_minutes(tier_delay_minutes: int | None) -> int:
    """The true delay behind a price a caller sees, in minutes.

    The vendor's delay applies to every tier; a tier-imposed delay (0 today,
    see services/tier.py) is added on top of it, never instead of it.
    """
    return PRICE_DELAY_MINUTES + int(tier_delay_minutes or 0)
