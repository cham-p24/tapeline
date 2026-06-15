"""Canonical sector normalization.

Tickers land in Tapeline with sector strings from three different feeds:
the signal-system Google Sheet (often blank → "Unknown"), Finnhub
(`/stock/profile2` returns specific industry strings like
"Pharmaceuticals" or "Biotechnology"), and Polygon (legacy, rough GICS-
ish). Without normalization the heatmap renders 51 "sectors" — many of
them subsectors (Biotech, Pharma) that should roll up to Health Care,
and several near-duplicates ("Health Care" vs "Healthcare", "Financials"
vs "Financial Services" vs "Banking").

`canonical_sector()` maps any of those raw strings to one of 13 buckets:

  - 11 GICS top-level sectors
  - "Funds & ETFs" — for ETF-asset-class tiles
  - "Commodities" — Tapeline's own grouping for commodity-exposure ETFs
  - "Uncategorized" — the new label for tickers whose sector hasn't been
    backfilled yet (replaces the noisier "Unknown" / "N/A" strings)

Unknown raw strings fall through to "Uncategorized" rather than passing
through verbatim, so a new Finnhub industry name we haven't mapped won't
silently fragment the heatmap.
"""
from __future__ import annotations

# The 13 canonical sectors. Stable identity; UI sorts by ticker count.
GICS_TECHNOLOGY     = "Information Technology"
GICS_HEALTH_CARE    = "Health Care"
GICS_FINANCIALS     = "Financials"
GICS_INDUSTRIALS    = "Industrials"
GICS_CONSUMER_DISC  = "Consumer Discretionary"
GICS_CONSUMER_STAP  = "Consumer Staples"
GICS_COMMS          = "Communication Services"
GICS_ENERGY         = "Energy"
GICS_MATERIALS      = "Materials"
GICS_UTILITIES      = "Utilities"
GICS_REAL_ESTATE    = "Real Estate"
TAPE_COMMODITIES    = "Commodities"
TAPE_ETF            = "Funds & ETFs"
TAPE_UNCATEGORIZED  = "Uncategorized"


# Lowercased lookup — every raw string we've seen in production data plus a
# few obvious aliases. Add to this dict rather than spreading branching logic.
# Keys are matched case-insensitive against the trimmed raw sector string.
_SECTOR_ALIASES: dict[str, str] = {
    # Technology
    "technology":                       GICS_TECHNOLOGY,
    "information technology":           GICS_TECHNOLOGY,
    "semiconductors":                   GICS_TECHNOLOGY,
    "software":                         GICS_TECHNOLOGY,
    "tech":                             GICS_TECHNOLOGY,

    # Health Care
    "health care":                      GICS_HEALTH_CARE,
    "healthcare":                       GICS_HEALTH_CARE,
    "biotechnology":                    GICS_HEALTH_CARE,
    "biotech":                          GICS_HEALTH_CARE,
    "pharmaceuticals":                  GICS_HEALTH_CARE,
    "pharma":                           GICS_HEALTH_CARE,
    "life sciences tools & services":   GICS_HEALTH_CARE,
    "medical devices":                  GICS_HEALTH_CARE,
    "health":                           GICS_HEALTH_CARE,

    # Financials
    "financials":                       GICS_FINANCIALS,
    "financial services":               GICS_FINANCIALS,
    "banking":                          GICS_FINANCIALS,
    "banks":                            GICS_FINANCIALS,
    "insurance":                        GICS_FINANCIALS,
    "trading companies & distributors": GICS_FINANCIALS,
    "distributors":                     GICS_FINANCIALS,
    "capital markets":                  GICS_FINANCIALS,
    "consumer finance":                 GICS_FINANCIALS,

    # Industrials — biggest cluster because Finnhub returns very granular
    # sub-industries (Aerospace, Machinery, Logistics, Construction...).
    "industrials":                      GICS_INDUSTRIALS,
    "aerospace & defense":              GICS_INDUSTRIALS,
    "aerospace and defense":            GICS_INDUSTRIALS,
    "defense":                          GICS_INDUSTRIALS,
    "machinery":                        GICS_INDUSTRIALS,
    "commercial services & supplies":   GICS_INDUSTRIALS,
    "professional services":            GICS_INDUSTRIALS,
    "airlines":                         GICS_INDUSTRIALS,
    "road & rail":                      GICS_INDUSTRIALS,
    "rail":                             GICS_INDUSTRIALS,
    "logistics & transportation":       GICS_INDUSTRIALS,
    "transportation":                   GICS_INDUSTRIALS,
    "construction":                     GICS_INDUSTRIALS,
    "construction & engineering":       GICS_INDUSTRIALS,
    "building":                         GICS_INDUSTRIALS,
    "building products":                GICS_INDUSTRIALS,
    "electrical equipment":             GICS_INDUSTRIALS,

    # Consumer Discretionary
    "consumer discretionary":           GICS_CONSUMER_DISC,
    "retail":                           GICS_CONSUMER_DISC,
    "specialty retail":                 GICS_CONSUMER_DISC,
    "internet retail":                  GICS_CONSUMER_DISC,
    "hotels, restaurants & leisure":    GICS_CONSUMER_DISC,
    "hotels restaurants & leisure":     GICS_CONSUMER_DISC,
    "diversified consumer services":    GICS_CONSUMER_DISC,
    "auto components":                  GICS_CONSUMER_DISC,
    "automobiles":                      GICS_CONSUMER_DISC,
    "leisure products":                 GICS_CONSUMER_DISC,
    "textiles, apparel & luxury goods": GICS_CONSUMER_DISC,
    "consumer products":                GICS_CONSUMER_DISC,
    "household durables":               GICS_CONSUMER_DISC,

    # Consumer Staples
    "consumer staples":                 GICS_CONSUMER_STAP,
    "food products":                    GICS_CONSUMER_STAP,
    "beverages":                        GICS_CONSUMER_STAP,
    "household products":               GICS_CONSUMER_STAP,
    "personal products":                GICS_CONSUMER_STAP,
    "food & staples retailing":         GICS_CONSUMER_STAP,
    "tobacco":                          GICS_CONSUMER_STAP,

    # Communication Services (GICS 2018 reorg: includes Media now)
    "communication services":           GICS_COMMS,
    "communications":                   GICS_COMMS,
    "telecommunication":                GICS_COMMS,
    "telecommunications":               GICS_COMMS,
    "telecom":                          GICS_COMMS,
    "media":                            GICS_COMMS,
    "entertainment":                    GICS_COMMS,
    "interactive media & services":     GICS_COMMS,

    # Energy
    "energy":                           GICS_ENERGY,
    "oil & gas":                        GICS_ENERGY,
    "oil, gas & consumable fuels":      GICS_ENERGY,

    # Materials
    "materials":                        GICS_MATERIALS,
    "metals & mining":                  GICS_MATERIALS,
    "mining":                           GICS_MATERIALS,
    "chemicals":                        GICS_MATERIALS,
    "packaging":                        GICS_MATERIALS,
    "containers & packaging":           GICS_MATERIALS,
    "paper & forest products":          GICS_MATERIALS,

    # Utilities
    "utilities":                        GICS_UTILITIES,
    "electric utilities":               GICS_UTILITIES,
    "gas utilities":                    GICS_UTILITIES,
    "water utilities":                  GICS_UTILITIES,

    # Real Estate
    "real estate":                      GICS_REAL_ESTATE,
    "reits":                            GICS_REAL_ESTATE,
    "real estate investment trusts":    GICS_REAL_ESTATE,
    "real estate management":           GICS_REAL_ESTATE,

    # Tapeline-specific buckets
    "commodities":                      TAPE_COMMODITIES,
    "etf":                              TAPE_ETF,
    "etfs":                             TAPE_ETF,
    "fund":                             TAPE_ETF,
    "funds":                            TAPE_ETF,

    # Explicitly-uncategorized signals from upstream feeds
    "unknown":                          TAPE_UNCATEGORIZED,
    "n/a":                              TAPE_UNCATEGORIZED,
    "—":                                TAPE_UNCATEGORIZED,
    "-":                                TAPE_UNCATEGORIZED,
    "other":                            TAPE_UNCATEGORIZED,
}


# Display order for the heatmap — biggest GICS first (Tech / Health Care /
# Financials traditionally), then Industrials and the cyclicals, then defensives,
# then Tapeline buckets, with Uncategorized last so it doesn't clutter the top
# of the heatmap above the meaningful clusters.
CANONICAL_ORDER: list[str] = [
    GICS_TECHNOLOGY,
    GICS_HEALTH_CARE,
    GICS_FINANCIALS,
    GICS_INDUSTRIALS,
    GICS_CONSUMER_DISC,
    GICS_CONSUMER_STAP,
    GICS_COMMS,
    GICS_ENERGY,
    GICS_MATERIALS,
    GICS_UTILITIES,
    GICS_REAL_ESTATE,
    TAPE_COMMODITIES,
    TAPE_ETF,
    TAPE_UNCATEGORIZED,
]


def canonical_sector(raw: str | None, asset_class: str | None = None) -> str:
    """Return the canonical sector bucket for a raw sector string.

    Args:
        raw: The sector string from the ticker row. May be None, "Unknown",
            a Finnhub industry name, or a clean GICS sector name.
        asset_class: Optional asset_class to route ETFs to "Funds & ETFs"
            even when their sector field is blank. Commodity-exposure ETFs
            keep their "Commodities" label (set by mock_feed/sheet feeds) so
            they cluster as a thematic group rather than scatter into ETFs.

    Returns:
        One of the 13 canonical buckets. Never None, never an empty string.
        Unknown inputs fall through to "Uncategorized" rather than passing
        verbatim — a new unmapped Finnhub industry name shows up as
        Uncategorized in the heatmap until we add it to _SECTOR_ALIASES,
        rather than fragmenting the layout.
    """
    if raw:
        key = raw.strip().lower()
        if key in _SECTOR_ALIASES:
            return _SECTOR_ALIASES[key]
    # No raw match — route based on asset_class as a fallback so ETFs
    # without a specific sector land in a meaningful bucket rather than
    # Uncategorized. Commodities asset_class stays Commodities (mock_feed
    # tags its 32 commodity ETFs that way explicitly).
    if asset_class:
        ac = asset_class.strip().lower()
        if ac in ("commodity", "commodities"):
            return TAPE_COMMODITIES
        if ac in ("etf", "fund"):
            return TAPE_ETF
    return TAPE_UNCATEGORIZED
