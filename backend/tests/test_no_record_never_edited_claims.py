"""No email, MCP text or growth post says the public record is never edited.

Integrity wave, part 2 (founder approval 2026-09-14; follow-up to #817, #818,
#820, #821). Recorded values in the public record were changed twice:

* 15 June 2026: every recorded score above 100 was set to 100 and the originals
  were not kept (all 190 entries from 18 May to 12 June 2026 now read 100);
* 25 August 2026: recorded prices were restated (684 of 688 rows).

No top 10 was recorded for 31 August, 2 September, 4 September or
9 September 2026. The record also stores no per-pick reasoning or signal label
(scorecard_export.COLUMNS), so "with the original reasoning" was false too.

Emails are swept through the same introspected renderer list as
test_no_congress_or_squeeze_benefit_claims.py, so a renderer added later is
covered without anyone listing it.
"""
from __future__ import annotations

import inspect
import re

import pytest

import app.services.email as email_mod
from app.routers import mcp as mcp_module
from app.services import growth_bot, scorecard_export
from app.services.universe import ACTIVE_UNIVERSE_SIZE, SCORED_TICKERS_IN_COPY
from tests.test_no_congress_or_squeeze_benefit_claims import _cases

BANNED = [
    r"never[\s-]+(?:been\s+)?edit",
    r"\bun-?edited\b",
    r"\bno[\s-]+edits\b",
    r"append[\s-]only",
    r"\bimmutable\b",
    r"no hindsight",
    r"hindsight edit",
    r"never retroactively",
    r"can(?:'|’)?t go back and edit",
    r"original reasoning",
    r"reasoning it was published",
    r"every call we(?:'|’)?ve (?:ever )?made",
    r"re-ranked, edited or removed",
    r"nothing is pruned",
    r"it never paused",
]
BANNED_RE = re.compile("|".join(f"(?:{p})" for p in BANNED), re.IGNORECASE)

APPROVED = (
    "Entries are not re-ranked or deleted. We have corrected recorded values twice, "
    "and said so: prices on 25 August 2026, and scores from 18 May to 12 June capped "
    "on 15 June 2026."
)
MISSING = (
    "No top 10 was recorded for 31 August, 2 September, 4 September or "
    "9 September 2026."
)


def _hits(text: str) -> list[str]:
    return [text[max(0, m.start() - 50): m.end() + 50] for m in BANNED_RE.finditer(text)]


@pytest.mark.parametrize("name,fn,kwargs", _cases())
async def test_no_email_renderer_claims_the_record_is_never_edited(name, fn, kwargs):
    try:
        out = fn(**kwargs)
        if inspect.isawaitable(out):
            out = await out
    except Exception as exc:  # never a silent skip
        pytest.fail(f"{name} could not be rendered with synthesised args ({exc!r})")
    text = out if isinstance(out, str) else str(out)
    assert not _hits(text), f"{name}: {_hits(text)[:3]}"


def test_the_record_stores_no_reasoning_column():
    """Why 'with the original reasoning' had to go: the record has no such field."""
    assert not any("reason" in c or "signal" in c for c in scorecard_export.COLUMNS)


def test_mcp_instructions_and_tool_descriptions():
    blob = " ".join(
        [mcp_module.INSTRUCTIONS, mcp_module.DISCLAIMER]
        + [t["description"] for t in mcp_module.TOOLS]
    )
    assert not _hits(blob), _hits(blob)
    assert APPROVED in mcp_module.INSTRUCTIONS
    assert MISSING in mcp_module.INSTRUCTIONS


def test_mcp_handler_payload_text_in_source():
    """The `note` and `how_it_works` strings are built inside the handlers;
    read them from source so no database is needed."""
    # The whole module, comments included: nothing in it should say this.
    assert not _hits(inspect.getsource(mcp_module)), _hits(inspect.getsource(mcp_module))
    picks = inspect.getsource(mcp_module._tool_daily_picks)
    assert "Entries are not re-ranked or deleted." in picks
    record = inspect.getsource(mcp_module._tool_track_record)
    assert "Entries are not re-ranked or deleted." in record
    assert "No top 10 was recorded for 31 August" in record


def test_growth_bot_topics():
    for heading, body in growth_bot._LINKEDIN_TOPIC_ROTATION:
        assert not _hits(heading + " " + body), (heading, body)


def test_emails_print_the_measured_count_not_the_snapshot_ceiling():
    """ACTIVE_UNIVERSE_SIZE (12,000) is a snapshot ceiling, not a count."""
    assert SCORED_TICKERS_IN_COPY < ACTIVE_UNIVERSE_SIZE
    re_html = email_mod.render_re_engagement_email("Sam", trading_days_away=10)
    day7 = email_mod.render_trial_day7_email("Sam")
    for html in (re_html, day7):
        assert f"{ACTIVE_UNIVERSE_SIZE:,}" not in html
        assert f"about {SCORED_TICKERS_IN_COPY:,} US stocks and ETFs" in html


def test_carded_trial_value_email_does_not_promise_the_dark_watchlist_record():
    """watchlist.track_record is held dark for every tier (tier.DISABLED_FEATURES),
    so the email must not send a trial user to a record they cannot see."""
    from app.services import tier

    assert "watchlist.track_record" in tier.DISABLED_FEATURES
    html = email_mod.render_carded_trial_value_email("Sam")
    assert "watchlist's record" not in html.lower()
    assert "its own version" not in html
    assert "own scored record" not in html
    assert "Open your watchlist" in html


WATCHLIST_RECORD_PROMISES = ("watchlist's own record", "watchlist's record", "own scored record")


@pytest.mark.parametrize("name,fn,kwargs", _cases())
async def test_no_email_renderer_promises_the_dark_watchlist_record(name, fn, kwargs):
    """watchlist.track_record is dark for every tier (tier.DISABLED_FEATURES), so
    no email may promise it. render_free_trial_invite_email listed "Your
    watchlist's own record" under what a trial adds; the plain score-since-added
    comparison is on the free watchlist anyway, so a trial adds neither."""
    from app.services import tier

    assert "watchlist.track_record" in tier.DISABLED_FEATURES
    try:
        out = fn(**kwargs)
        if inspect.isawaitable(out):
            out = await out
    except Exception as exc:  # never a silent skip
        pytest.fail(f"{name} could not be rendered with synthesised args ({exc!r})")
    text = (out if isinstance(out, str) else str(out)).replace("&#x27;", "'").replace("&#39;", "'").replace("’", "'").lower()
    for phrase in WATCHLIST_RECORD_PROMISES:
        assert phrase not in text, f"{name} promises {phrase!r}"


def test_the_free_trial_invite_email_is_in_the_sweep():
    names = {p.values[0] for p in _cases()}
    assert "render_free_trial_invite_email" in names
