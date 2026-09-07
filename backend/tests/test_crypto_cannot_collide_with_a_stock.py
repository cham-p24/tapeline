"""A coin must never be storable under a real company's ticker.

On 2026-09-03 production published a token's price on four real listed
companies' pages:

    SOL  Emeren Group Ltd (NYSE solar, ~$1.94)   published at $64.45  (Solana)
    EOS  Eaton Vance Enhanced Equity Income II   published at $0.0625 (EOS)
    BGB  Blackstone Strategic Credit 2027 Term   published at $1.8568
    LEO  BNY Mellon Strategic Municipals Inc     published at $6.15   (UNUS SED LEO)

Each carried a six-factor score and a signal label on a public per-ticker page
with JSON-LD, under a no-AFSL publisher posture. That is a false statement of
fact about a named, real, listed security — the most serious defect this
product can produce, and worse than serving nothing.

The vendor namespaces pairs (`X:SOLUSD`), and keeping that prefix all the way
into the database makes the collapse unrepresentable. The tests below exist
because the first draft of `crypto_feed` did NOT do that: it called
`clean_symbol(..., allow_crypto=True)`, which WIDENS the accepted set rather
than narrowing it, so a bare "SOL" arriving from the crypto endpoint sailed
through and produced `{"symbol": "SOL", "asset_class": "crypto"}` — the
incident, reintroduced. A smoke test caught it before it ran once.
"""
from __future__ import annotations

import pytest

from app.services.crypto_feed import (
    CRYPTO_FACTORS,
    CRYPTO_FACTORS_NOT_APPLICABLE,
    _row_from_bar,
    pct_change,
)
from app.services.symbols import (
    clean_symbol,
    crypto_display_symbol,
    is_crypto_symbol,
)

#: The four symbols from the incident, plus the obvious near-misses.
COLLIDING_TICKERS = ["SOL", "EOS", "BGB", "LEO", "BTC", "ETH", "XRP", "DOGE"]


@pytest.mark.parametrize("ticker", COLLIDING_TICKERS)
def test_a_bare_symbol_from_the_crypto_feed_is_refused(ticker):
    """The incident itself. A bare ticker must never become a crypto row."""
    row = _row_from_bar({"T": ticker, "c": 64.45, "o": 60.0, "v": 1_000_000})
    assert row is None, (
        f"the crypto feed accepted the bare ticker {ticker!r} and produced "
        f"{row!r} — that row would be written over the real listed company of "
        f"the same name, which is exactly the 2026-09-03 incident"
    )


@pytest.mark.parametrize("ticker", COLLIDING_TICKERS)
def test_the_namespaced_form_of_the_same_symbol_is_accepted(ticker):
    """The prefix is what makes the coin safe to store, so it must work."""
    row = _row_from_bar({"T": f"X:{ticker}USD", "c": 64.45, "o": 60.0, "v": 1_000_000})
    assert row is not None, f"X:{ticker}USD was rejected"
    assert row["symbol"] == f"X:{ticker}USD"
    assert row["asset_class"] == "crypto"


def test_the_stored_symbol_keeps_the_prefix():
    """Display may shorten it; storage may not.

    `crypto_display_symbol` exists so a page can show "BTC" as a heading. If
    that shortened form were ever used as a key, the collision is back.
    """
    row = _row_from_bar({"T": "X:BTCUSD", "c": 79675.12, "o": 78000.0, "v": 13653})
    assert row["symbol"] == "X:BTCUSD"
    assert crypto_display_symbol(row["symbol"]) == "BTC"
    assert crypto_display_symbol("BTC") is None, (
        "a bare ticker was treated as a crypto symbol by the display helper"
    )


def test_the_workbook_parser_still_refuses_crypto_symbols():
    """`allow_crypto` is opt-in, and the sheet must never opt in.

    The workbook is a human-typed column and is where the collision actually
    came from. Widening `clean_symbol`'s default would re-open that door for
    every caller at once.
    """
    assert clean_symbol("X:BTCUSD") is None, (
        "clean_symbol accepts a crypto pair by default, so any caller — "
        "including the workbook parser — now ingests them"
    )
    assert clean_symbol("X:BTCUSD", allow_crypto=True) == "X:BTCUSD"


def test_equity_symbols_are_unaffected():
    """Adding a shape must not remove one. Futures and class shares still pass."""
    for sym in ("AAPL", "BRK.B", "BRK-B", "CL=F", "ZC=F", "SPY", "SOL"):
        assert clean_symbol(sym) == sym, f"{sym} stopped validating"
        assert not is_crypto_symbol(sym)


@pytest.mark.parametrize("junk", ["X:BAD", "X:USD", "X:TOOLONGSYMBOLUSD", "X:", "XBTCUSD", "x:btcusd "])
def test_malformed_pairs_are_refused(junk):
    """The prefix is not a licence to accept anything after it."""
    if junk.strip().upper() == "X:BTCUSD":
        pytest.skip("that one is well-formed once normalised")
    assert _row_from_bar({"T": junk, "c": 1.0, "o": 1.0, "v": 1}) is None


# ── the row itself ─────────────────────────────────────────────────────────

def test_a_zero_or_missing_price_is_skipped_not_published():
    """A no-read is not a value — the rule the whole feed layer runs on."""
    for bar in ({"T": "X:BTCUSD", "c": 0}, {"T": "X:BTCUSD", "c": None},
                {"T": "X:BTCUSD"}, {"T": "X:BTCUSD", "c": "79675"}):
        assert _row_from_bar(bar) is None, f"published a row for {bar!r}"


def test_the_days_move_is_computed_from_the_days_own_bar():
    row = _row_from_bar({"T": "X:ETHUSD", "c": 110.0, "o": 100.0, "v": 5})
    assert row["change_pct_1d"] == pytest.approx(10.0)


def test_a_missing_open_leaves_the_move_absent_rather_than_zero():
    """0.0% is a claim the coin did not move. None is the truth."""
    row = _row_from_bar({"T": "X:ETHUSD", "c": 110.0, "v": 5})
    assert row["change_pct_1d"] is None


def test_dollar_volume_uses_price_times_units():
    row = _row_from_bar({"T": "X:BTCUSD", "c": 80_000.0, "o": 79_000.0, "v": 10})
    assert row["dollar_volume"] == pytest.approx(800_000.0)


# ── history ────────────────────────────────────────────────────────────────

def test_a_short_history_returns_none_not_zero():
    """A coin listed three weeks ago has no 3-month return.

    Zero would score it as "flat", which is a measurement. Absent is the fact,
    and the composite already knows how to refuse a row with too few factors.
    """
    bars = [{"c": 100.0}] * 10
    assert pct_change(bars, 90) is None
    assert pct_change(bars, 5) == pytest.approx(0.0)


def test_pct_change_reads_the_right_end_of_the_series():
    bars = [{"c": 100.0}, {"c": 105.0}, {"c": 110.0}]
    assert pct_change(bars, 1) == pytest.approx(110 / 105 * 100 - 100)
    assert pct_change(bars, 2) == pytest.approx(10.0)


# ── the factor split ───────────────────────────────────────────────────────

def test_the_two_impossible_factors_are_named_not_faked():
    """A token has no revenue and no directors filing with the SEC.

    Scoring those as NEUTRAL 50 would put a placeholder in the same column as
    a real reading, indistinguishable from one. They are declared absent so
    the front end can grey the spoke and say why.
    """
    assert set(CRYPTO_FACTORS_NOT_APPLICABLE) == {"fundamentals", "smart_money"}
    assert not set(CRYPTO_FACTORS) & set(CRYPTO_FACTORS_NOT_APPLICABLE)
    assert len(CRYPTO_FACTORS) + len(CRYPTO_FACTORS_NOT_APPLICABLE) == 6, (
        "the six-factor composite has six factors; crypto must account for "
        "all of them as either applicable or explicitly not"
    )
