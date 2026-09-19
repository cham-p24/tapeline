"""Listings stored as stocks that are not a company's common shares.

WHY THIS EXISTS. Discovery admits whatever the vendor types as common stock
(CS/ADRC), and the sheet ingest inserts any symbol it is handed as `equity`.
Through both doors came notes, preferreds, warrants, rights and SPAC units, and
each one was scored on the six factors and given a signal label like any stock.
Measured read-only on production 2026-09-18: 120 of the 6,012 equity-bucket rows
are one of these, 118 of them scored. GREEL, a Greenidge 8.50% senior note due
2026, read STRONG SETUP at 70.4. BHFAO, a Brighthouse 6.75% non-cumulative
preferred, was listed fourth on the public record on 2026-06-23 (disclosed by
#873). GREEL scored above the day's record cutoff on 2026-09-14 and tied it
on 2026-09-17, and only the liquidity floor kept it out.

WHY THE SCORE DOES NOT MEAN WHAT IT SAYS ON THESE. Trend, relative strength and
momentum read a price series. A note's price is anchored to par and moves with
its issuer's credit and with rates; a preferred's to its coupon; a warrant's is
a geared option on the common; a SPAC unit's to the trust. A high reading on
any of them is a statement about that structure, not about a company's shares,
and ranking it beside operating companies, unlabelled, is the misleading part.
Same argument as services/leverage.py, one step further on.

WHAT THE FLAG DOES. `Ticker.is_non_common` holds these out of the scorecard
freeze, the default scanner, its CSV export and the MCP `daily_picks` tool,
exactly as `is_leveraged` does for geared funds (#761). It is not a ban: the
scanner's `include_non_common=true` returns them, per-ticker pages and search
are unchanged, and every scanner row ships the fact so a client can label
instead of hide. It is a FACT about the security, in the register of
`asset_class`; nothing built on it may call these risky or advise against them.

SCOPE, and what is deliberately NOT flagged:
  * Only the equity bucket. Exchange-traded notes are stored as ETFs, sit in
    the universe by design (polygon_feed's type map admits ETN), and the geared
    ones are already out as leveraged funds. They are out of scope here.
  * CIG and PBR.A. The shared predicate names them because they are preferred
    ADRs, not the issuer's common, which is what Form 4 attribution needs to
    know. For THIS question they are equity: a Brazilian preferred share is the
    company's main traded equity line (PBR.A traded about $143M a day on
    2026-09-18) and carries the company's price risk, not a coupon.

DETECTION IS BY NAME AND SYMBOL GRAMMAR, because no stored field states the
security type (the vendor's CS/ADRC type is what let them in). The predicate
lives in services/security_type.py, shared with Form 4 attribution, and is
written to under-claim: a preferred whose name and symbol both look like the
common's is treated as common unless it is listed there by symbol. Its
precision on a hand-labelled sample was 38/38, and none of the 77 labelled
common stocks was flagged. Its recall was 79%, so some non-common listings
still pass as stocks. A false positive would hide a real stock from the ranked
view, which is the error this is built to avoid.

WHO KEEPS THE COLUMN RIGHT. The fifth-letter rules need the whole universe: a
Nasdaq symbol's fifth letter U, R or W marks a unit, right or warrant only when
its four-letter base is listed too (PTACU, BTSGU, CORZW). So:
  * Discovery sees every symbol and derives the flag exactly on insert and on
    reclassification.
  * A writer that sets `name` or `asset_class` without seeing the universe (the
    sheet upserts, the asset-class repair, the sector backfill's name repair)
    uses
    `non_common_on_write()`: it raises the flag when the row's own name or
    symbol says so and clears it when the row leaves the equity bucket, but
    never clears it otherwise, because it cannot tell whether a universe rule
    set it. The sheet upsert runs every five minutes, so a writer that
    recomputed blind would unflag PTACU on every pass.
  * `reconcile_non_common_flags()` settles every row against the universe on
    boot, after discovery and after the sector backfill.
  * The daily freeze re-derives the flag for its own candidates against the
    whole universe, so the permanent record never depends on the column being
    current.
"""
from __future__ import annotations

import logging
from collections.abc import Set as AbstractSet

from sqlalchemy import select, update

from app.services.asset_class import bucket_of
from app.services.security_type import is_non_common_listing

logger = logging.getLogger(__name__)

#: Preferred ADRs that are their company's main traded equity line. See the
#: module docstring: the shared predicate names them for Form 4 attribution,
#: and this flag deliberately does not.
EQUITY_LIKE_PREFERRED_ADRS: frozenset[str] = frozenset({"CIG", "PBR.A"})


def is_non_common_equity(
    symbol: str | None,
    name: str | None,
    asset_class: str | None,
    universe: AbstractSet[str] = frozenset(),
) -> bool:
    """True when an equity-bucket row is a note, preferred, warrant, right or unit.

    `universe` is every stored symbol. Without it the fifth-letter rules
    cannot fire, so the answer under-claims; `reconcile_non_common_flags()`
    closes that gap.
    """
    if bucket_of(asset_class) != "equity":
        return False
    if (symbol or "").strip().upper() in EQUITY_LIKE_PREFERRED_ADRS:
        return False
    return is_non_common_listing(symbol, name, universe)


def non_common_on_write(
    symbol: str | None,
    name: str | None,
    asset_class: str | None,
    stored: bool | None,
) -> bool:
    """The flag to store after a writer that cannot see the universe.

    Raises it when the row's own name or symbol says so, clears it when the
    row is no longer in the equity bucket, and otherwise keeps `stored`, which
    a universe rule may have set. See the module docstring.
    """
    if bucket_of(asset_class) != "equity":
        return False
    if (symbol or "").strip().upper() in EQUITY_LIKE_PREFERRED_ADRS:
        return False
    return bool(stored) or is_non_common_listing(symbol, name)


async def reconcile_non_common_flags() -> int:
    """Recompute `is_non_common` for every row against the whole universe.

    Writes only the rows whose stored value is wrong, and holds `updated_at`
    still: the flag is reference data, not a refresh of the row's live
    numbers (see the comment on Ticker.updated_at). Returns the number of rows
    changed. Never raises: a failure is logged and the column is left as it
    was, to be settled on the next run.
    """
    from app.db import session_scope
    from app.models import Ticker

    try:
        async with session_scope() as session:
            result = await session.execute(
                select(Ticker.symbol, Ticker.name, Ticker.asset_class, Ticker.is_non_common)
            )
            rows = result.all()
            universe = frozenset(r[0] for r in rows)
            to_true: list[str] = []
            to_false: list[str] = []
            for symbol, name, asset_class, stored in rows:
                want = is_non_common_equity(symbol, name, asset_class, universe)
                if want and not stored:
                    to_true.append(symbol)
                elif stored and not want:
                    to_false.append(symbol)
            for value, symbols in ((True, to_true), (False, to_false)):
                if symbols:
                    await session.execute(
                        update(Ticker)
                        .where(Ticker.symbol.in_(symbols))
                        .values(is_non_common=value, updated_at=Ticker.updated_at)
                    )
        changed = len(to_true) + len(to_false)
        if changed:
            logger.info(
                "non_common.reconciled flagged=%d unflagged=%d", len(to_true), len(to_false),
            )
        return changed
    except Exception:
        logger.exception("non_common.reconcile_failed")
        return 0


__all__ = [
    "EQUITY_LIKE_PREFERRED_ADRS",
    "is_non_common_equity",
    "non_common_on_write",
    "reconcile_non_common_flags",
]
