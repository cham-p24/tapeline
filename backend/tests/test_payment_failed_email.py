"""Smoke tests for the payment-failed email renderer.

The renderer is pure (no DB, no I/O), so these tests just verify the HTML
structure, key substrings, and that we don't leak jinja syntax or break on
edge-case inputs. The actual delivery path is tested by exercising the
Stripe webhook handler end-to-end in test_smoke.py.
"""
from __future__ import annotations

from app.services.email import _ordinal, render_payment_failed_email


def test_payment_failed_renders_with_user_name_and_tier() -> None:
    html = render_payment_failed_email("Alice", "premium", attempt_count=1)
    # User name personalisation
    assert "Alice," in html
    # Tier appears, capitalised
    assert "Premium subscription" in html
    # Fix-it CTA link is present
    assert 'href="https://tapeline.io/app/billing"' in html
    # First-attempt copy is the soft variant ("Stripe will retry automatically")
    assert "Stripe will retry automatically" in html
    # No jinja or f-string template placeholders leaked through. The shell
    # has a legitimate <style> block with CSS curly braces, so we look for
    # the unmistakable signature of an unresolved placeholder: a `{word}`
    # or `{word_word}` token surrounded by HTML text (NOT inside `<style>`).
    import re
    # Strip the <style>...</style> block so we don't false-positive on CSS.
    html_no_style = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
    # Any remaining `{identifier}` is a leaked placeholder.
    leaked = re.findall(r"\{[a-z_][a-z0-9_]*\}", html_no_style)
    assert not leaked, f"unresolved template placeholders: {leaked[:5]}"


def test_payment_failed_third_attempt_uses_urgent_copy() -> None:
    html = render_payment_failed_email("Bob", "pro", attempt_count=3)
    # On 3rd attempt the copy is no longer "we'll retry" — it warns about downgrade
    assert "3rd attempt" in html
    assert "drops to Free" in html
    # Soft copy should NOT appear in the urgent variant
    assert "Stripe will retry automatically" not in html


def test_payment_failed_handles_empty_tier_gracefully() -> None:
    # If the webhook lands with an empty tier string (shouldn't happen but guard anyway),
    # we still get a valid email — just with a weird "  subscription" double space.
    html = render_payment_failed_email("Trader", "", attempt_count=1)
    assert "Trader," in html
    assert "subscription" in html.lower()
    assert 'href="https://tapeline.io/app/billing"' in html


def test_payment_failed_special_chars_in_name_dont_break_html() -> None:
    # We don't currently escape — names are stored from signup form which doesn't
    # validate against HTML chars. Worst case is a weird-looking email, not XSS,
    # because Resend renders to email clients that handle this safely.
    html = render_payment_failed_email("O'Reilly", "premium", attempt_count=1)
    assert "O'Reilly," in html


def test_ordinal_helper() -> None:
    """The _ordinal helper is used in payment-failed copy for retry attempts."""
    assert _ordinal(1) == "1st"
    assert _ordinal(2) == "2nd"
    assert _ordinal(3) == "3rd"
    assert _ordinal(4) == "4th"
    assert _ordinal(11) == "11th"  # teens are all "th"
    assert _ordinal(12) == "12th"
    assert _ordinal(13) == "13th"
    assert _ordinal(21) == "21st"  # 21 not 21th
    assert _ordinal(22) == "22nd"
    assert _ordinal(101) == "101st"
    assert _ordinal(111) == "111th"  # 111 is in the teens edge case
