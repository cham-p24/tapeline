"""The vendor's own time for a price — never ours.

WHY THIS EXISTS
---------------
`Ticker.updated_at` is our database write time. The 60-second tick re-stamps it
on every row it writes, including rows the vendor returned nothing for, and
every in-app "As of" read it. The price plan (Massive Stocks Starter) is
15-minute delayed — measured 14 Sep 2026: the AAPL snapshot 899 s old, the
newest minute bar 961 s old — so a quarter-hour-old price was shown as seconds
old. `polygon_feed._to_scanner_row` stamped `datetime.now(UTC)` into a
`last_timestamp` key that was never persisted, and threw the vendor's own
timestamp fields away.

WHAT COUNTS AS A QUOTE TIME
---------------------------
Only a field the vendor attached to the price, in this order:

1. ``last_trade.sip_timestamp``, then ``last_trade.participant_timestamp`` —
   when the last trade printed. The truest answer to "how old is this price".
2. ``last_quote.sip_timestamp``, then ``last_quote.participant_timestamp``.
3. The END of the last minute bar: ``last_minute.window_start`` (v3 naming) or
   ``last_minute.t`` (a bar-style fallback name) plus one minute. A bar is
   stamped with its start and its close printed somewhere inside it, so the
   end is the LATEST the price can be from: an upper bound on the trade time.
   An age measured from it can be understated by up to 60 seconds, small
   beside the plan's ~15-minute delay.

Deliberately NOT used:

* Any ``last_updated`` / ``updated`` field. Measured 14 Sep 2026 on this plan,
  the snapshot's ``last_updated`` fields read ~0 s old — the time of the
  RESPONSE, not of the trade (docs/DATA_SOURCES.md). Using one would re-create
  exactly the false "seconds old" this module exists to remove.
* Our clock. If the vendor sends none of the fields above, the answer is None,
  and the UI states the plan's delay instead of a time.

Which fields the plan actually returns was unknown when this was written (the
14 Sep measurement found no last-trade or last-quote keys at all; nobody may
call the vendor from a dev machine to check). `polygon_feed` logs the field
names it received once per process at INFO — see `describe_quote_fields` — so
production says which of these branches is live.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

#: Width of the `tickers.quote_timeframe` column (migration 0075).
QUOTE_TIMEFRAME_MAX_LEN = 16

#: Earliest instant accepted as a real quote time. Anything before this is a
#: unit error (seconds read as nanoseconds, a zero placeholder), not a quote.
_EARLIEST = datetime(2000, 1, 1, tzinfo=UTC)

#: How far past our clock a vendor time may sit before it is rejected as a
#: unit error. Bounds the value; it is never used AS the value.
_FUTURE_SLACK = timedelta(minutes=5)

#: A minute bar is stamped with its start; its close is no later than its end.
MINUTE_BAR = timedelta(minutes=1)

#: (object, field, offset added to the instant), in preference order.
_CANDIDATES: tuple[tuple[str, str, timedelta], ...] = (
    ("last_trade", "sip_timestamp", timedelta(0)),
    ("last_trade", "participant_timestamp", timedelta(0)),
    ("last_quote", "sip_timestamp", timedelta(0)),
    ("last_quote", "participant_timestamp", timedelta(0)),
    ("last_minute", "window_start", MINUTE_BAR),
    ("last_minute", "t", MINUTE_BAR),
)

#: The objects whose field NAMES are logged once per process.
_DESCRIBED_OBJECTS = ("session", "last_minute", "last_trade", "last_quote")


def epoch_to_utc(value: Any) -> datetime | None:
    """A vendor epoch number -> an aware UTC datetime, or None.

    The unit is read from the magnitude, because the vendor mixes them
    (nanoseconds on v3 trade/quote timestamps, milliseconds on v2 bars):
    around 2026 an instant is ~1.8e18 in ns, ~1.8e15 in µs, ~1.8e12 in ms and
    ~1.8e9 in s, so the four ranges cannot overlap for any date this product
    will see. Integer division for ns/µs keeps the conversion exact rather
    than routing a 19-digit integer through a float.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            value = int(text) if text.lstrip("-").isdigit() else float(text)
        except ValueError:
            return None
    if not isinstance(value, int | float):
        return None
    if value <= 0:
        return None
    try:
        if value >= 1e17:  # nanoseconds
            n = int(value)
            dt = datetime.fromtimestamp(n // 1_000_000_000, UTC) + timedelta(
                microseconds=(n % 1_000_000_000) // 1_000
            )
        elif value >= 1e14:  # microseconds
            n = int(value)
            dt = datetime.fromtimestamp(n // 1_000_000, UTC) + timedelta(
                microseconds=n % 1_000_000
            )
        elif value >= 1e11:  # milliseconds
            dt = datetime.fromtimestamp(value / 1_000, UTC)
        else:  # seconds
            dt = datetime.fromtimestamp(value, UTC)
    except (OverflowError, OSError, ValueError):
        return None
    return dt


def _plausible(dt: datetime | None, now: datetime) -> datetime | None:
    if dt is None or dt < _EARLIEST or dt > now + _FUTURE_SLACK:
        return None
    return dt


def _timeframe(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().upper()
    return text[:QUOTE_TIMEFRAME_MAX_LEN] or None


def extract_quote_time(
    snap: dict[str, Any], *, now: datetime | None = None,
) -> tuple[datetime | None, str | None, str | None]:
    """(quote_at, timeframe, source) from one v3 snapshot result.

    `source` names the field the time came from (e.g. "last_trade.sip_timestamp")
    and is None when no vendor field held a usable time. `now` bounds the
    answer (a time far in the future is a unit error) and is never returned.
    """
    bound = now or datetime.now(UTC)
    quote_at: datetime | None = None
    source: str | None = None
    for obj_name, field, offset in _CANDIDATES:
        obj = snap.get(obj_name)
        if not isinstance(obj, dict) or field not in obj:
            continue
        instant = epoch_to_utc(obj.get(field))
        if instant is None:
            continue
        # A bar end can legitimately sit in the future while its minute is
        # still open, so the plausibility bound is applied to the instant the
        # vendor sent, and the offset added after.
        if _plausible(instant, bound) is None:
            continue
        quote_at = instant + offset
        source = f"{obj_name}.{field}"
        break

    # The timeframe flag describes the plan's delivery, not one object, so any
    # object that carries it is informative. The object the time came from is
    # asked first.
    order: list[Any] = []
    if source is not None:
        order.append(snap.get(source.split(".", 1)[0]))
    order += [snap.get("last_trade"), snap.get("last_quote"), snap]
    timeframe = None
    for obj in order:
        if isinstance(obj, dict):
            timeframe = _timeframe(obj.get("timeframe"))
            if timeframe:
                break
    return quote_at, timeframe, source


def describe_quote_fields(snap: dict[str, Any]) -> dict[str, list[str]]:
    """The field NAMES one snapshot result carried, per object — no values.

    Logged once per process so production records which timestamp fields the
    plan returns. Names only: nothing here can carry a key, a URL or a price.
    """
    out: dict[str, list[str]] = {"top": sorted(str(k) for k in snap)}
    for name in _DESCRIBED_OBJECTS:
        obj = snap.get(name)
        out[name] = sorted(str(k) for k in obj) if isinstance(obj, dict) else []
    return out


def iso_utc(dt: datetime | None) -> str | None:
    """ISO-8601 with an explicit UTC offset, or None.

    SQLite hands back naive datetimes (Postgres returns aware ones). A naive
    ISO string parses as LOCAL time in a browser, which would shift a quote
    time by the reader's UTC offset, so a naive value is marked UTC here.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()
