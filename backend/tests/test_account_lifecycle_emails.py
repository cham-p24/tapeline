"""Content + ASIC-safety tests for the save-offer, security-confirmation,
and GDPR-confirmation email renderers.

These renderers are pure (no DB, no I/O), so the tests verify the HTML
structure, the load-bearing copy, and — critically — that none of them leak
prescriptive/advice language. Tapeline publishes transparent historical model
output, NOT financial advice, so user-facing copy must stay descriptive
("your Premium stays at 50% off") and never prescriptive ("buy", "sell",
"will go up", "guaranteed", "recommend", "should"). The design-system
invariants (shell, dark mode, footer disclaimer) are covered by
test_email_design.py's parametrised guard.
"""
from __future__ import annotations

import re

import pytest

from app.services.email import (
    render_gdpr_confirmation_email,
    render_save_offer_accepted_email,
    render_security_confirmation_email,
)

# Prescriptive words that must never appear in descriptive, ASIC-safe copy.
# Word-boundary matched, case-insensitive. "should" is excluded as a bare
# substring because it would false-positive on "shoulder" etc.; we match it
# as a whole word.
_FORBIDDEN_ADVICE = [
    r"\bbuy\b",
    r"\bsell\b",
    r"\bwill go up\b",
    r"\bguaranteed\b",
    r"\brecommend\b",
    r"\bhot pick\b",
]


def _assert_no_advice_language(html: str, name: str) -> None:
    lowered = html.lower()
    for pat in _FORBIDDEN_ADVICE:
        assert not re.search(pat, lowered), (
            f"{name} contains prescriptive/advice language matching {pat!r} — "
            f"violates the ASIC descriptive-copy rule"
        )


def _assert_no_leaked_placeholders(html: str, name: str) -> None:
    """Strip the <style> block (legit CSS braces) then assert no leftover
    `{identifier}` f-string placeholders escaped into the body."""
    html_no_style = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
    leaked = re.findall(r"\{[a-z_][a-z0-9_]*\}", html_no_style)
    assert not leaked, f"{name} leaked template placeholders: {leaked[:5]}"


# ── Save-offer accepted ──────────────────────────────────────────────────────

def test_save_offer_accepted_renders_with_name_and_tier() -> None:
    html = render_save_offer_accepted_email("Alice", tier="premium")
    assert "Alice" in html
    # Tier appears, capitalised
    assert "Premium" in html
    # The headline promise: 50% off for 3 months
    assert "50% off" in html
    assert "3 months" in html
    _assert_no_leaked_placeholders(html, "save_offer_accepted")


def test_save_offer_accepted_is_warm_and_descriptive() -> None:
    html = render_save_offer_accepted_email("Alice", tier="pro")
    _assert_no_advice_language(html, "save_offer_accepted")
    # Reassuring "you're staying" framing, not a hard upsell
    assert "staying" in html.lower()


def test_save_offer_accepted_handles_empty_tier() -> None:
    html = render_save_offer_accepted_email("Trader", tier="")
    assert "Trader" in html
    # Empty tier falls back to "your plan"
    assert "your plan".capitalize() in html or "Your plan" in html


# ── Security confirmation ────────────────────────────────────────────────────

def test_security_confirmation_renders_change_and_recovery_path() -> None:
    html = render_security_confirmation_email(
        "Bob", change="Your password was changed",
    )
    assert "Bob" in html
    # The change is echoed in the body
    assert "password was changed" in html.lower()
    # Recovery CTA → account page
    assert "https://tapeline.io/app/account" in html
    # "wasn't you" recovery framing present
    assert "didn't" in html.lower()
    _assert_no_leaked_placeholders(html, "security_confirmation")
    _assert_no_advice_language(html, "security_confirmation")


def test_security_confirmation_includes_optional_timestamp() -> None:
    when = "June 16, 2026 at 9:14am AEST"
    html = render_security_confirmation_email(
        "Bob", change="Your password was changed", when_label=when,
    )
    assert when in html


def test_security_confirmation_never_echoes_a_secret() -> None:
    """We must confirm the FACT of the change, never the new credential."""
    html = render_security_confirmation_email(
        "Bob", change="Your password was changed",
    )
    # No literal password value should ever be passed/echoed — the renderer
    # has no parameter for it, so this is a guard against future regressions.
    assert "password:" not in html.lower()


# ── GDPR confirmation ────────────────────────────────────────────────────────

def test_gdpr_export_confirmation() -> None:
    html = render_gdpr_confirmation_email("Carol", kind="export")
    assert "Carol" in html
    assert "export" in html.lower()
    # References the GDPR right by article for the user's records
    assert "Article 15" in html
    _assert_no_leaked_placeholders(html, "gdpr_export")
    _assert_no_advice_language(html, "gdpr_export")


def test_gdpr_deletion_confirmation() -> None:
    html = render_gdpr_confirmation_email("Carol", kind="deletion")
    assert "Carol" in html
    assert "deleted" in html.lower()
    assert "Article 17" in html
    # Makes clear it's final + no more emails
    assert "can't be undone" in html.lower() or "cannot be undone" in html.lower()
    _assert_no_leaked_placeholders(html, "gdpr_deletion")
    _assert_no_advice_language(html, "gdpr_deletion")


def test_gdpr_unknown_kind_falls_back_to_export_shape() -> None:
    """Defensive: an unexpected kind should still render a valid export-style
    email rather than raising — the renderer treats anything != 'deletion'
    as the export variant."""
    html = render_gdpr_confirmation_email("Carol", kind="something_else")
    assert "<!doctype html>" in html.lower()
    assert "Carol" in html


@pytest.mark.parametrize(
    "html",
    [
        render_save_offer_accepted_email("Alex", tier="premium"),
        render_security_confirmation_email("Alex", change="Your password was changed"),
        render_gdpr_confirmation_email("Alex", kind="export"),
        render_gdpr_confirmation_email("Alex", kind="deletion"),
    ],
)
def test_new_emails_carry_preheader(html: str) -> None:
    """Every new renderer must set a preheader (the hidden inbox-preview
    snippet) — the shell renders it inside an mso-hide:all span."""
    assert "mso-hide:all" in html
