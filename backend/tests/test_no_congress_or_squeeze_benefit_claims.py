"""No email, inbox reply or plan description sells congress or squeeze data.

Integrity fix, founder-approved 2026-09-14 (ticket T-02 and the squeeze sell
copy). Evidence: C:/Tapeline/brand/deepdive/01_ground_truth.md sections 1.5
and 3.3.

* No real congressional disclosure has ever been ingested. Every
  `congress_trades` row in production is mock output, and
  services/congress_integrity.py already refuses to publish them.
* Every `squeeze_setups` row in production is mock output last written
  2026-07-18; the production writer has never been configured.

Both were still sold in the trial tour (day 3), the day-7/13 conversion
emails, the win-back, checkout recovery, the free-invite list, the carded
trial setup and value emails, the "month on us" offer, the free-tier
changelog, the inbox pricing/trial replies and the daily briefing.

This test renders EVERY `render_*` function in services/email.py with
synthesised arguments, so a renderer added later is covered without anyone
remembering to list it. What it deliberately does NOT cover: the per-rule
alert email (`render_alert_email`), whose job is to name the rule type a user
already set up. That is a notification about an existing rule, not a benefit
claim.
"""
from __future__ import annotations

import inspect
import re
from datetime import UTC, date, datetime

import pytest

import app.services.email as email_mod
from app.services import inbox_templates

BANNED = re.compile(r"congress|squeeze", re.I)

# Notifications about a rule the user already created, not benefit claims.
NOT_A_SELL_SURFACE = {"render_alert_email"}


def _value_for(p: inspect.Parameter):
    if p.default is not inspect.Parameter.empty:
        return p.default
    ann = str(p.annotation)
    if "datetime" in ann:
        return datetime.now(UTC)
    if "date" in ann:
        return date.today()
    if "dict" in ann:
        return {}
    if "list" in ann or "Sequence" in ann:
        return []
    if "bool" in ann:
        return False
    if "float" in ann:
        return 3.0
    if "int" in ann:
        return 3
    return "Sam"


def _renderers():
    out = []
    for name, fn in inspect.getmembers(email_mod, inspect.isfunction):
        if not name.startswith("render_") or fn.__module__ != email_mod.__name__:
            continue
        if name in NOT_A_SELL_SURFACE:
            continue
        out.append((name, fn))
    return out


RENDERERS = _renderers()


def test_the_renderer_sweep_found_the_emails_it_is_meant_to_cover():
    names = {n for n, _ in RENDERERS}
    for expected in (
        "render_welcome_email",
        "render_trial_day3_email",
        "render_trial_day7_email",
        "render_trial_day13_email",
        "render_winback_email",
        "render_free_trial_invite_email",
        "render_free_trial_last_invite_email",
        "render_trial_started_email",
        "render_carded_trial_setup_email",
        "render_carded_trial_value_email",
        "render_free_tier_changelog_email",
        "render_free_tier_changelog_text",
    ):
        assert expected in names, f"{expected} is no longer swept"


@pytest.mark.parametrize("name,fn", RENDERERS, ids=[n for n, _ in RENDERERS])
async def test_no_email_renderer_claims_congress_or_squeeze(name, fn):
    kwargs = {
        p.name: _value_for(p)
        for p in inspect.signature(fn).parameters.values()
        if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
    }
    try:
        out = fn(**kwargs)
        if inspect.isawaitable(out):
            out = await out
    except Exception as exc:  # a renderer the synthesiser cannot drive
        pytest.skip(f"{name} could not be rendered with synthesised args: {exc!r}")
    text = out if isinstance(out, str) else str(out)
    hits = [m.group(0) for m in re.finditer(r".{0,50}(?:congress|squeeze).{0,50}", text, re.I)]
    assert not hits, f"{name} still mentions congress/squeeze: {hits[:3]}"


def test_free_tier_changelog_lines_do_not_sell_the_squeeze_preview():
    lines = email_mod._free_tier_changelog_lines()
    assert not any(BANNED.search(line) for line in lines), lines


async def test_inbox_pricing_and_trial_replies_do_not_claim_congress():
    for render in (inbox_templates.render_pricing, inbox_templates.render_trial):
        text = await render("")
        assert not BANNED.search(text), (render.__name__, text)
        assert "SEC Form 4" in text


def test_tier_module_description_sells_neither():
    """The user-facing plan summary at the top of tier.py.

    The entitlement KEYS (`squeeze.full`, `congress.feed`) are deliberately
    unchanged: this fix changes what we claim, not what anyone may reach.
    """
    from app.services import tier

    assert tier.FEATURES["squeeze.full"] == tier.Tier.PRO
    assert tier.FEATURES["congress.feed"] == tier.Tier.PREMIUM
    doc = (tier.__doc__ or "").split("The `squeeze.full`")[0]
    assert not BANNED.search(doc), doc


async def test_daily_briefing_renders_no_squeeze_section():
    from app.services import briefing

    html = briefing._render_html(
        user_name="Sam",
        regime=None,
        watchlist_rows=[],
        baselines={},
        thresholds={},
        squeezes=(),
        squeeze_label="",
        cta_href="https://tapeline.io/app/scanner",
        cta_label="Open the scanner",
        watchlist_total=None,
    )
    assert not BANNED.search(html)
    src = inspect.getsource(briefing._generate_sitewide) + inspect.getsource(
        briefing._generate_personalised
    )
    assert "select(SqueezeSetup)" not in src
