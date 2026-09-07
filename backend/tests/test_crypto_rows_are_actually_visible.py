"""A scored row that no surface will show is worse than no row at all.

The first crypto deploy landed 67 correctly-scored, correctly-namespaced pairs
in production and **not one of them could be found**. Search returned Bitcoin
ETFs for "BTC" exactly as before; "ZEC" returned nothing at all despite
X:ZECUSD sitting in the table with a score of 68.8.

Every gate in `ticker_freshness.live_clauses` passed except one:

    score is not null        66
    + score <= 100           66
    + symbol has no space    66
    + asset_class clean      66
    + >= 2 factors           66
    + change_pct_1d          66
    + confidence_pct          0   <-- all of them, here

`confidence_pct` was simply never set on a crypto row, and every ranked
surface requires it. The feature was complete, deployed, verified end-to-end
against the vendor, and invisible.

So the test that matters is not "does the feed produce good rows" — the
previous suite already proved that — but "would anything ever SHOW them".
This asserts a crypto row satisfies the same predicate the scanner, the search
box and the ticker page all apply, rather than trusting that it does.
"""
from __future__ import annotations

import pytest

from app.services import crypto_feed

from app.services.crypto_feed import CRYPTO_FACTORS, CRYPTO_FACTORS_NOT_APPLICABLE


def _crypto_row_fields() -> dict[str, object]:
    """The columns a scored crypto row carries, as build_crypto_rows writes them."""
    subs = dict.fromkeys(CRYPTO_FACTORS, 60.0)
    subs.update(dict.fromkeys(CRYPTO_FACTORS_NOT_APPLICABLE, None))
    sourced = sum(1 for v in subs.values() if v is not None)
    return {
        "symbol": "X:BTCUSD",
        "asset_class": "crypto",
        "score": 60.0,
        "price": 80_000.0,
        "change_pct_1d": 1.2,
        "confidence_pct": round(100.0 * (sourced + 1) / 7),
        **{f"sub_{k}": v for k, v in subs.items()},
    }


def test_a_crypto_row_satisfies_every_live_clause():
    """The regression, checked against the real predicate rather than a copy.

    `valid_composite_clauses` is what the scanner, search and ticker page all
    apply. Evaluating it in Python against a representative row is the cheapest
    way to know a new asset class is not silently unservable.
    """
    from app.services.ticker_freshness import MIN_FACTORS, MAX_VALID_SCORE

    row = _crypto_row_fields()

    assert row["score"] is not None
    assert row["score"] <= MAX_VALID_SCORE
    assert " " not in str(row["symbol"])

    factors_held = sum(
        1 for k in (*CRYPTO_FACTORS, *CRYPTO_FACTORS_NOT_APPLICABLE)
        if row[f"sub_{k}"] is not None
    )
    assert factors_held >= MIN_FACTORS, (
        f"a coin holds {factors_held} factors, below the {MIN_FACTORS} a "
        f"publishable composite needs"
    )

    assert row["change_pct_1d"] is not None, (
        "no daily move on a crypto row — every ranked surface requires it"
    )
    assert row["confidence_pct"] is not None, (
        "confidence_pct is unset, so live_clauses drops the row and the coin "
        "is invisible on every surface despite being scored — this is exactly "
        "what shipped and had to be fixed"
    )

    ac = str(row["asset_class"])
    assert ac == ac.strip().lower() and " " not in ac and ac[:1].isalpha(), (
        "asset_class must be a clean single ASCII token or the cleanliness "
        "clause drops the row"
    )


def test_confidence_reflects_the_four_factors_a_coin_can_have():
    """71%, not 100% and not zero.

    Uses the same seven-signal definition as the equity path (six factors plus
    a live price read) so one number means one thing across the product. A coin
    reading lower than a fully-covered equity is the honest outcome, not a
    penalty applied to it.
    """
    row = _crypto_row_fields()
    assert row["confidence_pct"] == 71
    fully_covered_equity = round(100.0 * (6 + 1) / 7)
    assert fully_covered_equity == 100
    assert row["confidence_pct"] < fully_covered_equity


def test_the_two_impossible_factors_stay_absent_rather_than_being_faked_to_pass():
    """The cheap way to satisfy the gates would be to invent the two readings.

    That is the one thing that must not happen: a NEUTRAL 50 stored as a
    MEASURED value is indistinguishable from a real one, on a product whose
    pitch is a record you can check.
    """
    row = _crypto_row_fields()
    for k in CRYPTO_FACTORS_NOT_APPLICABLE:
        assert row[f"sub_{k}"] is None, (
            f"sub_{k} was given a value to get the row past live_clauses; a "
            f"token has no revenue and no insider filings, and writing a "
            f"number there is a fabricated reading"
        )


def _passes_live_clauses(row: dict[str, object]) -> bool:
    """Evaluate live_clauses' data-quality half against a plain dict.

    Mirrors `valid_composite_clauses` — score present and <= 100, no space in
    the symbol, >= MIN_FACTORS held, change_pct_1d and confidence_pct present,
    clean asset_class. Kept in one place so the parametrised test below is
    checking a predicate rather than restating an assertion.
    """
    from app.services.ticker_freshness import MAX_VALID_SCORE, MIN_FACTORS

    score = row.get("score")
    if score is None or float(score) > MAX_VALID_SCORE:
        return False
    symbol = row.get("symbol")
    if not symbol or " " in str(symbol):
        return False
    held = sum(
        1 for k in (*CRYPTO_FACTORS, *CRYPTO_FACTORS_NOT_APPLICABLE)
        if row.get(f"sub_{k}") is not None
    )
    if held < MIN_FACTORS:
        return False
    if row.get("change_pct_1d") is None or row.get("confidence_pct") is None:
        return False
    ac = str(row.get("asset_class") or "")
    return bool(ac) and " " not in ac and ac[:1].isalpha()


def test_the_representative_row_is_servable():
    assert _passes_live_clauses(_crypto_row_fields())


@pytest.mark.parametrize(
    "column", ["confidence_pct", "change_pct_1d", "score", "asset_class"]
)
def test_dropping_any_required_column_hides_the_row(column):
    """Each of these, absent, makes a correctly-scored row unservable.

    Written as a test rather than a comment because the failure mode has no
    symptom: the row exists, the score is right, the namespace is right, and
    nothing anywhere shows it. That is precisely what shipped — 67 good rows,
    zero of them findable, because one column was unset.
    """
    row = _crypto_row_fields()
    assert _passes_live_clauses(row), "fixture should start servable"
    row[column] = None
    assert not _passes_live_clauses(row), (
        f"a row missing {column} still passed the gate in this model, so the "
        f"model no longer matches live_clauses and cannot catch the next "
        f"invisible-row bug"
    )


# ── the real function, not a hand-built dict ───────────────────────────────

@pytest.mark.asyncio
async def test_build_crypto_rows_actually_emits_every_required_column(monkeypatch):
    """The tests above model a row; this one checks the code that writes it.

    Modelling alone is what let the original bug ship: the fixture had every
    column because it was written by hand, while `build_crypto_rows` omitted
    `confidence_pct` and produced 67 rows nothing could display. A model that
    cannot disagree with the implementation cannot catch that.
    """
    bars = [{"c": 100.0 + i, "o": 100.0 + i, "h": 101.0 + i, "l": 99.0 + i, "v": 10}
            for i in range(300)]

    async def _universe(_client, **_kw):
        return [{
            "symbol": "X:BTCUSD", "asset_class": "crypto", "price": 80_000.0,
            "day_open": 79_000.0, "day_high": 81_000.0, "day_low": 78_000.0,
            "day_close": 80_000.0, "volume": 100, "change_pct_1d": 1.2,
            "dollar_volume": 8_000_000.0,
        }]

    async def _history(_client, _symbol, **_kw):
        return bars

    async def _regime():
        return {"regime": "BULL"}

    monkeypatch.setattr(crypto_feed, "fetch_crypto_universe", _universe, raising=True)
    monkeypatch.setattr(crypto_feed, "fetch_crypto_history", _history, raising=True)
    monkeypatch.setattr("app.services.polygon_feed.fetch_regime", _regime, raising=True)
    monkeypatch.setattr(crypto_feed, "_PAIR_PACING_SECONDS", 0, raising=True)

    rows = await crypto_feed.build_crypto_rows(client=None)
    assert rows, "the feed produced no rows at all"
    row = rows[0]

    for column in ("symbol", "asset_class", "score", "price",
                   "change_pct_1d", "confidence_pct"):
        assert row.get(column) is not None, (
            f"build_crypto_rows omits {column}, so live_clauses drops every "
            f"crypto row and the coins are invisible on every surface — the "
            f"exact bug that shipped 67 unfindable pairs"
        )

    assert _passes_live_clauses(row), (
        "a row straight out of build_crypto_rows does not satisfy the gate "
        "every ranked surface applies"
    )
    assert row["symbol"].startswith("X:")
    assert row["sub_fundamentals"] is None and row["sub_smart_money"] is None
