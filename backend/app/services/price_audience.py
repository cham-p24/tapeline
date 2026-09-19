"""Who may be served vendor prices, and what a keyless caller gets instead.

WHY THIS EXISTS (2026-09-19)
----------------------------
Our market-data plan (Massive Stocks Starter) is individual-use, and Massive's
own knowledge base calls showing prices in an app "almost certainly
redistribution". The widest exposure was never the pages people read: it was
the KEYLESS machine-readable surfaces, where anyone could pull the whole
universe's prices as JSON with no account and no key and re-serve them —
`/api/public/signals` (2,000 rows a request, offset-walkable), the MCP server,
`/api/ticker/{symbol}` for anonymous callers, and the sector heatmap aggregate.

So those surfaces now split their audience in two:

* **Signed-in users and our own server-side renders** keep prices. The in-app
  pages and the public HTML ticker pages are unchanged by this module; whether
  the plan covers DISPLAY is a separate licence question, not settled here.
  Our own SSR is recognised by the INTERNAL_SSR_TOKEN shared secret, the same
  one the rate limiter already trusts (see `is_trusted_ssr`).
* **Everyone else** — a script, a scraper, an agent, a browser with no session
  — gets scores, labels, ranks and the six sub-scores, and no price, no daily
  move, no OHLC, no volume, no market cap.

The keyed Premium `/api/v1` is NOT routed through here and still carries
prices. The scorecard CSV/JSON exports are a named exception too (close-only,
seven days delayed for anonymous callers), and so are the record rows the
ticker payload embeds, which come from the same archive.

An UNSET token degrades safely: our own SSR is then treated as keyless, so the
SEO pages render dashes where prices were. That is a visible, reversible
failure in the safe direction, never a leak.
"""
from __future__ import annotations

import secrets
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

#: Header our own frontend's server runtime sends (frontend/lib/ssrHeaders.ts).
INTERNAL_SSR_HEADER = "x-tapeline-internal"

#: What a keyless response says instead of carrying prices. Factual, and it
#: names the two ways a price IS available rather than implying there is none.
KEYLESS_PRICE_NOTE = (
    "Prices, daily moves, volume and market cap are not served through this "
    "endpoint without a signed-in session. Scores, labels and sub-scores are."
)

#: Root-level fields on a ticker row that are vendor market data (or a move
#: that inverts back to a price). Stripped for keyless callers.
PRICE_FIELDS: tuple[str, ...] = (
    "price",
    "change_pct_1d",
    "change_pct_5d",
    "change_pct_1m",
    "volume",
    "market_cap",
)

#: `key_stats` fields stripped for keyless callers: the price block, the
#: volumes and market cap, and the Finnhub-sourced valuation numbers (Finnhub's
#: terms bar sharing its data with third parties; P/E is also price-derived).
#: The two dates (next earnings, ex-dividend) stay.
KEY_STATS_PRICE_FIELDS: tuple[str, ...] = (
    "price",
    "previous_close",
    "day_open",
    "day_low",
    "day_high",
    "week52_low",
    "week52_high",
    "volume",
    "avg_volume_30d",
    "market_cap",
    "beta",
    "pe_ttm",
    "eps_ttm",
    "dividend_yield",
)


def is_trusted_ssr(request: Request, *, token: str | None = None) -> bool:
    """True when this request carries our own SSR shared secret.

    Constant-time compare, and an unset token disables the trust entirely, so a
    missing or mis-set secret degrades to "treat as an anonymous caller" rather
    than opening anything. The token is server-only on the frontend (never
    NEXT_PUBLIC_*), so it is not reachable from a browser bundle.

    `token` lets main.py's rate limiter pass the value from its own settings
    object; everyone else reads it from get_settings(). In production they are
    the same object.
    """
    if token is None:
        token = get_settings().internal_ssr_token
    if not token:
        return False
    presented = request.headers.get(INTERNAL_SSR_HEADER)
    if not presented:
        return False
    return secrets.compare_digest(presented, token)


async def may_see_prices(request: Request, session: AsyncSession) -> bool:
    """True for our own SSR and for any signed-in user; False for keyless callers.

    SSR is checked first so the common case (a crawled public page) costs no
    auth read at all.
    """
    if is_trusted_ssr(request):
        return True
    from app.services.auth import current_user_optional

    return await current_user_optional(request, session) is not None


def strip_price_fields(row: dict[str, Any]) -> dict[str, Any]:
    """A copy of a ticker-shaped dict without the market-data fields."""
    out = {k: v for k, v in row.items() if k not in PRICE_FIELDS}
    stats = out.get("key_stats")
    if isinstance(stats, dict):
        out["key_stats"] = {
            k: v for k, v in stats.items() if k not in KEY_STATS_PRICE_FIELDS
        }
    return out
