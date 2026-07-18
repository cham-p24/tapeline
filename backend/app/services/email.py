"""Email delivery via Resend with per-persona sender routing.

Tapeline sends 14 distinct email categories. Recipients are confused (and
deliverability suffers) when every email comes from a single From: alias.
This module dispatches by `persona`:

    "default"   transactional onboarding (welcome, referrals, activation)
                    From: hello@tapeline.io
    "sales"     conversion nurture (trial drip day-7+, re-engagement, win-back)
                    From: christian@tapeline.io
    "billing"   Stripe payment failures, invoices
                    From: billing@tapeline.io
    "alerts"    automated digests + user alert rules
                    From: alerts@tapeline.io

Reply-To always points at support@tapeline.io which IS routed via Cloudflare
Email Routing → tapeline.inbox@gmail.com. So replies always land somewhere
real, even before per-persona aliases get their own routing rules.

Every renderer here composes its body via the helpers in
`app.services.email_design` and wraps with `shell(...)`. Inline raw HTML
is reserved for one-off pricing/header layouts that don't fit a primitive
yet. See email_design.py for the design system rationale.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal

import httpx

from app.config import get_settings
from app.services.email_design import (
    ACCENT,
    FONT_MONO,
    FONT_SANS,
    LIGHT_BORDER,
    LIGHT_FG,
    LIGHT_MUTED,
    LIGHT_SUBTLE,
    SIG_BEAR,
    SIG_BULL,
    button,
    card,
    footnote,
    h1,
    lead,
    muted_paragraph,
    paragraph,
    score_color,
    secondary_link,
    shell,
    stat_row,
    ticker_card,
    watchlist_table,
)

# Freemium caps quoted in email copy. Referencing the tier.py constants (the
# single source of truth) instead of hardcoding numbers means a freemium
# retune can never leave the drip emails selling against a Free tier that no
# longer exists (which is exactly what happened after the 2026-06-20 retune).
# The global frequency governor. Every non-transactional send in this module
# routes through it so no user can receive colliding messages from two flows
# that don't know about each other. Safe to import at module scope: lifecycle
# imports nothing from here (its only app import is a TYPE_CHECKING-guarded
# models reference), so there's no cycle.
from app.services.lifecycle import FrequencyGovernor, SendClass
from app.services.tier import (
    FREE_DAILY_LOOKUPS,
    FREE_SCANNER_ROWS,
    FREE_WATCHLIST_TICKERS,
    FREE_WEB_PUSH_ALERTS,
)
from app.services.universe import ACTIVE_UNIVERSE_SIZE

logger = logging.getLogger(__name__)
settings = get_settings()

RESEND_API = "https://api.resend.com"

EmailPersona = Literal["default", "sales", "billing", "alerts"]


def _persona_addresses(persona: EmailPersona) -> tuple[str, str]:
    """Return (from_address, reply_to_address) for the given persona.

    All four addresses live under the Resend-verified tapeline.io domain —
    no extra DNS work is needed to start sending from any of them. Reply-To
    is shared across personas (support@tapeline.io, already routed) so we
    have a single bounce-safe reply hub.
    """
    sender = {
        "default": settings.email_from,
        "sales":   settings.email_from_sales,
        "billing": settings.email_from_billing,
        "alerts":  settings.email_from_alerts,
    }[persona]
    return sender, settings.email_reply_to


async def send_email(
    to: str,
    subject: str,
    html: str,
    text: str | None = None,
    *,
    persona: EmailPersona = "default",
    unsubscribe_user_id: str | None = None,
    unsubscribe_category: str = "all",
    skip_if_undeliverable: bool = True,
) -> dict[str, Any]:
    """Send a single email via Resend. Returns the Resend response or raises.

    Pick `persona` based on what category of email this is:

        send_email(..., persona="sales")     # trial drip day 7+, re-engagement
        send_email(..., persona="billing")   # Stripe events
        send_email(..., persona="alerts")    # automated digests
        send_email(..., )                    # everything else (transactional)

    Marketing-category emails should also pass `unsubscribe_user_id` and
    optionally `unsubscribe_category` — we inject the RFC 8058 +
    RFC 2369 List-Unsubscribe headers so Gmail renders a native opt-out
    button next to the sender name. Transactional emails (welcome,
    payment-failed, verification, subscription-started) should NOT pass
    these — they're account-state notifications the user can't opt out
    of, and adding the header would mislead Gmail's classifier.

    `skip_if_undeliverable` defaults True — checks `User.email_undeliverable_at`
    via the email address (one extra DB query per send, acceptable at our
    volume). Stops us burning Resend reputation on bounces / spam-flags.
    Set False for self-test paths (admin "send to me" button) that need
    to deliver regardless of historical bounces.
    """
    if not settings.resend_api_key:
        logger.warning(
            "email.skipped reason=no_api_key persona=%s to=%s subject=%s",
            persona, to, subject,
        )
        return {"skipped": True, "reason": "no_api_key"}

    # Stop sending to addresses Resend has already told us are dead. One
    # cheap query per send; saves us from racking up bounces that would
    # tank the domain's sender reputation.
    if skip_if_undeliverable:
        try:
            from sqlalchemy import select

            from app.db import session_scope
            from app.models import User

            async with session_scope() as s:
                r = await s.execute(
                    select(User.email_undeliverable_at).where(
                        User.email == to.lower().strip(),
                    )
                )
                row = r.first()
                if row is not None and row[0] is not None:
                    logger.info(
                        "email.skipped reason=undeliverable persona=%s to=%s",
                        persona, to,
                    )
                    return {"skipped": True, "reason": "undeliverable"}
        except Exception:
            # Never let a stray DB error block a send; we'd rather burn
            # a tiny reputation hit than fail to deliver a real message.
            logger.exception("email.undeliverable_check_failed to=%s", to)

    sender, reply_to = _persona_addresses(persona)

    payload: dict[str, Any] = {
        "from": f"Tapeline <{sender}>",
        "to": [to],
        "subject": subject,
        "html": html,
        "reply_to": [reply_to],
    }
    if text:
        payload["text"] = text

    # RFC 8058 / 2369 List-Unsubscribe headers for marketing categories.
    # Gmail + Outlook render a native unsubscribe button when both headers
    # are present and the URL resolves on POST. Omitted when session_secret
    # isn't configured (orchestrator passes the user id but unsubscribe.py
    # returns {} for the headers).
    if unsubscribe_user_id:
        try:
            from app.services.unsubscribe import list_unsubscribe_headers
            extra_headers = list_unsubscribe_headers(
                unsubscribe_user_id, unsubscribe_category,
            )
            if extra_headers:
                payload["headers"] = extra_headers
        except Exception:
            logger.exception(
                "email.unsubscribe_header_failed user=%s",
                unsubscribe_user_id,
            )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{RESEND_API}/emails",
            json=payload,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()


# ── Alert emails ────────────────────────────────────────────────────────────

def render_alert_email(
    user_name: str, rule_name: str, symbol: str, score: float, message: str,
) -> str:
    """User-rule alert (score / squeeze / regime / congress / news).

    Single CTA → /app/scanner since these are usually market-wide signals;
    if the alert is symbol-specific the receiver can click into the ticker
    from the scanner.
    """
    body = (
        h1(f"Alert: {rule_name}")
        + lead(
            f"Hi {user_name}, one of your alert rules just triggered. "
            f"Score and signal below — open the scanner for the full breakdown."
        )
        + card(
            f'<div class="tl-fg" style="font-family:{FONT_MONO};font-size:24px;font-weight:700;color:{LIGHT_FG};line-height:1;">{symbol}</div>'
            f'<div style="margin-top:6px;color:{score_color(score)};font-weight:600;font-size:14px;font-family:{FONT_SANS};">Score · {score:.1f}</div>'
            f'<div class="tl-muted" style="margin-top:10px;color:{LIGHT_MUTED};font-size:14px;line-height:1.55;font-family:{FONT_SANS};">{message}</div>',
            accent=True,
        )
        + button("Open the scanner", "https://tapeline.io/app/scanner")
    )
    return shell(
        body,
        preheader=f"{rule_name} triggered on {symbol} (score {score:.0f}).",
    )


def render_watchlist_alert_email(
    user_name: str,
    symbol: str,
    current_score: float,
    baseline_score: float,
    signal: str | None,
    reason: str | None,
) -> str:
    """Smart alert: a watchlisted ticker's score moved past the user's delta
    threshold relative to where they added it.

    Distinct from the EOD digest — this is per-ticker, intra-day, and only
    fires on significant moves. Debounced 24h via WatchlistItem.last_alert_at.
    """
    delta = current_score - baseline_score
    sign = "+" if delta >= 0 else ""
    direction = "moved up past" if delta >= 0 else "dropped past"
    delta_col = SIG_BULL if delta >= 0 else SIG_BEAR
    return shell(
        h1(f"Watchlist alert · {symbol}")
        + lead(
            f"Hi {user_name}, <strong>{symbol}</strong> {direction} your alert "
            f"threshold. Here's where it sits right now."
        )
        + card(
            f"""
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
              <tr>
                <td style="vertical-align:middle;">
                  <div class="tl-fg" style="font-family:{FONT_MONO};font-size:26px;font-weight:700;color:{LIGHT_FG};line-height:1;">{symbol}</div>
                  <div style="margin-top:6px;font-size:12px;text-transform:uppercase;letter-spacing:0.08em;color:{score_color(current_score)};font-family:{FONT_SANS};font-weight:600;">{signal or "—"}</div>
                </td>
                <td align="right" style="vertical-align:middle;">
                  <div style="font-family:{FONT_MONO};font-size:32px;font-weight:700;color:{score_color(current_score)};line-height:1;">{current_score:.0f}</div>
                  <div style="margin-top:6px;font-family:{FONT_MONO};font-size:13px;color:{delta_col};font-weight:600;">{sign}{delta:.1f}</div>
                </td>
              </tr>
            </table>
            <div class="tl-divider" style="height:1px;background:{LIGHT_BORDER};margin:14px 0;"></div>
            """
            + stat_row("Baseline (when you added)", f"{baseline_score:.0f}")
            + stat_row("Threshold crossed", f"{sign}{delta:.1f} pts", value_color=delta_col)
        )
        + (muted_paragraph(reason.strip()[:240]) if reason else "")
        + button(f"Open {symbol}", f"https://tapeline.io/app/ticker/{symbol}")
        + footnote(
            f"You're seeing this because <strong>{symbol}</strong> is on your watchlist. "
            f"We won't re-alert on this ticker for at least 24 hours."
        ),
        preheader=(
            f"{symbol} score now {current_score:.0f} ({sign}{delta:.1f} from baseline)."
        ),
    )


# ── Welcome / day-0 ─────────────────────────────────────────────────────────

def render_welcome_email(
    user_name: str, picks: list[dict[str, Any]] | None = None,
) -> str:
    """Day 0 — sent immediately on signup.

    `picks` is the top-3 currently-scored tickers from the live scanner.
    Embedding 3 actual scores here lets the user see the product in their
    inbox, not just a "click here to see scores" CTA. Falls back to the
    static three-things checklist if picks is empty (worker hasn't ticked
    yet, etc.).
    """
    if picks:
        picks_html = "".join(
            ticker_card(
                p.get("symbol", "?"),
                p.get("score"),
                p.get("signal"),
                p.get("reason"),
            )
            for p in picks[:3]
        )
        body = (
            h1(f"Welcome, {user_name}.")
            + lead(
                "Your <strong>14-day Premium trial</strong> is live — everything's "
                "unlocked. Three live scores from the scanner right now:"
            )
            + picks_html
            + button(
                "Open the full scanner",
                "https://tapeline.io/app/scanner?utm_source=email&utm_campaign=welcome&utm_medium=transactional",
            )
            + muted_paragraph(
                'Tap any card above to see the 6-factor breakdown. The formula '
                'is public — see <a href="https://tapeline.io/how-it-works" '
                f'style="color:{ACCENT};">how it works</a>.'
            )
            + footnote("No card on file. We'll remind you before the trial ends.")
        )
    else:
        body = (
            h1(f"Welcome, {user_name}.")
            + lead(
                "Your <strong>14-day Premium trial</strong> is live. Everything's unlocked."
            )
            + muted_paragraph("Three things to try in the first five minutes:")
            + card(
                f"""
                <ol style="margin:0;padding-left:20px;color:{LIGHT_FG};font-family:{FONT_SANS};font-size:14px;line-height:1.7;">
                  <li><strong>Scanner</strong> — every ticker scored; hover any score for the 6-factor breakdown</li>
                  <li><strong>Public scorecard</strong> — every call we've ever made, with the original reasoning</li>
                  <li><strong>Watchlist</strong> — add 5-10 tickers, get smart alerts when scores shift past your threshold</li>
                </ol>
                """
            )
            + button(
                "Open the scanner",
                "https://tapeline.io/app/scanner?utm_source=email&utm_campaign=welcome&utm_medium=transactional",
            )
            + footnote("No card on file. We'll remind you before the trial ends.")
        )
    return shell(
        body,
        preheader=(
            "Your 14-day Premium trial is live — three live scores inside."
            if picks else "Your 14-day Premium trial is live — open the scanner."
        ),
    )


def render_referral_referee_email(
    user_name: str, referrer_name: str | None,
) -> str:
    """Sent to a new user who signed up via a referral link."""
    referrer_str = referrer_name or "your friend"
    return shell(
        h1(f"Welcome, {user_name}.")
        + lead(
            f"You signed up via {referrer_str}'s referral link — that earned you "
            f"<strong>1 free month of Premium</strong> on top of your 14-day trial."
        )
        + card(
            f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-family:{FONT_SANS};font-weight:600;">Credit applied</div>'
            f'<div style="margin-top:6px;font-family:{FONT_MONO};font-size:26px;font-weight:700;color:{SIG_BULL};">+1 month Premium</div>'
            f'<div class="tl-muted" style="margin-top:6px;color:{LIGHT_MUTED};font-size:13px;font-family:{FONT_SANS};">Auto-redeems at your next checkout.</div>',
            accent=True,
        )
        + muted_paragraph(
            "Trial today, free month after — your first paid month is on us."
        )
        + button("Open the scanner", "https://tapeline.io/app/scanner"),
        preheader="You earned 1 free month of Premium — applied at your next checkout.",
    )


def render_referral_referrer_email(
    user_name: str, referee_email_masked: str,
) -> str:
    """Sent to an existing user when someone joins via their referral link."""
    return shell(
        h1(f"Nice, {user_name} — someone joined.")
        + lead(
            f'<code style="font-family:{FONT_MONO};">{referee_email_masked}</code> '
            f'just signed up with your referral link. That earned you '
            f'<strong>1 free month of Premium</strong>.'
        )
        + card(
            f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-family:{FONT_SANS};font-weight:600;">Credit applied</div>'
            f'<div style="margin-top:6px;font-family:{FONT_MONO};font-size:26px;font-weight:700;color:{SIG_BULL};">+1 month Premium</div>'
            f'<div class="tl-muted" style="margin-top:6px;color:{LIGHT_MUTED};font-size:13px;font-family:{FONT_SANS};">Auto-redeems at your next checkout. Stack credits — refer 12, get a free year.</div>',
            accent=True,
        )
        + button("See your referral page", "https://tapeline.io/app/referrals"),
        preheader="Someone joined via your link — +1 free month of Premium credited.",
    )


# Referral milestones (lever #5). The per-signup referrer email above reinforces
# the FIRST referral, so the celebratory milestone series starts at 3 to avoid
# double-emailing on signup #1. 12 confirmed signups == a free YEAR of Premium
# (one free month each), which is the recurring headline.
_REFERRAL_MILESTONES: tuple[int, ...] = (3, 5, 10, 25)


def render_referral_milestone_email(
    user_name: str, *, milestone: int, total_signups: int,
) -> str:
    """Celebratory note when a user crosses a referral-count milestone.

    Reports the free months they've banked (one per confirmed signup) and
    nudges toward the "refer 12, get a free year" headline. Treated like the
    per-signup referrer email — it reports reward state the user earned by
    referring — so it's transactional: persona "default", no List-Unsubscribe,
    not gated by email_prefs.
    """
    plural = "friend" if total_signups == 1 else "friends"
    months = f"{total_signups} month" + ("" if total_signups == 1 else "s")
    to_free_year = 12 - total_signups
    if to_free_year > 0:
        next_line = (
            f"You're <strong>{to_free_year}</strong> away from a free year of "
            f"Premium — every signup is another month on the house."
        )
    else:
        next_line = (
            "You've now banked more than a free year of Premium. Every extra "
            "signup keeps the credits stacking."
        )
    return shell(
        h1(f"{total_signups} {plural} in — nice work, {user_name}.")
        + lead(
            f"Your referral link just crossed <strong>{milestone}</strong> "
            f"signups. Each one credited you a free month of Premium."
        )
        + card(
            f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-weight:600;font-family:{FONT_SANS};">Free months earned</div>'
            f'<div style="margin-top:6px;font-family:{FONT_MONO};font-size:26px;font-weight:700;color:{SIG_BULL};">{months}</div>'
            f'<div class="tl-muted" style="margin-top:6px;color:{LIGHT_MUTED};font-size:13px;font-family:{FONT_SANS};">{next_line}</div>',
            accent=True,
        )
        + button("See your referral page", "https://tapeline.io/app/referrals")
        + muted_paragraph(
            "Credits auto-redeem at your next checkout — no code to enter."
        ),
        preheader=f"{total_signups} referrals and counting — your free months are stacking up.",
    )


# ── Trial drip ──────────────────────────────────────────────────────────────

def render_trial_day3_email(user_name: str, _summary: dict | None = None) -> str:
    """Day 3 — feature tour."""
    return shell(
        h1(f"{user_name}, three days in.")
        + lead(
            "If you've only been on the scanner, here's what else is in your trial."
        )
        + card(
            f'<div style="font-weight:600;color:{ACCENT};font-size:14px;font-family:{FONT_SANS};">Squeeze Watch</div>'
            f'<div class="tl-muted" style="margin-top:4px;color:{LIGHT_MUTED};font-size:14px;line-height:1.5;font-family:{FONT_SANS};">Bollinger Band compressions flagged before they break. Eight setups updated live.</div>'
        )
        + card(
            f'<div style="font-weight:600;color:{ACCENT};font-size:14px;font-family:{FONT_SANS};">Congress Trades</div>'
            f'<div class="tl-muted" style="margin-top:4px;color:{LIGHT_MUTED};font-size:14px;line-height:1.5;font-family:{FONT_SANS};">Politicians\' disclosed buys and sells. House and Senate, by ticker.</div>'
        )
        + card(
            f'<div style="font-weight:600;color:{ACCENT};font-size:14px;font-family:{FONT_SANS};">Recent insider buys</div>'
            f'<div class="tl-muted" style="margin-top:4px;color:{LIGHT_MUTED};font-size:14px;line-height:1.5;font-family:{FONT_SANS};">SEC Form 4 transactions across the universe — date, insider, shares, value.</div>'
        )
        + card(
            f'<div style="font-weight:600;color:{ACCENT};font-size:14px;font-family:{FONT_SANS};">Telegram alerts</div>'
            f'<div class="tl-muted" style="margin-top:4px;color:{LIGHT_MUTED};font-size:14px;line-height:1.5;font-family:{FONT_SANS};">Hourly digest of your watchlist + market regime, delivered to your phone.</div>'
        )
        + button("Try a Premium feature", "https://tapeline.io/app/holdings"),
        preheader="Squeeze Watch, Congress Trades, Insider Buys, Telegram — inside your trial.",
    )


def _trial_summary_block(summary: dict | None) -> str:
    """Per-user trial-period highlights block. Replaces the legacy
    _render_trial_summary_block with the new design tokens.

    Two streams blended:
      1. Watchlist density (count, HIGH/STRONG signals, biggest mover)
      2. Public scorecard during the trial window (picks logged, hit rate
         vs SPY, avg alpha, best pick)
    Empty → empty string; renderer drops the block silently.
    """
    if not summary:
        return ""
    lines: list[str] = []
    wl_count = summary.get("watchlist_count") or 0
    wl_strong = summary.get("watchlist_top_signals") or 0
    if wl_count > 0:
        lines.append(
            f'<li><strong>Watchlist:</strong> {wl_count} ticker'
            f'{"" if wl_count == 1 else "s"} on watch, '
            f'<span style="color:{SIG_BULL};font-weight:600;">{wl_strong}</span> '
            f'currently HIGH CONVICTION or STRONG SETUP.</li>'
        )
        best = summary.get("watchlist_best")
        if best and best.get("delta") is not None and abs(best["delta"]) >= 1:
            delta = best["delta"]
            sign = "+" if delta > 0 else ""
            colour = SIG_BULL if delta > 0 else SIG_BEAR
            lines.append(
                f'<li><strong>Biggest mover</strong> on your watchlist: '
                f'<code style="font-family:{FONT_MONO};">{best["symbol"]}</code> · '
                f'score now <strong>{best.get("score", 0):.0f}</strong> '
                f'(<span style="color:{colour};font-weight:600;">{sign}{delta:.1f}</span> '
                f'since you added it).</li>'
            )
    picks = summary.get("scorecard_picks_during_trial") or 0
    if picks > 0:
        hit = summary.get("scorecard_hit_rate")
        alpha = summary.get("scorecard_alpha_avg")
        bits = [f'{picks} top-10 pick{"" if picks == 1 else "s"} logged']
        if hit is not None:
            bits.append(f"{hit:.0f}% beat SPY next session")
        if alpha is not None:
            sign = "+" if alpha >= 0 else ""
            bits.append(f"avg alpha {sign}{alpha:.2f}%")
        lines.append(
            '<li><strong>Public scorecard during your trial:</strong> '
            + " · ".join(bits)
            + f' (full record at <a href="https://tapeline.io/scorecard" '
              f'style="color:{ACCENT};">/scorecard</a>).</li>'
        )
        best_pick = summary.get("scorecard_best")
        if best_pick and best_pick.get("alpha") is not None:
            alpha_v = best_pick["alpha"]
            sign = "+" if alpha_v >= 0 else ""
            lines.append(
                f'<li><strong>Best pick this trial:</strong> '
                f'<code style="font-family:{FONT_MONO};">{best_pick["symbol"]}</code> · '
                f'alpha vs SPY <span style="color:{SIG_BULL};font-weight:600;">{sign}{alpha_v:.2f}%</span>.</li>'
            )
    if not lines:
        return ""
    return card(
        f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;'
        f'letter-spacing:0.1em;color:{LIGHT_MUTED};margin-bottom:10px;font-weight:600;font-family:{FONT_SANS};">Your trial so far</div>'
        f'<ul class="tl-fg" style="color:{LIGHT_FG};line-height:1.75;padding-left:18px;'
        f'margin:0;font-size:14px;font-family:{FONT_SANS};">' + "".join(lines) + '</ul>'
    )


def _pricing_card(
    tier_label: str, monthly: str, annual_monthly: str,
    annual_yearly: str, savings: str, blurb: str, *, accent: bool,
) -> str:
    """One pricing tile used in the day-7 email. Pro card uses subtle
    styling; Premium card uses the accent stripe to draw the eye."""
    return f"""
    <div class="tl-card" style="background:#ffffff;border:1px solid {LIGHT_BORDER};{('border-left:3px solid ' + ACCENT + ';') if accent else ''}border-radius:8px;padding:18px 20px;margin:0 0 12px;">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
        <tr>
          <td class="tl-fg" style="font-size:16px;font-weight:600;color:{LIGHT_FG};font-family:{FONT_SANS};">{tier_label}</td>
          <td align="right" class="tl-fg" style="font-family:{FONT_MONO};font-size:20px;font-weight:700;color:{LIGHT_FG};">{monthly}<span class="tl-muted" style="font-size:13px;font-weight:400;color:{LIGHT_MUTED};">/mo</span></td>
        </tr>
      </table>
      <div style="margin-top:6px;font-size:13px;color:{SIG_BULL};font-family:{FONT_SANS};">
        or <strong>{annual_monthly}/mo</strong> billed annually ({annual_yearly}/yr · save {savings})
      </div>
      <div class="tl-muted" style="margin-top:8px;font-size:13px;line-height:1.5;color:{LIGHT_MUTED};font-family:{FONT_SANS};">{blurb}</div>
    </div>
    """


def render_trial_day7_email(user_name: str, summary: dict | None = None) -> str:
    """Day 7 — halfway. Reminder + nudge to add a card."""
    return shell(
        h1(f"Halfway through your trial, {user_name}.")
        + lead("Seven days left of full Premium access.")
        + _trial_summary_block(summary)
        + muted_paragraph(
            f"When the trial ends, your account drops to Free — the scanner cuts "
            f"from the full ~{ACTIVE_UNIVERSE_SIZE:,}-ticker universe to the top "
            f"{FREE_SCANNER_ROWS} rows, ticker look-ups cap at "
            f"{FREE_DAILY_LOOKUPS} a day, the watchlist caps at "
            f"{FREE_WATCHLIST_TICKERS} tickers, and alerts, Telegram, and the "
            f"Congress feed switch off. To keep what you have, add a card."
        )
        + _pricing_card(
            "Pro", "$9.99", "$8.25", "$99", "$20",
            "Full live scanner, squeeze, regime, watchlist, email alerts, daily briefing.",
            accent=False,
        )
        + _pricing_card(
            "Premium", "$19.99", "$16.58", "$199", "$40",
            "Everything in Pro + Congress + Telegram unlimited + insider Form 4 + analyst ratings.",
            accent=True,
        )
        + button("Add a card", "https://tapeline.io/app/billing")
        + footnote("Founding pricing — locked in for early subscribers. 30-day money back, cancel anytime in one click."),
        preheader="Seven days left on your trial — add a card to keep Premium.",
    )


def render_trial_day11_email(
    user_name: str,
    summary: dict | None = None,
    *,
    trial_ends_at: datetime | None = None,
    checkout_urls: dict[str, str] | None = None,
) -> str:
    """T-3 — 3 days remaining.

    `trial_ends_at` personalises the deadline to the user's actual expiry
    ("before Friday, July 10"); without it the copy falls back to the generic
    "before your trial ends". Previously this hardcoded "before Friday",
    which was wrong for anyone whose trial didn't end on a Friday.

    `checkout_urls` (services/email_checkout) makes the CTA a one-click signed
    Stripe-checkout link — no login wall between the decision and the payment
    page. Falls back to /app/billing when the signing secret isn't configured.
    """
    cu = checkout_urls or {}
    premium_url = cu.get("premium_monthly", "https://tapeline.io/app/billing")
    # "%A, %B" + .day (not %-d / %#d — those are platform-dependent) gives
    # "Friday, July 10".
    deadline = (
        f"{trial_ends_at:%A, %B} {trial_ends_at.day}"
        if trial_ends_at is not None
        else "your trial ends"
    )
    return shell(
        h1("3 days left on your trial.")
        + lead(
            f"{user_name}, you're 11 days into the 14-day Premium trial. "
            f"Here's what you've actually been using."
        )
        + _trial_summary_block(summary)
        + muted_paragraph(
            f"If you decide to keep Premium, add a card before {deadline} at "
            f"the founding price — $19.99/mo, or $16.58/mo billed annually "
            f"($199/yr). Annual saves you $40 over the year, and either way "
            f"your rate is locked in for as long as you stay subscribed. If "
            f"you don't add a card, the account drops to Free at expiry."
        )
        + button("Keep Premium", premium_url)
        + (
            muted_paragraph(
                "One click, no password — the button opens secure Stripe "
                "checkout for your account. Apple Pay, Google Pay, or card."
            )
            if cu
            else ""
        )
        + footnote("30-day money back. One-click cancel. No phone calls."),
        preheader="Three days left of Premium — add a card to keep it.",
    )


def render_trial_day13_email(
    user_name: str,
    summary: dict | None = None,
    *,
    checkout_urls: dict[str, str] | None = None,
) -> str:
    """T-1 — final urgency. Trial ends tomorrow.

    Uses the urgent button variant (amber) — the only place we do.

    `checkout_urls` (services/email_checkout.email_checkout_urls) makes the
    CTA a one-click signed Stripe-checkout link — no login wall between the
    decision moment and the payment page. Falls back to /app/billing when the
    signing secret isn't configured."""
    cu = checkout_urls or {}
    premium_url = cu.get("premium_monthly", "https://tapeline.io/app/billing")
    pro_url = cu.get("pro_monthly", "https://tapeline.io/app/billing")
    return shell(
        h1("Trial ends tomorrow.")
        + lead(
            f"{user_name}, your Premium trial expires in less than 24 hours."
        )
        + _trial_summary_block(summary)
        + muted_paragraph(
            f"If you don't add a card, your account drops to Free at expiry — "
            f"the scanner caps at the top {FREE_SCANNER_ROWS} rows, ticker "
            f"look-ups at {FREE_DAILY_LOOKUPS} a day, and alerts, Telegram, "
            f"and the Congress feed switch off."
        )
        + muted_paragraph(
            "Two ways to keep it: <strong>keep everything — Premium "
            "$19.99/mo</strong> (or $16.58/mo billed annually), or "
            f'<strong><a href="{pro_url}" style="color:{ACCENT};">keep the '
            "scanner — Pro $9.99/mo</a></strong> (or $8.25/mo billed "
            "annually). Founding pricing, locked in while you stay subscribed."
        )
        + button("Keep my account active", premium_url, variant="urgent")
        + (
            muted_paragraph(
                "One click, no password — the button opens secure Stripe "
                "checkout for your account. Apple Pay, Google Pay, or card."
            )
            if cu
            else ""
        )
        + footnote("30-day money back. One-click cancel. No phone calls."),
        preheader="Your Premium trial expires in less than 24 hours.",
    )


def render_trial_expired_email(
    user_name: str,
    summary: dict | None = None,
    *,
    checkout_urls: dict[str, str] | None = None,
) -> str:
    """T+0 — trial ended within the last 24 hours.

    `checkout_urls` → one-click signed Stripe-checkout CTA (no login wall);
    falls back to /app/billing when unavailable."""
    cu = checkout_urls or {}
    premium_url = cu.get("premium_monthly", "https://tapeline.io/app/billing")
    pro_url = cu.get("pro_monthly", "https://tapeline.io/app/billing")
    return shell(
        h1("Your Tapeline trial ended.")
        + lead(
            f"{user_name}, your 14-day Premium trial ended overnight. Your "
            f"account is now on the Free tier — still live data, but capped "
            f"at the top {FREE_SCANNER_ROWS} scanner rows and "
            f"{FREE_DAILY_LOOKUPS} ticker look-ups a day, with no Telegram "
            f"or smart alerts."
        )
        + _trial_summary_block(summary)
        + muted_paragraph(
            'A few things stay open regardless of tier: the '
            f'<a href="https://tapeline.io/scorecard" style="color:{ACCENT};">public scorecard</a> '
            '(every top-10 call back-checked vs SPY), the '
            f'<a href="https://tapeline.io/how-it-works" style="color:{ACCENT};">scoring formula</a>, '
            f'and your watchlist (capped at {FREE_WATCHLIST_TICKERS} tickers on Free).'
        )
        + muted_paragraph(
            "One click brings it all back, and your watchlist + alerts come "
            "back intact: <strong>keep everything — Premium $19.99/mo</strong> "
            "(or $16.58/mo billed annually), or "
            f'<strong><a href="{pro_url}" style="color:{ACCENT};">keep the '
            "scanner — Pro $9.99/mo</a></strong> (or $8.25/mo billed "
            "annually). Founding pricing, locked in while you stay subscribed."
        )
        + button("Re-activate Premium", premium_url)
        + (
            muted_paragraph(
                "No password needed — the button opens secure Stripe checkout "
                "for your account. Apple Pay, Google Pay, or card."
            )
            if cu
            else ""
        )
        + footnote("No more reminders unless you re-activate. One more note in 3 days then I'll stop emailing."),
        preheader="Trial ended — re-activate to bring your watchlist + alerts back.",
    )


def render_trial_post_expiry_email(
    user_name: str,
    _summary: dict | None = None,
    *,
    checkout_urls: dict[str, str] | None = None,
) -> str:
    """T+3 — 3 days after trial expiry. Final touch.

    No discount theatre. One direct ask + the reactivation link + a polite
    goodbye. Honest framing is the differentiator — most SaaS would offer
    50% off and an extended trial, both of which read as desperate.

    `checkout_urls` → one-click signed Stripe-checkout CTA (no login wall).
    """
    premium_url = (checkout_urls or {}).get(
        "premium_monthly", "https://tapeline.io/app/billing"
    )
    return shell(
        h1("Last note from Tapeline.")
        + lead(
            f"Hi {user_name} — it's been three days since your trial ended "
            f"and you haven't reactivated. That's fine; not every tool fits "
            f"every workflow."
        )
        + paragraph(
            'One ask, if you\'ve got 30 seconds: <strong>what was missing?</strong> '
            'Reply to this email with whatever made you not keep it — a specific '
            'feature, the pricing, a bug, a confusing page. First-hand input from '
            'someone who actually tried Tapeline is more useful than any analytics '
            'dashboard. The address (christian@tapeline.io) goes straight to me, '
            'not a support queue.'
        )
        + muted_paragraph(
            "If you change your mind, the trial benefits don't reset — re-activate "
            "any time and your watchlist + alerts come back. Otherwise, this is "
            "where the emails stop — we'll only write again if something material "
            "changes, like pricing."
        )
        + button("Re-activate Premium", premium_url)
        + footnote(
            '— Christian, founder. '
            f'<a href="https://tapeline.io/scorecard" style="color:{LIGHT_SUBTLE};text-decoration:underline;">Public scorecard stays free forever.</a>'
        ),
        preheader="Last note — what was missing? Reply and tell me.",
    )


def render_trial_lapse30_email(
    user_name: str,
    *,
    checkout_urls: dict[str, str] | None = None,
) -> str:
    """T+30 — one-shot win-back for lapsed NO-CARD trials.

    Structural gap this closes: run_winback_drip keys off canceled_at, which
    only ever gets set for users who SUBSCRIBED and then cancelled. A trial
    user who never added a card exited the funnel forever after the T+3
    "post3" note. This is the single scheduled touch after that.

    Honesty contract: post3 now says "we'll only write again if something
    material changes, like pricing" — so this email leads with exactly that:
    where founding pricing stands today, stated as current fact (no fake
    "price is going up" urgency, no discount theatre, no claims about tiers
    that don't exist). One CTA; `checkout_urls` makes it a one-click signed
    Stripe-checkout link (no login wall), falling back to /app/billing.
    """
    cu = checkout_urls or {}
    premium_url = cu.get("premium_monthly", "https://tapeline.io/app/billing")
    pro_url = cu.get("pro_monthly", "https://tapeline.io/app/billing")
    return shell(
        h1("One note, a month on.")
        + lead(
            f"{user_name}, your Tapeline trial ended about a month ago and "
            f"you never added a card — completely fair. This is the one "
            f"follow-up we promised, and it's about pricing."
        )
        + paragraph(
            "Founding pricing is now "
            f'<strong><a href="{pro_url}" style="color:{ACCENT};">$9.99/mo '
            "for Pro</a></strong> (the full scanner) and "
            f'<strong><a href="{premium_url}" style="color:{ACCENT};">'
            "$19.99/mo for Premium</a></strong> (scanner + smart alerts, "
            "Telegram, and the Congress feed) — locked in for early "
            "subscribers for as long as they stay subscribed."
        )
        + muted_paragraph(
            "Your watchlist is still saved, exactly as you left it. "
            "Re-activate and it comes back with your alert rules intact — "
            "no re-setup."
        )
        + button("Re-activate Premium", premium_url)
        + (
            muted_paragraph(
                "No password needed — the links open secure Stripe checkout "
                "for your account. Apple Pay, Google Pay, or card."
            )
            if cu
            else ""
        )
        + footnote(
            "30-day money back. One-click cancel. This is the last scheduled "
            "note in the trial series. — Christian, founder."
        ),
        preheader="Founding pricing: $9.99/mo Pro · $19.99/mo Premium, locked for early subscribers.",
    )


def render_trial_ended_email(user_name: str) -> str:
    """Soft "your trial just ended" note. NOT wired to any automated sender:
    the hourly worker downgrade (signal_publisher._downgrade_expired_trials)
    used to send this on top of the drip's T+0 "expired" email, double-mailing
    every user on expiry day — the worker send was removed and run_daily_drip
    now owns end-of-trial email. Kept for the admin email-preview gallery."""
    return shell(
        h1(f"Your trial just ended, {user_name}.")
        + lead(
            "Your account is now on the Free plan. Your watchlist and settings "
            "are intact — only the data feed changes."
        )
        + muted_paragraph(
            "If you want live data + alerts back, the door is always open."
        )
        + button("See plans", "https://tapeline.io/app/billing")
        + footnote(
            "No hard feelings if not. The public scorecard stays free for everyone, forever."
        ),
        preheader="You're on the Free plan now — settings + watchlist intact.",
    )


# ── Email verification ──────────────────────────────────────────────────────

def render_email_verification_email(
    user_name: str, verify_url: str, cancel_url: str,
) -> str:
    """Sent immediately after the welcome email at native signup.

    Two CTAs side by side: the primary "verify" link consumes the token
    and stamps `User.email_verified_at`; the secondary "this wasn't me"
    link cancels the account before any further damage. Both flow through
    the same `/api/auth/verify-email` and `/api/auth/cancel-account`
    endpoints which the frontend `/verify-email` page consumes.

    Tone: calm + procedural. No urgency, no fake "ACT NOW" — this is a
    routine security step.
    """
    return shell(
        h1(f"Confirm your email, {user_name}.")
        + lead(
            "One quick step to lock down your Tapeline account: confirm "
            "this is your address. Click the button below — the link is "
            "good for 24 hours."
        )
        + button("Confirm my email", verify_url)
        + muted_paragraph(
            f'Didn\'t sign up for Tapeline? <a href="{cancel_url}" '
            f'style="color:{ACCENT};">Tell us this wasn\'t you</a> and '
            f'we\'ll cancel the account immediately. No further emails.'
        )
        + footnote(
            "Confirming protects against someone signing up with your "
            "address by mistake (or on purpose). If you ignore this email, "
            "your account stays unverified and we'll nudge you once more."
        ),
        preheader="Confirm your Tapeline email — link good for 24 hours.",
    )


async def mint_and_send_verification(session, user) -> bool:
    """Helper: create a fresh 24h verification token for `user`, send the
    verification email, return True on success.

    Idempotent: wipes any prior unused tokens for this user before issuing
    a new one — clicking "Resend verification" later is safe and doesn't
    leave a forest of dead tokens in the DB.

    Used by both the signup hook (auto-send) and the resend-verification
    endpoint (manual trigger).
    """
    from sqlalchemy import delete

    from app.config import get_settings as _settings_factory
    from app.models import EmailVerificationToken

    s = _settings_factory()

    # Wipe any prior unused tokens — the latest is the only valid one.
    await session.execute(
        delete(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        )
    )

    import secrets
    from datetime import UTC, datetime, timedelta

    token = secrets.token_urlsafe(48)
    expires = datetime.now(UTC) + timedelta(hours=24)
    session.add(EmailVerificationToken(
        token=token, user_id=user.id, expires_at=expires,
    ))
    await session.commit()

    # Build the two links the email points at. The frontend `/verify-email`
    # page consumes the token and shows the result; both verify + cancel
    # flow through the same `?token=` URL so the bounce-back UI can decide
    # what to show based on the user's click.
    base = s.app_url.rstrip("/")
    verify_url = f"{base}/verify-email?token={token}"
    cancel_url = f"{base}/verify-email?token={token}&action=cancel"

    try:
        html = render_email_verification_email(
            user.name or "trader", verify_url, cancel_url,
        )
        res = await send_email(
            user.email,
            "Confirm your Tapeline email",
            html,
            persona="default",
        )
        return not res.get("skipped", False)
    except Exception:
        logger.exception("verification.send_failed user=%s", user.id)
        return False


# ── Password reset ───────────────────────────────────────────────────────────

def render_password_reset_email(user_name: str, reset_url: str) -> str:
    """Sent when a user clicks "Forgot password?" at /signin.

    Single CTA, short TTL (60 min in the orchestrator), terse copy. The
    "wasn't you?" angle for password reset is handled differently from
    verification: ignoring the email leaves the account intact, so the
    footer just tells them they can safely ignore.
    """
    return shell(
        h1(f"Reset your Tapeline password, {user_name}.")
        + lead(
            "Click below to choose a new password. The link is good for "
            "60 minutes — after that it stops working and you'll need "
            "to request a new one."
        )
        + button("Choose a new password", reset_url)
        + footnote(
            "Didn't request this? You can safely ignore this email — "
            "your password is unchanged and no one accessed your account. "
            "If you're seeing repeat reset emails you didn't ask for, "
            "let us know at support@tapeline.io."
        ),
        preheader="Reset link inside — good for 60 minutes.",
    )


async def mint_and_send_password_reset(session, user) -> bool:
    """Mint a fresh 60min password-reset token for `user`, send the
    email, return True if delivery was attempted (False if Resend was
    skipped or render failed).

    Idempotent: wipes any prior unused tokens for this user before
    issuing a new one. Means a user spam-clicking "forgot password"
    doesn't end up with multiple live links — only the latest works.
    """
    import secrets
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete

    from app.config import get_settings as _settings_factory
    from app.models import PasswordResetToken

    s = _settings_factory()

    await session.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    )

    token = secrets.token_urlsafe(48)
    expires = datetime.now(UTC) + timedelta(minutes=60)
    session.add(PasswordResetToken(
        token=token, user_id=user.id, expires_at=expires,
    ))
    await session.commit()

    base = s.app_url.rstrip("/")
    reset_url = f"{base}/reset-password?token={token}"

    try:
        html = render_password_reset_email(user.name or "trader", reset_url)
        res = await send_email(
            user.email,
            "Reset your Tapeline password",
            html,
            persona="default",
        )
        return not res.get("skipped", False)
    except Exception:
        logger.exception("password_reset.send_failed user=%s", user.id)
        return False


# ── Payment-failed ──────────────────────────────────────────────────────────

def _ordinal(n: int) -> str:
    """1 -> 1st, 2 -> 2nd, 3 -> 3rd, 4 -> 4th, etc."""
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def render_subscription_started_email(
    user_name: str,
    tier: str,
    billing_period: str = "monthly",
    amount_cents: int | None = None,
    currency: str = "usd",
    next_charge_iso: str | None = None,
) -> str:
    """Welcome-to-paid. Fires once on the FIRST `customer.subscription.created`
    Stripe webhook for a user (replay-safe via stripe_webhook_events dedup +
    the "no prior Subscription row" check at the webhook site).

    Tone:
      - Receipt-clean (acknowledge what they just paid for)
      - Quietly celebratory ("you're in")
      - Two concrete next steps, not three (less overwhelming than the day-0
        welcome which is for trial users with no commitment yet)
      - Acknowledges the 30-day refund window without leading with it

    Arguments map directly to fields available on the Stripe subscription
    object in the webhook handler — see routers/webhooks.py.
    """
    tier_label = tier.capitalize()
    period_label = "year" if billing_period == "annual" else "month"
    if amount_cents is not None and amount_cents > 0:
        dollars = amount_cents / 100
        price_line = f"${dollars:.2f} {currency.upper()} per {period_label}"
    else:
        # Fallback to the canonical sticker prices if the webhook didn't carry
        # an amount (shouldn't happen but better than printing nothing).
        sticker = {
            ("pro", "monthly"): "$9.99/mo",
            ("pro", "annual"): "$99/yr",
            ("premium", "monthly"): "$19.99/mo",
            ("premium", "annual"): "$199/yr",
        }.get((tier.lower(), billing_period), "")
        price_line = sticker
    next_charge_line = ""
    if next_charge_iso:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(next_charge_iso.replace("Z", "+00:00"))
            next_charge_line = f"Next charge: {dt.strftime('%b %d, %Y')}."
        except Exception:
            next_charge_line = ""
    return shell(
        h1(f"You're in, {user_name}.")
        + lead(
            f"Welcome to Tapeline <strong>{tier_label}</strong>. Your full data "
            f"feed is live — every score live-updating, every alert channel on, "
            f"the full universe scanner unlocked."
        )
        + card(
            f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-weight:600;font-family:{FONT_SANS};">Your subscription</div>'
            f'<div class="tl-fg" style="margin-top:6px;font-size:18px;font-weight:700;color:{LIGHT_FG};font-family:{FONT_SANS};">Tapeline {tier_label} · {price_line}</div>'
            f'<div class="tl-muted" style="margin-top:4px;font-size:13px;color:{LIGHT_MUTED};font-family:{FONT_SANS};">{next_charge_line}</div>',
            accent=True,
        )
        + muted_paragraph(
            "Two things worth doing in the first session:"
        )
        + card(
            f"""
            <ol style="margin:0;padding-left:20px;color:{LIGHT_FG};font-family:{FONT_SANS};font-size:14px;line-height:1.7;">
              <li><strong>Build your watchlist</strong> — add the names you actually
                  trade. Alerts fire the moment any score crosses your threshold.</li>
              <li><strong>Pick a notification channel</strong> — email's on by default,
                  but {tier_label} can also fire {("Telegram " if tier.lower() == "premium" else "")}browser push and
                  the daily briefing. <a href="https://tapeline.io/app/settings/email"
                  style="color:{ACCENT};">Channel settings</a>.</li>
            </ol>
            """
        )
        + button(
            "Open the scanner",
            "https://tapeline.io/app/scanner?utm_source=email&utm_campaign=subscription_started&utm_medium=transactional",
        )
        + footnote(
            "Changed your mind? <a href=\"https://tapeline.io/legal/refund\" "
            f"style=\"color:{LIGHT_MUTED};text-decoration:underline;\">30-day money "
            "back, no questions</a> — just reply to this email and we'll refund in full."
        ),
        preheader=f"Welcome to Tapeline {tier_label} — your full data feed is live.",
    )


def render_payment_failed_email(
    user_name: str, tier: str, attempt_count: int = 1, *, final_attempt: bool = False,
) -> str:
    """Stripe `invoice.payment_failed`. Tone is calm + practical, not
    alarmist. First-attempt failures are usually transient (bank fraud
    flag, expired card).

    `final_attempt` flips the copy to the last-chance variant: Stripe has
    no further automatic retries scheduled (`next_payment_attempt` is None),
    so the next failure ends the grace window and the account drops to Free.
    This is the most urgent touch in the dunning sequence."""
    tier_label = tier.capitalize()
    if final_attempt:
        urgency_line = (
            f"This was the last automatic retry. Update your card now or your "
            f"account drops to Free and you lose live {tier_label} access."
        )
    elif attempt_count == 1:
        urgency_line = "Stripe will retry automatically over the next few days."
    else:
        urgency_line = (
            f"This is the {_ordinal(attempt_count)} attempt — if it fails "
            f"again, your account drops to Free."
        )
    return shell(
        h1(f"{user_name}, your last payment didn't go through.")
        + lead(
            f"The renewal charge for your Tapeline {tier_label} subscription "
            f"was declined. Usually it's a card on file that expired, or a "
            f"bank fraud-system flag — not an actual problem with your account."
        )
        + muted_paragraph(
            f"{urgency_line} Nothing is paused on your end yet — you still "
            f"have full {tier_label} access."
        )
        + card(
            f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-weight:600;font-family:{FONT_SANS};">Fix it in two clicks</div>'
            f'<p class="tl-fg" style="margin:8px 0 12px;color:{LIGHT_FG};font-size:14px;line-height:1.55;font-family:{FONT_SANS};">Open your billing page, click "Update payment method", paste a new card. Stripe will run the failed charge again immediately.</p>'
            + button("Open billing", "https://tapeline.io/app/billing"),
            accent=True,
        )
        + footnote("Anything weird? Reply to this email — billing@tapeline.io reads every reply."),
        preheader=f"Your {tier_label} renewal charge was declined — fix it in two clicks.",
    )


def render_payment_recovered_email(user_name: str, *, tier: str) -> str:
    """Closes the dunning loop: a previously-failed renewal finally cleared
    (Stripe `invoice.payment_succeeded` while the account was mid-dunning).
    Reassures the customer they're square and nothing lapsed. Transactional
    (account-state), persona billing, no List-Unsubscribe."""
    tier_label = (tier or "your plan").capitalize()
    return shell(
        h1(f"You're all set, {user_name}.")
        + lead(
            f"Your Tapeline {tier_label} payment just went through — the card "
            f"on file was charged successfully and your subscription is fully "
            f"current again."
        )
        + muted_paragraph(
            f"Nothing lapsed: your {tier_label} access ran uninterrupted the "
            f"whole time. There's nothing you need to do."
        )
        + card(
            f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-weight:600;font-family:{FONT_SANS};">Back to it</div>'
            f'<p class="tl-fg" style="margin:8px 0 12px;color:{LIGHT_FG};font-size:14px;line-height:1.55;font-family:{FONT_SANS};">Jump back into the scanner — your watchlist, alerts, and saved scans are exactly where you left them.</p>'
            + button("Open Tapeline", "https://tapeline.io/app"),
            accent=True,
        )
        + footnote("Questions about the charge? Reply here — billing@tapeline.io reads every reply."),
        preheader=f"Payment received — your {tier_label} subscription is current again.",
    )


def render_checkout_abandoned_email(
    user_name: str, *, tier: str, billing_period: str = "monthly",
) -> str:
    """Checkout abandonment recovery — sent ~1-24h after a user mints a Stripe
    Checkout Session (clicked Subscribe) but never completed it.

    Tone: helpful, not pushy. They already decided to upgrade — this just
    clears the small friction of finishing. We don't deep-link the original
    Stripe session URL (it expires in 24h and may be dead by send time); the
    resume link lands on /app/billing with the tier + period pre-selected so a
    single click re-opens checkout on the right plan.

    Descriptive voice only — no "buy"/"sell"/"recommend" (publisher exemption).
    Marketing-class conversion nudge: persona "sales", gated on
    EmailPref.RE_ENGAGEMENT + carries List-Unsubscribe at the send site."""
    tier_label = (tier or "pro").capitalize()
    period = billing_period if billing_period in ("monthly", "annual") else "monthly"
    sticker = {
        ("pro", "monthly"): "$9.99/mo",
        ("pro", "annual"): "$99/yr",
        ("premium", "monthly"): "$19.99/mo",
        ("premium", "annual"): "$199/yr",
    }.get((tier.lower() if tier else "pro", period), "")
    price_line = f"Tapeline {tier_label} · {sticker}" if sticker else f"Tapeline {tier_label}"
    resume_url = (
        f"https://tapeline.io/app/billing?resume=1&tier={tier or 'pro'}"
        f"&billing_period={period}"
        f"&utm_source=email&utm_campaign=checkout_recovery&utm_medium=sales"
    )
    return shell(
        h1(f"You're one step away, {user_name}.")
        + lead(
            f"You started upgrading to Tapeline <strong>{tier_label}</strong> but "
            f"didn't quite finish. Your checkout is still saved — picking it back "
            f"up takes one click, and nothing was charged."
        )
        + card(
            f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-weight:600;font-family:{FONT_SANS};">Your plan</div>'
            f'<div class="tl-fg" style="margin-top:6px;font-size:18px;font-weight:700;color:{LIGHT_FG};font-family:{FONT_SANS};">{price_line}</div>'
            f'<p class="tl-fg" style="margin:10px 0 12px;color:{LIGHT_FG};font-size:14px;line-height:1.55;font-family:{FONT_SANS};">'
            f"Full universe scanner, live scores, squeeze + regime + heatmap, and "
            f"every alert channel — unlocked the moment you finish."
            f"</p>"
            + button(f"Finish upgrading to {tier_label}", resume_url),
            accent=True,
        )
        + muted_paragraph(
            "Changed your mind, or hit a snag on the payment page? Just reply — a "
            "human reads every message."
        )
        + footnote(
            "You're getting this because you started a checkout on Tapeline. "
            "Not ready yet? No problem — this is the only reminder we'll send."
        ),
        preheader=f"Your Tapeline {tier_label} checkout is still saved — finish in one click.",
    )


def render_subscription_canceled_email(
    user_name: str, *, tier: str, period_end_iso: str | None,
) -> str:
    """Transactional confirmation of a scheduled cancellation.

    Reassuring, no hard sell — they keep access until period end and one
    click reactivates. The actual win-back push comes later via the
    30/60/90-day drip. No List-Unsubscribe header (account-state, not
    marketing)."""
    tier_label = (tier or "your plan").capitalize()
    when = "the end of your current billing period"
    if period_end_iso:
        try:
            from datetime import datetime as _dt

            when = _dt.fromisoformat(period_end_iso).strftime("%b %d, %Y")
        except Exception:
            pass
    return shell(
        h1(f"Your plan is set to cancel, {user_name}.")
        + lead(
            f"We've scheduled your Tapeline {tier_label} subscription to end on "
            f"{when}. You keep full access until then — nothing changes today, "
            f"and you won't be charged again."
        )
        + muted_paragraph(
            f"After that your account moves to Free — still live data, but "
            f"capped at the top {FREE_SCANNER_ROWS} scanner rows and "
            f"{FREE_DAILY_LOOKUPS} ticker look-ups a day, with alerts switched "
            f"off. Your watchlist, saved scans, and alert rules are kept on "
            f"file, so if you come back they're exactly where you left them."
        )
        + card(
            f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-weight:600;font-family:{FONT_SANS};">Changed your mind?</div>'
            f'<p class="tl-fg" style="margin:8px 0 12px;color:{LIGHT_FG};font-size:14px;line-height:1.55;font-family:{FONT_SANS};">One click keeps everything running — same plan, same price, no gap in your data.</p>'
            + button("Keep my plan", "https://tapeline.io/app/billing"),
            accent=True,
        )
        + footnote(
            "Mind sharing why you're leaving? Just reply — every response is "
            "read by a human (me), and it's the single biggest thing that "
            "makes Tapeline better.<br><br>— Christian, founder."
        ),
        preheader=f"Access stays live until {when}. One click reactivates.",
    )


def render_save_offer_accepted_email(user_name: str, *, tier: str) -> str:
    """Transactional confirmation that the one-time 50%-off-3-months save
    offer was applied (POST /billing/save-offer → accept_save_offer).

    Sent right after we stamp `User.save_offer_redeemed_at`. The customer was
    on the way out, accepted the retention coupon, and is staying — so the tone
    is warm + reassuring, confirming exactly what changed (half price for three
    months, same plan, nothing else moves) without any advice language.
    Transactional/account-state: persona "billing", no List-Unsubscribe."""
    tier_label = (tier or "your plan").capitalize()
    return shell(
        h1(f"You're staying — and it's 50% off, {user_name}.")
        + lead(
            f"Done. Your Tapeline {tier_label} subscription stays exactly as it "
            f"is, and the discount is already applied — nothing else changes, and "
            f"your watchlist, alerts, and saved scans carry on uninterrupted."
        )
        + card(
            f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-weight:600;font-family:{FONT_SANS};">Discount applied</div>'
            f'<div style="margin-top:6px;font-family:{FONT_MONO};font-size:24px;font-weight:700;color:{SIG_BULL};line-height:1;">50% off · 3 months</div>'
            f'<p class="tl-fg" style="margin:10px 0 0;color:{LIGHT_FG};font-size:14px;line-height:1.55;font-family:{FONT_SANS};">'
            f"Your next three {tier_label} charges are half price, applied "
            "automatically — there's no code to enter. After three months it "
            "returns to the standard rate, and you can change or cancel any time."
            "</p>",
            accent=True,
        )
        + muted_paragraph(
            "Glad you're sticking around. Pick up right where you left off — the "
            "scanner, your watchlist, and every alert channel are all live."
        )
        + button(
            "Open the scanner",
            "https://tapeline.io/app/scanner?utm_source=email&utm_campaign=save_offer&utm_medium=transactional",
        )
        + footnote(
            "Questions about the discount or your bill? Reply to this email — "
            "billing@tapeline.io reads every reply."
        ),
        preheader=f"Your {tier_label} stays at 50% off for 3 months — applied automatically.",
    )


# ── EOD watchlist digest ────────────────────────────────────────────────────

def _today_short() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).strftime("%a %b %d")


def render_eod_watchlist_digest(user_name: str, items: list[dict]) -> str:
    """End-of-day watchlist summary — one email per Pro+ user per day."""
    if not items:
        return shell(
            h1(f"End of day · {_today_short()}")
            + lead("Your watchlist is empty. Add tickers to see them here tomorrow.")
            + button("Open watchlist", "https://tapeline.io/app/watchlist"),
            preheader="Your Tapeline watchlist is empty — add tickers to get a daily digest.",
        )
    return shell(
        h1(f"End of day · {_today_short()}")
        + lead(
            f"Hi {user_name}, here's where your {len(items)} watchlist "
            f"ticker{'' if len(items) == 1 else 's'} closed today."
        )
        + watchlist_table(items)
        + button("Open watchlist", "https://tapeline.io/app/watchlist"),
        preheader=(
            f"Watchlist EOD · {len(items)} ticker"
            f"{'' if len(items) == 1 else 's'} · {_today_short()}"
        ),
    )


# ── Re-engagement (14-day dormant) ──────────────────────────────────────────

def render_re_engagement_email(user_name: str) -> str:
    """One-shot nudge for users dormant ~14 days. Calm/factual voice; no
    drip after this."""
    return shell(
        h1(f"Tapeline missed you, {user_name}.")
        + lead(
            "It's been two weeks since you last opened the scanner. That's "
            "fine — life and the market both move on — but two weeks is "
            "also long enough that what you'd see today is meaningfully "
            "different from what was there when you stepped away."
        )
        + paragraph(
            'The fastest catch-up is the public '
            f'<a href="https://tapeline.io/scorecard?utm_source=email&utm_campaign=re_engagement&utm_medium=transactional" style="color:{ACCENT};">scorecard</a> — '
            'every top-10 daily pick we published while you were gone, '
            'back-checked against SPY the next session. No survivor bias; '
            'every miss is still on the page.'
        )
        + button(
            "Open the scanner",
            "https://tapeline.io/app/scanner?utm_source=email&utm_campaign=re_engagement&utm_medium=transactional",
        )
        + footnote(
            'If Tapeline isn\'t what you need, no follow-up — this is the only nudge.'
            '<br><br>— Christian, founder. '
            f'<a href="https://tapeline.io/how-it-works" style="color:{LIGHT_SUBTLE};text-decoration:underline;">The formula is still public.</a>'
        ),
        preheader="Two weeks since you last opened the scanner — the scorecard kept running.",
    )


# ── One-time free-tier changelog (manual admin re-contact) ──────────────────
#
# NOT wired to any scheduled worker. Sent only via the admin endpoint
# POST /api/admin/recontact/free-tier-changelog, and only when the founder
# passes confirm=true. See routers/admin.py for the gating rationale.
#
# Copy contract: this is a factual changelog of what the FREE plan includes
# today. No offer, no discount, no urgency, no performance or returns claim.
# It exists because the trial-series final email promises "we'll only write
# again if something material changes" — the free tier materially changed,
# so this note is the promise being kept, once.

RECONTACT_FREE_TIER_TOKEN = "rc_free1"
RECONTACT_FREE_TIER_SUBJECT = "What's on the Tapeline free plan now"

_RECONTACT_UTM = (
    "utm_source=email&utm_campaign=free_tier_changelog&utm_medium=transactional"
)


def _free_squeeze_preview_limit() -> int:
    """How many squeeze setups a free account can see.

    Lazy import: the constant's home is the squeeze router, and a service
    module importing a router at module scope risks an import cycle. Falls
    back to the shipped value if the import ever moves.
    """
    try:
        from app.routers.squeeze import FREE_SQUEEZE_PREVIEW_LIMIT

        return int(FREE_SQUEEZE_PREVIEW_LIMIT)
    except Exception:  # pragma: no cover - defensive
        return 3


def _free_tier_changelog_lines() -> list[str]:
    """The changelog rows, as plain sentences.

    Sourced from the tier.py constants (+ the squeeze router's preview cap)
    so the copy can never quote a cap the product no longer enforces. Shared
    by the HTML and plain-text renderers so the two can't drift.
    """
    return [
        f"A watchlist on the free plan, with up to {FREE_WATCHLIST_TICKERS} saved tickers.",
        f"{FREE_DAILY_LOOKUPS} full ticker look-ups a day.",
        f"{FREE_SCANNER_ROWS} live scanner rows (live data, not delayed).",
        f"The squeeze radar's top {_free_squeeze_preview_limit()} setups.",
        f"{FREE_WEB_PUSH_ALERTS} browser alerts you can set on your own tickers.",
    ]


def render_free_tier_changelog_email(user_name: str) -> str:
    """One-time re-contact for people who signed up before the free tier grew.

    Purely descriptive: it states what the free plan includes today and
    links to the public scorecard. There is deliberately no pricing block,
    no discount, no deadline, and no claim about outcomes.
    """
    rows = "".join(
        f'<li style="margin:0 0 8px;font-size:15px;line-height:1.55;'
        f'color:{LIGHT_FG};font-family:{FONT_SANS};">{line}</li>'
        for line in _free_tier_changelog_lines()
    )
    return shell(
        h1("What's on the free plan now.")
        + lead(
            f"Hi {user_name} — you made a Tapeline account a while back. When "
            f"the emails stopped, we said we'd only write again if something "
            f"material changed. The free plan changed, so here's the one note "
            f"about it."
        )
        + paragraph("What a free account includes today:")
        + card(
            f'<ul style="margin:0;padding:0 0 0 20px;">{rows}</ul>',
            accent=True,
        )
        + muted_paragraph(
            "All of that is on the free plan — no card, no trial clock. Your "
            "existing account already has it; there's nothing to switch on."
        )
        + paragraph(
            'The public '
            f'<a href="https://tapeline.io/scorecard?{_RECONTACT_UTM}" style="color:{ACCENT};">scorecard</a> '
            'is unchanged and still free to everyone: every daily top-10 pick '
            'we published, back-checked against SPY the next session, with '
            'every miss still on the page.'
        )
        + button(
            "Open the scorecard",
            f"https://tapeline.io/scorecard?{_RECONTACT_UTM}",
        )
        + footnote(
            "This is a one-off note, not a new series — there's no follow-up "
            "to this one. If Tapeline isn't for you, the unsubscribe link "
            "below stops everything."
            "<br><br>— Christian, founder."
        ),
        preheader=(
            f"The free plan now includes a {FREE_WATCHLIST_TICKERS}-ticker "
            f"watchlist, {FREE_DAILY_LOOKUPS} look-ups a day, and "
            f"{FREE_WEB_PUSH_ALERTS} browser alerts."
        ),
    )


def render_free_tier_changelog_text(user_name: str) -> str:
    """Plain-text alternative for the same email.

    Sent as the `text` part so the message isn't HTML-only — HTML-only
    marketing mail is a spam-filter signal, and this one has to land.
    """
    bullets = "\n".join(f"  - {line}" for line in _free_tier_changelog_lines())
    return (
        f"Hi {user_name},\n\n"
        "You made a Tapeline account a while back. When the emails stopped, "
        "we said we'd only write again if something material changed. The "
        "free plan changed, so here's the one note about it.\n\n"
        "What a free account includes today:\n"
        f"{bullets}\n\n"
        "All of that is on the free plan - no card, no trial clock. Your "
        "existing account already has it; there's nothing to switch on.\n\n"
        "The public scorecard is unchanged and still free to everyone: every "
        "daily top-10 pick we published, back-checked against SPY the next "
        "session, with every miss still on the page.\n\n"
        f"  https://tapeline.io/scorecard?{_RECONTACT_UTM}\n\n"
        "This is a one-off note, not a new series - there's no follow-up to "
        "this one. If Tapeline isn't for you, use the unsubscribe link in "
        "this email and everything stops.\n\n"
        "- Christian, founder\n\n"
        "Not investment advice. Tapeline is informational software - every "
        "score, signal, and headline is a data point, not a recommendation.\n"
    )


# ── Win-back (post-cancellation 30 / 60 / 90-day drip) ──────────────────────

def _winback_scorecard_line(scorecard: dict | None) -> str:
    """One-liner of public-scorecard proof, when we have it. Drives the
    'the track record kept running while you were gone' angle that makes
    win-back convert better than a bare discount.

    Reads defensively across the two scorecard shapes in the codebase:
    the newsletter payload (_build_newsletter_payload) uses hit_rate_pct /
    avg_alpha_pct / best; the scorecard router (_summary_stats) uses
    hit_rate_beat_spy / median_alpha_vs_spy. We accept whichever the
    caller hands us so the proof line never silently goes blank on a
    key rename."""
    if not scorecard:
        return ""

    def _first_num(*keys: str) -> float | None:
        for k in keys:
            v = scorecard.get(k)
            if isinstance(v, (int, float)):
                return float(v)
        return None

    hit = _first_num("hit_rate_pct", "hit_rate_beat_spy", "hit_rate")
    alpha = _first_num("avg_alpha_pct", "median_alpha_vs_spy", "median_alpha")
    best = scorecard.get("best")
    best = best if isinstance(best, dict) else None

    bits: list[str] = []
    if hit is not None:
        bits.append(f"{round(hit)}% of calls beat SPY")
    if alpha is not None:
        bits.append(f"{'+' if alpha >= 0 else ''}{alpha:.2f}% avg next-day alpha")
    if best and best.get("symbol") and isinstance(best.get("alpha"), (int, float)):
        a = float(best["alpha"])
        bits.append(f"best call {best['symbol']} {'+' if a >= 0 else ''}{a:.2f}% vs SPY")
    if not bits:
        return ""
    return paragraph(
        "Since you left, the public "
        f'<a href="https://tapeline.io/scorecard?utm_source=email&utm_campaign=winback&utm_medium=transactional" style="color:{ACCENT};">scorecard</a> '
        "kept running: " + " · ".join(bits) + "."
    )


def render_winback_email(
    user_name: str, *, stage: str, scorecard: dict | None = None,
) -> str:
    """Graduated post-cancellation win-back. `stage` in {wb30, wb60, wb90}.

    wb30 — soft: your setup is still saved, here's what you've missed.
    wb60 — proof: the public scorecard kept running; here are the numbers.
    wb90 — last call + a real returning-customer offer (40% off 3 months,
           server-gated on canceled_at so the link can't be farmed).
    Win-back is gated on EmailPref.RE_ENGAGEMENT and carries a
    List-Unsubscribe header (it's a marketing nudge, not account state)."""
    proof = _winback_scorecard_line(scorecard)
    if stage == "wb30":
        return shell(
            h1(f"Your Tapeline setup is still here, {user_name}.")
            + lead(
                "It's been about a month. Your watchlist, saved scans, and alert "
                "rules are exactly where you left them — nothing was deleted."
            )
            + proof
            + muted_paragraph(
                "If the timing just wasn't right, that's completely fair. When "
                "you want back in, one click restores Premium and everything "
                "lights up again — no re-setup."
            )
            + button(
                "Pick up where I left off",
                "https://tapeline.io/app/billing?utm_source=email&utm_campaign=winback_30&utm_medium=transactional",
            )
            + footnote("Two more notes over the next two months, then I'll stop. — Christian, founder."),
            preheader="Your watchlist + alerts are still saved — one click restores them.",
        )
    if stage == "wb60":
        return shell(
            h1("The track record kept running without you.")
            + lead(
                f"{user_name}, the thing most scanners hide is the one we publish: "
                f"every daily top-10 call, back-checked against SPY the next session."
            )
            + (proof or paragraph(
                "The public "
                f'<a href="https://tapeline.io/scorecard?utm_source=email&utm_campaign=winback_60&utm_medium=transactional" style="color:{ACCENT};">scorecard</a> '
                "shows every call we've made — hits and misses, no survivor bias."
            ))
            + muted_paragraph(
                "If Tapeline didn't earn its keep last time, the scorecard is the "
                "honest way to judge whether it would now. It's all there, public."
            )
            + button(
                "See the scorecard",
                "https://tapeline.io/scorecard?utm_source=email&utm_campaign=winback_60&utm_medium=transactional",
            )
            + footnote("One more note next month, then I'll stop emailing. — Christian, founder."),
            preheader="Every call we've made since you left — public, back-checked vs SPY.",
        )
    # wb90 — last call, with the returning-customer discount.
    return shell(
        h1("Last note — and a standing offer.")
        + lead(
            f"{user_name}, this is the final win-back email. If Tapeline isn't "
            f"for you, no hard feelings and no more mail."
        )
        + proof
        + card(
            f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-weight:600;font-family:{FONT_SANS};">Returning-customer offer</div>'
            f'<p class="tl-fg" style="margin:8px 0 12px;color:{LIGHT_FG};font-size:14px;line-height:1.55;font-family:{FONT_SANS};">Come back and your first 3 months are <strong>40% off</strong> — automatically applied at checkout. Your saved watchlist, scans, and alerts come back with you.</p>'
            + button(
                "Reactivate — 40% off 3 months",
                "https://tapeline.io/app/billing?winback=1&utm_source=email&utm_campaign=winback_90&utm_medium=transactional",
                variant="urgent",
            ),
            accent=True,
        )
        + footnote("This is the last email in this series. — Christian, founder."),
        preheader="Last win-back note — 40% off your first 3 months back.",
    )


# ── Activation nudges (lever #3: first-watchlist, first-alert) ──────────────
#
# Early-lifecycle prompts that fire when a user signed up but skipped the
# core habit-forming step. Both gate on EmailPref.TRIAL_DRIP (the
# early-lifecycle suppressable bucket) and send under the "default"
# transactional-onboarding persona. Dedup'd via User.drip_state tokens
# "act_wl" / "act_alert" in run_activation_drip below.

def render_activation_watchlist_email(user_name: str) -> str:
    """Activation nudge — signed up but hasn't added a single watchlist ticker
    within ~24h. The watchlist is the core habit loop: it powers smart alerts
    and the end-of-day digest, so the first ticker added is activation
    milestone #1. Calm, helpful voice; persona "default"."""
    return shell(
        h1(f"Add one ticker, {user_name}.")
        + lead(
            "You're all set up — but your watchlist is still empty. That's the "
            "one step that turns Tapeline from a scanner into your scanner."
        )
        + paragraph(
            # Rule 7: "a digest of what moved" was ambiguous — the EOD digest
            # reports SCORE changes (a factor value, which Rule 7 permits), but
            # the wording reads as price movement, which it does not permit.
            # Say which number changes and the ambiguity disappears.
            "Pick three or four names you already follow. From then on you get "
            "their current score, a flag when that score shifts, and an "
            "end-of-day digest of the score changes — without re-running a "
            "single filter."
        )
        + button(
            "Add my first tickers",
            "https://tapeline.io/app/scanner?utm_source=email&utm_campaign=activation_watchlist&utm_medium=transactional",
        )
        + footnote("Takes about thirty seconds. — Christian, founder."),
        preheader="One ticker on your watchlist unlocks alerts + your daily digest.",
    )


def render_activation_alert_email(user_name: str) -> str:
    """Activation nudge — three days in, on a plan that can set alerts (trial
    Premium or paid Pro/Premium), but no alert rule yet. Alerts are the
    retention hook: a user who receives one genuinely useful alert comes back.
    Persona "default"."""
    return shell(
        h1("Let Tapeline watch while you don't.")
        + lead(
            f"{user_name}, you've had a few days to look around. The next step "
            f"is to stop looking — set one alert and let the scanner tap you on "
            f"the shoulder instead."
        )
        + paragraph(
            # Rule 7: the earlier wording here ended "no missed setups", which
            # is a performance claim wearing a workflow costume — a setup is
            # only worth missing because of the return it implies. Replaced
            # with a description of what the rule actually does.
            "A rule takes one line: name a score threshold, a squeeze trigger, "
            "or a regime flip, and Tapeline emails you when the condition is "
            "met. No dashboard-watching required."
        )
        + button(
            "Set up an alert",
            "https://tapeline.io/app/alerts?utm_source=email&utm_campaign=activation_alert&utm_medium=transactional",
        )
        + footnote("One rule is enough to feel the difference. — Christian, founder."),
        preheader="Set one alert and let the scanner watch the tape for you.",
    )


# ── Behaviour-triggered activation series ───────────────────────────────────
#
# ⚠️  RULE 7 — READ BEFORE EDITING ANY TEMPLATE IN THIS SECTION  ⚠️
#
# These messages are 1:1 emails to a NAMED person about securities that person
# SELF-SELECTED. That is the single worst fact pattern for the personal-advice
# test under the ASIC / FTC framing in our legal review: a message that tells
# an identified individual how their chosen holdings did is, on its face,
# personal financial advice — and Tapeline is not licensed to give it.
#
# So the content of every message in this series is restricted to ACTIVITY —
# things the user did or did not do inside the product:
#
#     PERMITTED                         PROHIBITED
#     ─────────────────────────────     ──────────────────────────────────────
#     scans run (count)                 how any ticker MOVED or performed
#     tickers added to a watchlist      "AAPL is up 6% since you added it"
#     exports taken                     "your watchlist gained 3% this week"
#     factor VALUES that changed        "the setups you'd have caught"
#     ("RSI on your saved scan is 71")  "here's what you missed"
#     inclusion in the ALREADY-         "your best performer was …"
#     PUBLISHED daily list              any P&L, return, or alpha figure
#                                       any implied "you would have made money"
#
# The FOMO framings on the right are the ones a growth edit reaches for, which
# is exactly why they are named here. "What you missed" is not a softer version
# of a performance claim — it IS a performance claim, because the only thing
# that makes a missed setup regrettable is the return it implies.
#
# Describe the MECHANISM and stop. A disclaimer does not cure a non-compliant
# message (Rule 9) — the content itself has to be clean.
#
# Rule 6 also binds here: no countdowns, no scarcity, no deadline framing. A
# factual mention of the user's OWN real trial end date is permitted, styled
# calmly, and must never be described as a billing event — the trial takes no
# card, so nothing is charged when it ends.
#
# Enforced mechanically by scripts/lint-copy-compliance.mjs (rules
# `personalised-performance` and `urgency-scarcity`) and by
# tests/test_lifecycle_governor.py, which asserts on the RENDERED output.

def _calm_trial_note(trial_ends_at: datetime | None) -> str:
    """A factual, non-urgent note about the user's own trial end date.

    Rule 6 permits exactly this one time statement. Rendered as a muted
    footnote — no colour, no countdown, no ticking clock — and deliberately
    worded so it cannot read as a billing event: the trial takes no card, so
    nothing is charged and nothing lapses into a payment.

    Returns "" when the user has no trial, which is the common case for the
    6h nudge (free signups) and keeps the template branch-free.
    """
    if trial_ends_at is None:
        return ""
    return footnote(
        "For reference, your Premium trial runs to "
        f"{trial_ends_at.strftime('%d %b %Y')}. There's no card on file, so "
        "nothing is charged either way — the account simply stays on Free "
        "afterwards."
    )


def render_activation_first_scan_email(
    user_name: str, *, trial_ends_at: datetime | None = None,
) -> str:
    """Message #2 of the activation series — ~6h after signup, zero activity.

    Triggered by the ABSENCE of a recorded action, not by the calendar. Points
    at ONE concrete first step (run a scan) and describes what the scanner
    measures. No securities are named, so there is nothing here that could
    read as a recommendation.
    """
    return shell(
        h1(f"Run one scan, {user_name}.")
        + lead(
            "Your account is ready, and nothing has been scanned on it yet. "
            "One scan is the whole first step."
        )
        + paragraph(
            "The scanner ranks US equities on six measured factors — momentum, "
            "trend, relative volume, short interest, insider and institutional "
            "flow. You set the thresholds; it returns every name that currently "
            "meets them, with the underlying numbers shown next to each row so "
            "you can see why it matched."
        )
        + button(
            "Run my first scan",
            "https://tapeline.io/app/scanner?utm_source=email&utm_campaign=activation_first_scan&utm_medium=transactional",
        )
        + paragraph(
            "The default thresholds are a reasonable starting point if you'd "
            "rather not configure anything — hit run and adjust from what comes "
            "back."
        )
        + _calm_trial_note(trial_ends_at)
        + footnote(
            "Tapeline reports what the factors measure. It doesn't tell you "
            "what to buy. — Christian, founder."
        ),
        preheader="One scan is the first step — here's what the scanner measures.",
    )


def render_activation_ask_email(
    user_name: str, *, trial_ends_at: datetime | None = None,
) -> str:
    """Message #3 (final unprompted nudge) — ~48h after signup, still zero
    activity.

    A genuine question, not a pitch: the founder wants replies, because at this
    stage the useful thing is finding out what the product failed to make
    obvious. Deliberately asks about the PRODUCT experience, never about the
    reader's capital, holdings, goals, risk tolerance or experience — Rule 8
    forbids collecting any of that, and a reply-to-me email is still a
    collection surface.

    This is the LAST message in the series. Nothing follows it. See
    run_activation_nudge_drip for the enforcement.
    """
    return shell(
        h1("Can I ask what got in the way?")
        + lead(
            f"{user_name}, you signed up a couple of days ago and haven't run a "
            f"scan yet. That's genuinely useful information for me — it usually "
            f"means something in the product didn't land."
        )
        + paragraph(
            "So, honestly: what stopped you? Was the scanner screen confusing, "
            "did it not do the thing you assumed it did, or was it just a busy "
            "week? Any of those is a fair answer."
        )
        + paragraph(
            "Hit reply and tell me in one line. It comes straight to me and I "
            "read every one. If something's broken or unclear, that's the "
            "fastest way it gets fixed."
        )
        + secondary_link(
            "Or open the scanner",
            "https://tapeline.io/app/scanner?utm_source=email&utm_campaign=activation_ask&utm_medium=transactional",
        )
        + _calm_trial_note(trial_ends_at)
        + footnote(
            "This is the last note you'll get about getting started — I won't "
            "keep nudging. — Christian, founder."
        ),
        preheader="One question: what got in the way? Hit reply, it comes to me.",
    )


# ── Annual upgrade nudge (lever #2: monthly → annual, ~30 days post-convert) ─
#
# Per-tier annual-savings copy. Mirrors PricingTable.tsx / ComparisonTable.tsx
# — keep these numbers in sync if the published prices ever move.
_ANNUAL_PITCH: dict[str, dict[str, str]] = {
    "pro": {
        "label": "Pro",
        "monthly": "$9.99",
        "annual_monthly": "$8.25",
        "annual_yearly": "$99",
        "savings": "$20",
    },
    "premium": {
        "label": "Premium",
        "monthly": "$19.99",
        "annual_monthly": "$16.58",
        "annual_yearly": "$199",
        "savings": "$40",
    },
}


def render_annual_upgrade_email(user_name: str, *, tier: str) -> str:
    """Post-conversion nudge for MONTHLY subscribers (~30 days in) to switch to
    annual billing. Loss-aversion framing on the savings they're leaving on the
    table. Gated on EmailPref.RE_ENGAGEMENT (the sales-nurture suppressable
    bucket), persona "sales", carries a List-Unsubscribe header (it's a
    marketing upsell, not account state). Unknown tier falls back to the Pro
    pitch so the email never renders blank."""
    pitch = _ANNUAL_PITCH.get(tier, _ANNUAL_PITCH["pro"])
    return shell(
        h1(f"You're leaving {pitch['savings']} on the table, {user_name}.")
        + lead(
            f"You've been on Tapeline {pitch['label']} for about a month — long "
            f"enough to know it earns its keep. On monthly you're paying "
            f"{pitch['monthly']}/mo. Annual works out to {pitch['annual_monthly']}/mo."
        )
        + card(
            f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-weight:600;font-family:{FONT_SANS};">Switch to annual</div>'
            f'<p class="tl-fg" style="margin:8px 0 12px;color:{LIGHT_FG};font-size:14px;line-height:1.55;font-family:{FONT_SANS};">'
            f'{pitch["label"]} annual is <strong>{pitch["annual_yearly"]}/yr</strong> '
            f'({pitch["annual_monthly"]}/mo) — you keep every tool you have now and '
            f'<strong>save {pitch["savings"]} a year</strong>.</p>'
            + button(
                "Switch to annual",
                "https://tapeline.io/app/billing?utm_source=email&utm_campaign=annual_nudge&utm_medium=transactional",
            ),
            accent=True,
        )
        + muted_paragraph(
            "Same plan, same features — just a lower effective rate for paying "
            "once a year instead of twelve times."
        )
        + footnote("Staying monthly is completely fine too — no change needed. — Christian, founder."),
        preheader=f"Switch to annual and save {pitch['savings']} a year on {pitch['label']}.",
    )


# ── Proactive billing notices (renewal reminder + card-expiring) ─────────────
#
# Both are TRANSACTIONAL (billing/account state, not marketing): persona
# "billing", no List-Unsubscribe, no email_prefs gate. They head off
# *involuntary* churn — a courtesy heads-up before an annual plan auto-renews
# (kills surprise-renewal disputes), and a nudge to refresh a card BEFORE it
# expires and a renewal declines into the dunning sequence.

def render_annual_renewal_reminder_email(
    user_name: str, *, tier: str, amount_label: str, renew_date_label: str,
) -> str:
    """T-7 heads-up before an ANNUAL plan auto-renews. Gives a clean window to
    update a card or cancel, and stops the renewal charge being a surprise."""
    tier_label = tier.capitalize()
    return shell(
        h1(f"Your {tier_label} plan renews {renew_date_label}.")
        + lead(
            f"{user_name}, a quick heads-up so it's never a surprise: your "
            f"Tapeline {tier_label} annual plan renews on {renew_date_label} "
            f"for {amount_label}. It renews automatically — you don't need to "
            "do anything."
        )
        + card(
            f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-weight:600;font-family:{FONT_SANS};">Upcoming renewal</div>'
            f'<p class="tl-fg" style="margin:8px 0 12px;color:{LIGHT_FG};font-size:14px;line-height:1.55;font-family:{FONT_SANS};">'
            f'<strong>{amount_label}</strong> on <strong>{renew_date_label}</strong> &middot; {tier_label} annual. '
            "Want to switch plans, update your card, or cancel? It's all one click from billing.</p>"
            + button(
                "Manage billing",
                "https://tapeline.io/app/billing?utm_source=email&utm_campaign=renewal_reminder&utm_medium=transactional",
            ),
        )
        + muted_paragraph(
            "If everything looks right, there's nothing to do — this note just "
            "makes sure the charge never catches you off guard."
        )
        + footnote("Questions about your bill? Reply to this email — billing@tapeline.io reads every one."),
        preheader=f"Your Tapeline {tier_label} plan renews {renew_date_label} for {amount_label} — nothing to do.",
    )


def render_card_expiring_email(
    user_name: str, *, brand: str, last4: str, exp_label: str,
) -> str:
    """The card on file expires at month-end (Stripe customer.source.expiring).
    Nudge an update BEFORE the next renewal declines into dunning."""
    card_label = f"{brand} ending {last4}" if last4 else "the card on file"
    return shell(
        h1(f"Your card expires soon, {user_name}.")
        + lead(
            f"The card we have on file — {card_label} — expires {exp_label}. "
            "Update it before your next renewal so your Tapeline access never "
            "skips a beat."
        )
        + card(
            f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-weight:600;font-family:{FONT_SANS};">Update your card</div>'
            f'<p class="tl-fg" style="margin:8px 0 12px;color:{LIGHT_FG};font-size:14px;line-height:1.55;font-family:{FONT_SANS};">'
            "Open billing, click &ldquo;Update payment method&rdquo;, paste the new card. "
            "Takes about thirty seconds — nothing on your plan changes.</p>"
            + button(
                "Update card",
                "https://tapeline.io/app/billing?utm_source=email&utm_campaign=card_expiring&utm_medium=transactional",
            ),
            accent=True,
        )
        + muted_paragraph(
            "Already updated it? Then you're all set — you can ignore this."
        )
        + footnote("Anything weird? Reply to this email — billing@tapeline.io reads every reply."),
        preheader=f"The card on file ({card_label}) expires {exp_label} — update it to avoid an interruption.",
    )


# ── Founder-touch (lever #4: personal hello to high-value, engaged users) ────

def render_founder_touch_email(user_name: str) -> str:
    """Personal founder note to a high-value, engaged early user.

    Sent ~5-7 days after signup to someone on a trial-Premium or paid plan who
    has actually started using Tapeline (≥1 watchlist ticker) — the cohort
    worth a real 1:1 hello, not a cold blast. Deliberately plain: no stat card,
    no marketing button, just a short note that invites a reply. Persona
    "sales" (christian@), gated on EmailPref.RE_ENGAGEMENT, carries a
    List-Unsubscribe header. One-shot per user via User.founder_touch_sent_at.
    Voice stays descriptive — no "buy/sell/recommend" — per the publisher
    exemption."""
    return shell(
        h1(f"Hey {user_name} — Christian here.")
        + lead(
            "I'm the founder of Tapeline. I build it solo out of Melbourne, so I "
            "try to say hello to the people who actually start using it — and "
            "you have, which I genuinely appreciate."
        )
        + paragraph(
            "No pitch in this one. I just want to know how it's landing: what "
            "made you sign up, and whether the scanner is showing you what you "
            "hoped it would. If something feels missing or confusing, that's the "
            "single most useful thing you could tell me."
        )
        + paragraph(
            "Just hit reply — it comes straight to me, and I read every one."
        )
        + footnote("Thanks for giving it a shot. — Christian, founder, Tapeline"),
        preheader="A quick personal hello from Tapeline's founder.",
    )


# ── Security + privacy confirmations ─────────────────────────────────────────
#
# Account-state notifications a user can't opt out of: persona "default"
# (transactional onboarding/account hub, hello@), no List-Unsubscribe, no
# email_prefs gate. Calm + procedural voice — these are "for your records"
# receipts, not marketing. Descriptive only; no advice language.

def render_security_confirmation_email(
    user_name: str,
    *,
    change: str,
    when_label: str | None = None,
) -> str:
    """Confirmation that a security-relevant change just happened on the
    account — e.g. a completed password reset.

    `change` is a short human phrase describing what changed (e.g.
    "Your password was changed"). The email reassures the user it was them,
    and gives a clear "wasn't me?" recovery path if it wasn't. We never echo
    the new password or any secret — just the fact that the change occurred.

    Sent immediately after the change lands (e.g. password-reset completion).
    Transactional security receipt: persona "default", no List-Unsubscribe."""
    when_line = f" on {when_label}" if when_label else ""
    return shell(
        h1(f"{change}, {user_name}.")
        + lead(
            f"This is a confirmation for your records: {change.lower()}"
            f"{when_line}. If this was you, you're all set — there's nothing "
            "else to do."
        )
        + card(
            f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-weight:600;font-family:{FONT_SANS};">Didn\'t make this change?</div>'
            f'<p class="tl-fg" style="margin:8px 0 12px;color:{LIGHT_FG};font-size:14px;line-height:1.55;font-family:{FONT_SANS};">'
            "If you didn't do this, your account may be at risk. Reset your "
            "password right away, and reply to this email so we can help secure "
            "things — every reply reaches a real person.</p>"
            + button(
                "Secure my account",
                "https://tapeline.io/app/account?utm_source=email&utm_campaign=security_confirmation&utm_medium=transactional",
            ),
            accent=True,
        )
        + footnote(
            "We send this whenever a sensitive change happens on your account "
            "so an unexpected one never slips by unnoticed. Questions? Reply or "
            "email support@tapeline.io."
        ),
        preheader=f"Security confirmation: {change.lower()}{when_line}.",
    )


def render_gdpr_confirmation_email(
    user_name: str,
    *,
    kind: str,
) -> str:
    """Confirmation of a data-rights request. `kind` in {"export", "deletion"}.

    Wired into the account router:
      - "export"   — GDPR Art. 15 data-access export (GET /account/export)
      - "deletion" — GDPR Art. 17 erasure (DELETE /account)

    For deletion, this is the LAST email the account ever receives — so it must
    be sent before (or be captured from) the user row being removed. Calm,
    procedural, reassuring. Descriptive only; no advice language."""
    if kind == "deletion":
        body = (
            h1(f"Your account has been deleted, {user_name}.")
            + lead(
                "As you requested, we've permanently deleted your Tapeline "
                "account and the personal data tied to it — your profile, "
                "watchlist, alert rules, alert history, and subscription "
                "records. This action is final and can't be undone."
            )
            + card(
                f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-weight:600;font-family:{FONT_SANS};">What happens now</div>'
                f'<p class="tl-fg" style="margin:8px 0 0;color:{LIGHT_FG};font-size:14px;line-height:1.55;font-family:{FONT_SANS};">'
                "You won't receive any further emails from us. A small amount "
                "of information may persist in routine backups for a short "
                "retention window before it's overwritten, and we may keep "
                "limited records where the law requires (for example, billing "
                "history for tax purposes).</p>",
                accent=True,
            )
            + muted_paragraph(
                "If you'd like to use Tapeline again in the future, you're "
                "always welcome to sign up fresh. Thanks for giving it a try."
            )
            + footnote(
                "Sent to confirm your erasure request (GDPR Article 17). "
                "Didn't request this? Reply to this email immediately — "
                "support@tapeline.io reaches a real person."
            )
        )
        preheader = "Confirming your Tapeline account and personal data have been deleted."
    else:
        body = (
            h1(f"Your data export is ready, {user_name}.")
            + lead(
                "As you requested, we've generated a copy of the personal data "
                "we hold about you — your profile, watchlist, alert rules, "
                "alert history, and subscription records — and started the "
                "download in your browser."
            )
            + card(
                f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-weight:600;font-family:{FONT_SANS};">Your export</div>'
                f'<p class="tl-fg" style="margin:8px 0 12px;color:{LIGHT_FG};font-size:14px;line-height:1.55;font-family:{FONT_SANS};">'
                "The file is a single JSON document. If the download didn't "
                "start, open your account page and request it again — it's "
                "ready any time.</p>"
                + button(
                    "Open my account",
                    "https://tapeline.io/app/account?utm_source=email&utm_campaign=gdpr_export&utm_medium=transactional",
                ),
                accent=True,
            )
            + muted_paragraph(
                "We send this confirmation so you have a record of when a copy "
                "of your data was generated."
            )
            + footnote(
                "Sent to confirm your data-access request (GDPR Article 15). "
                "Didn't request this? Reply to this email — support@tapeline.io "
                "reaches a real person."
            )
        )
        preheader = "Your Tapeline data export is ready — download started in your browser."
    return shell(body, preheader=preheader)


# ── Worker orchestration ────────────────────────────────────────────────────
#
# These functions drive the trial drip, EOD digest, and re-engagement
# email cadences. Called from app.workers.signal_publisher; idempotent
# per-day via User.drip_state tokens.

async def trial_summary_for_user(session, user) -> dict | None:
    """Pull per-user trial-period highlights for the day-7/day-13 emails.

    Two data streams blended:
      1. **Watchlist density** — how many tickers the user is watching, how
         many of those currently sit in HIGH CONVICTION / STRONG SETUP, and
         the watchlist ticker with the largest absolute score delta since
         baseline. This is the personal signal.
      2. **Public scorecard during trial** — how many top-10 picks Tapeline
         logged between trial_start and now, the next-session hit rate vs
         SPY, the average alpha, and the single highest-alpha pick.

    Returns None if both streams are empty — the renderer treats None as
    "no summary block" and falls back to the prior generic-urgency text.
    Never raises: errors are swallowed because a failed personalisation
    must not block the drip.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.models import DailyScorecardEntry, Ticker, WatchlistItem

    try:
        trial_end = user.trial_ends_at
        if trial_end is None:
            return None
        trial_start = trial_end - timedelta(days=14)
        now = datetime.now(UTC)
        days_so_far = max(0, (now - trial_start).days)

        # ── Watchlist density ────────────────────────────────────────────
        wl_r = await session.execute(
            select(WatchlistItem, Ticker)
            .outerjoin(Ticker, Ticker.symbol == WatchlistItem.symbol)
            .where(WatchlistItem.user_id == user.id)
        )
        rows = wl_r.all()
        wl_count = len(rows)
        wl_strong = 0
        best_wl = None
        best_wl_abs = 0.0
        for w, t in rows:
            if t is None:
                continue
            if t.signal in ("HIGH CONVICTION", "STRONG SETUP"):
                wl_strong += 1
            if t.score is not None and w.baseline_score is not None:
                delta = t.score - w.baseline_score
                if abs(delta) > best_wl_abs:
                    best_wl_abs = abs(delta)
                    best_wl = {
                        "symbol": w.symbol,
                        "score": t.score,
                        "signal": t.signal or "",
                        "delta": delta,
                    }

        # ── Scorecard during trial window ────────────────────────────────
        sc_r = await session.execute(
            select(DailyScorecardEntry).where(
                DailyScorecardEntry.as_of >= trial_start.date(),
                DailyScorecardEntry.as_of <= now.date(),
            )
        )
        picks = sc_r.scalars().all()
        picks_n = len(picks)
        scored = [p for p in picks if p.alpha_vs_spy is not None]
        hit_rate = (
            100.0 * sum(1 for p in scored if (p.alpha_vs_spy or 0) > 0) / len(scored)
            if scored else None
        )
        avg_alpha = (
            sum(p.alpha_vs_spy or 0 for p in scored) / len(scored)
            if scored else None
        )
        best_pick = None
        if scored:
            b = max(scored, key=lambda p: p.alpha_vs_spy or 0)
            best_pick = {
                "symbol": b.symbol,
                "as_of": b.as_of.isoformat(),
                "alpha": b.alpha_vs_spy,
            }

        if wl_count == 0 and picks_n == 0:
            return None

        return {
            "trial_start": trial_start.date().isoformat(),
            "trial_end": trial_end.date().isoformat() if trial_end else None,
            "days_so_far": days_so_far,
            "watchlist_count": wl_count,
            "watchlist_top_signals": wl_strong,
            "watchlist_best": best_wl,
            "scorecard_picks_during_trial": picks_n,
            "scorecard_hit_rate": hit_rate,
            "scorecard_alpha_avg": avg_alpha,
            "scorecard_best": best_pick,
        }
    except Exception:
        logger.exception("trial_summary.failed user=%s", user.id)
        return None


async def run_eod_watchlist_digest(
    session, *, governor: FrequencyGovernor | None = None,
) -> int:
    """Send EOD watchlist email to every Pro+ user with watchlist items.

    Worker should call this once per day shortly after market close (4:05pm ET = 21:05 UTC).
    Returns count of emails sent. Pure no-op if RESEND_API_KEY isn't set.
    """
    from sqlalchemy import desc, select

    from app.models import Ticker, User, WatchlistItem

    users_r = await session.execute(
        select(User).where(User.tier.in_(["pro", "premium"]))
    )
    users = users_r.scalars().all()

    sent = 0
    for user in users:
        from app.services.email_prefs import EmailPref, wants
        if not wants(user, EmailPref.DAILY_DIGEST):
            continue
        # SCHEDULED: the user asked for this digest, so the governor never
        # blocks it — but it IS recorded below, so a lifecycle nudge later
        # today sees it and stays off this user.
        if governor is not None and not governor.allows(user, SendClass.SCHEDULED):
            continue
        wl_r = await session.execute(
            select(WatchlistItem, Ticker)
            .outerjoin(Ticker, Ticker.symbol == WatchlistItem.symbol)
            .where(WatchlistItem.user_id == user.id)
            .order_by(desc(WatchlistItem.added_at))
        )
        rows = wl_r.all()
        items = []
        for w, t in rows:
            if t is None:
                continue
            delta = (
                (t.score - w.baseline_score)
                if (t.score is not None and w.baseline_score is not None)
                else None
            )
            items.append({
                "symbol": w.symbol,
                "score": t.score,
                "signal": t.signal,
                "change_pct_1d": t.change_pct_1d,
                "score_delta": delta,
                "reason": t.reason,
            })

        # Nothing to report — skip the send entirely rather than mailing a
        # daily "your watchlist is empty" nag to a Pro+ user who hasn't
        # added anything yet.
        if not items:
            continue

        try:
            html = render_eod_watchlist_digest(user.name or "trader", items)
            res = await send_email(
                user.email, f"Tapeline EOD · {_today_short()}", html,
                persona="alerts",
                unsubscribe_user_id=user.id,
                unsubscribe_category="daily_digest",
            )
            if not res.get("skipped", False):
                sent += 1
                if governor is not None:
                    governor.record(user, SendClass.SCHEDULED)
        except Exception:
            logger.exception("eod_digest.send_failed user=%s", user.id)

    logger.info("eod_digest.sent count=%d", sent)
    return sent


async def run_daily_drip(
    session, *, governor: FrequencyGovernor | None = None,
) -> dict[str, int]:
    """Send the full trial-drip series. Returns per-stage counts.

    Stages, all dedup'd via `User.drip_state` (comma-separated tokens):

      Pre-expiry (trial_ends_at in the FUTURE — user is still on trial):
        - "3"   day-3  email   — trial_ends_at in (now+9d,  now+11d)
        - "7"   day-7  email   — trial_ends_at in (now+5d,  now+7d )
        - "11"  T-3    email   — trial_ends_at in (now+1d,  now+3d )
        - "13"  T-1    email   — trial_ends_at in (now,     now+1d )

      Post-expiry (trial_ends_at in the PAST — user didn't convert):
        - "expired" T+0  email — trial_ends_at in (now-2d, now)
        - "post3"   T+3  email — trial_ends_at in (now-5d, now-3d)

      Every window is 48h wide — the nominal fire day plus one grace day,
      mirroring the lapse30 pattern below. The windows used to be exactly
      24h, so one failed/missed daily run silently aged every in-window
      user out of their stage forever. The per-user drip_state token keeps
      each stage at-most-once, so the extra day can't double-send.

      day13 is the ONE exception: it stops dead at `now` (24h wide) so it
      can never overlap "expired". Its grace day used to reach back to
      now-1d, which meant an already-lapsed trial could be told "your
      trial ends tomorrow". A user missed on day13 now ages into the
      "expired" stage instead, which is the honest copy for them.

      Lapsed-trial win-back (handled in its own block below, NOT the
      shared windows loop — different pref bucket + tier filter):
        - "lapse30" ~T+30 email — trial_ends_at in (now-32d, now-30d],
          tier=free, no Stripe customer ever. Gated on RE_ENGAGEMENT
          (marketing bucket — the trial is long over, so TRIAL_DRIP is
          the wrong gate). Closes the structural funnel gap where no-card
          trials exited email forever after post3, because
          run_winback_drip requires canceled_at (i.e. a cancelled PAID
          subscription) and these users never had one.

    The T+0 "expired" stage is the ONLY end-of-trial email. The hourly
    worker downgrade (signal_publisher._downgrade_expired_trials) used to
    also fire render_trial_ended_email on the same day — that send was
    removed so expiry day produces exactly one email, dedup'd here.

    Tier filter: pre-expiry windows target users still on the trial
    (tier in pro/premium, no Stripe customer). Post-expiry windows drop
    the tier filter because auto-downgrade to Free may have already
    fired — we just need "had a trial that ended recently and never
    added a card".
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.models import User

    now = datetime.now(UTC)
    counts = {"day3": 0, "day7": 0, "day11": 0, "day13": 0, "expired": 0,
              "post3": 0, "lapse30": 0}

    # 48h windows: each stage's nominal day plus one grace day on the trailing
    # edge (the direction users age in), so a failed/missed daily run can't
    # silently drop a cohort — the next successful run still catches them, and
    # the drip_state tokens keep each stage at-most-once. day13 is the
    # exception: its lower bound is `now`, so it is mutually exclusive with
    # "expired" and an already-lapsed trial can never receive "your trial
    # ends tomorrow".
    windows = [
        # Pre-expiry
        ("3",   "day3",   now + timedelta(days=9),  now + timedelta(days=11),
         render_trial_day3_email,         "Tapeline — three days in",
         False, False),
        ("7",   "day7",   now + timedelta(days=5),  now + timedelta(days=7),
         render_trial_day7_email,         "Tapeline — halfway through your trial",
         True, False),
        ("11",  "day11",  now + timedelta(days=1),  now + timedelta(days=3),
         render_trial_day11_email,        "Tapeline — 3 days left on your trial",
         True, False),
        ("13",  "day13",  now,                      now + timedelta(days=1),
         render_trial_day13_email,        "Tapeline — your trial ends tomorrow",
         True, False),
        # Post-expiry
        ("expired", "expired", now - timedelta(days=2), now,
         render_trial_expired_email,      "Your Tapeline trial ended",
         True, True),
        ("post3",   "post3",   now - timedelta(days=5), now - timedelta(days=3),
         render_trial_post_expiry_email,  "Last note from Tapeline",
         False, True),
    ]

    for token, label, lower, upper, renderer, subject, personalise, post_expiry in windows:
        filters = [
            User.trial_ends_at.isnot(None),
            User.trial_ends_at >= lower,
            User.trial_ends_at < upper,
            User.stripe_customer_id.is_(None),
        ]
        if not post_expiry:
            filters.append(User.tier.in_(["pro", "premium"]))

        result = await session.execute(select(User).where(*filters))
        users = result.scalars().all()

        for user in users:
            sent_tokens = set((user.drip_state or "").split(",")) - {""}
            if token in sent_tokens:
                continue
            from app.services.email_prefs import EmailPref, wants
            if not wants(user, EmailPref.TRIAL_DRIP):
                continue
            if governor is not None and not governor.allows(
                user, SendClass.LIFECYCLE, token=token,
            ):
                continue
            try:
                # One-click signed Stripe-checkout links for the conversion
                # stages (day-11 / day-13 / expired / post3). Minted fresh per
                # user at send time; None when the signing secret isn't
                # configured, in which case the renderers fall back to the
                # /app/billing URL.
                from app.services.email_checkout import email_checkout_urls
                cu = (
                    email_checkout_urls(user.id)
                    if token in ("11", "13", "expired", "post3")
                    else None
                )
                if personalise:
                    summary = await trial_summary_for_user(session, user)
                    if token == "11":
                        # T-3 quotes the user's real deadline ("before
                        # Friday, July 10") instead of a hardcoded weekday.
                        # Called directly (not via `renderer`) because the
                        # keyword-only args aren't part of the shared shape.
                        html = render_trial_day11_email(
                            user.name or "trader", summary,
                            trial_ends_at=user.trial_ends_at,
                            checkout_urls=cu,
                        )
                    elif token == "13":
                        # Direct calls (not via `renderer`) for the same
                        # reason as day-11: the keyword-only checkout_urls
                        # arg isn't part of the shared renderer shape.
                        html = render_trial_day13_email(
                            user.name or "trader", summary, checkout_urls=cu,
                        )
                    elif token == "expired":
                        html = render_trial_expired_email(
                            user.name or "trader", summary, checkout_urls=cu,
                        )
                    else:
                        html = renderer(user.name or "trader", summary)
                elif token == "post3":
                    html = render_trial_post_expiry_email(
                        user.name or "trader", checkout_urls=cu,
                    )
                else:
                    html = renderer(user.name or "trader")
                # Day 3 is soft activation — keep under the default
                # transactional sender. Day 7 onwards is the conversion push.
                drip_persona: EmailPersona = "default" if token == "3" else "sales"
                res = await send_email(
                    user.email, subject, html, persona=drip_persona,
                    unsubscribe_user_id=user.id,
                    unsubscribe_category="trial_drip",
                )
                if not res.get("skipped", False):
                    sent_tokens.add(token)
                    user.drip_state = ",".join(sorted(sent_tokens))
                    # Commit per user, inside the try: a write that fails on
                    # one row must not roll back the tokens of users Resend
                    # has ALREADY delivered to (that turns one bad row into a
                    # batch-wide duplicate send on the next run).
                    await session.commit()
                    counts[label] += 1
                    if governor is not None:
                        governor.record(user, SendClass.LIFECYCLE)
            except Exception:
                logger.exception("drip.send_failed user=%s stage=%s", user.id, label)

    # ── "lapse30" — lapsed no-card trial win-back, ~T+30 ─────────────────────
    # Deliberately outside the windows loop: it flips BOTH knobs the loop
    # hardcodes (pref bucket → RE_ENGAGEMENT instead of TRIAL_DRIP, and it
    # re-adds a tier filter post-expiry: tier must be "free" so anyone who
    # subscribed — or was comped — is excluded on top of the no-Stripe-
    # customer check). Window is two days wide (T+30 .. T+32) so a single
    # missed worker day can't silently drop the one remaining touch; the
    # "lapse30" drip_state token still guarantees at-most-once.
    from app.services.email_prefs import EmailPref, wants

    lapse_result = await session.execute(select(User).where(
        User.trial_ends_at.isnot(None),
        User.trial_ends_at >= now - timedelta(days=32),
        User.trial_ends_at < now - timedelta(days=30),
        User.stripe_customer_id.is_(None),
        User.tier == "free",
    ))
    for user in lapse_result.scalars().all():
        sent_tokens = set((user.drip_state or "").split(",")) - {""}
        if "lapse30" in sent_tokens:
            continue
        if not wants(user, EmailPref.RE_ENGAGEMENT):
            continue
        if governor is not None and not governor.allows(
            user, SendClass.LIFECYCLE, token="lapse30",
        ):
            continue
        try:
            from app.services.email_checkout import email_checkout_urls
            html = render_trial_lapse30_email(
                user.name or "trader",
                checkout_urls=email_checkout_urls(user.id),
            )
            res = await send_email(
                user.email, "Tapeline — one note, a month on", html,
                persona="sales",
                unsubscribe_user_id=user.id,
                unsubscribe_category="re_engagement",
            )
            if not res.get("skipped", False):
                sent_tokens.add("lapse30")
                user.drip_state = ",".join(sorted(sent_tokens))
                await session.commit()
                counts["lapse30"] += 1
                if governor is not None:
                    governor.record(user, SendClass.LIFECYCLE)
        except Exception:
            logger.exception("drip.send_failed user=%s stage=lapse30", user.id)

    return counts


# ── Weekly market digest (newsletter) ───────────────────────────────────────

def render_weekly_market_digest(
    user_name: str,
    *,
    week_label: str,
    regime: dict | None,
    movers: list[dict],
    scorecard: dict | None,
    headlines: list[dict],
) -> str:
    """Monday newsletter — what the market did, what the public scorecard
    did, and the top scores right now.

    `regime`     {regime, vix, yield_10y, breadth_pct, sector_leaders} | None
    `movers`     list of {symbol, score, signal, reason} — top 5 by score
    `scorecard`  {picks, hit_rate_pct, avg_alpha_pct, best:{symbol,alpha}} | None
    `headlines`  list of {title, publisher, url, published_at} — top 3

    Every section degrades gracefully — if the regime row or scorecard
    data is missing the renderer just drops that block instead of
    failing the whole send.
    """
    # Regime block ------------------------------------------------------------
    if regime:
        regime_label = regime.get("regime", "—") or "—"
        regime_col = (
            SIG_BULL if regime_label == "BULL"
            else SIG_BEAR if regime_label == "BEAR"
            else "#f59e0b" if regime_label == "CAUTIOUS"
            else LIGHT_MUTED
        )
        regime_html = card(
            f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-weight:600;font-family:{FONT_SANS};">Market regime</div>'
            f'<div style="margin-top:8px;font-family:{FONT_MONO};font-size:24px;font-weight:700;color:{regime_col};line-height:1;">{regime_label}</div>'
            f'<div style="height:12px;"></div>'
            + stat_row("VIX", f"{regime.get('vix', 0):.2f}")
            + stat_row("10Y yield", f"{regime.get('yield_10y', 0):.2f}%")
            + stat_row("Breadth (% > 200DMA)", f"{regime.get('breadth_pct', 0):.0f}%"),
            accent=True,
        )
    else:
        regime_html = ""

    # Top movers --------------------------------------------------------------
    if movers:
        movers_html = (
            f'<div class="tl-fg" style="margin:24px 0 10px;font-size:14px;font-weight:600;color:{LIGHT_FG};font-family:{FONT_SANS};">Top 5 scores right now</div>'
        )
        movers_html += "".join(
            ticker_card(
                m.get("symbol", "?"), m.get("score"),
                m.get("signal"), m.get("reason"),
            )
            for m in movers[:5]
        )
    else:
        movers_html = ""

    # Scorecard block ---------------------------------------------------------
    if scorecard and scorecard.get("picks", 0) > 0:
        bits: list[str] = []
        picks = scorecard.get("picks", 0)
        bits.append(
            f'<li><strong>{picks}</strong> top-10 pick'
            f'{"" if picks == 1 else "s"} logged last week.</li>'
        )
        hr = scorecard.get("hit_rate_pct")
        if hr is not None:
            bits.append(f'<li><strong>{hr:.0f}%</strong> beat SPY the next session.</li>')
        aa = scorecard.get("avg_alpha_pct")
        if aa is not None:
            sign = "+" if aa >= 0 else ""
            col = SIG_BULL if aa >= 0 else SIG_BEAR
            bits.append(
                f'<li>Average alpha vs SPY: <span style="color:{col};font-weight:600;">{sign}{aa:.2f}%</span>.</li>'
            )
        best = scorecard.get("best")
        if best and best.get("alpha") is not None:
            ba = best["alpha"]
            sign = "+" if ba >= 0 else ""
            bits.append(
                f'<li>Best pick: <code style="font-family:{FONT_MONO};">{best["symbol"]}</code> · '
                f'alpha <span style="color:{SIG_BULL};font-weight:600;">{sign}{ba:.2f}%</span>.</li>'
            )
        scorecard_html = card(
            f'<div class="tl-muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:{LIGHT_MUTED};font-weight:600;font-family:{FONT_SANS};">Public scorecard last week</div>'
            f'<ul class="tl-fg" style="color:{LIGHT_FG};line-height:1.75;padding-left:18px;margin:10px 0 0;font-size:14px;font-family:{FONT_SANS};">'
            + "".join(bits)
            + f'</ul><div class="tl-muted" style="margin-top:10px;font-size:12px;color:{LIGHT_MUTED};font-family:{FONT_SANS};">'
            f'Full record at <a href="https://tapeline.io/scorecard" style="color:{ACCENT};">tapeline.io/scorecard</a> — every miss is still on the page.</div>'
        )
    else:
        scorecard_html = ""

    # Headlines ---------------------------------------------------------------
    if headlines:
        rows = []
        for hd in headlines[:3]:
            title = (hd.get("title") or "").strip()[:120]
            pub = hd.get("publisher") or ""
            url = hd.get("url") or "https://tapeline.io/app/scanner"
            rows.append(f"""
            <a href="{url}" target="_blank" style="display:block;text-decoration:none;color:inherit;">
              <div class="tl-card" style="background:#ffffff;border:1px solid {LIGHT_BORDER};border-radius:8px;padding:14px 18px;margin:0 0 8px;">
                <div class="tl-fg" style="font-size:14px;font-weight:600;color:{LIGHT_FG};line-height:1.4;font-family:{FONT_SANS};">{title}</div>
                <div class="tl-muted" style="margin-top:4px;font-size:12px;color:{LIGHT_MUTED};font-family:{FONT_SANS};">{pub}</div>
              </div>
            </a>
            """)
        headlines_html = (
            f'<div class="tl-fg" style="margin:24px 0 10px;font-size:14px;font-weight:600;color:{LIGHT_FG};font-family:{FONT_SANS};">Headlines worth a click</div>'
            + "".join(rows)
        )
    else:
        headlines_html = ""

    body = (
        h1(f"Weekly digest · {week_label}")
        + lead(
            f"Hi {user_name}, here's the week through Tapeline's eyes — "
            f"regime, the names the scanner is loudest on, and what the "
            f"public scorecard did."
        )
        + regime_html
        + movers_html
        + scorecard_html
        + headlines_html
        + button(
            "Open the scanner",
            "https://tapeline.io/app/scanner?utm_source=email&utm_campaign=weekly_digest&utm_medium=newsletter",
        )
        + footnote(
            "You're getting this because you opted into the weekly market "
            "digest. Toggle off any time at "
            f'<a href="https://tapeline.io/app/settings/email" '
            f'style="color:{LIGHT_SUBTLE};text-decoration:underline;">/app/settings/email</a>.'
        )
    )
    return shell(
        body,
        preheader=f"Weekly digest · {week_label} — regime, top scores, scorecard week-in-review.",
    )


async def _build_newsletter_payload(session) -> dict:
    """Pull the four content blocks the newsletter renderer needs.

    Each block is wrapped in its own try/except so a failure in one
    (e.g. the regime row doesn't exist yet) degrades gracefully — the
    email still sends with whatever's available rather than failing the
    whole batch.
    """
    from datetime import date, timedelta

    from sqlalchemy import desc, select

    from app.models import DailyScorecardEntry, NewsItem, RegimeState, Ticker
    from app.models.news import exclude_mock_clause

    out: dict = {
        "regime": None, "movers": [], "scorecard": None, "headlines": [],
    }

    # Regime
    try:
        r = await session.execute(select(RegimeState).where(RegimeState.id == 1))
        rg = r.scalar_one_or_none()
        if rg is not None:
            out["regime"] = {
                "regime": rg.regime,
                "vix": rg.vix,
                "yield_10y": rg.yield_10y,
                "breadth_pct": rg.breadth_pct,
                "sector_leaders": rg.sector_leaders,
            }
    except Exception:
        logger.exception("newsletter.regime_failed")

    # Top movers — top 5 by current score (freshness + data-quality floored;
    # no stale ghosts, no corrupt score>100 / emoji-symbol / <2-factor rows)
    try:
        from app.services.ticker_freshness import live_clauses
        _mv_stmt = select(
            Ticker.symbol, Ticker.score, Ticker.signal, Ticker.reason
        )
        for _clause in await live_clauses(session):
            _mv_stmt = _mv_stmt.where(_clause)
        r = await session.execute(
            _mv_stmt.order_by(desc(Ticker.score)).limit(5)
        )
        out["movers"] = [
            {"symbol": s, "score": sc, "signal": sg, "reason": rs}
            for s, sc, sg, rs in r.all()
        ]
    except Exception:
        logger.exception("newsletter.movers_failed")

    # Scorecard last 7 days
    try:
        today = date.today()
        week_ago = today - timedelta(days=7)
        sc_r = await session.execute(
            select(DailyScorecardEntry).where(
                DailyScorecardEntry.as_of >= week_ago,
                DailyScorecardEntry.as_of <= today,
            )
        )
        picks = sc_r.scalars().all()
        if picks:
            scored = [p for p in picks if p.alpha_vs_spy is not None]
            hit_rate = (
                100.0 * sum(1 for p in scored if (p.alpha_vs_spy or 0) > 0) / len(scored)
                if scored else None
            )
            avg_alpha = (
                sum(p.alpha_vs_spy or 0 for p in scored) / len(scored)
                if scored else None
            )
            best = None
            if scored:
                b = max(scored, key=lambda p: p.alpha_vs_spy or 0)
                best = {"symbol": b.symbol, "alpha": b.alpha_vs_spy}
            out["scorecard"] = {
                "picks": len(picks),
                "hit_rate_pct": hit_rate,
                "avg_alpha_pct": avg_alpha,
                "best": best,
            }
    except Exception:
        logger.exception("newsletter.scorecard_failed")

    # Headlines — 3 most recent
    try:
        r = await session.execute(
            # Never put a fabricated mock headline in an outbound email (LEGAL
            # read-path invariant). See models.news.exclude_mock_clause.
            select(NewsItem)
            .where(exclude_mock_clause())
            .order_by(desc(NewsItem.published_at))
            .limit(3)
        )
        items = r.scalars().all()
        out["headlines"] = [
            {
                "title": it.title,
                "publisher": it.publisher,
                "url": it.url,
                "published_at": it.published_at.isoformat() if it.published_at else None,
            }
            for it in items
        ]
    except Exception:
        logger.exception("newsletter.headlines_failed")

    return out


async def run_weekly_newsletter(
    session, *, now=None, governor: FrequencyGovernor | None = None,
) -> int:
    """Send the Monday market digest to every eligible user.

    Eligibility = both gates pass:
      1. `User.marketing_opt_in == True` (explicit GDPR consent at signup)
      2. `EmailPref.WEEKLY_NEWSLETTER` bit set (day-to-day toggle)

    Dedupe: a "weekly_{ISO-year}W{ISO-week}" token is added to
    User.drip_state on successful send, so a worker restart on the same
    Monday doesn't double-send. Superseded weekly_* tokens are dropped at
    the same time — only the current week's token is ever read, and
    appending forever overflowed the String(255) column. Returns the count
    of emails sent. Pure no-op when RESEND_API_KEY isn't set (send_email
    returns skipped:True).

    `now` is an optional override for tests — defaults to datetime.now(UTC).
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.models import User
    from app.services.email_prefs import EmailPref, wants

    now = now or datetime.now(UTC)
    iso_year, iso_week, _ = now.isocalendar()
    token = f"weekly_{iso_year}W{iso_week:02d}"
    monday = now - timedelta(days=now.weekday())
    week_label = monday.strftime("%b %d, %Y")

    payload = await _build_newsletter_payload(session)

    result = await session.execute(
        select(User).where(User.marketing_opt_in.is_(True))
    )
    users = result.scalars().all()

    sent = 0
    for user in users:
        if not wants(user, EmailPref.WEEKLY_NEWSLETTER):
            continue
        sent_tokens = set((user.drip_state or "").split(",")) - {""}
        if token in sent_tokens:
            continue
        # SCHEDULED: explicit marketing opt-in + the weekly bit. Never
        # blocked, but recorded so a lifecycle nudge does not land on the
        # same day as the newsletter.
        if governor is not None and not governor.allows(user, SendClass.SCHEDULED):
            continue
        try:
            html = render_weekly_market_digest(
                user.name or "trader",
                week_label=week_label,
                regime=payload["regime"],
                movers=payload["movers"],
                scorecard=payload["scorecard"],
                headlines=payload["headlines"],
            )
            res = await send_email(
                user.email,
                f"Tapeline weekly · {week_label}",
                html,
                persona="alerts",
                unsubscribe_user_id=user.id,
                unsubscribe_category="weekly_newsletter",
            )
            if not res.get("skipped", False):
                # Prune superseded weekly_* tokens. Only the CURRENT week's
                # token is ever read (the dedupe check above; nothing else
                # queries historical weekly tokens), and appending one 15-char
                # token per week overran drip_state's String(255) inside a few
                # months — Postgres then raised StringDataRightTruncation on
                # commit and took the rest of the batch down with it.
                sent_tokens = {
                    t for t in sent_tokens if not t.startswith("weekly_")
                }
                sent_tokens.add(token)
                user.drip_state = ",".join(sorted(sent_tokens))
                # Commit per user, inside the try — see run_daily_drip.
                await session.commit()
                sent += 1
                if governor is not None:
                    governor.record(user, SendClass.SCHEDULED)
        except Exception:
            logger.exception("weekly_newsletter.send_failed user=%s", user.id)

    logger.info("weekly_newsletter.sent count=%d token=%s", sent, token)
    return sent


async def run_re_engagement_drip(
    session, *, governor: FrequencyGovernor | None = None,
) -> dict[str, int]:
    """Send the re-engagement email to users dormant for ~14 days.

    Window: last_seen_at in [now-16d, now-14d) — 48h wide (nominal day-14
    plus one grace day), same missed-run protection as the trial-drip
    windows, so one failed/skipped daily run can't silently drop the touch.
    One-shot, deduplicated via the "re14" token in User.drip_state — so a
    user only ever receives this email once even if they fall back into
    dormancy later.

    Trial users are EXCLUDED — the trial drip is the right re-engagement
    channel for them.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import or_, select

    from app.models import User

    now = datetime.now(UTC)
    counts = {"re14": 0}

    lower = now - timedelta(days=16)
    upper = now - timedelta(days=14)

    filters = [
        User.last_seen_at.isnot(None),
        User.last_seen_at >= lower,
        User.last_seen_at < upper,
        or_(User.trial_ends_at.is_(None), User.trial_ends_at < now),
    ]

    result = await session.execute(select(User).where(*filters))
    users = result.scalars().all()

    any_sent = False
    for user in users:
        sent_tokens = set((user.drip_state or "").split(",")) - {""}
        if "re14" in sent_tokens:
            continue
        from app.services.email_prefs import EmailPref, wants
        if not wants(user, EmailPref.RE_ENGAGEMENT):
            continue
        if governor is not None and not governor.allows(
            user, SendClass.LIFECYCLE, token="re14",
        ):
            continue
        try:
            html = render_re_engagement_email(user.name or "trader")
            res = await send_email(
                user.email, "Tapeline missed you", html,
                persona="sales",
                unsubscribe_user_id=user.id,
                unsubscribe_category="re_engagement",
            )
            if not res.get("skipped", False):
                sent_tokens.add("re14")
                user.drip_state = ",".join(sorted(sent_tokens))
                counts["re14"] += 1
                any_sent = True
                if governor is not None:
                    governor.record(user, SendClass.LIFECYCLE)
        except Exception:
            logger.exception("re_engagement.send_failed user=%s", user.id)

    if any_sent:
        await session.commit()
    return counts


async def run_winback_drip(
    session, *, governor: FrequencyGovernor | None = None,
) -> dict[str, int]:
    """Graduated post-cancellation win-back at ~30 / 60 / 90 days.

    Population: users who cancelled (canceled_at set) AND have already
    dropped to free. The tier=="free" gate is what makes the clock honest
    for annual subscribers — they keep access for months after hitting
    cancel, so canceled_at only starts "counting" toward win-back once
    Stripe's subscription.deleted fires and the webhook drops their tier.
    A monthly user lands in this population ~immediately at period end.

    Stage selection is by elapsed days, NOT a strict ladder: we send the
    single stage whose window the user is currently in (≥90→wb90,
    ≥60→wb60, ≥30→wb30) and dedupe on that stage's token in
    winback_state. If the worker was down across a window the user simply
    skips the stale earlier note and gets the current one — we never
    backfill a "it's been about a month" email to someone gone 70 days.

    Resubscribe / pause / save-offer all clear canceled_at (billing
    endpoints + the subscription webhook), so a returning customer drops
    out of this query automatically. A fresh cancellation resets
    winback_state to "" (routers/billing.py), re-arming the full series.

    Marketing nudge → gated on EmailPref.RE_ENGAGEMENT and carries the
    List-Unsubscribe header via unsubscribe_category="re_engagement".
    No-op when RESEND_API_KEY is unset (send_email returns skipped:True).
    """
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.models import User
    from app.services.email_prefs import EmailPref, wants

    now = datetime.now(UTC)
    counts = {"wb30": 0, "wb60": 0, "wb90": 0}

    result = await session.execute(
        select(User).where(
            User.canceled_at.is_not(None),
            User.tier == "free",
        )
    )
    users = result.scalars().all()
    if not users:
        return counts

    # Public-scorecard proof line — fetched once, best-effort. Reuses the
    # newsletter payload builder (scorecard block only). A failure here
    # just yields a blank proof block; the win-back email still sends.
    scorecard = None
    try:
        scorecard = (await _build_newsletter_payload(session)).get("scorecard")
    except Exception:
        logger.exception("winback.scorecard_fetch_failed")

    subjects = {
        "wb30": "Your Tapeline setup is still saved",
        "wb60": "The track record kept running without you",
        "wb90": "One last note from Tapeline",
    }

    any_sent = False
    for user in users:
        if not user.email:
            continue
        # canceled_at is stored tz-aware, but SQLite hands it back naive —
        # normalise so the subtraction never raises on the test DB.
        ca = user.canceled_at
        if ca.tzinfo is None:
            ca = ca.replace(tzinfo=UTC)
        days_since = (now - ca).days
        if days_since >= 90:
            stage = "wb90"
        elif days_since >= 60:
            stage = "wb60"
        elif days_since >= 30:
            stage = "wb30"
        else:
            continue

        sent_tokens = set((user.winback_state or "").split(",")) - {""}
        if stage in sent_tokens:
            continue
        if not wants(user, EmailPref.RE_ENGAGEMENT):
            continue
        if governor is not None and not governor.allows(
            user, SendClass.LIFECYCLE, token=stage,
        ):
            continue
        try:
            html = render_winback_email(
                user.name or "trader", stage=stage, scorecard=scorecard,
            )
            res = await send_email(
                user.email, subjects[stage], html,
                persona="sales",
                unsubscribe_user_id=user.id,
                unsubscribe_category="re_engagement",
            )
            if not res.get("skipped", False):
                sent_tokens.add(stage)
                user.winback_state = ",".join(sorted(sent_tokens))
                counts[stage] += 1
                any_sent = True
                if governor is not None:
                    governor.record(user, SendClass.LIFECYCLE)
        except Exception:
            logger.exception("winback.send_failed user=%s stage=%s", user.id, stage)

    if any_sent:
        await session.commit()
    return counts


async def run_activation_drip(
    session, *, governor: FrequencyGovernor | None = None,
) -> dict[str, int]:
    """Early-lifecycle activation nudges. Returns per-stage counts.

    Two one-shot prompts, both dedup'd via User.drip_state tokens and gated
    on EmailPref.TRIAL_DRIP (the early-lifecycle suppressable bucket):

      "act_wl"    — signed up 24-72h ago and still has zero watchlist items.
                    The watchlist is the core habit loop (it powers smart
                    alerts and the EOD digest), so the first ticker added is
                    activation milestone #1. Sent to every tier — a Free user
                    with an empty watchlist is exactly who to nudge.

      "act_alert" — signed up 3-5 days ago, on a plan that can create alert
                    rules (trial Premium or paid Pro/Premium), but has none.
                    Free is excluded: alerts are a Pro+ feature, so nudging a
                    Free user toward one would just point at a paywall.

    Bounded signup windows (not just a lower bound) keep the nudge timely — we
    don't email someone who signed up two months ago. A daily run catches each
    user once inside the window; the drip_state token prevents a repeat if
    they're still empty the next day. Both send under the "default"
    transactional-onboarding persona. No-op when RESEND_API_KEY is unset
    (send_email returns skipped:True, so the token is never stamped).
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import exists, select

    from app.models import AlertRule, User, WatchlistItem
    from app.services.email_prefs import EmailPref, wants

    now = datetime.now(UTC)
    counts = {"act_wl": 0, "act_alert": 0}

    # act_wl — no watchlist item, 24-72h after signup. Correlated EXISTS so
    # the "has any ticker" test stays a single round-trip.
    no_watchlist = ~exists().where(WatchlistItem.user_id == User.id)
    wl_users = (
        await session.execute(
            select(User).where(
                User.created_at >= now - timedelta(hours=72),
                User.created_at < now - timedelta(hours=24),
                no_watchlist,
            )
        )
    ).scalars().all()

    # act_alert — no alert rule, 3-5d after signup, on an alert-capable tier.
    no_alert_rule = ~exists().where(AlertRule.user_id == User.id)
    al_users = (
        await session.execute(
            select(User).where(
                User.created_at >= now - timedelta(days=5),
                User.created_at < now - timedelta(days=3),
                User.tier.in_(["pro", "premium"]),
                no_alert_rule,
            )
        )
    ).scalars().all()

    stages = [
        ("act_wl", wl_users, render_activation_watchlist_email,
         "Your Tapeline watchlist is still empty"),
        ("act_alert", al_users, render_activation_alert_email,
         "Set one alert and let Tapeline watch for you"),
    ]

    any_sent = False
    for token, users, renderer, subject in stages:
        for user in users:
            if not user.email:
                continue
            sent_tokens = set((user.drip_state or "").split(",")) - {""}
            if token in sent_tokens:
                continue
            if not wants(user, EmailPref.TRIAL_DRIP):
                continue
            if governor is not None and not governor.allows(
                user, SendClass.LIFECYCLE, token=token,
            ):
                continue
            try:
                html = renderer(user.name or "trader")
                res = await send_email(
                    user.email, subject, html,
                    persona="default",
                    unsubscribe_user_id=user.id,
                    unsubscribe_category="trial_drip",
                )
                if not res.get("skipped", False):
                    sent_tokens.add(token)
                    user.drip_state = ",".join(sorted(sent_tokens))
                    counts[token] += 1
                    any_sent = True
                    if governor is not None:
                        governor.record(user, SendClass.LIFECYCLE)
            except Exception:
                logger.exception(
                    "activation.send_failed user=%s stage=%s", user.id, token,
                )

    if any_sent:
        await session.commit()
    return counts


async def run_activation_nudge_drip(
    session, *, governor: FrequencyGovernor | None = None, now=None,
) -> dict[str, int]:
    """Behaviour-triggered activation nudge for users who did NOTHING.

    The diagnosed leak is day-1 bounce: people sign up, look once, and never
    return. The two milestone drips above (act_wl / act_alert) fire at 24-72h
    and 3-5d, which is far too late to catch that — by then the person has
    forgotten they signed up.

    So this runs HOURLY (from the worker's hourly block, not the daily drip
    block) and fires on the absence of a recorded action:

      "act_scan6h"  ~6h after signup, zero recorded activity of any kind.
                    One short nudge pointing at one concrete first step.

      "act_ask48h"  ~48h after signup, STILL zero recorded activity. One
                    low-friction question inviting a reply.

    Then it stops. There is no third message, and that is enforced in three
    independent places so no single edit can reintroduce one: there are only
    two stages here, each carries a one-shot drip_state token, and the
    governor's MAX_ACTIVATION_SERIES_MESSAGES ceiling counts every activation
    token (including act_wl / act_alert and the day-0 welcome) against a cap
    of four.

    "Zero activity" is `lifecycle.has_recorded_activity`, which fails SAFE:
    any hint of use — a lookup consumed, a watchlist item, an alert rule, a
    saved scan, an activation stamp, or simply having come back to the site
    after signup — counts as active and suppresses the nudge. Telling someone
    who has used the product that they haven't is the worse error, so the
    ambiguous case is always "don't send".

    Windows are bounded on BOTH ends (6-24h, 48-96h) so a worker that was down
    for a week doesn't wake up and email a month of stale signups at once.

    Gated on EmailPref.TRIAL_DRIP, unsubscribe-aware via the governor, and a
    no-op without RESEND_API_KEY (send_email returns skipped:True, so no token
    is stamped and the user is retried on the next tick).
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import exists, select

    from app.models import AlertRule, ScannerPreset, User, WatchlistItem
    from app.services.email_prefs import EmailPref, wants
    from app.services.lifecycle import ActivitySnapshot, has_recorded_activity

    now = now or datetime.now(UTC)
    counts = {"act_scan6h": 0, "act_ask48h": 0}

    # Cheap durable-artefact filters pushed into SQL. The Python-side
    # has_recorded_activity() re-checks these AND the last_seen_at return
    # signal, so this is a pre-filter for volume, not the decision.
    no_artefacts = [
        User.activated_at.is_(None),
        User.lookups_reset_on.is_(None),
        ~exists().where(WatchlistItem.user_id == User.id),
        ~exists().where(AlertRule.user_id == User.id),
        ~exists().where(ScannerPreset.user_id == User.id),
    ]

    stages = [
        (
            "act_scan6h",
            now - timedelta(hours=24), now - timedelta(hours=6),
            render_activation_first_scan_email,
            "Your first Tapeline scan",
        ),
        (
            "act_ask48h",
            now - timedelta(hours=96), now - timedelta(hours=48),
            render_activation_ask_email,
            "What got in the way?",
        ),
    ]

    any_sent = False
    for token, lower, upper, renderer, subject in stages:
        users = (
            await session.execute(
                select(User).where(
                    User.created_at >= lower,
                    User.created_at < upper,
                    *no_artefacts,
                )
            )
        ).scalars().all()

        for user in users:
            if not user.email:
                continue
            sent_tokens = set((user.drip_state or "").split(",")) - {""}
            if token in sent_tokens:
                continue
            if not wants(user, EmailPref.TRIAL_DRIP):
                continue
            # Fail-safe activity re-check, including the last_seen_at return
            # signal that SQL above can't express.
            if has_recorded_activity(user, ActivitySnapshot()):
                continue
            if governor is not None and not governor.allows(
                user, SendClass.LIFECYCLE, token=token,
            ):
                continue
            try:
                html = renderer(
                    user.name or "trader", trial_ends_at=user.trial_ends_at,
                )
                res = await send_email(
                    user.email, subject, html,
                    persona="default",
                    unsubscribe_user_id=user.id,
                    unsubscribe_category="trial_drip",
                )
                if not res.get("skipped", False):
                    sent_tokens.add(token)
                    user.drip_state = ",".join(sorted(sent_tokens))
                    counts[token] += 1
                    any_sent = True
                    if governor is not None:
                        governor.record(user, SendClass.LIFECYCLE)
            except Exception:
                logger.exception(
                    "activation_nudge.send_failed user=%s stage=%s",
                    user.id, token,
                )

    if any_sent:
        await session.commit()
    return counts


async def run_annual_nudge_drip(
    session, *, governor: FrequencyGovernor | None = None,
) -> dict[str, int]:
    """Post-conversion nudge: monthly subscribers ~30 days in → switch to annual.

    Population: paid users (stripe_customer_id set, tier pro/premium) whose
    still-live subscription was created 28-45 days ago AND looks monthly.

    We don't persist the billing interval locally, so we infer it from the
    Subscription row: (current_period_end - created_at) < 180 days is monthly,
    otherwise annual. That inference is reliable *only* for young subscriptions
    — a long-tenured monthly sub's period end eventually advances past the
    180-day mark — which is exactly why the targeting window is bounded to the
    first ~6 weeks. An annual sub inside the window has current_period_end a
    full year out, so it's filtered out and never mis-nudged to "switch to
    annual" when it already is.

    Dedup'd via the "annual_p" drip_state token (one nudge ever, even if the
    user stays monthly). Gated on EmailPref.RE_ENGAGEMENT (the sales-nurture
    suppressable bucket), sent under the "sales" persona with a
    List-Unsubscribe header. No-op when RESEND_API_KEY is unset.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.models import Subscription, User
    from app.services.email_prefs import EmailPref, wants

    now = datetime.now(UTC)
    counts = {"annual_p": 0}

    rows = (
        await session.execute(
            select(User, Subscription)
            .join(Subscription, Subscription.user_id == User.id)
            .where(
                User.stripe_customer_id.is_not(None),
                User.tier.in_(["pro", "premium"]),
                Subscription.status.in_(["active", "trialing"]),
                Subscription.created_at >= now - timedelta(days=45),
                Subscription.created_at < now - timedelta(days=28),
            )
        )
    ).all()

    any_sent = False
    handled: set[str] = set()
    for user, sub in rows:
        if not user.email or user.id in handled:
            continue
        # Infer monthly vs annual from period length (see docstring). SQLite
        # hands datetimes back naive — normalise both sides before subtracting.
        cpe = sub.current_period_end
        created = sub.created_at
        if cpe.tzinfo is None:
            cpe = cpe.replace(tzinfo=UTC)
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if (cpe - created).days >= 180:
            handled.add(user.id)  # annual — already on the best rate, skip
            continue
        sent_tokens = set((user.drip_state or "").split(",")) - {""}
        if "annual_p" in sent_tokens:
            handled.add(user.id)
            continue
        if not wants(user, EmailPref.RE_ENGAGEMENT):
            handled.add(user.id)
            continue
        if governor is not None and not governor.allows(
            user, SendClass.LIFECYCLE, token="annual_p",
        ):
            continue
        try:
            html = render_annual_upgrade_email(user.name or "trader", tier=user.tier)
            res = await send_email(
                user.email,
                f"Switch to annual and save on Tapeline {user.tier.capitalize()}",
                html,
                persona="sales",
                unsubscribe_user_id=user.id,
                unsubscribe_category="re_engagement",
            )
            if not res.get("skipped", False):
                sent_tokens.add("annual_p")
                user.drip_state = ",".join(sorted(sent_tokens))
                counts["annual_p"] += 1
                any_sent = True
                handled.add(user.id)
                if governor is not None:
                    governor.record(user, SendClass.LIFECYCLE)
        except Exception:
            logger.exception("annual_nudge.send_failed user=%s", user.id)

    if any_sent:
        await session.commit()
    return counts


async def run_annual_renewal_reminder_drip(
    session, *, governor: FrequencyGovernor | None = None,
) -> dict[str, int]:
    """Courtesy heads-up ~7 days before an ANNUAL plan auto-renews.

    Population: active annual subscriptions whose current_period_end falls in
    (now+6d, now+8d) and aren't already set to cancel. Uses the real
    `Subscription.billing_period` column (added 0031) — no period-length
    inference needed. Transactional: always sent (no email_prefs gate, no
    List-Unsubscribe), persona "billing".

    Dedup is per renewal CYCLE via a date-stamped token "renA{YYMMDD}" keyed on
    current_period_end — so the reminder fires once each year (a fresh period
    end → a fresh token), not once ever. Superseded renA* tokens are dropped
    on write so drip_state doesn't grow one token per year. No-op when
    RESEND_API_KEY is unset.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.models import Subscription, User
    from app.services.tier import TIER_PRICES

    now = datetime.now(UTC)
    counts = {"renewal_reminder": 0}
    lower, upper = now + timedelta(days=6), now + timedelta(days=8)

    rows = (
        await session.execute(
            select(User, Subscription)
            .join(Subscription, Subscription.user_id == User.id)
            .where(
                Subscription.status == "active",
                Subscription.billing_period == "annual",
                Subscription.cancel_at_period_end.is_(False),
                Subscription.current_period_end >= lower,
                Subscription.current_period_end < upper,
            )
        )
    ).all()

    any_sent = False
    handled: set[str] = set()
    for user, sub in rows:
        if not user.email or user.id in handled:
            continue
        cpe = sub.current_period_end
        if cpe.tzinfo is None:
            cpe = cpe.replace(tzinfo=UTC)
        token = "renA" + cpe.strftime("%y%m%d")
        sent_tokens = set((user.drip_state or "").split(",")) - {""}
        if token in sent_tokens:
            handled.add(user.id)
            continue
        tier = (sub.tier or user.tier or "pro").lower()
        price = TIER_PRICES.get((tier, "annual"))
        amount_label = f"${price:,.2f}" if price else "your annual rate"
        # Portable day-without-leading-zero (Windows strftime lacks %-d).
        renew_date_label = f"{cpe.strftime('%B')} {cpe.day}, {cpe.year}"
        # SCHEDULED: a billing notice about a real, imminent charge. Never
        # suppressed — but recorded, so a nurture email does not land beside it.
        if governor is not None and not governor.allows(user, SendClass.SCHEDULED):
            continue
        try:
            html = render_annual_renewal_reminder_email(
                user.name or "trader",
                tier=tier,
                amount_label=amount_label,
                renew_date_label=renew_date_label,
            )
            res = await send_email(
                user.email,
                f"Your Tapeline {tier.capitalize()} plan renews {renew_date_label}",
                html,
                persona="billing",
            )
            if not res.get("skipped", False):
                # Dedupe is per renewal CYCLE, so only the current
                # period-end token matters — drop superseded renA* tokens
                # instead of appending one per year to drip_state.
                sent_tokens = {
                    t for t in sent_tokens if not t.startswith("renA")
                }
                sent_tokens.add(token)
                user.drip_state = ",".join(sorted(sent_tokens))
                counts["renewal_reminder"] += 1
                any_sent = True
                handled.add(user.id)
                if governor is not None:
                    governor.record(user, SendClass.SCHEDULED)
        except Exception:
            logger.exception("renewal_reminder.send_failed user=%s", user.id)

    if any_sent:
        await session.commit()
    return counts


async def run_founder_touch_drip(
    session, *, governor: FrequencyGovernor | None = None,
) -> dict[str, int]:
    """Personal founder hello to high-value, engaged early users (lever #4).

    Population: signed up 5-7 days ago, still inside an active Premium trial OR
    already paying (stripe_customer_id set), who have actually started using
    the product (≥1 watchlist item) and haven't yet received the note
    (founder_touch_sent_at is null). That intersection is the cohort worth a
    1:1 — engaged and high-intent — not a cold blast to every signup.

    One-shot per user, stamped on User.founder_touch_sent_at (its own column,
    not a drip_state token — front-loaded in migration 0029 so this ships
    migration-free). Gated on EmailPref.RE_ENGAGEMENT (the founder-signed
    nurture bucket, same as re-engagement / win-back / annual-nudge), sent
    under the "sales" persona (christian@) with a List-Unsubscribe header.
    No-op when RESEND_API_KEY is unset (send_email returns skipped:True, so
    founder_touch_sent_at stays null and the next pass retries once the key
    is live).
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import exists, or_, select

    from app.models import User, WatchlistItem
    from app.services.email_prefs import EmailPref, wants

    now = datetime.now(UTC)
    counts = {"founder_touch": 0}

    # Correlated EXISTS keeps the "has any ticker" test a single round-trip.
    has_watchlist = exists().where(WatchlistItem.user_id == User.id)
    users = (
        await session.execute(
            select(User).where(
                User.created_at >= now - timedelta(days=7),
                User.created_at < now - timedelta(days=5),
                User.founder_touch_sent_at.is_(None),
                has_watchlist,
                or_(
                    User.stripe_customer_id.is_not(None),
                    User.trial_ends_at > now,
                ),
            )
        )
    ).scalars().all()

    any_sent = False
    for user in users:
        if not user.email:
            continue
        if not wants(user, EmailPref.RE_ENGAGEMENT):
            continue
        if governor is not None and not governor.allows(
            user, SendClass.LIFECYCLE, token="founder_touch",
        ):
            continue
        try:
            html = render_founder_touch_email(user.name or "there")
            res = await send_email(
                user.email,
                "A quick hello from Tapeline's founder",
                html,
                persona="sales",
                unsubscribe_user_id=user.id,
                unsubscribe_category="re_engagement",
            )
            if not res.get("skipped", False):
                user.founder_touch_sent_at = now
                counts["founder_touch"] += 1
                any_sent = True
                if governor is not None:
                    governor.record(user, SendClass.LIFECYCLE)
        except Exception:
            logger.exception("founder_touch.send_failed user=%s", user.id)

    if any_sent:
        await session.commit()
    return counts


async def run_referral_milestone_drip(
    session, *, governor: FrequencyGovernor | None = None,
) -> dict[str, int]:
    """Celebrate referral momentum at 3 / 5 / 10 / 25 confirmed signups (#5).

    Counts how many accounts list each user as `referred_by` (the referrer's
    own id, set in the signup flow), finds the highest milestone that user has
    crossed which isn't yet stamped in drip_state ("ref_m{n}"), and sends one
    celebratory note. At most one email per user per run — the highest
    newly-crossed tier — and dedup'd per-tier, so someone who later crosses the
    next milestone still gets that one.

    Treated like the per-signup referrer email (it reports reward state the
    user earned by referring): transactional, persona "default", no
    List-Unsubscribe, NOT gated by email_prefs. No-op when RESEND_API_KEY is
    unset (token only stamped on a non-skipped send).
    """
    from sqlalchemy import func, select

    from app.models import User

    counts = {f"ref_m{m}": 0 for m in _REFERRAL_MILESTONES}

    # Confirmed signups per referrer, one grouped query.
    rows = (
        await session.execute(
            select(User.referred_by, func.count())
            .where(User.referred_by.is_not(None))
            .group_by(User.referred_by)
        )
    ).all()
    smallest = min(_REFERRAL_MILESTONES)
    signups_by_referrer = {ref_id: n for ref_id, n in rows if ref_id and n >= smallest}
    if not signups_by_referrer:
        return counts

    referrers = (
        await session.execute(
            select(User).where(User.id.in_(list(signups_by_referrer)))
        )
    ).scalars().all()

    any_sent = False
    for user in referrers:
        if not user.email:
            continue
        n = signups_by_referrer.get(user.id, 0)
        crossed = [m for m in _REFERRAL_MILESTONES if n >= m]
        if not crossed:
            continue
        target = max(crossed)
        token = f"ref_m{target}"
        sent_tokens = set((user.drip_state or "").split(",")) - {""}
        if token in sent_tokens:
            continue
        # SCHEDULED: a real account event the user earned (credits accrued),
        # not something we initiated to move them along.
        if governor is not None and not governor.allows(user, SendClass.SCHEDULED):
            continue
        try:
            html = render_referral_milestone_email(
                user.name or "trader", milestone=target, total_signups=n,
            )
            res = await send_email(
                user.email,
                f"You've referred {n} — your free months are stacking up",
                html,
                persona="default",
            )
            if not res.get("skipped", False):
                sent_tokens.add(token)
                user.drip_state = ",".join(sorted(sent_tokens))
                counts[token] += 1
                any_sent = True
                if governor is not None:
                    governor.record(user, SendClass.SCHEDULED)
        except Exception:
            logger.exception("referral_milestone.send_failed user=%s", user.id)

    if any_sent:
        await session.commit()
    return counts


async def run_checkout_abandonment_recovery(
    session, *, governor: FrequencyGovernor | None = None,
) -> dict[str, int]:
    """Recover started-but-incomplete Stripe checkouts. Returns {"abandon1": n}.

    Population: users whose checkout_started_at sits in the 1-24h window —
    long enough that they're plainly not still mid-card-entry, recent enough
    that the nudge is timely (and not creepy). checkout_started_at is stamped
    when POST /api/billing/checkout mints the Stripe session and CLEARED by the
    checkout.session.completed webhook, so a converted user drops out of this
    query automatically — the timestamp itself is the abandonment signal (no
    tier check needed; a trial user converting early counts too).

    One email, ever, per checkout attempt: dedup'd on the "abandon1" drip_state
    token. A fresh checkout (POST /checkout) strips that token, re-arming the
    nudge for the new attempt.

    Marketing-class conversion nudge → gated on EmailPref.RE_ENGAGEMENT and
    carries the List-Unsubscribe header via unsubscribe_category="re_engagement".
    Only stamps the token on a NON-skipped send, so no RESEND_API_KEY = no-op
    (send_email returns skipped:True and the token stays unset for a later run).

    The 1-24h window is evaluated in Python (not SQL) after a coarse
    is_not(None) filter, normalising SQLite's naive datetimes to UTC — the same
    tz-safety dance run_winback_drip does, and robust across SQLite + Postgres.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.models import User
    from app.services.email_prefs import EmailPref, wants

    now = datetime.now(UTC)
    counts = {"abandon1": 0}

    result = await session.execute(
        select(User).where(User.checkout_started_at.is_not(None))
    )
    users = result.scalars().all()
    if not users:
        return counts

    lower = timedelta(hours=1).total_seconds()
    upper = timedelta(hours=24).total_seconds()

    any_sent = False
    for user in users:
        if not user.email:
            continue
        started = user.checkout_started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        age = (now - started).total_seconds()
        if age < lower or age > upper:
            continue
        sent_tokens = set((user.drip_state or "").split(",")) - {""}
        if "abandon1" in sent_tokens:
            continue
        if not wants(user, EmailPref.RE_ENGAGEMENT):
            continue
        tier = user.checkout_tier or "pro"
        period = user.checkout_billing_period or "monthly"
        # SCHEDULED: the user initiated a payment minutes-to-hours ago. This is
        # the highest-intent message we send and suppressing it would cost a
        # real conversion — recorded, never blocked.
        if governor is not None and not governor.allows(user, SendClass.SCHEDULED):
            continue
        try:
            html = render_checkout_abandoned_email(
                user.name or "trader", tier=tier, billing_period=period,
            )
            res = await send_email(
                user.email,
                f"You're one step from Tapeline {tier.capitalize()}",
                html,
                persona="sales",
                unsubscribe_user_id=user.id,
                unsubscribe_category="re_engagement",
            )
            if not res.get("skipped", False):
                sent_tokens.add("abandon1")
                user.drip_state = ",".join(sorted(sent_tokens))
                counts["abandon1"] += 1
                any_sent = True
                if governor is not None:
                    governor.record(user, SendClass.SCHEDULED)
        except Exception:
            logger.exception("checkout_recovery.send_failed user=%s", user.id)

    if any_sent:
        await session.commit()
    return counts
