"""Crypto news must never be the wrong company's news.

The vendor tags crypto articles with the BARE base symbol. Verified against the
live feed on 2026-09-07:

    ?ticker=X:BTCUSD  ->  0 items
    ?ticker=BTC       ->  "Bitcoin Leads Crypto Surge on Tuesday"

So reading crypto news at all means querying the bare form — and that is the
SOL/Emeren collision one layer up. "SOL" in a news feed could be Solana or
Emeren Group, a real NYSE solar company. "EOS" could be the token or Eaton
Vance Enhanced Equity Income II. "LEO" the token or BNY Mellon. Those four
symbols already had a token's PRICE published on their pages on 2026-09-03;
attaching the wrong company's headlines is the same class of false statement
about a named security, and it is not made harmless by being "only news".

Hence an allowlist rather than a transformation. A coin that is not on it shows
no news, which is honest. Stripping the prefix and hoping is not.
"""
from __future__ import annotations

import inspect

import pytest

from app.services.crypto_feed import CRYPTO_NEWS_TAGS, crypto_news_tag

#: The four symbols from the incident. Each is a real listed company AND a token.
INCIDENT_SYMBOLS = ["SOL", "EOS", "LEO", "BGB"]


@pytest.mark.parametrize("base", INCIDENT_SYMBOLS)
def test_the_incident_symbols_are_not_allowlisted(base):
    """These are exactly the ones that must never borrow a company's headlines."""
    assert crypto_news_tag(f"X:{base}USD") is None, (
        f"X:{base}USD would read news tagged {base!r}, which is also a real "
        f"listed company — the 2026-09-03 collision, in the news layer"
    )
    assert base not in CRYPTO_NEWS_TAGS.values()


def test_the_majors_do_resolve():
    """The allowlist has to be useful, not just safe."""
    assert crypto_news_tag("X:BTCUSD") == "BTC"
    assert crypto_news_tag("X:ETHUSD") == "ETH"
    assert crypto_news_tag("X:DOGEUSD") == "DOGE"


def test_an_unknown_pair_returns_none_rather_than_stripping_the_prefix():
    """None is the deliberate outcome, not a gap to fill with a fallback.

    A `crypto_display_symbol` fallback here is precisely what would put a solar
    company's headlines on Solana's page.
    """
    assert crypto_news_tag("X:NEWCOINUSD") is None
    assert crypto_news_tag("X:ZZZUSD") is None


def test_an_equity_symbol_is_never_translated():
    for sym in ("NVDA", "BTC", "SPY", "SOL"):
        assert crypto_news_tag(sym) is None


def test_every_allowlisted_key_is_a_namespaced_pair():
    """A bare key would silently make the lookup match equities too."""
    for key in CRYPTO_NEWS_TAGS:
        assert key.startswith("X:") and key.endswith("USD"), (
            f"{key!r} is not a namespaced pair, so it could collide with a "
            f"listed ticker of the same name"
        )


def test_the_news_lookup_uses_the_allowlist_and_not_a_prefix_strip():
    """Guards the call site, not just the helper.

    The helper being correct is worthless if the route computes its own
    fallback. This asserts the route consults `crypto_news_tag` and does not
    reach for `crypto_display_symbol`, which is display-only by contract.
    """
    from app.routers import ticker as tk

    src = inspect.getsource(tk._fetch_ticker_news)
    assert "crypto_news_tag" in src, (
        "the news lookup does not consult the allowlist, so a crypto page "
        "either shows nothing or shows another company's headlines"
    )
    assert "crypto_display_symbol" not in src, (
        "the news lookup falls back to the display symbol; that is exactly "
        "how Emeren Group's headlines reach Solana's page"
    )
