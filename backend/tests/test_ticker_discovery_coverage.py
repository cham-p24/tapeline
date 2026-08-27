"""Universe discovery must cover the market, not a prefix of the alphabet.

Two independent defects made `discover_active_us_tickers` blind to most of the
US market. Measured against the live vendor on 2026-08-27:

1. ALPHABETICAL TRUNCATION. `max_tickers` defaulted to 5,000 and the loop is
   `while next_url and len(rows) < max_tickers`, so the cap counts ACCEPTED
   rows. The vendor returns tickers in ascending symbol order, so a binding cap
   does not sample the market — it cuts it off at a letter. There are 13,148
   active US tickers; 5,000 accepted lands around H/I. Everything from roughly
   I to Z was never discovered, and therefore never had `name` or
   `asset_class` reconciled either.

   The live symptom: a 2,463-row universe holding 750 A-tickers, 626 B, 671 C
   — and exactly ONE E-ticker, in a market with hundreds (EBAY, EOG, EQT, EL,
   EW, EXC...). The placeholder-name defect clustered the same way: 91% of
   P-tickers had no company name, versus 0.1% of A-tickers.

2. TOO-NARROW TYPE FILTER. `if ttype not in ("CS", "ETF")` dropped:
     * ADRC (376 active) — American Depositary Receipts, i.e. EVERY US-listed
       foreign company. The vendor types ASML as ADRC, not CS.
     * ETV (90 active) — commodity trusts: GLD, SLV, USO. That is Tapeline's
       entire "Commodities" sector.
   Both categories are already sold in the product, so they could not be
   discovered OR repaired.

These tests pin the coverage and, just as importantly, pin the EXCLUSIONS —
widening this filter to everything the vendor returns would put warrants,
rights and SPAC units into a scanner whose six factors assume an equity-like
price series.
"""

import pytest

from app.services.polygon_feed import (
    DISCOVERY_MAX_TICKERS,
    VENDOR_TYPE_TO_ASSET_CLASS,
    discover_active_us_tickers,
)

# ---------------------------------------------------------------------------
# Instrument coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "vendor_type,expected_class,why",
    [
        ("CS", "equity", "ordinary common stock"),
        ("ADRC", "equity", "ASML and every other US-listed foreign company"),
        ("ETF", "etf", "ordinary ETFs"),
        ("ETV", "etf", "GLD/SLV/USO — Tapeline's whole Commodities sector"),
        ("ETS", "etf", "single-security ETF"),
        ("ETN", "etf", "exchange-traded note"),
    ],
)
def test_scoreable_instrument_types_are_included(vendor_type, expected_class, why):
    assert VENDOR_TYPE_TO_ASSET_CLASS.get(vendor_type) == expected_class, (
        f"{vendor_type} ({why}) is not discoverable"
    )


@pytest.mark.parametrize(
    "vendor_type",
    ["PFD", "WARRANT", "RIGHT", "UNIT", "SP", "FUND", "BOND", "BASKET", "OTHER"],
)
def test_non_equity_instrument_types_stay_excluded(vendor_type):
    """The fix for a too-narrow filter is not "accept everything".

    A trend/momentum read on a warrant or a SPAC unit is noise, and closed-end
    funds trade at NAV premiums and discounts, so a price-derived composite
    means something different for them. Including those is a product decision,
    not a bug fix.
    """
    assert vendor_type not in VENDOR_TYPE_TO_ASSET_CLASS


def test_asml_would_be_typed_equity_and_gld_etf():
    """The two symbols that proved the defect. Kept as an explicit case so the
    mapping cannot be 'tidied' back into a CS/ETF-only tuple."""
    assert VENDOR_TYPE_TO_ASSET_CLASS["ADRC"] == "equity"
    assert VENDOR_TYPE_TO_ASSET_CLASS["ETV"] == "etf"


# ---------------------------------------------------------------------------
# The cap must not bind
# ---------------------------------------------------------------------------


def test_the_cap_is_far_above_the_real_market_size():
    """13,148 active US tickers on 2026-08-27, ~11,400 of them scoreable types.

    The cap is a runaway guard, not a sizing knob: because it counts accepted
    rows against a symbol-ordered feed, any cap that actually binds truncates
    the universe alphabetically.
    """
    assert DISCOVERY_MAX_TICKERS >= 20_000, (
        f"cap {DISCOVERY_MAX_TICKERS} is close enough to the real market size "
        f"(~11.4k scoreable of 13.1k active) to risk cutting the universe off "
        f"at a letter again"
    )


# ---------------------------------------------------------------------------
# End-to-end over a faked vendor
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _install_fake_vendor(monkeypatch, pages):
    """Serve `pages` sequentially, regardless of URL/params."""
    from app.services import polygon_feed

    monkeypatch.setattr(polygon_feed, "_api_key", lambda: "test-key")

    calls = {"n": 0}

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, headers=None):
            i = calls["n"]
            calls["n"] += 1
            return _FakeResponse(pages[i] if i < len(pages) else {"results": []})

    monkeypatch.setattr(
        polygon_feed.httpx, "AsyncClient", lambda *a, **k: _FakeClient()
    )
    return calls


@pytest.mark.asyncio
async def test_discovery_returns_adrs_and_commodity_trusts(monkeypatch):
    _install_fake_vendor(
        monkeypatch,
        [
            {
                "results": [
                    {"ticker": "ASML", "name": "ASML Holding NV", "type": "ADRC"},
                    {"ticker": "GLD", "name": "SPDR Gold Trust", "type": "ETV"},
                    {"ticker": "AAPL", "name": "Apple Inc.", "type": "CS"},
                    {"ticker": "SPY", "name": "SPDR S&P 500", "type": "ETF"},
                    # must NOT come through
                    {"ticker": "ZZWS", "name": "Zebra Warrant", "type": "WARRANT"},
                    {"ticker": "ZZPF", "name": "Zebra Preferred", "type": "PFD"},
                    {"ticker": "ZZUN", "name": "Zebra Unit", "type": "UNIT"},
                ],
                "next_url": None,
            }
        ],
    )
    rows = await discover_active_us_tickers()
    by_sym = {r["symbol"]: r for r in rows}

    assert by_sym["ASML"]["asset_class"] == "equity"
    assert by_sym["ASML"]["name"] == "ASML Holding NV"
    assert by_sym["GLD"]["asset_class"] == "etf"
    assert by_sym["AAPL"]["asset_class"] == "equity"
    assert by_sym["SPY"]["asset_class"] == "etf"

    for excluded in ("ZZWS", "ZZPF", "ZZUN"):
        assert excluded not in by_sym, f"{excluded} should not be scoreable"


@pytest.mark.asyncio
async def test_discovery_pages_past_the_first_response(monkeypatch):
    """The alphabetical truncation only shows up across pages, so a
    single-page test would pass against the broken version."""
    calls = _install_fake_vendor(
        monkeypatch,
        [
            {
                "results": [{"ticker": "AAA", "name": "Aaa Corp", "type": "CS"}],
                "next_url": "https://vendor/page2",
            },
            {
                "results": [{"ticker": "ZZZ", "name": "Zzz Corp", "type": "CS"}],
                "next_url": None,
            },
        ],
    )
    rows = await discover_active_us_tickers()
    syms = {r["symbol"] for r in rows}
    assert syms == {"AAA", "ZZZ"}, (
        "the walk stopped after the first page, so late-alphabet tickers are "
        "never discovered"
    )
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_a_binding_cap_is_logged_as_an_error(monkeypatch, caplog):
    """Silent truncation is the whole bug. If the cap ever binds again it must
    be impossible to miss in the logs."""
    _install_fake_vendor(
        monkeypatch,
        [
            {
                "results": [
                    {"ticker": f"S{i:04d}", "name": f"Co {i}", "type": "CS"}
                    for i in range(5)
                ],
                "next_url": "https://vendor/page2",
            }
        ],
    )
    with caplog.at_level("ERROR"):
        await discover_active_us_tickers(max_tickers=3)
    assert any("TRUNCATED" in r.message for r in caplog.records), (
        "a binding cap truncated the universe without an error log"
    )
