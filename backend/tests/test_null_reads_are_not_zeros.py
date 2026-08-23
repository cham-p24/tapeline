"""A null read must render as an em-dash — never as a measured zero.

~72% of the universe has no price/volume read on a given tick, so the
null-handling paths fire constantly. Each of the paths pinned here used to
turn "we have no reading" into a confident, wrong one:

  * email_design.watchlist_table  — `it.get("score") or 0` printed "0.0" and
    `it.get("change_pct_1d") or 0` printed "+0.00%" for a ticker with no read.
  * briefing._render_html         — a null composite rendered "0.0" AND was
    then differenced against the user's since-you-added baseline, so a missing
    score manufactured a full-size collapse, sometimes tagged "· ALERT".
  * email.render_alert_email      — news / congress / regime rules never read
    the ticker's composite and passed a hardcoded 0, printing "Score · 0.0".
  * polygon_feed._to_scanner_row  — volume 0 (Massive's "no read") was written
    as a measured 0, and a just-listed ticker with no previous close and no
    session open was published at change_pct_1d = 0.0, a flat session that
    never happened.

Zero is a measurement. These tests render the real thing and read the output;
they deliberately do not assert on source text.
"""
from __future__ import annotations

import re

from app.models import Ticker
from app.services import briefing
from app.services.email import render_alert_email
from app.services.email_design import watchlist_table
from app.services.polygon_feed import _to_scanner_row

EM_DASH = "—"


def _cells(html: str) -> list[str]:
    """Inner text of every <td>, tags stripped, whitespace collapsed."""
    return [
        re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", td)).strip()
        for td in re.findall(r"<td[^>]*>(.*?)</td>", html, re.S)
    ]


# -- EOD watchlist digest table ---------------------------------------------

def test_watchlist_table_renders_em_dash_for_null_score_and_change():
    html = watchlist_table([{
        "symbol": "AAPL", "score": None, "signal": None,
        "change_pct_1d": None, "score_delta": None,
    }])
    cells = _cells(html)
    # symbol, score, signal, 1D
    assert cells[0] == "AAPL"
    assert cells[1] == EM_DASH, cells
    assert cells[2] == EM_DASH, cells
    assert cells[3] == EM_DASH, cells
    # No fabricated readings anywhere in the row.
    assert "0.00%" not in html


def test_watchlist_table_withholds_the_delta_badge_when_the_score_is_null():
    """A Δ beside an em-dash describes a move between two unshowable numbers."""
    html = watchlist_table([{
        "symbol": "AAPL", "score": None, "signal": None,
        "change_pct_1d": None, "score_delta": -12.4,
    }])
    assert "12.4" not in html
    assert "Δ" not in html


def test_watchlist_table_still_prints_a_genuine_zero():
    """A real 0.0 score / flat session is a measurement — it must survive."""
    html = watchlist_table([{
        "symbol": "MSFT", "score": 0.0, "signal": "BEAR",
        "change_pct_1d": 0.0, "score_delta": None,
    }])
    cells = _cells(html)
    assert cells[1] == "0.0", cells
    assert cells[3] == "+0.00%", cells


def test_watchlist_table_unchanged_for_a_fully_populated_row():
    html = watchlist_table([{
        "symbol": "NVDA", "score": 82.4, "signal": "STRONG SETUP",
        "change_pct_1d": -1.25, "score_delta": None,
    }])
    cells = _cells(html)
    assert cells[1] == "82.4", cells
    assert cells[3] == "-1.25%", cells


# -- Personalised daily briefing --------------------------------------------

def _briefing_html(ticker: Ticker, *, baseline: float | None) -> str:
    return briefing._render_html(
        user_name="Alex",
        regime=None,
        watchlist_rows=[ticker],
        baselines={ticker.symbol: baseline},
        thresholds={ticker.symbol: 10.0},
        squeezes=[],
        squeeze_label="Squeeze setups",
        cta_href="https://tapeline.io/app/watchlist",
        cta_label="Open watchlist",
        watchlist_total=1,
    )


def test_briefing_null_composite_is_an_em_dash_not_zero():
    html = _briefing_html(
        Ticker(symbol="AAPL", score=None, signal=None, reason=""), baseline=None,
    )
    cells = _cells(html)
    assert EM_DASH in cells, cells
    assert "0.0" not in cells, cells


def test_briefing_suppresses_the_delta_when_the_score_is_null():
    """A null score against a real baseline must NOT manufacture a collapse."""
    html = _briefing_html(
        Ticker(symbol="AAPL", score=None, signal=None, reason=""), baseline=78.0,
    )
    # The old code computed 0.0 - 78.0 = -78.0 and tagged it "· ALERT".
    assert "78.0" not in html
    assert "ALERT" not in html
    assert "▼" not in html and "▲" not in html


def test_briefing_still_shows_the_delta_when_both_sides_are_present():
    html = _briefing_html(
        Ticker(symbol="AAPL", score=66.0, signal="CONSTRUCTIVE", reason=""),
        baseline=78.0,
    )
    assert "12.0" in html           # |66 - 78|
    assert "ALERT" in html          # 12 >= threshold of 10
    assert "▼" in html


# -- Per-rule alert email ---------------------------------------------------

def test_alert_email_omits_the_score_line_when_there_is_no_score():
    html = render_alert_email(
        "Alex", "AAPL in the news", "AAPL", None,
        "AAPL news: Something happened (Reuters)",
    )
    assert "Score ·" not in html
    assert "(score" not in html          # preheader clause dropped too
    assert "AAPL" in html                # the alert itself still renders


def test_alert_email_keeps_the_score_line_when_there_is_one():
    html = render_alert_email(
        "Alex", "AAPL crossed 80", "AAPL", 81.5,
        "Score crossed your threshold of 80",
    )
    assert "Score · 81.5" in html
    assert "(score 82)" in html


def test_alert_email_prints_a_genuine_zero_score():
    """0.0 from the scanner is a real bottom-of-range reading, not a placeholder."""
    html = render_alert_email("Alex", "rule", "AAPL", 0.0, "msg")
    assert "Score · 0.0" in html


# -- Massive v3 snapshot -> scanner row --------------------------------------

def test_no_volume_read_is_null_not_zero():
    row = _to_scanner_row({
        "ticker": "THIN",
        "session": {"price": 4.20, "previous_close": 4.10,
                    "change_percent": 2.44, "volume": 0},
    })
    assert row is not None
    assert row["volume"] is None


def test_missing_volume_key_is_null():
    row = _to_scanner_row({
        "ticker": "THIN",
        "session": {"price": 4.20, "previous_close": 4.10, "change_percent": 2.44},
    })
    assert row is not None
    assert row["volume"] is None


def test_real_volume_survives_as_an_int():
    row = _to_scanner_row({
        "ticker": "AAPL",
        "session": {"price": 293.41, "previous_close": 293.32,
                    "change_percent": 0.0307, "volume": 5.27e7},
    })
    assert row is not None
    assert row["volume"] == 52_700_000
    assert isinstance(row["volume"], int)


def test_just_listed_ticker_with_no_base_has_null_change_not_a_flat_session():
    """No change_percent, no previous_close, no open -> we don't know the move."""
    row = _to_scanner_row({"ticker": "IPO", "session": {"price": 31.00}})
    assert row is not None
    assert row["change_pct_1d"] is None
    # A naive score derived from a move we never measured is equally fabricated.
    assert row["score"] is None
    assert row["signal"] is None


def test_change_is_computed_from_the_open_when_there_is_no_previous_close():
    row = _to_scanner_row({
        "ticker": "IPO",
        "session": {"price": 110.0, "open": 100.0},
    })
    assert row is not None
    assert row["change_pct_1d"] == 10.0


def test_vendor_change_percent_is_used_verbatim():
    row = _to_scanner_row({
        "ticker": "AAPL",
        "session": {"price": 293.41, "previous_close": 293.32,
                    "change_percent": 0.0307, "volume": 1_000},
    })
    assert row is not None
    assert row["change_pct_1d"] == 0.03


def test_a_genuinely_flat_session_still_reports_zero():
    """change_percent of 0.0 IS a measurement — it must not become NULL."""
    row = _to_scanner_row({
        "ticker": "FLAT",
        "session": {"price": 50.0, "previous_close": 50.0,
                    "change_percent": 0.0, "volume": 250_000},
    })
    assert row is not None
    assert row["change_pct_1d"] == 0.0
    assert row["score"] is not None
