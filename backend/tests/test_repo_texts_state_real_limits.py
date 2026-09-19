"""Repo texts that stated limits the code and the vendor do not have.

The repo is public, so these read as claims to anyone who opens it.

1. README's Premium line said "unlimited email alerts". The sender caps every
   channel at services/alerts.ALERT_DAILY_CEILING (50 deliveries per UTC day)
   on every plan, and Pro's own email cap is 10 a day (tier.TIER_LIMITS).
2. Code comments, a workflow and two docs said the Stocks Starter plan allows
   5 requests a minute, and some said only the Developer tier could go faster.
   The vendor's pricing page (massive.com/pricing, read 2026-09-19) lists
   Starter, the plan in use, with unlimited API calls; 5 calls a minute is the
   free Basic tier. The pacing in those places is our own choice. A sentence
   may put a 5-a-minute rate next to a paid plan's name only when it also
   names the Basic tier, i.e. when it is the correction.
3. polygon_feed.fetch_squeezes said DEFAULT_UNIVERSE "takes ~15 minutes to
   sweep" and that squeeze detection "runs on a slower cadence than
   snapshots". Nothing calls it: the worker imports mock_feed.fetch_squeezes,
   which is switched off in production. Its docstring now says it is unused,
   and this pins that claim to the code.
4. The polygon_feed header once said Starter carried "commercial
   redistribution rights". #880 corrected it. The phrase survives only inside
   the sentence that says it was untrue, and this pins that.
"""
from __future__ import annotations

import ast
import pathlib
import re

from app.services import alerts
from app.services.tier import TIER_LIMITS, Tier

ROOT = pathlib.Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
README = ROOT / "README.md"
POLYGON_FEED = APP / "services" / "polygon_feed.py"
VENDOR_TEXTS = (
    POLYGON_FEED,
    ROOT / ".github" / "workflows" / "rederive-scorecard.yml",
)
RATE_TEXTS = (
    *VENDOR_TEXTS,
    APP / "services" / "squeeze_detection.py",
    APP / "services" / "historical_bars.py",
    APP / "scripts" / "rederive_scorecard.py",
    APP / "scripts" / "walk_forward_backtest.py",
    ROOT / "docs" / "DATA_SOURCES.md",
    ROOT / "docs" / "BACKTEST.md",
)


def test_readme_never_calls_alerts_unlimited():
    text = README.read_text(encoding="utf-8")
    hit = re.search(r"unlimited[^.\n]{0,40}alerts?", text, re.I)
    assert hit is None, f"README still says {hit.group(0)!r}"


def test_readme_premium_line_states_the_real_alert_caps():
    lines = [ln for ln in README.read_text(encoding="utf-8").splitlines()
             if ln.startswith("- **Premium**")]
    assert len(lines) == 1, lines
    line = lines[0]
    ceiling = alerts.ALERT_DAILY_CEILING["email"]
    assert set(alerts.ALERT_DAILY_CEILING.values()) == {ceiling}, (
        "README says every alert channel shares one ceiling; the channels differ now"
    )
    pro_email = TIER_LIMITS[Tier.PRO]["email_alerts_per_day"]
    assert f"email alerts up to {ceiling}/day" in line, line
    assert f"Pro's {pro_email}" in line, line
    assert f"capped at {ceiling} per UTC day" in line, line


# A 5-per-minute rate: "5 req/min", "5 requests/min", "5 calls / minute",
# "5/min", "5 calls a minute", "5 per minute".
_FIVE_PER_MIN = re.compile(
    r"\b5\s*(?:req(?:uest)?s?|calls?)?\s*(?:/|\ba\b|\bper\b)\s*min(?:ute)?\b", re.I
)
_PAID_PLAN = re.compile(r"\b(?:Starter|Developer)\b")
_COMMENT_MARKER = re.compile(r"^\s*(?:#:?|//|\*)\s?")


def _sentences(text: str) -> list[str]:
    """The file as sentences: comment markers dropped, lines joined, split
    after '.', ';', '!' or '?' followed by whitespace. A claim wrapped across
    comment lines is read as one sentence."""
    joined = " ".join(_COMMENT_MARKER.sub("", ln) for ln in text.splitlines())
    joined = re.sub(r"\s+", " ", joined)
    return re.split(r"(?<=[.;!?])\s+", joined)


def test_no_text_ties_a_five_per_minute_limit_to_a_paid_plan():
    for path in RATE_TEXTS:
        for sentence in _sentences(path.read_text(encoding="utf-8")):
            if _FIVE_PER_MIN.search(sentence) and _PAID_PLAN.search(sentence):
                assert "Basic" in sentence, (
                    f"{path.relative_to(ROOT)} ties 5/min to a paid plan: "
                    f"{sentence[:240]!r}"
                )


def _imports_polygon_fetch_squeezes(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and (node.module or "").endswith("polygon_feed")
            and any(alias.name == "fetch_squeezes" for alias in node.names)
        ):
            return True
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "fetch_squeezes"
            and isinstance(node.value, ast.Name)
            and node.value.id == "polygon_feed"
        ):
            return True
    return False


def test_polygon_fetch_squeezes_is_documented_as_unused_and_is_unused():
    from app.services import mock_feed, polygon_feed
    from app.workers import signal_publisher

    # The worker's squeeze source is the mock generator, not the vendor one.
    assert signal_publisher.fetch_squeezes is mock_feed.fetch_squeezes

    callers = [
        str(p.relative_to(ROOT))
        for p in APP.rglob("*.py")
        if p != POLYGON_FEED
        and _imports_polygon_fetch_squeezes(ast.parse(p.read_text(encoding="utf-8")))
    ]
    assert callers == [], (
        f"polygon_feed.fetch_squeezes now has callers {callers}; its docstring "
        f"says it is unused, so rewrite the docstring to say what it does now"
    )

    doc = " ".join((polygon_feed.fetch_squeezes.__doc__ or "").split())
    assert "nothing calls this function" in doc, doc
    assert "No real squeeze source is configured" in doc, doc
    for stale in ("slower cadence", "~15 minutes", "takes ~"):
        assert stale not in doc, f"docstring still says {stale!r}: {doc}"


def test_commercial_redistribution_appears_only_as_a_retraction():
    for path in VENDOR_TEXTS:
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"commercial\s+redistribution", text, re.I):
            after = text[m.end(): m.end() + 160]
            assert "neither was true" in after, (
                f"{path.relative_to(ROOT)} claims commercial redistribution: "
                f"{text[m.start(): m.end() + 80]!r}"
            )
