"""A renamed column in the founder's workbook must not degrade scores in silence.

`csv.DictReader` has no opinion about a rename. `raw.get("3M Return %")` on a
sheet that now says "3M %" returns None, `_parse_float` passes the None along,
and `compute_tapeline_composite` treats a missing input as a factor it cannot
read — which scores NEUTRAL 50 by design. So a spreadsheet edit quietly moves
every score toward the middle and nothing anywhere says a word.

Measured against the live workbook on 2026-09-07, six columns this parser reads
had already gone. Three were renamed, three were removed outright:

    3M Return % / 6M Return % / 1Y Return %  ->  "3M %" / "6M %" / "1Y %"
    Asset Class / Conviction / Strategy      ->  removed

`Asset Class` is the dangerous one, because it is what the crypto fail-closed
guard reads. `raw.get` on an absent column returns None — the single input that
guard lets through, since a blank cell legitimately means "the sheet did not
say" for sheet-governed ETFs. So the guard added days earlier to stop a token's
price being published under a real company's ticker (SOL/Emeren, EOS/Eaton
Vance, BGB/Blackstone, LEO/BNY Mellon) had been silently disarmed.

The obvious repair is to alias `Asset Class` to the surviving `Type` column,
and it is wrong twice over.

It drops rows. `is_unrecognised_asset_class` treats a value it cannot classify
as a refusal to publish, and Type says "Small Cap" / "Mid Cap" / "Large Cap" /
"Penny (<$5)" — 2,966 of the workbook's 4,112 rows. Without teaching the
normaliser that vocabulary, the alias deletes 72% of the sheet.

And it mislabels the rest. Type is a SIZE bucket that spends one of its values
on "ETF"; it never asserts that a "Large Cap" row is not a fund. Measured
against the live workbook, taking it as an asset class relabels 114 real funds
as equities — BNO (Brent Oil Fund), CEF (Sprott Gold Trust), BAR (Gold Trust),
BKCH (Blockchain ETF) and a row of single-stock leveraged ETFs. That is exactly
the defect #761 exists to prevent.

So the guard and the stored value read different things: the guard consults
every column that can carry a class signal, while the value comes only from the
authoritative one and stays silent when it is absent.
"""
from __future__ import annotations

import logging

import pytest

from app.services.sheet_feed import (
    _ALL_SIGNALS_COLUMNS,
    audit_headers,
    is_unrecognised_asset_class,
    normalize_asset_class,
    parse_all_signals_csv,
)

# The workbook's ALL SIGNALS header row, fetched live 2026-09-07. Pinned here
# so a future rename fails a test instead of a quarter's worth of scores.
LIVE_HEADERS = [
    "Ranking", "BUY NOW", "Ticker", "Price", "Name", "Type", "Sector",
    "Horizon", "Verdict", "Timing", "Exit Signal", "Crash Risk", "Why",
    "Score", "Rev Growth %", "Trend", "1M %", "3M %", "6M %", "1Y %",
    "3Y %", "5Y %", "10Y %", "CAGR %", "RS vs SPY 3M %", "RS vs SPY 6M %",
    "RS vs SPY 1Y %", "Near 52W High %", "Momentum Quality", "Market Regime",
    "Max Drawdown %", "Liquidity $M/day",
]

# Every distinct value in that column, live, with its row count.
LIVE_TYPE_VALUES = {
    "Small Cap": 1415,
    "ETF": 965,
    "Mid Cap": 812,
    "Large Cap": 556,
    "Penny (<$5)": 183,
    "Leveraged ETF": 181,
}


def _csv(headers: list[str], rows: list[dict[str, str]]) -> str:
    out = [",".join(f'"{h}"' for h in headers)]
    for r in rows:
        out.append(",".join(f'"{r.get(h, "")}"' for h in headers))
    return "\n".join(out)


def _live_row(**over) -> dict[str, str]:
    row = {
        "Ticker": "AAPL", "Price": "230.5", "Type": "Large Cap",
        "Score": "78", "3M %": "12.5", "6M %": "20.1", "1Y %": "31.0",
        "RS vs SPY 3M %": "4.2", "RS vs SPY 6M %": "6.1",
        "RS vs SPY 1Y %": "9.9", "Near 52W High %": "-3.1",
        "Momentum Quality": "Strong", "Market Regime": "Risk-On",
    }
    row.update(over)
    return row


# ── the rename itself ───────────────────────────────────────────────────────

def test_the_renamed_return_columns_are_still_read():
    """The regression. These feed sub_trend; None scores as NEUTRAL 50."""
    rows = parse_all_signals_csv(_csv(LIVE_HEADERS, [_live_row()]))
    assert len(rows) == 1, "the live header row must still parse"
    row = rows[0]
    assert row["change_pct_3m"] == 12.5, (
        "the workbook's '3M %' was not read — the parser is still looking for "
        "'3M Return %', so this arrives as None and scores NEUTRAL 50"
    )
    assert row["change_pct_6m"] == 20.1
    assert row["change_pct_1y"] == 31.0


def test_the_original_spellings_still_work():
    """Aliases are additive. An older export must not break."""
    old_headers = [
        "Ticker", "Price", "Asset Class", "Score", "Conviction",
        "3M Return %", "6M Return %", "1Y Return %",
        "RS vs SPY 3M %", "RS vs SPY 6M %", "RS vs SPY 1Y %",
        "Near 52W High %", "Momentum Quality", "Market Regime",
    ]
    row = {
        "Ticker": "MSFT", "Price": "410", "Asset Class": "stock", "Score": "80",
        "Conviction": "HIGH", "3M Return %": "8.0", "6M Return %": "15.0",
        "1Y Return %": "25.0", "RS vs SPY 3M %": "2.0",
        "RS vs SPY 6M %": "3.0", "RS vs SPY 1Y %": "4.0",
        "Near 52W High %": "-1.0", "Momentum Quality": "Strong",
        "Market Regime": "Risk-On",
    }
    out = parse_all_signals_csv(_csv(old_headers, [row]))
    assert len(out) == 1
    assert out[0]["change_pct_3m"] == 8.0
    assert out[0]["asset_class"] == "equity"


def test_the_canonical_column_wins_when_both_are_present():
    """During a transition both may exist. An alias is a fallback, not an override.

    It matters because a PRESENT-but-blank canonical cell means "the sheet
    declined to say", which several callers treat as meaningful. An alias that
    overrode it would turn that silence into an assertion.
    """
    headers = ["Ticker", "Price", "Type", "Score", "3M Return %", "3M %"]
    row = {"Ticker": "NVDA", "Price": "1", "Type": "Large Cap", "Score": "70",
           "3M Return %": "1.0", "3M %": "99.0"}
    out = parse_all_signals_csv(_csv(headers, [row]))
    assert out[0]["change_pct_3m"] == 1.0, (
        "the alias overrode the canonical column that was present"
    )


# ── the trap in the fix: dropping most of the sheet ─────────────────────────

@pytest.mark.parametrize("value,count", sorted(LIVE_TYPE_VALUES.items()))
def test_every_live_type_value_classifies(value, count):
    """Unclassifiable means DROPPED, not mislabelled.

    `is_unrecognised_asset_class` is a fail-closed guard: a value it cannot
    read is a refusal to publish. Aliasing Asset Class -> Type without this
    vocabulary would have deleted 2,966 of the workbook's 4,112 rows.
    """
    assert normalize_asset_class(value) is not None, (
        f"the workbook's Type value {value!r} ({count} rows) does not "
        f"classify, so every one of those rows is dropped from the universe"
    )
    assert not is_unrecognised_asset_class(value)


def test_the_cap_buckets_are_equities_and_the_funds_are_etfs():
    """Classifying is necessary but not sufficient — it must be RIGHT.

    The scanner's asset-class filter and /t/<symbol> both read this column, and
    #761 exists because a leveraged fund surfaced where a visitor expected a
    stock. Calling one an equity would put it back.
    """
    for v in ("Small Cap", "Mid Cap", "Large Cap", "Penny (<$5)"):
        assert normalize_asset_class(v) == "equity", f"{v!r} misclassified"
    for v in ("ETF", "Leveraged ETF"):
        assert normalize_asset_class(v) == "etf", f"{v!r} misclassified"


def test_a_full_live_sheet_is_not_mass_dropped():
    """End to end over the real vocabulary, in the real proportions."""
    rows = []
    for i, (value, _) in enumerate(sorted(LIVE_TYPE_VALUES.items())):
        rows.append(_live_row(Ticker=f"SYM{i}", Type=value))
    out = parse_all_signals_csv(_csv(LIVE_HEADERS, rows))
    assert len(out) == len(rows), (
        f"only {len(out)} of {len(rows)} rows survived ingest — the "
        f"fail-closed guard is refusing real listings"
    )


# ── the crypto guard, re-armed ──────────────────────────────────────────────

def test_crypto_is_dropped_through_the_renamed_column():
    """The guard reads the asset-class column. It must follow the rename.

    While it read only "Asset Class" on a sheet that says "Type", every row
    looked like "the sheet said nothing" — the one case it lets through.
    """
    rows = [_live_row(Ticker="SOL", Type="crypto"),
            _live_row(Ticker="AAPL", Type="Large Cap")]
    out = parse_all_signals_csv(_csv(LIVE_HEADERS, rows))
    assert [r["symbol"] for r in out] == ["AAPL"], (
        "a crypto row was ingested through the renamed column; this is how a "
        "token's price came to be published under four real companies' tickers"
    )


def test_an_unreadable_asset_class_still_fails_closed():
    """Unchanged behaviour, asserted so the alias work cannot loosen it."""
    rows = [_live_row(Ticker="XYZ", Type="digital asset"),
            _live_row(Ticker="AAPL", Type="Large Cap")]
    out = parse_all_signals_csv(_csv(LIVE_HEADERS, rows))
    assert [r["symbol"] for r in out] == ["AAPL"]


def test_a_blank_type_cell_still_passes():
    """Sheet-governed ETFs (SPY, QQQ, GLD) leave it empty by design."""
    out = parse_all_signals_csv(_csv(LIVE_HEADERS, [_live_row(Ticker="SPY", Type="")]))
    assert [r["symbol"] for r in out] == ["SPY"]


# ── the alarm ───────────────────────────────────────────────────────────────

def test_the_audit_reports_a_column_that_has_no_successor():
    """`Conviction` is gone from the workbook with nothing to alias to."""
    missing = audit_headers(LIVE_HEADERS)
    assert "Conviction" in missing, (
        "the audit did not report Conviction as missing, so confidence_pct "
        "silently stays None for every sheet-governed row"
    )


def test_the_audit_is_quiet_about_columns_that_were_only_renamed():
    """An alias that works is not drift worth paging anyone about."""
    missing = audit_headers(LIVE_HEADERS)
    for renamed in ("3M Return %", "6M Return %", "1Y Return %"):
        assert renamed not in missing, (
            f"{renamed} is aliased and readable, so reporting it as missing "
            f"would train the reader to ignore this warning"
        )


def test_asset_class_is_reported_missing_even_though_type_exists():
    """They are not the same column and must not be aliased to each other.

    "Asset Class" asserts what an instrument IS. "Type" is a size bucket that
    spends one of its values on "ETF" — it says nothing about whether a
    "Large Cap" row is a fund. Measured against the live workbook, treating
    Type as an asset class relabels 114 real funds as equities: BNO (Brent Oil
    Fund), CEF (Sprott Gold Trust), BAR (Gold Trust), BKCH (Blockchain ETF)
    and a row of single-stock leveraged ETFs. #761 exists because a leveraged
    fund surfaced where a visitor expected a stock.
    """
    assert "Asset Class" in audit_headers(LIVE_HEADERS)
    assert "Type" not in audit_headers(LIVE_HEADERS)


def test_the_size_bucket_never_becomes_the_stored_asset_class():
    """The value the DB stores comes only from the authoritative column."""
    rows = parse_all_signals_csv(_csv(LIVE_HEADERS, [_live_row(Ticker="BNO", Type="Large Cap")]))
    assert rows[0]["asset_class"] is None, (
        f"the size bucket was stored as asset_class={rows[0]['asset_class']!r}; "
        f"upsert_tickers overwrites on a truthy value, so this would relabel "
        f"BNO — an oil FUND — as an equity and hide it from the ETF filter"
    )


def test_the_authoritative_column_is_still_stored_when_present():
    """Splitting guard from value must not stop the sheet asserting properly."""
    headers = LIVE_HEADERS + ["Asset Class"]
    row = _live_row(Ticker="SPY", Type="Large Cap")
    row["Asset Class"] = "etf"
    rows = parse_all_signals_csv(_csv(headers, [row]))
    assert rows[0]["asset_class"] == "etf"


def test_the_audit_reports_a_brand_new_rename():
    """The point of the mechanism: the NEXT rename is loud."""
    headers = [h for h in LIVE_HEADERS if h != "Score"] + ["Composite Score"]
    assert "Score" in audit_headers(headers)


def test_losing_every_class_signal_is_logged_at_error(caplog):
    """With no class column at all the crypto guard passes everything.

    Categorically worse than a lost factor, so it is separable in logs rather
    than sharing a WARNING with cosmetic drift.
    """
    headers = [h for h in LIVE_HEADERS if h != "Type"]
    with caplog.at_level(logging.WARNING, logger="app.services.sheet_feed"):
        parse_all_signals_csv(_csv(headers, [_live_row()]))
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors, "losing every asset-class signal produced no ERROR"
    assert any("Asset Class" in r.getMessage() for r in errors)


def test_losing_only_one_class_signal_does_not_page(caplog):
    """The guard needs one of the two. Crying wolf while it works is how a
    real alarm gets tuned out — and today's workbook is exactly this case."""
    with caplog.at_level(logging.WARNING, logger="app.services.sheet_feed"):
        parse_all_signals_csv(_csv(LIVE_HEADERS, [_live_row()]))
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert not errors, (
        f"an ERROR fired while the crypto guard was still armed via Type: "
        f"{[r.getMessage() for r in errors]}"
    )


def test_a_clean_sheet_logs_nothing():
    """No crying wolf: a workbook with every column present is silent."""
    full = LIVE_HEADERS + ["Asset Class", "Conviction", "Strategy", "Raw Score"]
    assert audit_headers(full) == []


def test_every_column_the_parser_reads_is_registered():
    """The table drives both the aliases and the alarm.

    A `raw.get("New Column")` added straight into the parser would be readable
    but invisible to the audit, so the next rename of THAT column would be
    silent again — reintroducing the exact bug. Registration is what makes the
    alarm complete rather than a snapshot of one afternoon.
    """
    import inspect
    import re

    from app.services import sheet_feed

    src = inspect.getsource(sheet_feed.parse_all_signals_csv)
    read = set(re.findall(r'_cell\(\s*raw\s*,\s*"([^"]+)"', src))
    unregistered = read - set(_ALL_SIGNALS_COLUMNS)
    assert not unregistered, (
        f"parse_all_signals_csv reads {sorted(unregistered)} but they are not "
        f"in _ALL_SIGNALS_COLUMNS, so audit_headers cannot warn when they are "
        f"renamed"
    )
    assert not re.search(r'raw\.get\(\s*"', src), (
        "parse_all_signals_csv still reads a column via raw.get(); use "
        "_cell(raw, ...) so the alias table and the audit both see it"
    )


# ── stranded asset_class values ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_stranded_emoji_asset_class_is_repaired():
    """These rows are permanently unservable until something revisits them.

    `normalize_asset_class` strips the sheet's decoration at WRITE time, but it
    was added after rows had already been stored as "<icon> stock" and
    "<icon> holding co" — and nothing ever went back. Measured in production
    2026-09-07: 14 rows, including BRK-A and BRK-B (Berkshire Hathaway) and
    SPLG (the SPDR S&P 500 ETF). Scored, priced, and invisible everywhere,
    because `valid_composite_clauses` requires a clean single-token class.

    They are no longer sheet-governed, so the write-time normaliser will never
    see them again.
    """
    import uuid

    from sqlalchemy import delete, select

    from app.db import session_scope
    from app.models import Ticker
    from app.services.sheet_feed import repair_dirty_asset_classes

    sym = f"ZR{uuid.uuid4().hex[:5].upper()}"
    async with session_scope() as s:
        s.add(Ticker(symbol=sym, name="Stranded", sector="Financials",
                     asset_class="\U0001F3DB holding co", score=56.2, price=500.0))
    try:
        async with session_scope() as s:
            await repair_dirty_asset_classes(s)
        async with session_scope() as s:
            row = (await s.execute(select(Ticker).where(Ticker.symbol == sym))).scalar_one()
        assert row.asset_class == "equity", (
            f"a stranded row kept asset_class={row.asset_class!r}, so it stays "
            f"invisible on every ranked surface"
        )
    finally:
        async with session_scope() as s:
            await s.execute(delete(Ticker).where(Ticker.symbol == sym))


@pytest.mark.asyncio
async def test_a_value_the_normaliser_cannot_read_is_left_alone():
    """"We do not understand this" is not licence to guess a class."""
    import uuid

    from sqlalchemy import delete, select

    from app.db import session_scope
    from app.models import Ticker
    from app.services.sheet_feed import repair_dirty_asset_classes

    sym = f"ZS{uuid.uuid4().hex[:5].upper()}"
    async with session_scope() as s:
        s.add(Ticker(symbol=sym, name="Unknown", sector="?",
                     asset_class="\U0001F4A0 quantum widget", score=50.0, price=1.0))
    try:
        async with session_scope() as s:
            out = await repair_dirty_asset_classes(s)
        assert out["unclassifiable"] >= 1
        async with session_scope() as s:
            row = (await s.execute(select(Ticker).where(Ticker.symbol == sym))).scalar_one()
        assert row.asset_class == "\U0001F4A0 quantum widget", (
            "the repair invented a class for a value it cannot read"
        )
    finally:
        async with session_scope() as s:
            await s.execute(delete(Ticker).where(Ticker.symbol == sym))
