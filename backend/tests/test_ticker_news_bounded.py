"""Regression guard for the 2026-06-01 ticker news-scan death-spiral.

GET /api/ticker/{symbol} once served per-ticker headlines via an UNBOUNDED
``tickers LIKE '%SYM%' ORDER BY published_at DESC LIMIT 8``. The leading-
wildcard LIKE can't use the tickers index, so Postgres walked the
``published_at`` index newest-to-oldest filtering every row until it found 8
matches. For a symbol rare in recent news (TSLA, GME, BABA, ...) that walk ran
to the end of the table -- a 30s+ hang holding a pooled connection. Under
fan-out (the daily SEO audit / a crawl) those holds exhausted the connection
pool and 500'd EVERY /t page (latency death-spiral).

The fix (commits 4ddd98a / 3fd0453) bounds the scan three ways, all inside
``app.routers.ticker``: a recency window (NEWS_LOOKBACK_DAYS), a Postgres
per-statement timeout (NEWS_QUERY_TIMEOUT_MS), and an isolated, degrade-to-[]
helper (_fetch_ticker_news).

If this test fails, ticker.py has reverted to the unbounded query. DO NOT
MERGE the revert -- re-apply the bound before the page-killing hang returns.
"""
from app.routers import ticker


def test_ticker_news_scan_stays_bounded() -> None:
    # The bounded-scan helper must still exist and be the thing the request
    # path uses (the old code built `news_payload` from an inline LIKE query).
    assert hasattr(ticker, "_fetch_ticker_news"), (
        "ticker._fetch_ticker_news is gone -- the per-ticker news scan reverted "
        "to the unbounded inline LIKE query (2026-06-01 death-spiral). Re-apply "
        "the recency window + statement timeout before merging."
    )

    # Recency window: a sane, positive day-cap that keeps the index walk bounded.
    assert hasattr(ticker, "NEWS_LOOKBACK_DAYS"), "NEWS_LOOKBACK_DAYS removed"
    assert 0 < ticker.NEWS_LOOKBACK_DAYS <= 365

    # Postgres per-statement timeout backstop must stay set (> 0 ms).
    assert hasattr(ticker, "NEWS_QUERY_TIMEOUT_MS"), "NEWS_QUERY_TIMEOUT_MS removed"
    assert ticker.NEWS_QUERY_TIMEOUT_MS > 0
