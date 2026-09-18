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
* A worker pass rewrites every covered stock and ETF. Before #843 passes landed
  69.7 to 74.3 s apart (the tick plus a 60-second sleep). Since #843 (merged
  14 Sep 18:34 UTC) the loop is fixed-rate: 22 gaps measured 59.99 to 60.02 s
  during the US session. A deploy or restart still leaves a gap of minutes.
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

# Held across every steady-state pass measured after #843 (14 Sep 2026).
PASS_INTERVAL_SECONDS = 60
PASS_CADENCE_PHRASE = f"about every {PASS_INTERVAL_SECONDS} seconds"

PRICE_FRESHNESS_SENTENCE = (
    f"Prices are {PRICE_DELAY_PHRASE}. Tapeline re-reads them for every covered "
    f"stock and ETF {PASS_CADENCE_PHRASE} during US market hours, and less often "
    "around deploys."
)

SCORE_CADENCE_SENTENCE = (
    "Scores are recalculated on each pass, but their inputs (daily price bars and "
    "the macro regime, plus fundamentals and SEC Form 4 filings, which update less "
    "often) change at most about once a day, so a score usually changes about once a day."
)

# Crypto is daily for BOTH price and score, and its tail is much older than
# that. The refresh is one detached job per worker process, latched at 24h and
# set before dispatch, so a failed run is not retried for a day; a pair that
# drops out of the 120 the job fetches keeps its last close until it comes back.
# The price itself is a completed UTC-day close, so a day is added on top.
#
# Measured in production 2026-09-17 22:45 UTC, across 118 crypto rows: 51
# carried a price written more than 25 hours earlier, 39 more than two days
# earlier, and 23 more than four days earlier. The oldest was written
# 2026-09-13 13:53 UTC, four days and nine hours before the reading. "Updated
# once a day" was true of the job, and false of the data on 43% of pairs.
CRYPTO_CADENCE_SENTENCE = (
    "Crypto prices and scores come from daily closes, refreshed about once a "
    "day; a pair the daily pass misses keeps its last close for several days."
)

# The same fact where only a parenthetical fits.
CRYPTO_CADENCE_PHRASE = "daily closes, sometimes several days old"


def data_delayed_minutes(tier_delay_minutes: int | None) -> int:
    """The true delay behind a price a caller sees, in minutes.

    The vendor's delay applies to every tier; a tier-imposed delay (0 today,
    see services/tier.py) is added on top of it, never instead of it.
    """
    return PRICE_DELAY_MINUTES + int(tier_delay_minutes or 0)
