"""Retiring tickers that have stopped trading.

Nothing used to do this. The universe refresh (signal_publisher._refresh_universe)
reconciled the vendor's active-listings walk into the tickers table but never
looked at what the walk had STOPPED returning, and its docstring claimed a
delisted ticker "just stops receiving snapshot updates". Measured read-only on
2026-09-19, that was false: a dead symbol kept a price (day_close equal to
previous_close), a daily score, a row in the daily score archive and a
rank. GREE (Greenidge, renamed VIP on 24 Jul 2026) read 75.8 STRONG SETUP;
HLX (merged into HOS, last traded 1 Sep) 65.3; CYCN (now KRSA since
9 Sep) 60.8 beside a -85.5% "daily move"; TOI (now STLN since 4 Aug) 66.0;
BBBY (now NXH since 17 Aug) 28.1.

A price heuristic cannot find these: day_close == previous_close flags 556 of
6,012 equities that day, most of them thinly traded names that simply closed
flat. The vendor's own list of active listings is the evidence, so the rule is:

    A stored equity/etf row is RETIRED (`Ticker.delisted_at` stamped) when a
    COMPLETE discovery walk, whose active set is plausibly the whole market,
    does not list its symbol under ANY instrument type.

and every guard below exists because a wrong retirement hides a live stock
from every surface at once:

* COMPLETE only. `polygon_feed.discover_active_us_tickers` used to return a
  partial list silently when a page failed. A symbol missing from a partial
  list proves nothing. (A plain list, which is what a test double hands over,
  counts as incomplete.)
* ANY type. Discovery keeps only CS/ADRC/ETF/ETV/ETS/ETN rows, but a stored row
  the vendor types PFD or UNIT is still trading; the full active set decides.
* PLAUSIBLY WHOLE. The vendor listed 13,148 active US tickers on 2026-08-27. A
  "complete" walk that saw fewer than MIN_PLAUSIBLE_ACTIVE is a short answer,
  not a market that lost a quarter of its listings overnight.
* CAPPED. If one run would newly retire more than `max_new_retirements()`, it
  retires NOTHING and logs at ERROR with a sample. A vendor glitch (a type
  missing from the answer, a page silently dropped) must never retire the
  universe; a real backlog that trips the cap is read from the log and the cap
  raised by hand, the same contract as polygon_feed.DISCOVERY_MAX_TICKERS.
* Equity and ETF rows only. Crypto (X: pairs) is priced by another feed and is
  not on this list at all; neither are the continuous-futures rows.
* VENDOR SPELLING only. Absence from the vendor's list means something only
  for a symbol spelled the way the vendor spells it. On 2026-09-19 production
  held 13 equity/etf rows that are not: BRK-A and BRK-B (the vendor writes
  BRK.A / BRK.B, which are separate, priced rows), FFH.TO (a Toronto listing)
  and ten preferreds written BAC.PRL, NEE.PRT ... (the vendor writes BACpL).
  All are still trading, and none can ever appear on the list under that
  spelling, so retiring them would publish "No longer trading" about Berkshire
  Hathaway. `is_vendor_spelling` keeps them out; what to do with a row the
  vendor cannot price under its stored spelling is services/coverage.py's
  question, not this one.

A stamped symbol that reappears on ANY walk, complete or not, is un-retired:
presence is positive evidence, absence is not.

Retiring KEEPS the row. Watchlists still hold it, and the public record's
entries for it (TOI was on the record 1-5 June 2026) are immutable and still
render on /scorecard. What stops is everything that treats it as a live
listing: see ticker_freshness.listed_clause for the one predicate.
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime

#: Stored asset classes this rule may retire. Everything else (crypto,
#: future_commodity, anything new) is priced or listed elsewhere, so the stocks
#: reference list saying nothing about it is not evidence of anything.
RETIRABLE_CLASSES: frozenset[str] = frozenset({"equity", "etf"})

#: Below this many active symbols, a walk that claims to be complete is treated
#: as a short answer and retires nothing. The vendor listed 13,148 active US
#: tickers on 2026-08-27; 10,000 tolerates ordinary drift in that number while
#: refusing an answer missing a quarter of the market.
MIN_PLAUSIBLE_ACTIVE = 10_000

#: The per-run cap on NEW retirements: the larger of an absolute floor and a
#: fraction of the stored equity+etf rows (11,828 on 2026-09-19, so 592).
#:
#: Sizing. Ordinary US delistings (mergers, SPAC liquidations, renames) run to
#: tens a week, and the walk runs weekly and on every worker boot, so a normal
#: run retires a handful. The FIRST run carries the whole backlog: rows the
#: vendor never listed (sheet and legacy rows: TOI, PXD, LTHM, DCP ...) plus
#: every delisting since the walk was widened on 2026-08-28, estimated at a few
#: hundred. The failure the cap exists for is far larger: one dropped page is
#: 1,000 symbols (~8.5% of the stored rows) and a missing instrument type is
#: thousands (5,816 stored ETFs). 5% sits between the two.
MAX_NEW_RETIREMENT_FRACTION = 0.05
MAX_NEW_RETIREMENTS_FLOOR = 400

#: How the vendor spells a US stock or ETF symbol: a letter, up to five more
#: letters or digits, and optionally a one-letter share class after a dot
#: (BRK.B). Anything else (BRK-B, FFH.TO, BAC.PRL, CL=F) is a spelling the
#: vendor's list never contains, so its absence there is not evidence.
_VENDOR_SPELLING_RE = re.compile(r"^[A-Z][A-Z0-9]{0,5}(\.[A-Z])?$")


def is_vendor_spelling(symbol: str) -> bool:
    """True when the vendor's active list could contain `symbol` as written."""
    return bool(_VENDOR_SPELLING_RE.match(symbol.upper()))


#: How many symbols a log line names.
LOG_SAMPLE = 25


def max_new_retirements(stored_retirable: int) -> int:
    """The most rows one run may newly retire, given the stored equity+etf count."""
    return max(
        MAX_NEW_RETIREMENTS_FLOOR,
        math.ceil(stored_retirable * MAX_NEW_RETIREMENT_FRACTION),
    )


@dataclass
class DelistingPlan:
    """What one discovery walk says to do. Empty lists mean "change nothing"."""

    retire: list[str] = field(default_factory=list)
    restore: list[str] = field(default_factory=list)
    #: Why retirement was skipped this run (None when it was evaluated).
    skipped: str | None = None
    #: How many rows the walk WOULD have retired, even when skipped by the cap.
    candidates: int = 0
    cap: int = 0
    #: The first LOG_SAMPLE candidates, named in the log line either way.
    sample: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StoredListing:
    asset_class: str | None
    delisted_at: datetime | None


def plan_delistings(
    stored: Mapping[str, StoredListing],
    *,
    active_symbols: Iterable[str],
    discovered_symbols: Iterable[str],
    complete: bool,
) -> DelistingPlan:
    """Decide which stored rows to retire and which to un-retire.

    `active_symbols` is every symbol the vendor listed as active, of any type;
    `discovered_symbols` is the type-filtered rows (a subset in a real walk,
    and the only thing a plain-list test double carries). Both count as
    "listed" for un-retiring; only a complete, plausible walk may retire.
    """
    active = {s.upper() for s in active_symbols}
    listed = active | {s.upper() for s in discovered_symbols}
    plan = DelistingPlan()

    plan.restore = sorted(
        sym for sym, row in stored.items()
        if row.delisted_at is not None and sym.upper() in listed
    )

    if not complete:
        plan.skipped = "walk_incomplete"
        return plan
    if len(active) < MIN_PLAUSIBLE_ACTIVE:
        plan.skipped = "active_set_implausible"
        return plan

    retirable = {
        sym: row for sym, row in stored.items()
        if row.asset_class in RETIRABLE_CLASSES
        and not sym.upper().startswith("X:")
        and is_vendor_spelling(sym)
    }
    candidates = sorted(
        sym for sym, row in retirable.items()
        if row.delisted_at is None and sym.upper() not in active
    )
    plan.candidates = len(candidates)
    plan.sample = candidates[:LOG_SAMPLE]
    plan.cap = max_new_retirements(len(retirable))
    if len(candidates) > plan.cap:
        plan.skipped = "safety_cap"
        return plan
    plan.retire = candidates
    return plan


def retired_message(symbol: str, delisted_at: datetime) -> str:
    """The 404 detail for a retired symbol; the frontend shows it verbatim."""
    day = f"{delisted_at.day} {delisted_at:%B %Y}"
    return (
        f"No longer trading: {symbol} was not in our data vendor's list of "
        f"active US listings on {day}, so Tapeline no longer ranks it."
    )


#: The prefix every retired_message starts with; the frontend keys on it.
RETIRED_PREFIX = "No longer trading:"
