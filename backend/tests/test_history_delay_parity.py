"""The three public views of the scorecard must apply the SAME delay.

`/api/scorecard`, the CSV/JSON export and `/api/ticker/{symbol}/history` all
serve the same per-flag rows. The first two withhold the most recent
_FREE_DELAY_DAYS from anyone not on a paying tier, and the export's own metadata
tells readers so in words: "entries are published about N days after".

`/history` took no user at all and served today's flags to anonymous callers.
Both statements could not be true at once, and on a product whose entire claim is
that it does not misstate things, the open door is what gets closed — not the
promise.

These tests pin the parity, because the drift is invisible from either side
alone: the endpoint looks fine, the export looks fine, and only reading both
together reveals the contradiction.
"""
from __future__ import annotations

import inspect

from app.routers import ticker as ticker_router
from app.routers.scorecard import _FREE_DELAY_DAYS, _can_see_live_picks

SRC = inspect.getsource(ticker_router.ticker_score_history)


def test_history_applies_the_shared_delay():
    assert "_FREE_DELAY_DAYS" in SRC
    assert "_can_see_live_picks" in SRC


def test_the_delay_is_imported_not_redeclared():
    """A second copy of the constant is how three surfaces drift apart."""
    assert "from app.routers.scorecard import" in SRC
    assert "_FREE_DELAY_DAYS = " not in SRC, (
        "the delay window is re-declared here; import it so scorecard, export "
        "and history can never disagree"
    )


def test_paying_tiers_still_see_live():
    """The gate is entitlement, not a blanket delay."""

    class _U:
        def __init__(self, tier: str) -> None:
            self.tier = tier

    assert _can_see_live_picks(_U("pro")) is True
    assert _can_see_live_picks(_U("premium")) is True
    assert _can_see_live_picks(_U("free")) is False
    assert _can_see_live_picks(None) is False


def test_the_response_discloses_the_delay():
    """A chart or an MCP client cannot otherwise tell a complete series from a
    truncated one — silence here would be its own small misstatement."""
    assert '"delay_days"' in SRC
    assert f"0 if delay_cutoff is None else _FREE_DELAY_DAYS" in SRC


def test_the_delay_window_is_still_seven_days():
    """If this changes, the export's published wording must change with it."""
    assert _FREE_DELAY_DAYS == 7
