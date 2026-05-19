"""
Tests for the walk-forward backtest script.

Covers:
  - CLI argument parsing + validation
  - Schema of the generated CSV (header, columns, footer)
  - Determinism (same input → same output)
  - Graceful behaviour when a factor is unavailable
  - The script can be invoked as a module without crashing on a tiny window
  - Live mode end-to-end with a mocked Massive HTTP layer (no real network)

These are unit-level tests against the importable functions in
`app.scripts.walk_forward_backtest`. The full CLI is exercised by parsing a
fixture argument vector via `parse_args` rather than spawning a subprocess —
keeps the suite fast and avoids any shell/quoting weirdness on Windows CI.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from app.scripts.walk_forward_backtest import (
    WEIGHTS,
    BacktestConfig,
    FactorAvailability,
    main,
    parse_args,
    render_csv,
    run_backtest,
)
from app.services import historical_bars

# ---------------------------------------------------------------------------
# WEIGHTS invariant
# ---------------------------------------------------------------------------


def test_weights_sum_to_one():
    """The published 25/20/15/15/15/10 must sum to 1.0 exactly. If this ever
    breaks the public /how-it-works page is now lying."""
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_weights_contain_all_six_factors():
    expected = {"trend", "rs", "fundamentals", "smart_money", "macro", "momentum"}
    assert set(WEIGHTS.keys()) == expected


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------


def test_parse_args_minimal():
    cfg = parse_args(["--start", "2024-01-01", "--end", "2024-01-15"])
    assert cfg.start == date(2024, 1, 1)
    assert cfg.end == date(2024, 1, 15)
    assert cfg.rebalance == "weekly"
    assert cfg.top_n == 10
    assert cfg.output is None
    assert cfg.mode == "walk-forward"
    assert cfg.universe_source == "mock"


def test_parse_args_rejects_inverted_dates():
    with pytest.raises(SystemExit):
        parse_args(["--start", "2024-12-31", "--end", "2024-01-01"])


def test_parse_args_rejects_zero_top_n():
    with pytest.raises(SystemExit):
        parse_args(["--start", "2024-01-01", "--end", "2024-01-31", "--top-n", "0"])


def test_parse_args_accepts_monthly():
    cfg = parse_args([
        "--start", "2024-01-01", "--end", "2024-12-31",
        "--rebalance", "monthly", "--top-n", "5",
    ])
    assert cfg.rebalance == "monthly"
    assert cfg.top_n == 5


# ---------------------------------------------------------------------------
# Smoke test: short window end-to-end
# ---------------------------------------------------------------------------


def _short_window_config(tmp_path: Path | None = None) -> BacktestConfig:
    return BacktestConfig(
        start=date(2024, 1, 1),
        end=date(2024, 1, 14),  # 2 weeks
        rebalance="weekly",
        top_n=5,
        output=None,
        mode="walk-forward",
        universe_source="mock",
    )


def test_smoke_two_week_window():
    """The script runs end-to-end on a 2-week window without crashing and
    produces a non-empty report."""
    config = _short_window_config()
    report = run_backtest(config)
    assert len(report.periods) >= 1, "must produce at least one rebalance period"
    for p in report.periods:
        assert p.n_picks == 5, "n_picks should equal --top-n when universe is large enough"
        assert -100.0 < p.avg_pick_return < 100.0, "sanity bounds on return"
        assert isinstance(p.best_pick, str)
        assert isinstance(p.worst_pick, str)


def test_csv_schema_smoke():
    """Generated CSV has the required columns + header comments + footer."""
    config = _short_window_config()
    report = run_backtest(config)
    csv_text = render_csv(report)
    lines = csv_text.splitlines()

    # Find the header data row
    header_row = next(
        line for line in lines
        if line.startswith("rebalance_date,") and not line.startswith("#")
    )
    cols = header_row.split(",")
    assert cols == [
        "rebalance_date", "n_picks", "avg_pick_return", "spy_return",
        "avg_alpha", "hit_rate_beat_spy", "best_pick", "best_alpha",
        "worst_pick", "worst_alpha",
    ]

    # Comment header is present + documents the formula
    leading_comments = [line for line in lines if line.startswith("#")]
    assert any("composite = 0.25*trend" in line for line in leading_comments), \
        "formula must be documented in the CSV header"
    assert any("LIMITATIONS" in line for line in leading_comments), \
        "limitations block must be documented"

    # Summary footer present
    assert any(line.startswith("# total_periods,") for line in lines)
    assert any(line.startswith("# overall_hit_rate,") for line in lines)
    assert any(line.startswith("# overall_avg_alpha,") for line in lines)
    assert any(line.startswith("# sharpe_of_alpha_series,") for line in lines)
    assert any(line.startswith("# methodology_notes,") for line in lines)


def test_summary_footer_numbers_parse_as_floats():
    """The values after the comma in summary lines must be valid floats."""
    config = _short_window_config()
    report = run_backtest(config)
    csv_text = render_csv(report)

    def _value_after(prefix: str) -> str:
        for line in csv_text.splitlines():
            if line.startswith(prefix):
                return line.split(",", 1)[1].strip().rstrip("%")
        raise AssertionError(f"no line starting with {prefix!r}")

    # These three MUST parse cleanly. `total_periods` is an int but float() works.
    float(_value_after("# total_periods,"))
    float(_value_after("# overall_hit_rate,"))
    float(_value_after("# overall_avg_alpha,"))
    float(_value_after("# sharpe_of_alpha_series,"))


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_two_runs_produce_identical_output():
    """Crucial for the podcast use case — the founder must be able to re-run
    the script and produce the same numbers. Determinism prevents any
    accidental cherry-picking from re-rolling the dice."""
    config = _short_window_config()
    a = render_csv(run_backtest(config))
    b = render_csv(run_backtest(config))
    # Strip the generated_at timestamp line which legitimately changes.
    def _strip_ts(text: str) -> str:
        return "\n".join(
            line for line in text.splitlines() if not line.startswith("# generated_at:")
        )
    assert _strip_ts(a) == _strip_ts(b)


# ---------------------------------------------------------------------------
# Factor unavailability
# ---------------------------------------------------------------------------


def test_no_crash_when_all_factors_zeroed():
    """Pathological case: every factor unavailable. The composite collapses
    to zero for every ticker but the script must still produce sane output,
    not crash on a divide-by-zero or empty-top-N."""
    from app.scripts.walk_forward_backtest import (
        _composite_score,
    )

    avail = FactorAvailability(
        trend=False, rs=False, fundamentals=False,
        smart_money=False, macro=False, momentum=False,
    )
    score = _composite_score("AAPL", date(2024, 1, 1), avail)
    assert score == 0.0


def test_zeroed_factors_documented_in_header():
    """The CSV header must enumerate exactly which factors were zeroed for
    the run — a reader needs this to interpret the numbers."""
    config = _short_window_config()
    report = run_backtest(config)
    # Default availability zeros smart_money + fundamentals
    csv_text = render_csv(report)
    assert "smart_money" in csv_text
    assert "fundamentals" in csv_text


# ---------------------------------------------------------------------------
# main() exit code
# ---------------------------------------------------------------------------


def test_main_returns_zero_on_success(tmp_path: Path, monkeypatch):
    """The script returns exit code 0 on a happy-path run."""
    out = tmp_path / "out.csv"
    code = main([
        "--start", "2024-01-01", "--end", "2024-01-14",
        "--rebalance", "weekly", "--top-n", "5",
        "--output", str(out),
    ])
    assert code == 0
    assert out.exists()
    text = out.read_text()
    assert "rebalance_date," in text
    assert "# Summary" in text


def test_main_writes_to_stdout_when_no_output(monkeypatch, capsys):
    """No --output flag → CSV streams to stdout."""
    code = main([
        "--start", "2024-01-01", "--end", "2024-01-14",
        "--rebalance", "weekly", "--top-n", "3",
    ])
    assert code == 0
    captured = capsys.readouterr()
    assert "rebalance_date," in captured.out
    assert "# Summary" in captured.out


# ---------------------------------------------------------------------------
# Rebalance schedule
# ---------------------------------------------------------------------------


def test_weekly_rebalance_dates_are_mondays():
    """Weekly cadence must snap every rebalance to a Monday."""
    from app.scripts.walk_forward_backtest import _rebalance_dates
    dates = _rebalance_dates(date(2024, 1, 1), date(2024, 3, 1), "weekly")
    assert len(dates) > 0
    for d in dates:
        assert d.weekday() == 0, f"{d} is not a Monday"


def test_monthly_rebalance_dates_are_weekdays_at_month_start():
    """Monthly cadence picks the first weekday of each month."""
    from app.scripts.walk_forward_backtest import _rebalance_dates
    dates = _rebalance_dates(date(2024, 1, 1), date(2024, 6, 30), "monthly")
    assert len(dates) >= 6
    for d in dates:
        assert d.weekday() < 5, f"{d} is a weekend"
        assert d.day <= 3, f"{d} is not near the start of its month"


# ---------------------------------------------------------------------------
# Live-mode wiring: historical_bars provider + end-to-end CLI run
#
# CRITICAL: these tests must NEVER make a real network call. The fixtures
# below either mock httpx.Client transport or set TAPELINE_BAR_CACHE_DIR to
# a tmp_path so the cache layer doesn't read from the user's home dir.
# ---------------------------------------------------------------------------


def _make_massive_response(symbol: str, n_bars: int = 5) -> dict:
    """Build a fake Massive `/v2/aggs` response body — same shape the real
    endpoint returns (the production adapter at polygon_feed.fetch_aggregates
    parses identical fields). Five bars is enough to exercise the parser
    without bloating the test."""
    base_ts = int(datetime(2024, 1, 2, tzinfo=UTC).timestamp() * 1000)
    one_day_ms = 86400 * 1000
    return {
        "ticker": symbol,
        "status": "OK",
        "queryCount": n_bars,
        "resultsCount": n_bars,
        "adjusted": True,
        "results": [
            {
                "v": 1_000_000 + i * 1000,
                "vw": 100.0 + i,
                "o": 100.0 + i,
                "c": 101.0 + i,
                "h": 102.0 + i,
                "l": 99.0 + i,
                "t": base_ts + i * one_day_ms,
                "n": 50000,
            }
            for i in range(n_bars)
        ],
    }


@pytest.fixture
def fresh_cache_dir(tmp_path: Path, monkeypatch):
    """Point the historical_bars cache at a tmp_path + reset the rate
    limiter with a no-op sleep so the 5-call/min budget never actually
    blocks the test. Without this override the live-mode test would sleep
    ~60s every 5 symbols → ~20 min hang for the 100-symbol universe."""
    monkeypatch.setenv("TAPELINE_BAR_CACHE_DIR", str(tmp_path))
    historical_bars.reset_rate_limiter(sleep_fn=lambda _seconds: None)
    yield tmp_path
    # Clean up after the test so other tests see a real (default) limiter
    historical_bars.reset_rate_limiter()


def test_historical_bars_provider_returns_shape(monkeypatch, fresh_cache_dir):
    """The historical_bars adapter parses Massive's `/v2/aggs` response into
    BarData rows with the documented schema. We mock the HTTP layer via
    httpx.MockTransport so no real Massive call fires — CI machines do not
    have a MASSIVE_API_KEY and must not depend on the network."""
    # Set a fake key so the configured() branch fires
    monkeypatch.setenv("MASSIVE_API_KEY", "test-key-not-real")

    captured_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        return httpx.Response(200, json=_make_massive_response("AAPL", n_bars=5))

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)

    bars = historical_bars.fetch_daily_bars(
        "AAPL", date(2024, 1, 1), date(2024, 1, 31), client=client,
    )

    # Five bars in, five bars out
    assert len(bars) == 5

    # Schema check: every field is the documented type
    for b in bars:
        assert b.symbol == "AAPL"
        assert isinstance(b.bar_date, date)
        assert isinstance(b.open, float)
        assert isinstance(b.high, float)
        assert isinstance(b.low, float)
        assert isinstance(b.close, float)
        assert isinstance(b.volume, int)

    # First bar is 2024-01-02 (the base_ts from the fixture)
    assert bars[0].bar_date == date(2024, 1, 2)
    assert bars[0].close == 101.0
    assert bars[0].volume == 1_000_000

    # The request went to the Massive aggregates path with adjusted=true + sort=asc
    assert len(captured_urls) == 1
    url = captured_urls[0]
    assert "/v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-31" in url
    assert "adjusted=true" in url
    assert "sort=asc" in url
    assert "apiKey=test-key-not-real" in url

    # Cache file was written + has the bars JSON-serialised
    cache_files = list(fresh_cache_dir.iterdir())
    assert len(cache_files) == 1
    cache_payload = json.loads(cache_files[0].read_text())
    assert cache_payload["symbol"] == "AAPL"
    assert len(cache_payload["bars"]) == 5
    assert cache_payload["bars"][0]["close"] == 101.0


def test_live_backtest_runs_with_real_provider(monkeypatch, tmp_path, fresh_cache_dir):
    """The CLI invoked with --universe-source live, when MASSIVE_API_KEY is
    set and the HTTP layer returns valid bars, produces a CSV whose
    data_source footer line is `massive_live`. Mocks every httpx call so
    no real network traffic happens — CI must remain fully offline."""
    monkeypatch.setenv("MASSIVE_API_KEY", "test-key-not-real")

    # MockTransport handler that returns the standard fixture for any symbol.
    # We don't care which symbols get hit — only that the live path resolves
    # to massive_live and the CSV is well-formed.
    def handler(request: httpx.Request) -> httpx.Response:
        # Pull the symbol out of the URL path so the response ticker matches
        # the request (handy for debuggability even though the parser doesn't
        # check it).
        parts = request.url.path.split("/")
        symbol = parts[parts.index("ticker") + 1] if "ticker" in parts else "UNKNOWN"
        # 30 bars covers a 6-week window with weekday-only emission
        return httpx.Response(200, json=_make_massive_response(symbol, n_bars=30))

    # Patch the constructor used in historical_bars._fetch_from_massive so
    # every new client gets the MockTransport. This is the cleanest way to
    # intercept the per-call client without changing the production signature.
    real_client_cls = httpx.Client

    def patched_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client_cls(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", patched_client)

    out = tmp_path / "live_out.csv"
    code = main([
        "--start", "2024-01-01", "--end", "2024-01-14",
        "--rebalance", "weekly", "--top-n", "3",
        "--universe-source", "live",
        "--output", str(out),
    ])
    assert code == 0
    assert out.exists()
    text = out.read_text()

    # Honest footer: data_source line says massive_live (NOT synthetic_fallback)
    assert "# data_source,massive_live" in text, (
        "live mode with a configured key + mocked-HTTP success "
        "must land on massive_live, not synthetic_fallback. CSV was:\n" + text
    )

    # Header carries the live data-source classification too
    assert "# data_source: massive_live" in text

    # The synthetic-GBM caveat must NOT fire on a real-data run
    assert "deterministic GBM-style synthetic walks" not in text, (
        "GBM caveat should be replaced by the Massive-data note when bars are real"
    )
    assert "Prices sourced from Massive" in text

    # Backwards-compat: the CSV header columns are unchanged from PR #42
    lines = text.splitlines()
    header_row = next(
        line for line in lines
        if line.startswith("rebalance_date,") and not line.startswith("#")
    )
    cols = header_row.split(",")
    assert cols == [
        "rebalance_date", "n_picks", "avg_pick_return", "spy_return",
        "avg_alpha", "hit_rate_beat_spy", "best_pick", "best_alpha",
        "worst_pick", "worst_alpha",
    ]
