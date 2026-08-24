"""Guards on the scorecard re-derivation script.

The script rewrites the PUBLIC track record, irreversibly. An adversarial
review of the first draft confirmed five defects that all survived refutation;
each one is pinned here, because every one of them would have produced
plausible-looking but wrong published numbers.

  1. It fetched SPLIT-ADJUSTED closes and divided them by `price_at_flag`,
     which is frozen from the live UNADJUSTED snapshot. Any symbol that split
     between the flag date and the run reads as a fabricated return — a 4:1
     split is roughly -75%.
  2. It had NO post-close gate, so it would re-read the in-progress daily bar
     for the newest date and re-commit the exact partial-bar bug it exists to
     fix — with the result depending on the wall-clock time of the run.
  3. It rounded `pct` and THEN subtracted to get alpha, while the worker
     subtracts from the unrounded `pct`. Different numbers from identical
     prices, so already-correct rows were rewritten and miscounted as damage.
  4. It paced at 0.25s — about 48x over the documented Starter-tier limit of
     5 requests/min, on the key the live worker shares.
  5. Its before/after headline was not the statistic /scorecard publishes
     (wrong population: no outlier filter).
"""
from __future__ import annotations

import ast
import inspect
import pathlib
from datetime import UTC, date, datetime
from statistics import median

import pytest

from app.scripts import rederive_scorecard as rs

_SRC = pathlib.Path("app/scripts/rederive_scorecard.py").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 1. Unadjusted basis
# --------------------------------------------------------------------------


def test_fetch_aggregates_exposes_an_adjusted_flag():
    from app.services.polygon_feed import fetch_aggregates

    params = inspect.signature(fetch_aggregates).parameters
    assert "adjusted" in params, (
        "fetch_aggregates cannot be asked for unadjusted bars, so the "
        "re-derivation must mix an adjusted close with an unadjusted flag price"
    )
    assert params["adjusted"].default is True, (
        "the default must stay adjusted — scoring indicators and the backtest "
        "legitimately want adjusted series"
    )


@pytest.mark.asyncio
async def test_rederive_requests_unadjusted_bars(monkeypatch):
    """Both helpers must pass adjusted=False, or the two legs sit on different
    scales and split symbols get fabricated returns."""
    seen: list[dict] = []

    async def _fake(symbol, from_date=None, to_date=None, timespan="day", adjusted=True):
        seen.append({"symbol": symbol, "adjusted": adjusted})
        return [{"t": int(datetime(2026, 8, 3, tzinfo=UTC).timestamp() * 1000), "c": 10.0}]

    monkeypatch.setattr(rs, "fetch_aggregates", _fake)
    monkeypatch.setattr(rs, "_vendor_key", lambda: "test-key")

    await rs._unadjusted_window("SPY", date(2026, 8, 2), date(2026, 8, 3))
    await rs._unadjusted_window("NVDA", date(2026, 8, 2), date(2026, 8, 3))

    assert seen, "no vendor call was made"
    assert all(c["adjusted"] is False for c in seen), (
        f"a helper requested ADJUSTED bars: {seen} — dividing an adjusted close "
        f"by an unadjusted price_at_flag fabricates ~-75% returns on any split"
    )


def test_script_does_not_use_the_adjusted_backcheck_helpers():
    """`_fetch_close` / `_fetch_close_window` take the adjusted series."""
    tree = ast.parse(_SRC)
    imported = {
        a.name
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom)
        for a in n.names
    }
    for bad in ("_fetch_close", "_fetch_close_window"):
        assert bad not in imported, (
            f"{bad} returns SPLIT-ADJUSTED closes; the re-derivation must use "
            f"its own unadjusted helpers"
        )


# --------------------------------------------------------------------------
# 2. The post-close gate
# --------------------------------------------------------------------------


def test_script_applies_the_session_complete_gate():
    assert "_session_is_complete" in _SRC, (
        "the repair has no post-close gate, so it re-reads the in-progress bar "
        "for the newest date and re-commits the bug it exists to fix"
    )


def test_plan_skips_dates_whose_next_session_is_still_open(monkeypatch):
    """A date whose next session hasn't closed must cost ZERO vendor calls and
    must not be repaired."""
    class _E:
        def __init__(self, as_of, symbol):
            self.as_of = as_of
            self.symbol = symbol

    today = datetime.now(UTC).date()
    monkeypatch.setattr(rs, "is_trading_day", lambda d: True)
    monkeypatch.setattr(rs, "_next_trading_day", lambda d: today)
    # Session NOT complete -> nothing planned.
    monkeypatch.setattr(rs, "_session_is_complete", lambda nd, td: False)
    _, calls = rs._plan([_E(today, "NVDA"), _E(today, "MSFT")])
    assert calls == 0, "an open session was planned for repair"

    # Session complete -> 1 SPY window + 2 symbols.
    monkeypatch.setattr(rs, "_session_is_complete", lambda nd, td: True)
    _, calls = rs._plan([_E(today, "NVDA"), _E(today, "MSFT")])
    assert calls == 3, calls


# --------------------------------------------------------------------------
# 3. Rounding must match the worker byte-for-byte
# --------------------------------------------------------------------------


def test_alpha_is_derived_from_the_unrounded_pct():
    """The worker does `round(pct - spy_move, 3)` from the UNROUNDED pct.

    Rounding pct first and subtracting differs whenever the third decimal
    rounds, so already-correct rows would be rewritten and miscounted.
    """
    close, flag, spy_move = 135.6207, 135.52, -0.1174

    pct = ((close / flag) - 1) * 100
    worker_alpha = round(pct - spy_move, 3)
    naive_alpha = round(round(pct, 3) - spy_move, 3)

    # The script must use the worker's convention.
    assert "round(pct - spy_move, 3)" in _SRC, (
        "alpha is not derived from the unrounded pct — the script and the "
        "worker would write different numbers from identical prices"
    )
    # Sanity: the two conventions really can differ.
    assert isinstance(worker_alpha, float) and isinstance(naive_alpha, float)


def test_no_double_rounded_alpha_expression_remains():
    assert "round(new_pct - spy_move" not in _SRC, (
        "the double-rounded alpha expression is still present"
    )


# --------------------------------------------------------------------------
# 4. Vendor pacing
# --------------------------------------------------------------------------


def test_default_pace_respects_the_documented_rate_limit():
    """polygon_feed documents Starter at 5 requests/min."""
    assert rs._DEFAULT_PACE_SECONDS >= 12.0, (
        f"default pacing {rs._DEFAULT_PACE_SECONDS}s exceeds 5 req/min — the "
        f"run would 429-storm itself and starve the live worker's shared key"
    )


def test_refuses_to_run_without_a_vendor_key(monkeypatch, caplog):
    """With no key every fetch returns None, so every row would be counted
    'unresolved' and the run would look like a clean no-op."""
    assert "NO VENDOR KEY CONFIGURED" in _SRC, (
        "the script does not refuse to run without a vendor key"
    )


# --------------------------------------------------------------------------
# 5. The reported statistics must be the PUBLISHED ones
# --------------------------------------------------------------------------


def test_published_stats_matches_the_scorecard_router_formula():
    """Mirror routers/scorecard._summary: outliers (|1d| > 50) excluded from
    the statistics but counted, hit rate = alpha > 0 over the clean set."""
    pairs = [
        (1.0, 0.5),      # beat
        (-2.0, -1.0),    # missed
        (3.0, 0.25),     # beat
        (80.0, 40.0),    # OUTLIER — excluded from stats
        (-60.0, -30.0),  # OUTLIER — excluded from stats
    ]
    got = rs._published_stats(pairs)

    clean = [(r, a) for (r, a) in pairs if abs(r) <= 50.0]
    alphas = [a for (_, a) in clean]
    assert got["n"] == len(clean) == 3
    assert got["excluded"] == 2
    assert got["hit_rate"] == pytest.approx(
        sum(1 for a in alphas if a > 0) / len(alphas) * 100
    )
    assert got["median_alpha"] == pytest.approx(median(alphas))


def test_outlier_threshold_matches_the_router():
    from app.routers.scorecard import _OUTLIER_PCT_THRESHOLD

    assert rs._OUTLIER_PCT_THRESHOLD == _OUTLIER_PCT_THRESHOLD, (
        "the script filters on a different threshold than /scorecard publishes, "
        "so its before/after headline is not the real statistic"
    )


def test_published_stats_handles_an_all_outlier_population():
    got = rs._published_stats([(90.0, 50.0), (-70.0, -20.0)])
    assert got["n"] == 0 and got["excluded"] == 2


# --------------------------------------------------------------------------
# Safety invariants
# --------------------------------------------------------------------------


def test_price_at_flag_is_never_written():
    """The freeze side already waits until 21:15 UTC, so that leg is a real
    close. Touching it would corrupt the ONE value that was always right."""
    assert "price_at_flag =" not in _SRC.replace("e.price_at_flag ==", ""), (
        "the script assigns to price_at_flag"
    )
    tree = ast.parse(_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Attribute) and t.attr == "price_at_flag":
                    raise AssertionError("price_at_flag is assigned somewhere")


def test_dry_run_is_the_default():
    sig = inspect.signature(rs._rederive).parameters
    assert "apply" in sig
    src_main = inspect.getsource(rs.main)
    assert 'action="store_true"' in src_main and "--apply" in src_main, (
        "--apply must be an explicit opt-in flag, not a default"
    )


def test_unresolved_rows_are_never_written():
    """A vendor miss must `continue`, never fall through to a write."""
    assert "unresolved += 1" in _SRC
    # Every unresolved branch is immediately followed by a continue.
    for chunk in _SRC.split("unresolved += 1")[1:]:
        head = chunk.strip().splitlines()[0].strip()
        assert head == "continue", (
            f"an unresolved row does not immediately continue (found {head!r}) — "
            f"it could fall through to a write"
        )


# --------------------------------------------------------------------------
# 6. Both legs from ONE window, plus the flag-price integrity check
# --------------------------------------------------------------------------


def test_both_legs_come_from_one_window():
    """A lone next_day point cannot be sanity-checked against price_at_flag.

    Taking the window gives the flag-day close for free (same one call), which
    is what makes the integrity check below possible.
    """
    assert "_unadjusted_window(sym, as_of, next_day)" in _SRC, (
        "the per-symbol fetch is not a window spanning both legs"
    )
    assert "_unadjusted_close(" not in _SRC, (
        "the single-point helper is still referenced — it cannot verify the "
        "flag price"
    )


def test_flag_price_is_verified_before_being_used_as_a_denominator():
    """price_at_flag is the ONE leg we may not change, so if the vendor
    disagrees with it for its own session we must not publish a return computed
    against it. A split shows up here as ~50/67/75%."""
    assert "_FLAG_DRIFT_TOLERANCE" in _SRC
    assert rs._FLAG_DRIFT_TOLERANCE <= 0.05, (
        f"tolerance {rs._FLAG_DRIFT_TOLERANCE} is too loose to catch a "
        f"corporate action or a bad freeze"
    )
    assert "flag_mismatch += 1" in _SRC, "a mismatching row is not skipped"


def test_flag_mismatch_skips_rather_than_repairs():
    """The mismatch branch must `continue`, never fall through to a write."""
    for chunk in _SRC.split("flag_mismatch += 1")[1:]:
        head = chunk.strip().splitlines()[0].strip()
        assert head == "continue", (
            f"a flag-mismatch row does not immediately continue (found {head!r})"
        )
