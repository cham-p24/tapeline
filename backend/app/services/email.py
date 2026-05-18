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
    shell,
    stat_row,
    ticker_card,
    watchlist_table,
)

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
) -> dict[str, Any]:
    """Send a single email via Resend. Returns the Resend response or raises.

    Pick `persona` based on what category of email this is:

        send_email(..., persona="sales")     # trial drip day 7+, re-engagement
        send_email(..., persona="billing")   # Stripe events
        send_email(..., persona="alerts")    # automated digests
        send_email(..., )                    # everything else (transactional)
    """
    if not settings.resend_api_key:
        logger.warning(
            "email.skipped reason=no_api_key persona=%s to=%s subject=%s",
            persona, to, subject,
        )
        return {"skipped": True}

    sender, reply_to = _persona_addresses(persona)

    payload = {
        "from": f"Tapeline <{sender}>",
        "to": [to],
        "subject": subject,
        "html": html,
        "reply_to": [reply_to],
    }
    if text:
        payload["text"] = text

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
            "When the trial ends, your account drops to Free — top 20 tickers, "
            "24-hour delayed, no alerts. To keep what you have, add a card."
        )
        + _pricing_card(
            "Pro", "$29.99", "$24.99", "$299.99", "$60",
            "Full live scanner, squeeze, regime, watchlist, email alerts, daily briefing.",
            accent=False,
        )
        + _pricing_card(
            "Premium", "$49.99", "$39.99", "$479.99", "$120",
            "Everything in Pro + Congress + Telegram unlimited + insider Form 4 + analyst ratings.",
            accent=True,
        )
        + button("Add a card", "https://tapeline.io/app/billing")
        + footnote("7-day money back, cancel anytime in one click."),
        preheader="Seven days left on your trial — add a card to keep Premium.",
    )


def render_trial_day11_email(user_name: str, summary: dict | None = None) -> str:
    """T-3 — 3 days remaining."""
    return shell(
        h1("3 days left on your trial.")
        + lead(
            f"{user_name}, you're 11 days into the 14-day Premium trial. "
            f"Here's what you've actually been using."
        )
        + _trial_summary_block(summary)
        + muted_paragraph(
            "If you decide to keep Premium, add a card before Friday — at the "
            "standard Premium price ($49.99/mo, or $39.99/mo billed annually). "
            "If you don't, the account drops to Free at expiry."
        )
        + button("Keep Premium", "https://tapeline.io/app/billing")
        + footnote("7-day money back. One-click cancel. No phone calls."),
        preheader="Three days left of Premium — add a card to keep it.",
    )


def render_trial_day13_email(user_name: str, summary: dict | None = None) -> str:
    """T-1 — final urgency. Trial ends tomorrow.

    Uses the urgent button variant (amber) — the only place we do."""
    return shell(
        h1("Trial ends tomorrow.")
        + lead(
            f"{user_name}, your Premium trial expires in less than 24 hours."
        )
        + _trial_summary_block(summary)
        + muted_paragraph(
            "If you don't add a card, your account drops to Free at expiry — "
            "the scanner shows yesterday's data on 20 tickers, no alerts, "
            "no Telegram, no Congress feed."
        )
        + button("Keep my account active", "https://tapeline.io/app/billing", variant="urgent")
        + footnote("7-day money back. One-click cancel. No phone calls."),
        preheader="Your Premium trial expires in less than 24 hours.",
    )


def render_trial_expired_email(user_name: str, summary: dict | None = None) -> str:
    """T+0 — trial ended within the last 24 hours."""
    return shell(
        h1("Your Tapeline trial ended.")
        + lead(
            f"{user_name}, your 14-day Premium trial ended overnight. Your "
            f"account is now on the Free tier — top 20 tickers, 24-hour "
            f"delayed, no Telegram or smart alerts."
        )
        + _trial_summary_block(summary)
        + muted_paragraph(
            'A few things stay open regardless of tier: the '
            f'<a href="https://tapeline.io/scorecard" style="color:{ACCENT};">public scorecard</a> '
            '(every top-10 call back-checked vs SPY), the '
            f'<a href="https://tapeline.io/how-it-works" style="color:{ACCENT};">scoring formula</a>, '
            'and your watchlist (capped at 5 tickers on Free). One click '
            're-activates Premium at the same price — your watchlist + '
            'alerts come back intact.'
        )
        + button("Re-activate Premium", "https://tapeline.io/app/billing")
        + footnote("No more reminders unless you re-activate. One more note in 3 days then I'll stop emailing."),
        preheader="Trial ended — re-activate to bring your watchlist + alerts back.",
    )


def render_trial_post_expiry_email(user_name: str, _summary: dict | None = None) -> str:
    """T+3 — 3 days after trial expiry. Final touch.

    No discount theatre. One direct ask + the reactivation link + a polite
    goodbye. Honest framing is the differentiator — most SaaS would offer
    50% off and an extended trial, both of which read as desperate.
    """
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
            "the last email; no more drip after this."
        )
        + button("Re-activate Premium", "https://tapeline.io/app/billing")
        + footnote(
            '— Christian, founder. '
            f'<a href="https://tapeline.io/scorecard" style="color:{LIGHT_SUBTLE};text-decoration:underline;">Public scorecard stays free forever.</a>'
        ),
        preheader="Last note — what was missing? Reply and tell me.",
    )


def render_trial_ended_email(user_name: str) -> str:
    """Sent on actual downgrade — soft re-engagement (separate code path
    from the drip series; preserved for the legacy webhook hook)."""
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


# ── Payment-failed ──────────────────────────────────────────────────────────

def _ordinal(n: int) -> str:
    """1 -> 1st, 2 -> 2nd, 3 -> 3rd, 4 -> 4th, etc."""
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def render_payment_failed_email(
    user_name: str, tier: str, attempt_count: int = 1,
) -> str:
    """Stripe `invoice.payment_failed`. Tone is calm + practical, not
    alarmist. First-attempt failures are usually transient (bank fraud
    flag, expired card)."""
    tier_label = tier.capitalize()
    urgency_line = (
        "Stripe will retry automatically over the next few days."
        if attempt_count == 1
        else f"This is the {_ordinal(attempt_count)} attempt — if it fails again, your account drops to Free."
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


async def run_eod_watchlist_digest(session) -> int:
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

        try:
            html = render_eod_watchlist_digest(user.name or "trader", items)
            res = await send_email(
                user.email, f"Tapeline EOD · {_today_short()}", html,
                persona="alerts",
            )
            if not res.get("skipped", False):
                sent += 1
        except Exception:
            logger.exception("eod_digest.send_failed user=%s", user.id)

    logger.info("eod_digest.sent count=%d", sent)
    return sent


async def run_daily_drip(session) -> dict[str, int]:
    """Send the full trial-drip series. Returns per-stage counts.

    Stages, all dedup'd via `User.drip_state` (comma-separated tokens):

      Pre-expiry (trial_ends_at in the FUTURE — user is still on trial):
        - "3"   day-3  email   — trial_ends_at in (now+10d, now+11d)
        - "7"   day-7  email   — trial_ends_at in (now+6d,  now+7d )
        - "11"  T-3    email   — trial_ends_at in (now+2d,  now+3d )
        - "13"  T-1    email   — trial_ends_at in (now+0d,  now+1d )

      Post-expiry (trial_ends_at in the PAST — user didn't convert):
        - "expired" T+0  email — trial_ends_at in (now-1d, now)
        - "post3"   T+3  email — trial_ends_at in (now-4d, now-3d)

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
    counts = {"day3": 0, "day7": 0, "day11": 0, "day13": 0, "expired": 0, "post3": 0}

    windows = [
        # Pre-expiry
        ("3",   "day3",   now + timedelta(days=10), now + timedelta(days=11),
         render_trial_day3_email,         "Tapeline — three days in",
         False, False),
        ("7",   "day7",   now + timedelta(days=6),  now + timedelta(days=7),
         render_trial_day7_email,         "Tapeline — halfway through your trial",
         True, False),
        ("11",  "day11",  now + timedelta(days=2),  now + timedelta(days=3),
         render_trial_day11_email,        "Tapeline — 3 days left on your trial",
         True, False),
        ("13",  "day13",  now,                      now + timedelta(days=1),
         render_trial_day13_email,        "Tapeline — your trial ends tomorrow",
         True, False),
        # Post-expiry
        ("expired", "expired", now - timedelta(days=1), now,
         render_trial_expired_email,      "Your Tapeline trial ended",
         True, True),
        ("post3",   "post3",   now - timedelta(days=4), now - timedelta(days=3),
         render_trial_post_expiry_email,  "Last note from Tapeline",
         False, True),
    ]

    any_sent = False
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
            try:
                if personalise:
                    summary = await trial_summary_for_user(session, user)
                    html = renderer(user.name or "trader", summary)
                else:
                    html = renderer(user.name or "trader")
                # Day 3 is soft activation — keep under the default
                # transactional sender. Day 7 onwards is the conversion push.
                drip_persona: EmailPersona = "default" if token == "3" else "sales"
                res = await send_email(user.email, subject, html, persona=drip_persona)
                if not res.get("skipped", False):
                    sent_tokens.add(token)
                    user.drip_state = ",".join(sorted(sent_tokens))
                    counts[label] += 1
                    any_sent = True
            except Exception:
                logger.exception("drip.send_failed user=%s stage=%s", user.id, label)

    if any_sent:
        await session.commit()
    return counts


async def run_re_engagement_drip(session) -> dict[str, int]:
    """Send the re-engagement email to users dormant for ~14 days.

    Window: last_seen_at in [now-15d, now-14d). One-shot, deduplicated via
    the "re14" token in User.drip_state — so a user only ever receives
    this email once even if they fall back into dormancy later.

    Trial users are EXCLUDED — the trial drip is the right re-engagement
    channel for them.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import or_, select

    from app.models import User

    now = datetime.now(UTC)
    counts = {"re14": 0}

    lower = now - timedelta(days=15)
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
        try:
            html = render_re_engagement_email(user.name or "trader")
            res = await send_email(
                user.email, "Tapeline missed you", html,
                persona="sales",
            )
            if not res.get("skipped", False):
                sent_tokens.add("re14")
                user.drip_state = ",".join(sorted(sent_tokens))
                counts["re14"] += 1
                any_sent = True
        except Exception:
            logger.exception("re_engagement.send_failed user=%s", user.id)

    if any_sent:
        await session.commit()
    return counts
