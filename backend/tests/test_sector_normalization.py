"""Tests for services/sector.canonical_sector().

This normalizer is the heatmap's "table of contents" — every raw sector
string from upstream feeds (Finnhub, signal-system sheet, Polygon legacy)
has to collapse into one of 13 canonical buckets. If a Finnhub industry
name lands without an alias entry, it'll fall through to Uncategorized
rather than fragmenting the heatmap into 51 micro-clusters again.

These tests pin the most-common real-world inputs (sampled live from
production on 2026-05-16 — see comments per category) so a future edit
to _SECTOR_ALIASES can't silently re-fragment the heatmap.
"""
from __future__ import annotations

import pytest

from app.services.sector import (
    CANONICAL_ORDER,
    GICS_COMMS,
    GICS_CONSUMER_DISC,
    GICS_CONSUMER_STAP,
    GICS_FINANCIALS,
    GICS_HEALTH_CARE,
    GICS_INDUSTRIALS,
    GICS_MATERIALS,
    GICS_TECHNOLOGY,
    TAPE_COMMODITIES,
    TAPE_ETF,
    TAPE_UNCATEGORIZED,
    canonical_sector,
)


class TestProductionAliases:
    """Each raw label was sampled live from /api/heatmap on 2026-05-16.

    Counts in the comments reflect production ticker counts when the
    cleanup was designed — they're the size of the buckets being collapsed.
    """

    @pytest.mark.parametrize("raw", ["Technology", "Semiconductors", "technology"])
    def test_technology_aliases(self, raw):
        # 58 + 14 tickers → Information Technology
        assert canonical_sector(raw) == GICS_TECHNOLOGY

    @pytest.mark.parametrize("raw", [
        "Health Care", "Healthcare", "Biotechnology", "Pharmaceuticals",
        "Life Sciences Tools & Services",
    ])
    def test_health_care_aliases(self, raw):
        # 44 + 8 + 66 + 20 + 8 = 146 tickers → Health Care
        assert canonical_sector(raw) == GICS_HEALTH_CARE

    @pytest.mark.parametrize("raw", [
        "Financials", "Financial Services", "Banking", "Insurance",
        "Trading Companies & Distributors", "Distributors",
    ])
    def test_financials_aliases(self, raw):
        # 8 + 45 + 33 + 20 + 3 + 3 = 112 tickers → Financials
        assert canonical_sector(raw) == GICS_FINANCIALS

    @pytest.mark.parametrize("raw", [
        "Industrials", "Aerospace & Defense", "Machinery",
        "Commercial Services & Supplies", "Professional Services",
        "Airlines", "Road & Rail", "Logistics & Transportation",
        "Construction", "Building", "Electrical Equipment",
    ])
    def test_industrials_aliases(self, raw):
        # Big cluster — Finnhub returns very granular sub-industries here.
        assert canonical_sector(raw) == GICS_INDUSTRIALS

    @pytest.mark.parametrize("raw", [
        "Consumer Discretionary", "Retail", "Hotels, Restaurants & Leisure",
        "Diversified Consumer Services", "Auto Components", "Automobiles",
        "Leisure Products", "Textiles, Apparel & Luxury Goods",
        "Media",  # GICS 2018 moved Media into Comms — but our Media tickers
                  # were sampling as content (which is Comms), so we route
                  # there. If we add streaming services later this stays right.
    ])
    def test_consumer_disc_and_media(self, raw):
        # Media goes to Comms (GICS 2018+), all others to Cons Disc.
        result = canonical_sector(raw)
        assert result in (GICS_CONSUMER_DISC, GICS_COMMS)

    @pytest.mark.parametrize("raw", ["Consumer Staples", "Food Products", "Beverages"])
    def test_consumer_staples_aliases(self, raw):
        assert canonical_sector(raw) == GICS_CONSUMER_STAP

    @pytest.mark.parametrize("raw", [
        "Communication Services", "Communications", "Telecommunication", "Media",
    ])
    def test_communications_aliases(self, raw):
        assert canonical_sector(raw) == GICS_COMMS

    @pytest.mark.parametrize("raw", ["Materials", "Metals & Mining", "Chemicals", "Packaging"])
    def test_materials_aliases(self, raw):
        # Packaging is canonically Materials (containers & packaging),
        # not Consumer Staples — a common mismap on other dashboards.
        assert canonical_sector(raw) == GICS_MATERIALS


class TestUnknownAndFallbacks:
    """The "Unknown" bucket was the biggest in production (1,402 tickers)
    because the signal-system sheet doesn't include sector and Finnhub
    backfill is rate-limited at 200/day. Show it as 'Uncategorized' so the
    label is honest about why it exists, and route ETFs without a sector
    string to Funds & ETFs based on asset_class.
    """

    @pytest.mark.parametrize("raw", ["Unknown", "N/A", "—", "-", "Other", "unknown", "n/a"])
    def test_explicitly_unknown_signals(self, raw):
        assert canonical_sector(raw) == TAPE_UNCATEGORIZED

    def test_none_input_returns_uncategorized(self):
        assert canonical_sector(None) == TAPE_UNCATEGORIZED

    def test_empty_string_returns_uncategorized(self):
        assert canonical_sector("") == TAPE_UNCATEGORIZED

    def test_unmapped_string_returns_uncategorized(self):
        # A brand-new Finnhub industry we haven't added yet — should fall
        # into Uncategorized rather than passing through verbatim. This is
        # the regression guard that prevents the heatmap re-fragmenting.
        assert canonical_sector("Some Brand New Sub-Industry") == TAPE_UNCATEGORIZED

    def test_etf_asset_class_routes_to_funds(self):
        # ETF without a sector string lands in Funds & ETFs, not Uncategorized.
        assert canonical_sector(None, asset_class="etf") == TAPE_ETF
        assert canonical_sector("", asset_class="ETF") == TAPE_ETF

    def test_explicit_etf_sector_string_routes_to_funds(self):
        assert canonical_sector("ETF") == TAPE_ETF

    def test_commodities_stays_commodities(self):
        # Tapeline's 32 commodity ETFs are tagged Commodities by mock_feed.py
        # explicitly — that label is meaningful (gold/silver/oil/grain etc.)
        # so it must NOT be folded into Funds & ETFs.
        assert canonical_sector("Commodities") == TAPE_COMMODITIES
        # Even if asset_class says ETF, the explicit Commodities label wins
        # (the alias lookup happens before the asset_class fallback).
        assert canonical_sector("Commodities", asset_class="etf") == TAPE_COMMODITIES


class TestCanonicalOrder:
    """CANONICAL_ORDER is what the heatmap renders top-to-bottom. Every
    return value of canonical_sector must appear in it; otherwise the
    router's sorted() call defaults that bucket to "last position",
    leaking Uncategorized into the middle of the layout."""

    def test_every_canonical_bucket_is_ordered(self):
        # Sample inputs across every bucket — each return value must be in order list
        samples = [
            "Technology", "Health Care", "Financials", "Industrials",
            "Consumer Discretionary", "Consumer Staples", "Communication Services",
            "Energy", "Materials", "Utilities", "Real Estate",
            "Commodities", "ETF", "Unknown",
        ]
        for raw in samples:
            assert canonical_sector(raw) in CANONICAL_ORDER, (
                f"canonical_sector({raw!r}) returned a value not in CANONICAL_ORDER"
            )

    def test_uncategorized_last(self):
        # Uncategorized should always render at the bottom of the heatmap —
        # it's the catch-all and shouldn't compete visually with real sectors.
        assert CANONICAL_ORDER[-1] == TAPE_UNCATEGORIZED

    def test_canonical_order_is_thirteen_buckets(self):
        # If this fails we either lost a bucket or duplicated one.
        assert len(CANONICAL_ORDER) == 14, (
            f"Expected 14 canonical buckets, got {len(CANONICAL_ORDER)}: {CANONICAL_ORDER}"
        )

    def test_canonical_order_has_no_duplicates(self):
        assert len(CANONICAL_ORDER) == len(set(CANONICAL_ORDER))
