"""Cross-sectional percentiles — where one ticker sits inside its peer group.

WHY THIS EXISTS
---------------
A number helps a reader decide only when it is LOCATABLE. "Trend 74" is a fact
about a ticker, locatable against nothing. "Trend 74 — 91st percentile of
Health Care (n=763)" is a decision aid: the same line carries the reading, the
comparison and the audit trail, so a reader can check the claim instead of
taking it on faith. This module produces the second half of that sentence for
the composite score and each of the six sub-factors.

WHAT IT REFUSES TO DO
---------------------
Every number here arrives with its own denominator, and a comparison that
cannot be made honestly is refused rather than approximated:

  * A peer with no value for a factor is not a peer FOR THAT FACTOR. Only rows
    carrying a non-NULL value count toward n — which is exactly what SQL's
    ``COUNT(expr)`` does, so each of the seven fields gets its own denominator
    out of the same pass.
  * Below ``MIN_PEERS`` covered peers the percentile is ``None`` with
    ``reason="insufficient_peers"``. See MIN_PEERS for the justification.
  * A ticker with no value of its own is ``None`` with ``reason="no_value"`` —
    there is nothing to locate.
  * "Uncategorized" is not a peer group. It means "we do not know this
    ticker's sector" and ~944 tickers share it; NULL, "Unknown" and "N/A" mean
    the same thing. Those tickers fall back to the whole covered universe and
    SAY SO — in ``basis="universe"`` and in the peer-group label the caller
    prints.

No value is ever synthesised, and 0 is never a stand-in for unknown: an
unrankable field returns ``percentile=None`` plus the reason, never a zero.

PORTABILITY
-----------
One statement, no window functions. SQLite (dev + CI) ships neither
``percentile_cont`` nor a dependable ``percent_rank``, so the rank is expressed
as plain conditional aggregates — how many peers are strictly below, and how
many are comparable at all. That is SQL-92 and runs identically on SQLite and
Postgres. It is also ONE pass over the peer group for all seven fields rather
than seven queries, which matters because this runs on every ticker page view
(see the cost note in ``peer_percentiles``).

DEFINITION (stated once, so the printed number is checkable)
------------------------------------------------------------
    percentile = round( 100 * (peers strictly below) / (covered peers) )

The ticker itself sits inside its own peer group, so it counts toward n. A
ticker holding the single highest value among 763 covered peers therefore
prints 762/763 → 100th. Ties never inflate a rank, because the comparison is
strictly ``<``: ten tickers sharing one value all land on the same percentile.
"""
from __future__ import annotations

import math
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Ticker

# ---------------------------------------------------------------------------
# Minimum covered peers before a percentile may be published.
#
# 30 is chosen on RESOLUTION, not on tradition. A percentile computed as a
# count over n peers can only move in steps of 100/n points, so at n=30 one
# peer is worth ~3.3 points — the printed integer is honest to roughly ±3,
# tight enough that "91st percentile" does not overstate what we know. At n=10
# a single peer swings the number by 10 points; at n=5, by 20. "80th
# percentile" computed off five rows claims a precision the data cannot
# support, and a percentile with a tiny denominator is worse than no percentile
# at all. (30 is also the conventional small-sample floor, so it needs no
# special defence to a reader who asks where the cutoff came from.)
#
# Consequence, INTENDED rather than a bug: sub_fundamentals and sub_smart_money
# sit at ~15% universe coverage, and our fundamentals vendor has no coverage
# for most ETFs and funds, so whole peer groups legitimately return None for
# those two factors. The caller then renders "not enough covered peers to rank"
# — a true statement about our data — instead of a manufactured number computed
# over a handful of rows.
# ---------------------------------------------------------------------------
MIN_PEERS = 30

# The seven ranked fields: public key -> Ticker column name. "score" first (the
# composite), then the six sub-factors in the same order as the `breakdown`
# block in routers/ticker.py, so a caller can zip the two.
FIELDS: tuple[tuple[str, str], ...] = (
    ("score", "score"),
    ("trend", "sub_trend"),
    ("rs", "sub_rs"),
    ("fundamentals", "sub_fundamentals"),
    ("smart_money", "sub_smart_money"),
    ("macro", "sub_macro"),
    ("momentum", "sub_momentum"),
)

# Sector strings that mean "we do not know the sector" rather than naming a
# peer group. Matched case-insensitively on the trimmed value. These are the
# sentinels the ingestion path actually produces — see services/sector.py
# (canonical_sector routes every unmapped string to "Uncategorized") plus the
# legacy "Unknown" / "N/A" rows that predate it.
_NO_SECTOR_SENTINELS = frozenset(
    {"", "uncategorized", "unknown", "n/a", "na", "none", "null"}
)

# Label used when a ticker has no usable sector and is compared against
# everything we cover. Worded to read correctly inside the sentence the page
# prints: "…91st percentile of all covered tickers (n=6,545)".
UNIVERSE_LABEL = "all covered tickers"

# `reason` values. A None percentile ALWAYS carries one of these, so the page
# can say which of the two honest refusals applied instead of rendering a
# silent blank.
REASON_NO_VALUE = "no_value"                       # we hold no value for this ticker
REASON_INSUFFICIENT_PEERS = "insufficient_peers"   # fewer than MIN_PEERS covered peers

BASIS_SECTOR = "sector"
BASIS_UNIVERSE = "universe"


def peer_group_for(sector: str | None) -> tuple[str, str]:
    """Resolve the peer group for a ticker's stored sector.

    Returns ``(label, basis)``. The label is what the page prints after "of";
    the basis says which comparison was actually made, so a caller never has to
    guess whether "Uncategorized" was treated as a sector (it never is).

    The sector string is used VERBATIM when it is a real one — we group on the
    value stored on the row, not on a re-derived bucket, so the printed label
    and the SQL predicate can never describe different populations. A raw,
    unmapped vendor string (e.g. "Semiconductors" on a row the sector backfill
    has not normalised yet) therefore forms its own small group; MIN_PEERS is
    what stops such a group from being published as a percentile.
    """
    if sector is None or sector.strip().lower() in _NO_SECTOR_SENTINELS:
        return UNIVERSE_LABEL, BASIS_UNIVERSE
    return sector, BASIS_SECTOR


def _percentile(below: int, n: int) -> int:
    """``round(100 * below / n)``, half-up, clamped to 0-100.

    Half-up rather than Python's banker's rounding: a reader checking our
    printed integer against their own arithmetic expects .5 to go up, and a
    rule that rounds 84.5 down but 85.5 up is a support ticket waiting to
    happen.
    """
    if n <= 0:
        return 0
    return max(0, min(100, math.floor((100.0 * below / n) + 0.5)))


async def peer_percentiles(
    session: AsyncSession,
    ticker: Ticker,
    *,
    min_peers: int = MIN_PEERS,
) -> dict[str, Any]:
    """Locate one ticker's composite + six sub-factors against its peers.

    Takes the already-loaded ``Ticker`` row (the ticker page has it in hand),
    so the only DB work is the single peer-group aggregate below.

    Shape::

        {
          "peer_group": "Health Care",     # what the page prints after "of"
          "basis": "sector",               # "sector" | "universe"
          "group_size": 763,               # every ticker in the group
          "min_peers": 30,
          "fields": {
            "score": {
              "value": 88.1,               # this ticker's own value, or None
              "percentile": 91,            # None when it cannot be published
              "n": 763,                    # COVERED peers, this ticker included
              "peer_group": "Health Care", # repeated so each row self-describes
              "basis": "sector",
              "reason": None,              # why percentile is None, when it is
            },
            ...
          }
        }

    Every field is nullable end to end. ``n`` is the honest count of peers we
    hold a value for and is reported even when the percentile is refused — "we
    cover 114 peers for Fundamentals but hold no Fundamentals score for this
    ticker" tells a reader more than a blank does.

    PEER SET: every row in ``tickers`` in the group carrying a non-NULL value
    for the field. Deliberately NOT filtered by ``services.ticker_freshness``:
    n then means exactly "tickers we hold a value for", which is what the
    printed denominator claims, and it is the same population the coverage
    numbers quoted elsewhere on the page are measured against. A ticker outside
    the active scoring universe can therefore contribute a value last refreshed
    some time ago. Tightening the peer set to freshly-scored rows only is a
    real refinement, but it would change what the denominator MEANS, so it
    belongs in its own decision rather than being smuggled in here.

    COST: one aggregate scan of the peer group (≤ ~1.4k rows for the largest
    sector, ~8.9k for the universe fallback) with at most 14 conditional
    aggregates. MEASURED, against a synthetic 8,879-row table built to the
    verified prod sector sizes and coverage mix (SQLite, warm cache, two runs):

        sector path      (n≈763)    median 1.8-2.4 ms   p95 3.1-4.1 ms
        universe path    (n≈8,879)  median 4.0-4.8 ms   p95 5.2-7.2 ms

    That is the same order as the point lookups this endpoint already performs
    and well inside its latency budget, so this pass adds NO cache — a cache
    nobody needs is just a staleness bug waiting to happen. Only ~11% of
    tickers (NULL / Uncategorized sector) take the slower full-universe path.

    If the universe grows enough to matter, the cheap next step is to memoise
    the sorted value arrays per (peer group, scan tick) and rank by bisect:
    identical arithmetic, one query per group per tick instead of one per page
    view, and still no new column, index or migration.
    """
    label, basis = peer_group_for(ticker.sector)

    # ── ONE statement, conditional aggregates ───────────────────────────────
    # Per field: COUNT(col) is the denominator (SQL counts only non-NULLs, so a
    # peer with no value for this factor is not counted as a peer for it), and
    # SUM(CASE WHEN col < :own THEN 1 ELSE 0 END) is the strictly-below
    # numerator. The below-column is emitted ONLY for fields where this ticker
    # actually has a value — there is nothing to rank otherwise, and skipping
    # it keeps a NULL bind parameter out of the comparison entirely.
    # COUNT(*) over the group, independent of any field. This is what makes
    # thin coverage LEGIBLE rather than merely disclosed: "91st percentile of
    # Health Care (n=114)" is honest but leaves a reader who knows the sector
    # has 763 names guessing. With group_size beside it the page can print
    # "n=114 of 763 Health Care names", which states in one line both the
    # comparison and how much of the sector it actually covers. Free — same
    # pass, one more aggregate.
    selects: list[Any] = [func.count().label("group_size")]
    ranked: set[str] = set()
    for key, attr in FIELDS:
        col = getattr(Ticker, attr)
        selects.append(func.count(col).label(f"n_{key}"))
        own = getattr(ticker, attr)
        if own is not None:
            ranked.add(key)
            selects.append(
                # coalesce: SUM over an empty group is NULL, not 0.
                func.coalesce(
                    func.sum(case((col < own, 1), else_=0)), 0
                ).label(f"below_{key}")
            )

    stmt = select(*selects)
    if basis == BASIS_SECTOR:
        # Equality on the stored string — the same value peer_group_for
        # returned as the label, so the predicate and the printed label can
        # never describe different populations.
        stmt = stmt.where(Ticker.sector == ticker.sector)
    row = (await session.execute(stmt)).one()._mapping

    fields: dict[str, dict[str, Any]] = {}
    for key, attr in FIELDS:
        own = getattr(ticker, attr)
        n = int(row[f"n_{key}"] or 0)
        entry: dict[str, Any] = {
            "value": own,
            "percentile": None,
            "n": n,
            "peer_group": label,
            "basis": basis,
            "reason": None,
        }
        if own is None:
            # No reading of our own — nothing to locate. Reported ahead of a
            # thin denominator because it is the more direct answer: even with
            # 10,000 covered peers we still could not place this ticker.
            entry["reason"] = REASON_NO_VALUE
        elif n < min_peers:
            entry["reason"] = REASON_INSUFFICIENT_PEERS
        else:
            entry["percentile"] = _percentile(int(row[f"below_{key}"] or 0), n)
        fields[key] = entry

    return {
        "peer_group": label,
        "basis": basis,
        # Every ticker in the peer group, whether or not we hold any factor for
        # it. Each field's own `n` is a subset of this; the gap between them IS
        # our coverage of that factor in this group.
        "group_size": int(row["group_size"] or 0),
        "min_peers": min_peers,
        "fields": fields,
    }
