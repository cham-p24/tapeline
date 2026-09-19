"""Repo texts that stated limits the code and the vendor do not have.

The repo is public, so these read as claims to anyone who opens it.

1. README's Premium line said "unlimited email alerts". The sender caps every
   channel at services/alerts.ALERT_DAILY_CEILING (50 deliveries per UTC day)
   on every plan, and Pro's own email cap is 10 a day (tier.TIER_LIMITS).
2. polygon_feed.fetch_squeezes and .github/workflows/rederive-scorecard.yml
   said the Stocks Starter plan allows 5 requests a minute, and the workflow
   said only the Developer tier could go faster. The vendor's pricing page
   (massive.com/pricing, read 2026-09-19) lists Starter, the plan in use, with
   unlimited API calls; 5 calls a minute is the free Basic tier. The 12 s
   pacing in both places is our own choice.
3. The polygon_feed header once said Starter carried "commercial
   redistribution rights". #880 corrected it. The phrase survives only inside
   the sentence that says it was untrue, and this pins that.
"""
from __future__ import annotations

import pathlib
import re

from app.services import alerts
from app.services.tier import TIER_LIMITS, Tier

ROOT = pathlib.Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
VENDOR_TEXTS = (
    ROOT / "backend" / "app" / "services" / "polygon_feed.py",
    ROOT / ".github" / "workflows" / "rederive-scorecard.yml",
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


# A 5-per-minute rate written as "5 req/min", "5 requests/min", "5 calls/min"
# or "5/min".
_FIVE_PER_MIN = re.compile(r"\b5\s*(?:req(?:uest)?s?|calls?)?\s*/\s*min\b", re.I)


def test_no_text_ties_a_five_per_minute_limit_to_a_paid_plan():
    for path in VENDOR_TEXTS:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _FIVE_PER_MIN.search(line):
                assert not re.search(r"Starter|Developer", line), (
                    f"{path.relative_to(ROOT)}:{n} ties 5/min to a paid plan: {line.strip()}"
                )


def test_commercial_redistribution_appears_only_as_a_retraction():
    for path in VENDOR_TEXTS:
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"commercial\s+redistribution", text, re.I):
            after = text[m.end(): m.end() + 160]
            assert "neither was true" in after, (
                f"{path.relative_to(ROOT)} claims commercial redistribution: "
                f"{text[m.start(): m.end() + 80]!r}"
            )
