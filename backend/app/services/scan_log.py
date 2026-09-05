"""record_scan_log — preserve what a scan asked for and what it returned.

OPENS ITS OWN SESSION, and does not take the caller's — the same rule
`record_funnel_event` follows, for the same reason. That function's docstring
records the outage: rolling an instrumentation failure back inside the caller's
session left it poisoned, and the scanner endpoint then died with
PendingRollbackError on its very next statement. Instrumentation gets its own
short-lived session so no failure here can reach the user.

NEVER RAISES. Every path is wrapped. A scan that succeeded must be returned to
the user whether or not we managed to write down what it contained; the log is
worth having, and it is not worth a 500.

SIGNED-IN ONLY. The caller gates on `user is not None`, matching
record_funnel_event. The question this table exists to answer is about people
with accounts who cancelled, and excluding anonymous traffic keeps a
per-request table off the public SEO surfaces entirely. Revisit if the question
ever becomes "what do logged-out visitors see".
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.db import session_scope
from app.models.scan_log import (
    SCAN_LOG_TOP_N,
    SCAN_SOURCE_UNKNOWN,
    SCAN_SOURCES,
    ScanLog,
)

logger = logging.getLogger(__name__)

#: Hard ceiling on each stored blob. The filter set is ~12 short fields and the
#: symbol list is capped at SCAN_LOG_TOP_N, so neither comes close in practice
#: — this exists so a future filter dimension carrying free text cannot quietly
#: turn an instrumentation row into a multi-megabyte write on the hot path.
_MAX_BLOB_CHARS = 8_000


def _truncate(blob: str, what: str) -> str:
    if len(blob) <= _MAX_BLOB_CHARS:
        return blob
    logger.warning("scan_log.blob_truncated field=%s len=%d", what, len(blob))
    return blob[:_MAX_BLOB_CHARS]


def summarise_rows(rows: list[Any], top_n: int = SCAN_LOG_TOP_N) -> list[dict]:
    """The first `top_n` returned tickers, flattened to plain values.

    Values are read off the ORM objects HERE, at scan time, precisely so the
    stored record does not depend on `tickers` rows that the worker rewrites
    every 60 seconds. See models/scan_log.py.

    Tolerates rows missing any attribute (None) rather than raising: a partial
    record of what the user saw beats no record because one column was null.
    """
    out: list[dict] = []
    for row in rows[:top_n]:
        out.append(
            {
                "symbol": getattr(row, "symbol", None),
                "score": getattr(row, "score", None),
                "price": getattr(row, "price", None),
                "volume": getattr(row, "volume", None),
            }
        )
    return out


def normalise_src(src: str | None) -> str:
    """Map a caller-supplied source onto the closed SCAN_SOURCES set.

    Anything unrecognised — including None and, importantly, a FastAPI
    `Query(...)` object arriving from a handler called as a plain function —
    becomes "unknown" rather than being written through. Same posture as
    FUNNEL_EVENTS and CAP_NAMES: a typo in one caller must not silently split
    the dataset into two populations that look like one.
    """
    return src if isinstance(src, str) and src in SCAN_SOURCES else SCAN_SOURCE_UNKNOWN


async def record_scan_log(
    user: Any,
    *,
    filters: dict[str, Any],
    rows: list[Any],
    total_matched: int | None,
    row_cap: int,
    tier: str,
    src: str | None = None,
    duration_ms: int | None = None,
) -> None:
    """Write one row describing this scan. Fire-and-forget: never raises."""
    try:
        top = summarise_rows(rows)
        # default=str so an unexpected non-serialisable filter value (a Decimal,
        # an Enum) degrades to its string form instead of throwing inside the
        # instrumentation and losing the whole row.
        filters_json = _truncate(json.dumps(filters, default=str, sort_keys=True), "filters")
        top_json = _truncate(json.dumps(top, default=str), "top_symbols")

        async with session_scope() as s:
            s.add(
                ScanLog(
                    user_id=user.id,
                    tier=str(tier),
                    src=normalise_src(src),
                    duration_ms=duration_ms,
                    filters_json=filters_json,
                    result_count=len(rows),
                    total_matched=total_matched,
                    row_cap=row_cap,
                    top_symbols_json=top_json,
                )
            )
            await s.commit()
    except Exception:
        # Deliberately broad. The caller has already produced a correct scan
        # response; nothing that happens here may change that.
        logger.exception(
            "scan_log.write_failed user=%s", getattr(user, "id", "?"),
        )
