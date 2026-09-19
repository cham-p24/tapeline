"""One Form 4 line, listed once, however many share classes carry it.

WHY THIS EXISTS. Since 2026-09-19 a filing's lines are stored under EVERY
common-stock ticker of the issuer (`services/edgar_form4.py`, point 5): Alphabet's
lines under GOOG and GOOGL, Berkshire's under BRK.A, BRK.B and the hyphen twins
BRK-A and BRK-B that the universe also carries. That is right per ticker - each
ticker page and each score reads its own rows - but a list that spans tickers
(/api/holdings, its Free preview, /api/public/insider-buys, and the "tracked
transactions" count beside them) would show one insider's one trade two or four
times. Measured 2026-09-19 before this change, the Berkshire hyphen twins
already did: BRK-A and BRK.A each held Buffett's 2026-07-14 gifts.

THE KEY, AND WHY IT IS NOT JUST THE LINE'S CONTENT. `insider_transactions` has
no accession number and no issuer CIK, and this change adds no migration. The
line's content - (insider, trade date, shares, price, code, line_seq) - is the
same on every class that carries it, but it is NOT unique to one company.
Measured read-only on 2026-09-19 over 54,592 production rows: MetLife
Investment Management's $25.00 redemptions of 36,000 shares on 2026-08-24 sit
under CCD and CHI, two different Calamos funds; "Orwin John A" exercised 1,300
options at $0 on 2026-09-15 at both ANAB and TRAX. Keyed on content alone,
those would be merged into one company's line.

So the issuer is taken from the parsed-filing cache, `edgar_form4_filings`,
which every EDGAR row was written from and which is never pruned: rows that
share a content key are merged only when EVERY cached filing containing that
line (same owner, date, shares, code and price) belongs to ONE issuer CIK. Each
row's own filing is among them, so a single CIK means every ticker in the group
is that issuer's; two companies' identical lines produce two CIKs and stay
apart. Rows not from EDGAR (`source` other than "edgar": pre-2026-09-14 Finnhub
rows) have no filing to check and are never merged.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Sequence
from typing import Any

logger = logging.getLogger(__name__)

#: How many rows a cross-ticker list reads per line it returns. Four is the
#: most tickers one issuer's lines were measured under on 2026-09-19 (Berkshire:
#: BRK.A, BRK.B, BRK-A, BRK-B), so LIMIT x 4 rows always hold LIMIT distinct
#: lines when that many exist. An issuer with more classes only shortens a page.
MAX_CLASS_COPIES = 4

#: Owner names per IN (...) list, well under every driver's bind-parameter cap.
_OWNERS_PER_QUERY = 500

#: (insider, trade date, shares, price, code, line_seq)
LineKey = tuple[str, str, int, float, str, int]


def line_key(row: dict[str, Any]) -> LineKey:
    return (
        row["insider_name"], row["transaction_date"], int(row["share_change"]),
        round(float(row["transaction_price"] or 0.0), 4), row["code"] or "",
        int(row.get("line_seq") or 0),
    )


def _filing_key(owner: str, line: dict[str, Any]) -> tuple[str, str, int, float, str]:
    """A cached filing line in the shape an insider row stores it
    (`finnhub_feed.set_recent_insider_transactions_db`)."""
    return (
        owner, str(line.get("transaction_date") or "")[:10], int(line.get("share_change") or 0),
        round(float(line.get("transaction_price") or 0.0), 4), str(line.get("code") or "")[:4],
    )


async def _issuers_by_line(keys: Iterable[LineKey]) -> dict[tuple[str, str, int, float, str], set[str]]:
    """For each (owner, date, shares, price, code), the issuer CIKs of every
    cached filing that contains such a line."""
    from sqlalchemy import select

    from app.db import session_scope
    from app.models import EdgarForm4Filing

    wanted = {(k[0], k[1], k[2], k[3], k[4]) for k in keys}
    if not wanted:
        return {}
    owners = sorted({k[0] for k in wanted})
    # A filing is never dated before a trade it reports (edgar_form4 drops such
    # lines), so nothing older than the oldest trade in question can hold one.
    earliest = min(k[1] for k in wanted)
    found: dict[tuple[str, str, int, float, str], set[str]] = {}
    rows: list[Any] = []
    async with session_scope() as session:
        for start in range(0, len(owners), _OWNERS_PER_QUERY):
            rows.extend((await session.execute(
                select(
                    EdgarForm4Filing.owner_name, EdgarForm4Filing.issuer_cik,
                    EdgarForm4Filing.rows_json,
                )
                .where(
                    EdgarForm4Filing.owner_name.in_(owners[start:start + _OWNERS_PER_QUERY]),
                    EdgarForm4Filing.filing_date >= earliest,
                    EdgarForm4Filing.rows_json.is_not(None),
                )
            )).all())
    for owner, issuer_cik, rows_json in rows:
        if not issuer_cik:
            continue
        try:
            lines = json.loads(rows_json)
        except ValueError:
            continue
        for line in lines if isinstance(lines, list) else []:
            if not isinstance(line, dict):
                continue
            key = _filing_key(owner, line)
            if key in wanted:
                found.setdefault(key, set()).add(issuer_cik)
    return found


async def _one_issuer_groups(groups: dict[LineKey, list[dict[str, Any]]]) -> set[LineKey]:
    """The content keys, among `groups`, whose rows provably belong to one
    issuer; see the module docstring."""
    candidates = {
        key for key, rows in groups.items()
        if len({r["symbol"] for r in rows}) > 1
        and all(r.get("source") == "edgar" for r in rows)
    }
    if not candidates:
        return set()
    issuers = await _issuers_by_line(candidates)
    return {key for key in candidates if len(issuers.get(key[:5], ())) == 1}


def _listed_symbols(symbols: set[str]) -> list[str]:
    """The classes a merged line is listed under, sorted, leaving out symbols we
    do not cover when a covered one remains (2026-09-19). BRK-A sorts before
    BRK.A, and BRK-A now answers "Not covered" (services/coverage.py), so a
    merged Berkshire line was labelled, and linked, to a page with nothing on
    it. A group made only of uncovered symbols keeps them, rather than vanish."""
    from app.services.coverage import not_covered_message

    ordered = sorted(symbols)
    covered = [s for s in ordered if not_covered_message(s) is None]
    return covered or ordered


async def collapse_share_classes(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """`rows` (insider_transactions as dicts, newest first, carrying `line_seq`
    and `source`) with every line that several classes of ONE issuer carry
    listed once. Each result carries `symbols`, the tickers it belongs to, and
    `symbol`, the first of them; order is kept, at the first copy's place."""
    groups: dict[LineKey, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(line_key(row), []).append(row)
    merge = await _one_issuer_groups(groups)
    out: list[dict[str, Any]] = []
    emitted: set[LineKey] = set()
    for row in rows:
        key = line_key(row)
        if key in merge:
            if key in emitted:
                continue
            emitted.add(key)
            symbols = _listed_symbols({r["symbol"] for r in groups[key]})
            out.append({**row, "symbol": symbols[0], "symbols": symbols})
        else:
            out.append({**row, "symbols": [row["symbol"]]})
    return out


async def distinct_line_count() -> int:
    """How many distinct Form 4 lines `insider_transactions` holds: every row,
    less the extra copies one issuer's classes share. The "tracked
    transactions" figure beside the feed, which would otherwise count
    Alphabet's lines twice and Berkshire's four times."""
    from sqlalchemy import case, func, select

    from app.db import session_scope
    from app.models import InsiderTransaction as T

    async with session_scope() as session:
        total = int(await session.scalar(select(func.count(T.id))) or 0)
        shared = (await session.execute(
            select(
                T.insider_name, T.transaction_date, T.share_change, T.transaction_price,
                T.code, T.line_seq, func.count(), func.count(func.distinct(T.symbol)),
            )
            .group_by(
                T.insider_name, T.transaction_date, T.share_change, T.transaction_price,
                T.code, T.line_seq,
            )
            .having(
                func.count(func.distinct(T.symbol)) > 1,
                # Every copy from EDGAR; see collapse_share_classes.
                func.min(case((T.source == "edgar", 1), else_=0)) == 1,
            )
        )).all()
    if not shared:
        return total
    issuers = await _issuers_by_line(
        (name, day, int(shares), round(float(price or 0.0), 4), code or "", int(seq or 0))
        for name, day, shares, price, code, seq, _n, _symbols in shared
    )
    extra = sum(
        n - 1
        for name, day, shares, price, code, _seq, n, _symbols in shared
        if len(issuers.get((name, day, int(shares), round(float(price or 0.0), 4), code or ""), ())) == 1
    )
    return total - extra
