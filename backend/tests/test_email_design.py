"""Email design-system invariants.

Every renderer must produce HTML that:
  1. Carries a preheader (the hidden inbox-preview snippet)
  2. Includes the `prefers-color-scheme: dark` override block
  3. Declares color-scheme meta tags so Gmail doesn't double-invert
  4. Uses the system font stack (Inter and JetBrains Mono don't load in
     Gmail/Outlook desktop)
  5. Renders the Tapeline brand header
  6. Renders the standard footer with the Not-investment-advice disclaimer
     + manage-prefs link
  7. Renders a clickable CTA href to a tapeline.io URL

If any of these regresses, an email shipped to a real inbox will look
broken in at least one major client. Cheaper to assert here than to find
out from a customer.
"""
from __future__ import annotations

import pytest

from app.services import email as e


def _all_html_outputs() -> list[tuple[str, str]]:
    """Render one variant of each renderer with representative inputs."""
    return [
        ("welcome_with_picks", e.render_welcome_email(
            "Alex",
            picks=[
                {"symbol": "AAPL", "score": 82, "signal": "STRONG SETUP",
                 "reason": "Trend strong, fundamentals 78, RS +4%"},
                {"symbol": "MSFT", "score": 71, "signal": "STRONG SETUP",
                 "reason": "Earnings beat + sector momentum"},
                {"symbol": "NVDA", "score": 88, "signal": "HIGH CONVICTION",
                 "reason": "Squeeze setup confirmed, smart money 90"},
            ],
        )),
        ("welcome_fallback", e.render_welcome_email("Alex", picks=None)),
        ("referral_referee", e.render_referral_referee_email("Alex", "Sam")),
        ("referral_referrer", e.render_referral_referrer_email("Alex", "ne***@example.com")),
        ("day3", e.render_trial_day3_email("Alex")),
        ("day7_no_summary", e.render_trial_day7_email("Alex", None)),
        ("day7_with_summary", e.render_trial_day7_email("Alex", {
            "watchlist_count": 8, "watchlist_top_signals": 3,
            "watchlist_best": {"symbol": "AMD", "score": 84, "signal": "STRONG SETUP", "delta": 12.4},
            "scorecard_picks_during_trial": 12,
            "scorecard_hit_rate": 67.0, "scorecard_alpha_avg": 0.82,
            "scorecard_best": {"symbol": "PLTR", "as_of": "2026-05-10", "alpha": 3.4},
        })),
        ("day11", e.render_trial_day11_email("Alex", None)),
        ("day13", e.render_trial_day13_email("Alex", None)),
        ("trial_expired", e.render_trial_expired_email("Alex", None)),
        ("trial_post_expiry", e.render_trial_post_expiry_email("Alex")),
        ("trial_ended", e.render_trial_ended_email("Alex")),
        ("payment_failed_first", e.render_payment_failed_email("Alex", "pro", 1)),
        ("payment_failed_third", e.render_payment_failed_email("Alex", "premium", 3)),
        ("alert", e.render_alert_email(
            "Alex", "AAPL crossed 80", "AAPL", 81.5,
            "Score crossed your threshold of 80",
        )),
        ("watchlist_alert", e.render_watchlist_alert_email(
            "Alex", "AMD", 78.0, 65.0, "STRONG SETUP",
            "Trend and momentum both turned up sharply.",
        )),
        ("digest_with_items", e.render_eod_watchlist_digest(
            "Alex",
            [
                {"symbol": "AAPL", "score": 82, "signal": "STRONG SETUP",
                 "change_pct_1d": 1.4, "score_delta": 3.2,
                 "reason": "Trend strong, fundamentals 78"},
                {"symbol": "MSFT", "score": 71, "signal": "CONSTRUCTIVE",
                 "change_pct_1d": -0.6, "score_delta": -1.1,
                 "reason": "Sector weak today"},
            ],
        )),
        ("digest_empty", e.render_eod_watchlist_digest("Alex", [])),
        ("re_engagement", e.render_re_engagement_email("Alex")),
        ("weekly_newsletter_full", e.render_weekly_market_digest(
            "Alex",
            week_label="May 19, 2026",
            regime={"regime": "BULL", "vix": 14.3, "yield_10y": 4.2,
                    "breadth_pct": 67.0, "sector_leaders": "Tech, Healthcare"},
            movers=[
                {"symbol": "NVDA", "score": 88, "signal": "HIGH CONVICTION",
                 "reason": "Smart money + squeeze"},
                {"symbol": "AAPL", "score": 82, "signal": "STRONG SETUP",
                 "reason": "Trend + RS"},
            ],
            scorecard={"picks": 50, "hit_rate_pct": 62.0, "avg_alpha_pct": 0.41,
                       "best": {"symbol": "NVDA", "alpha": 4.8}},
            headlines=[
                {"title": "Fed holds rates",
                 "publisher": "Reuters", "url": "https://tapeline.io"},
            ],
        )),
        ("weekly_newsletter_empty", e.render_weekly_market_digest(
            "Alex",
            week_label="May 19, 2026",
            regime=None, movers=[], scorecard=None, headlines=[],
        )),
        ("email_verification", e.render_email_verification_email(
            "Alex",
            verify_url="https://tapeline.io/verify-email?token=demo",
            cancel_url="https://tapeline.io/verify-email?token=demo&action=cancel",
        )),
        ("subscription_started_pro", e.render_subscription_started_email(
            "Alex", tier="pro", billing_period="monthly",
            amount_cents=2999, currency="usd",
            next_charge_iso="2026-06-19T00:00:00+00:00",
        )),
        ("password_reset", e.render_password_reset_email(
            "Alex",
            reset_url="https://tapeline.io/reset-password?token=demo",
        )),
    ]


@pytest.mark.parametrize("name,html", _all_html_outputs(), ids=lambda x: x if isinstance(x, str) else "")
def test_email_carries_design_system_invariants(name: str, html: str) -> None:
    """Single parametrised guard across every renderer.

    Asserts the shell wired up the design system end-to-end. If a future
    renderer is added that bypasses `shell(...)` and inlines its own
    document, these checks fail and force the author to use the helpers.
    """
    # 1. Non-empty + recognisable as our shell
    assert html, f"{name} returned empty HTML"
    assert "<!doctype html>" in html.lower(), f"{name} missing doctype"

    # 2. color-scheme support so Gmail doesn't double-invert
    assert 'name="color-scheme"' in html, f"{name} missing color-scheme meta"
    assert 'name="supported-color-schemes"' in html, (
        f"{name} missing supported-color-schemes meta"
    )

    # 3. Dark-mode override present
    assert "prefers-color-scheme: dark" in html, (
        f"{name} missing dark-mode media query — light-only emails look "
        f"flat in Apple Mail / Outlook iOS dark themes"
    )

    # 4. System font stack — NOT loading Inter/JetBrains Mono which don't
    # render in Gmail or Outlook desktop. Verifies we're using the stack
    # from email_design.FONT_SANS.
    assert "-apple-system" in html, f"{name} missing system font stack"
    # Inter must not appear — it's a sign someone left the old shell.
    assert "Inter," not in html, f"{name} still references the legacy Inter font"

    # 5. Brand header present
    assert ">Tapeline<" in html, f"{name} missing Tapeline brand header"

    # 6. Footer present (disclaimer + email-prefs link)
    assert "Not investment advice" in html, f"{name} missing legal disclaimer"
    assert "/app/settings/email" in html, (
        f"{name} missing 'Manage email preferences' footer link — CAN-SPAM hygiene"
    )

    # 7. CTA points at tapeline.io
    assert "tapeline.io" in html, f"{name} has no tapeline.io links — broken CTA"


def test_preheader_present_on_every_renderer_that_should_have_one() -> None:
    """Most renderers MUST include a preheader (the inbox-preview snippet);
    that's a serious open-rate lever. The shell makes preheader text
    visible only as the hidden snippet — we look for the `mso-hide:all`
    span which wraps it.
    """
    must_have = [
        ("welcome", e.render_welcome_email("Alex", picks=None)),
        ("day7", e.render_trial_day7_email("Alex", None)),
        ("day13", e.render_trial_day13_email("Alex", None)),
        ("watchlist_alert", e.render_watchlist_alert_email(
            "Alex", "AMD", 78.0, 65.0, "STRONG SETUP", "test reason",
        )),
        ("digest", e.render_eod_watchlist_digest("Alex", [
            {"symbol": "X", "score": 70, "signal": "STRONG SETUP",
             "change_pct_1d": 1.0, "score_delta": 1.0, "reason": "r"},
        ])),
        ("payment_failed", e.render_payment_failed_email("Alex", "pro", 1)),
    ]
    for name, html in must_have:
        assert "mso-hide:all" in html, (
            f"{name} missing preheader (no mso-hide:all span) — that's a "
            f"meaningful open-rate hit because the inbox-preview falls back "
            f"to whatever text appears first in the email body"
        )


def test_day13_uses_urgent_button_variant() -> None:
    """The T-1 email is the only renderer that should use the amber/urgent
    button. Asserts the visual urgency is actually wired up."""
    html = e.render_trial_day13_email("Alex", None)
    # Amber background hex from email_design.button(variant="urgent")
    assert "#f59e0b" in html, "day-13 should use the urgent amber button"


def test_non_urgent_renderers_use_accent_button() -> None:
    """Sanity check: the non-T-1 renderers should NOT use the amber urgency
    colour for their primary CTA — that visual cue is reserved."""
    blue = "#3b82f6"  # ACCENT
    amber = "#f59e0b"
    for name, html in [
        ("welcome", e.render_welcome_email("Alex", picks=None)),
        ("day3", e.render_trial_day3_email("Alex")),
        ("day7", e.render_trial_day7_email("Alex", None)),
        ("day11", e.render_trial_day11_email("Alex", None)),
        ("re_engagement", e.render_re_engagement_email("Alex")),
    ]:
        assert blue in html, f"{name} should use the accent button"
        # The amber may still appear in the score_color palette for a CAUTION
        # ticker; we only care that it's NOT used as the CTA background. We
        # look for the bulletproof button anchor where bg=amber.
        assert f"background:{amber};color:#0a0a0a" not in html, (
            f"{name} should not use the urgent button variant"
        )
