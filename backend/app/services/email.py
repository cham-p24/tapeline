"""Email delivery via Resend."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

RESEND_API = "https://api.resend.com"


async def send_email(to: str, subject: str, html: str, text: str | None = None) -> dict[str, Any]:
    """Send a single email. Returns the Resend response or raises."""
    if not settings.resend_api_key:
        logger.warning("email.skipped reason=no_api_key to=%s subject=%s", to, subject)
        return {"skipped": True}

    payload = {
        "from": f"Tapeline <{settings.email_from}>",
        "to": [to],
        "subject": subject,
        "html": html,
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


def render_alert_email(user_name: str, rule_name: str, symbol: str, score: float, message: str) -> str:
    """Render an alert email. Minimal branded HTML."""
    return f"""<!doctype html>
<html><body style="font-family:Inter,system-ui,sans-serif;background:#0a0a0a;color:#f4f4f5;padding:24px;">
  <div style="max-width:560px;margin:0 auto;background:#121214;border-radius:12px;padding:32px;border:1px solid #1f1f23;">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:24px;">
      <div style="width:24px;height:8px;border-radius:999px;background:#3b82f6;"></div>
      <strong style="font-size:18px;">Tapeline</strong>
    </div>
    <h1 style="margin:0 0 8px;font-size:22px;">Alert: {rule_name}</h1>
    <p style="color:#9ca3af;margin:0 0 24px;">Hi {user_name}, one of your rules just triggered.</p>

    <div style="background:#0a0a0a;border-radius:8px;padding:20px;border:1px solid #1f1f23;">
      <div style="font-size:32px;font-weight:700;font-family:'JetBrains Mono',monospace;">{symbol}</div>
      <div style="margin-top:4px;color:#10b981;font-weight:500;">Score: {score:.1f}</div>
      <div style="margin-top:12px;color:#f4f4f5;">{message}</div>
    </div>

    <a href="https://tapeline.io/app/scanner" style="display:inline-block;margin-top:24px;background:#3b82f6;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none;font-weight:500;">Open dashboard &rarr;</a>

    <hr style="border:0;border-top:1px solid #1f1f23;margin:32px 0 16px;">
    <p style="color:#9ca3af;font-size:12px;margin:0;">
      <strong>Not investment advice.</strong> For informational purposes only. You're receiving this because you set up an alert at tapeline.io.
      <br><br>
      <a href="https://tapeline.io/app/alerts" style="color:#9ca3af;">Manage alerts</a>
    </p>
  </div>
</body></html>"""


def _shell(body_html: str) -> str:
    """Wrap body content in the standard Tapeline email shell."""
    return f"""<!doctype html>
<html><body style="font-family:Inter,system-ui,sans-serif;background:#0a0a0a;color:#f4f4f5;padding:24px;margin:0;">
  <div style="max-width:560px;margin:0 auto;background:#121214;border-radius:12px;padding:32px;border:1px solid #1f1f23;">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:24px;">
      <div style="width:24px;height:8px;border-radius:999px;background:#3b82f6;"></div>
      <strong style="font-size:18px;">Tapeline</strong>
    </div>
    {body_html}
    <hr style="border:0;border-top:1px solid #1f1f23;margin:32px 0 16px;">
    <p style="color:#6b7280;font-size:11px;margin:0;">
      <strong>Not investment advice.</strong> For informational purposes only.
      <br><br>
      <a href="https://tapeline.io/app/account" style="color:#9ca3af;">Manage notifications</a>
      &nbsp;·&nbsp;
      <a href="https://tapeline.io/app/billing" style="color:#9ca3af;">Billing</a>
    </p>
  </div>
</body></html>"""


def _render_pick_card(symbol: str, score: float | None, signal: str | None, reason: str | None) -> str:
    """Single ticker row used inside the welcome email's "live picks" block."""
    score_str = f"{score:.0f}" if score is not None else "—"
    signal_str = signal or "—"
    # Score-tier colour matches /how-it-works.
    if score is None:
        col = "#a1a1aa"
    elif score >= 70:
        col = "#22c55e"
    elif score >= 55:
        col = "#14b8a6"
    elif score >= 40:
        col = "#a1a1aa"
    elif score >= 25:
        col = "#fbbf24"
    else:
        col = "#ef4444"
    why = (reason or "")[:120]
    return f"""
    <a href="https://tapeline.io/t/{symbol}"
       style="display:block;text-decoration:none;background:#0a0a0a;border:1px solid #1f1f23;border-radius:8px;padding:14px 16px;margin-bottom:8px;">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;">
        <div>
          <div style="font-family:'JetBrains Mono',ui-monospace,monospace;font-size:18px;font-weight:700;color:#f4f4f5;">{symbol}</div>
          <div style="margin-top:4px;color:#9ca3af;font-size:12px;">{why}</div>
        </div>
        <div style="text-align:right;flex-shrink:0;">
          <div style="font-size:26px;font-weight:700;color:{col};font-family:'JetBrains Mono',ui-monospace,monospace;line-height:1;">{score_str}</div>
          <div style="margin-top:4px;font-size:10px;text-transform:uppercase;letter-spacing:0.1em;color:{col};">{signal_str}</div>
        </div>
      </div>
    </a>
    """


def render_welcome_email(user_name: str, picks: list[dict[str, Any]] | None = None) -> str:
    """Day 0 — sent immediately on signup.

    `picks` is an optional list of {symbol, score, signal, reason} dicts the
    auth handler fetches from the live DB before calling this renderer.
    Embedding 3 actual scores here lets the user see the product in their
    inbox, not just a "click here to see scores" CTA. Falls back to the
    static three-things checklist if picks is empty (worker hasn't ticked
    yet, etc.).
    """
    if picks:
        picks_html = "".join(
            _render_pick_card(p.get("symbol", "?"), p.get("score"), p.get("signal"), p.get("reason"))
            for p in picks[:3]
        )
        body = f"""
        <h1 style="margin:0 0 12px;font-size:26px;">Welcome, {user_name}.</h1>
        <p style="color:#d1d5db;margin:0 0 24px;">Your <strong>14-day Premium trial</strong> is live. Three live scores from the scanner right now:</p>
        {picks_html}
        <a href="https://tapeline.io/app/scanner?utm_source=email&amp;utm_campaign=welcome&amp;utm_medium=transactional" style="display:inline-block;margin-top:8px;background:#3b82f6;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:500;">Open the full scanner &rarr;</a>
        <p style="color:#9ca3af;margin-top:24px;font-size:13px;">Tap any card above to see the 6-factor breakdown for that ticker. The
        formula is public — see <a href="https://tapeline.io/how-it-works" style="color:#3b82f6;">how it works</a>.</p>
        <p style="color:#6b7280;margin-top:18px;font-size:13px;">No card on file. We'll remind you before the trial ends.</p>
        """
    else:
        body = f"""
        <h1 style="margin:0 0 12px;font-size:26px;">Welcome, {user_name}.</h1>
        <p style="color:#d1d5db;margin:0 0 16px;">Your <strong>14-day Premium trial</strong> is live. Everything's unlocked.</p>
        <p style="color:#9ca3af;margin:0 0 20px;">Three things to try in the first five minutes:</p>
        <ol style="color:#d1d5db;line-height:1.7;padding-left:20px;margin:0 0 24px;">
          <li><strong>Scanner</strong> — see every ticker scored, hover any score for the 6-factor breakdown</li>
          <li><strong>Public scorecard</strong> — every call we've ever made, with the original reasoning</li>
          <li><strong>Watchlist</strong> — add 5-10 tickers you're following, get smart alerts when scores shift</li>
        </ol>
        <a href="https://tapeline.io/app/scanner?utm_source=email&amp;utm_campaign=welcome&amp;utm_medium=transactional" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:500;">Open the scanner &rarr;</a>
        <p style="color:#6b7280;margin-top:24px;font-size:13px;">No card on file. We'll remind you before the trial ends.</p>
        """
    return _shell(body)


def render_trial_day3_email(user_name: str, _summary: dict | None = None) -> str:
    """Day 3 — feature tour, what they may have missed.

    Signature matches day-7/day-13 so the drip dispatcher can call every
    renderer with the same shape regardless of whether it personalises.
    `_summary` is ignored on day 3 — it's too early for meaningful trial
    data and the feature-tour copy doesn't need it.
    """
    return _shell(f"""
    <h1 style="margin:0 0 12px;font-size:24px;">{user_name}, three days in.</h1>
    <p style="color:#d1d5db;margin:0 0 16px;">If you've only been on the scanner, here's what else is in your trial:</p>
    <div style="background:#0a0a0a;border:1px solid #1f1f23;border-radius:8px;padding:18px;margin:16px 0;">
      <div style="margin-bottom:14px;">
        <strong style="color:#3b82f6;">🔥 Squeeze Watch</strong>
        <p style="color:#9ca3af;margin:4px 0 0;font-size:14px;">Bollinger Band compressions flagged before they break. Eight setups updated live.</p>
      </div>
      <div style="margin-bottom:14px;">
        <strong style="color:#3b82f6;">🏛️ Congress Trades</strong>
        <p style="color:#9ca3af;margin:4px 0 0;font-size:14px;">Politicians' disclosed buys and sells. House and Senate, by ticker.</p>
      </div>
      <div style="margin-bottom:14px;">
        <strong style="color:#3b82f6;">💼 Elite Holdings</strong>
        <p style="color:#9ca3af;margin:4px 0 0;font-size:14px;">Latest 13F positions from Buffett, Burry, Tepper, Ackman, and four more.</p>
      </div>
      <div>
        <strong style="color:#3b82f6;">📲 Telegram alerts</strong>
        <p style="color:#9ca3af;margin:4px 0 0;font-size:14px;">Hourly digest of your watchlist + market regime, delivered to your phone.</p>
      </div>
    </div>
    <a href="https://tapeline.io/app/holdings" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:500;">Try a Premium feature &rarr;</a>
    """)


def _render_trial_summary_block(summary: dict | None) -> str:
    """Render a per-user trial-period highlights block for the day-7/13 emails.

    Pulls together:
      - the user's watchlist density (how many high-signal names they're
        currently watching, and the best score-delta mover)
      - the public-scorecard cadence during their trial window (how many
        top-10 picks logged, hit rate vs SPY, best alpha pick)

    Falls back to an empty string when there's no usable signal — so the
    email is never worse than the prior generic-urgency version.
    """
    if not summary:
        return ""
    lines: list[str] = []
    wl_count = summary.get("watchlist_count") or 0
    wl_strong = summary.get("watchlist_top_signals") or 0
    if wl_count > 0:
        lines.append(
            f"<li><strong>Watchlist:</strong> {wl_count} ticker"
            f"{'' if wl_count == 1 else 's'} on watch, "
            f"<span style=\"color:#10b981;\">{wl_strong}</span> currently "
            f"HIGH CONVICTION or STRONG SETUP.</li>"
        )
        best = summary.get("watchlist_best")
        if best and best.get("delta") is not None and abs(best["delta"]) >= 1:
            delta = best["delta"]
            sign = "+" if delta > 0 else ""
            colour = "#10b981" if delta > 0 else "#ef4444"
            lines.append(
                f"<li><strong>Biggest mover</strong> on your watchlist: "
                f"<code style=\"font-family:'JetBrains Mono',monospace;\">"
                f"{best['symbol']}</code> · score now "
                f"<strong>{best.get('score', 0):.0f}</strong> "
                f"(<span style=\"color:{colour};\">{sign}{delta:.1f}</span> "
                f"since you added it).</li>"
            )
    picks = summary.get("scorecard_picks_during_trial") or 0
    if picks > 0:
        hit = summary.get("scorecard_hit_rate")
        alpha = summary.get("scorecard_alpha_avg")
        bits = [f"{picks} top-10 pick{'' if picks == 1 else 's'} logged"]
        if hit is not None:
            bits.append(f"{hit:.0f}% beat SPY next session")
        if alpha is not None:
            sign = "+" if alpha >= 0 else ""
            bits.append(f"avg alpha {sign}{alpha:.2f}%")
        lines.append(
            "<li><strong>Public scorecard during your trial:</strong> "
            + " · ".join(bits)
            + " (full record at <a href=\"https://tapeline.io/scorecard\" "
            "style=\"color:#3b82f6;\">/scorecard</a>).</li>"
        )
        best_pick = summary.get("scorecard_best")
        if best_pick and best_pick.get("alpha") is not None:
            alpha_v = best_pick["alpha"]
            sign = "+" if alpha_v >= 0 else ""
            lines.append(
                "<li><strong>Best pick this trial:</strong> "
                f"<code style=\"font-family:'JetBrains Mono',monospace;\">"
                f"{best_pick['symbol']}</code> · alpha vs SPY "
                f"<span style=\"color:#10b981;\">{sign}{alpha_v:.2f}%</span>.</li>"
            )
    if not lines:
        return ""
    return (
        "<div style=\"background:#0a0a0a;border:1px solid #1f1f23;"
        "border-radius:8px;padding:18px 22px;margin:16px 0;\">"
        "<div style=\"color:#9ca3af;font-size:11px;text-transform:uppercase;"
        "letter-spacing:0.1em;margin-bottom:10px;\">Your trial so far</div>"
        "<ul style=\"color:#d1d5db;line-height:1.7;padding-left:18px;"
        "margin:0;font-size:14px;\">"
        + "".join(lines)
        + "</ul></div>"
    )


def render_trial_day7_email(user_name: str, summary: dict | None = None) -> str:
    """Day 7 — halfway. Reminder + nudge to add a card.

    `summary` is the optional per-user trial-period highlight dict from
    `trial_summary_for_user`. When present, the email leads with concrete
    user-specific evidence ("X watchlist names HIGH CONVICTION, Y scorecard
    picks beat SPY") before the pricing block. Falls back gracefully.
    """
    summary_block = _render_trial_summary_block(summary)
    return _shell(f"""
    <h1 style="margin:0 0 12px;font-size:24px;">Halfway through your trial, {user_name}.</h1>
    <p style="color:#d1d5db;margin:0 0 16px;">Seven days left of full Premium access.</p>
    {summary_block}
    <p style="color:#9ca3af;margin:0 0 20px;">When the trial ends, your account drops to Free — top 20 tickers, 24-hour delayed, no alerts. To keep what you have, add a card.</p>
    <div style="background:#0a0a0a;border:1px solid #1f1f23;border-radius:8px;padding:20px;margin:16px 0;">
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;">
        <strong style="font-size:18px;">Pro</strong>
        <span style="font-size:22px;font-weight:700;">$29.99<span style="font-size:14px;color:#9ca3af;">/mo</span></span>
      </div>
      <p style="color:#22c55e;margin:0 0 8px;font-size:13px;">or <strong>$24.99/mo billed annually</strong> — save $60/yr</p>
      <p style="color:#9ca3af;margin:0;font-size:13px;">Full live scanner, squeeze, regime, watchlist, email alerts, daily briefing.</p>
    </div>
    <div style="background:#121214;border:1px solid #3b82f6;border-radius:8px;padding:20px;margin:16px 0;">
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;">
        <strong style="font-size:18px;color:#3b82f6;">Premium</strong>
        <span style="font-size:22px;font-weight:700;">$49.99<span style="font-size:14px;color:#9ca3af;">/mo</span></span>
      </div>
      <p style="color:#22c55e;margin:0 0 8px;font-size:13px;">or <strong>$39.99/mo billed annually</strong> — save $120/yr</p>
      <p style="color:#9ca3af;margin:0;font-size:13px;">Everything in Pro + Congress + Telegram unlimited + API + elite 13F holdings.</p>
    </div>
    <a href="https://tapeline.io/app/billing" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:500;margin-top:8px;">Add a card &rarr;</a>
    <p style="color:#6b7280;margin-top:18px;font-size:13px;">7-day money back, cancel anytime in one click.</p>
    """)


def render_trial_day13_email(user_name: str, summary: dict | None = None) -> str:
    """Day 13 — final urgency. Trial ends tomorrow.

    `summary` is the optional per-user trial-period highlight dict. When
    present, the email reframes generic loss ("no alerts, no Telegram") as
    specific loss anchored on the user's actual trial-period evidence — the
    upgrade trigger the article called out as 10x more effective than
    feature-checklist urgency.
    """
    summary_block = _render_trial_summary_block(summary)
    return _shell(f"""
    <h1 style="margin:0 0 12px;font-size:24px;color:#f59e0b;">Trial ends tomorrow.</h1>
    <p style="color:#d1d5db;margin:0 0 16px;">{user_name}, your Premium trial expires in less than 24 hours.</p>
    {summary_block}
    <p style="color:#9ca3af;margin:0 0 20px;">If you don't add a card, your account drops to Free at expiry — the scanner shows yesterday's data on 20 tickers, no alerts, no Telegram, no Congress feed.</p>
    <a href="https://tapeline.io/app/billing" style="display:inline-block;background:#f59e0b;color:#0a0a0a;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:600;margin-top:8px;">Keep my account active &rarr;</a>
    <p style="color:#6b7280;margin-top:24px;font-size:13px;">7-day money back. One-click cancel. No phone calls.</p>
    """)


def render_trial_day11_email(user_name: str, summary: dict | None = None) -> str:
    """T-3 — 3 days remaining on the 14-day trial.

    Sits between day 7 (halfway) and day 13 (last day). Lead with specific
    trial-period evidence from `summary` (when available), then a concrete
    list of what stays vs what drops at expiry — same anchoring as day 13
    but without the urgency colour.
    """
    summary_block = _render_trial_summary_block(summary)
    return _shell(f"""
    <h1 style="margin:0 0 12px;font-size:24px;color:#f4f4f5;">3 days left on your trial.</h1>
    <p style="color:#d1d5db;margin:0 0 16px;">{user_name}, you're 11 days into the 14-day Premium trial. Here's what you've actually been using:</p>
    {summary_block}
    <p style="color:#9ca3af;margin:0 0 20px;">If you decide to keep Premium, add a card before Friday — same price you signed up at ($39.99/mo or $39.99/mo billed annually saves $120/yr). If you don't, the account drops to Free at expiry (top 20 tickers, 24-hour delayed, no Telegram).</p>
    <a href="https://tapeline.io/app/billing" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:500;margin-top:8px;">Keep Premium &rarr;</a>
    <p style="color:#6b7280;margin-top:24px;font-size:13px;">7-day money back. One-click cancel. No phone calls.</p>
    """)


def render_trial_expired_email(user_name: str, summary: dict | None = None) -> str:
    """T+0 — trial ended within the last 24 hours.

    Honest framing: account is now on Free. Reactivation is one click, the
    public scorecard stays open even at Free tier, and the trial benefits
    never reset so this is the only "your previous setup is intact" moment.
    """
    summary_block = _render_trial_summary_block(summary)
    return _shell(f"""
    <h1 style="margin:0 0 12px;font-size:24px;color:#f4f4f5;">Your Tapeline trial ended.</h1>
    <p style="color:#d1d5db;margin:0 0 16px;">{user_name}, your 14-day Premium trial ended overnight. Your account is now on the Free tier — top 20 tickers, 24-hour delayed, no Telegram or smart alerts.</p>
    {summary_block}
    <p style="color:#9ca3af;margin:0 0 20px;">A few things stay open regardless of tier: the <a href="https://tapeline.io/scorecard" style="color:#3b82f6;">public scorecard</a> (every top-10 call back-checked vs SPY), the <a href="https://tapeline.io/how-it-works" style="color:#3b82f6;">scoring formula</a>, and your watchlist (capped at 5 tickers on Free). If you want everything back, one click re-activates Premium at the same price — your watchlist + alerts come back intact.</p>
    <a href="https://tapeline.io/app/billing" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:500;margin-top:8px;">Re-activate Premium &rarr;</a>
    <p style="color:#6b7280;margin-top:24px;font-size:13px;">No more reminders unless you re-activate. One more note in 3 days then I'll stop emailing.</p>
    """)


def render_trial_post_expiry_email(user_name: str, _summary: dict | None = None) -> str:
    """T+3 — 3 days after trial expiry. Final touch.

    No discount theatre, no fake urgency, no "wait we'll give you more time"
    games. One direct question + the reactivation link + a polite goodbye.
    The honesty is the differentiator here; most SaaS would offer 50% off
    and a 6-month-extended trial, both of which read as desperate.
    """
    return _shell(f"""
    <h1 style="margin:0 0 12px;font-size:24px;color:#f4f4f5;">Last note from Tapeline.</h1>
    <p style="color:#d1d5db;margin:0 0 16px;">Hi {user_name} — it's been three days since your trial ended and you haven't reactivated. That's fine; not every tool fits every workflow.</p>
    <p style="color:#d1d5db;margin:0 0 16px;">One ask, if you've got 30 seconds: <strong style="color:#f4f4f5;">what was missing?</strong> Reply to this email with whatever made you not keep it — a specific feature, the pricing, a bug, a confusing page. First-hand input from someone who actually tried Tapeline is more useful than any analytics dashboard. The address (chamara@tapeline.io) goes straight to me, not a support queue.</p>
    <p style="color:#9ca3af;margin:0 0 20px;">If you change your mind, the trial benefits don't reset — re-activate any time and your watchlist + alerts come back. Otherwise, this is the last email; no more drip after this.</p>
    <a href="https://tapeline.io/app/billing" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:500;margin-top:8px;">Re-activate Premium &rarr;</a>
    <p style="color:#6b7280;margin-top:24px;font-size:13px;">— Chamara, founder. <a href="https://tapeline.io/scorecard" style="color:#6b7280;">Public scorecard stays free forever.</a></p>
    """)


async def trial_summary_for_user(session, user) -> dict | None:
    """Pull per-user trial-period highlights for the day-7/day-13 emails.

    Two data streams blended:
      1. **Watchlist density** — how many tickers the user is watching, how
         many of those currently sit in HIGH CONVICTION / STRONG SETUP, and
         the watchlist ticker with the largest absolute score delta since
         baseline. This is the personal signal.
      2. **Public scorecard during trial** — how many top-10 picks Tapeline
         logged between trial_start and now, the next-session hit rate vs
         SPY, the average alpha, and the single highest-alpha pick. Same for
         every user in the same trial cohort, but grounds the email in real
         numbers instead of "trust us."

    Returns None if both streams are empty (no watchlist and no scorecard
    activity during the trial) — the renderer treats None as "no summary
    block" and falls back to the prior generic-urgency text. Never raises:
    errors are swallowed because a failed personalisation must not block the
    drip.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.models import DailyScorecardEntry, Ticker, WatchlistItem

    try:
        # Trial window: from trial_ends_at - 14d (signup) to now.
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
            if scored
            else None
        )
        avg_alpha = (
            sum(p.alpha_vs_spy or 0 for p in scored) / len(scored)
            if scored
            else None
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


def render_eod_watchlist_digest(user_name: str, items: list[dict]) -> str:
    """End-of-day watchlist summary. Rendered into the standard email shell.

    Items shape: each dict has {symbol, score, signal, change_pct_1d, baseline_score?, score_delta?, reason}.
    """
    if not items:
        body = f"""
        <h1 style="margin:0 0 12px;font-size:24px;">End of day · {_today_short()}</h1>
        <p style="color:#9ca3af;margin:0 0 20px;">Your watchlist is empty. Add tickers to see them here tomorrow.</p>
        <a href="https://tapeline.io/app/watchlist" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:500;">Open watchlist &rarr;</a>
        """
        return _shell(body)

    rows_html = []
    for it in items:
        sym = it.get("symbol", "")
        score = it.get("score") or 0
        sig = it.get("signal") or ""
        change = it.get("change_pct_1d") or 0
        delta = it.get("score_delta")
        sig_color = (
            "#10b981" if sig in ("HIGH CONVICTION", "STRONG SETUP")
            else "#3b82f6" if sig == "CONSTRUCTIVE"
            else "#f59e0b" if sig == "CAUTION"
            else "#ef4444" if sig == "WEAK"
            else "#9ca3af"
        )
        change_color = "#10b981" if change > 0 else "#ef4444" if change < 0 else "#9ca3af"
        change_str = f"{'+' if change >= 0 else ''}{change:.2f}%"
        delta_str = ""
        if delta is not None and abs(delta) >= 1:
            delta_color = "#10b981" if delta > 0 else "#ef4444"
            delta_sign = "+" if delta > 0 else ""
            delta_str = f"<span style=\"color:{delta_color};font-size:11px;margin-left:6px;\">Δ {delta_sign}{delta:.1f}</span>"
        reason = (it.get("reason") or "").replace("<", "&lt;").replace(">", "&gt;")
        rows_html.append(f"""
        <tr style="border-bottom:1px solid #1f1f23;">
          <td style="padding:10px 6px;font-family:'JetBrains Mono',monospace;font-weight:600;">
            <a href="https://tapeline.io/app/ticker/{sym}" style="color:#f4f4f5;text-decoration:none;">{sym}</a>
          </td>
          <td style="padding:10px 6px;text-align:right;font-weight:600;">{score:.1f}{delta_str}</td>
          <td style="padding:10px 6px;text-align:left;color:{sig_color};font-size:12px;font-weight:500;">{sig}</td>
          <td style="padding:10px 6px;text-align:right;color:{change_color};font-weight:500;">{change_str}</td>
        </tr>
        <tr style="border-bottom:1px solid #1f1f23;">
          <td colspan="4" style="padding:0 6px 10px;color:#9ca3af;font-size:12px;font-style:italic;">{reason}</td>
        </tr>
        """)

    body = f"""
    <h1 style="margin:0 0 12px;font-size:24px;">End of day · {_today_short()}</h1>
    <p style="color:#9ca3af;margin:0 0 16px;">Hi {user_name}, here's where your {len(items)} watchlist ticker{'' if len(items) == 1 else 's'} closed today.</p>
    <table style="width:100%;border-collapse:collapse;background:#0a0a0a;border:1px solid #1f1f23;border-radius:8px;margin:16px 0;">
      <thead>
        <tr style="border-bottom:1px solid #1f1f23;">
          <th style="padding:10px 6px;text-align:left;color:#9ca3af;font-size:11px;text-transform:uppercase;">Ticker</th>
          <th style="padding:10px 6px;text-align:right;color:#9ca3af;font-size:11px;text-transform:uppercase;">Score</th>
          <th style="padding:10px 6px;text-align:left;color:#9ca3af;font-size:11px;text-transform:uppercase;">Signal</th>
          <th style="padding:10px 6px;text-align:right;color:#9ca3af;font-size:11px;text-transform:uppercase;">1D</th>
        </tr>
      </thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
    <a href="https://tapeline.io/app/watchlist" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:500;margin-top:8px;">Open watchlist &rarr;</a>
    """
    return _shell(body)


def _today_short() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).strftime("%a %b %d")


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
            delta = (t.score - w.baseline_score) if (t.score is not None and w.baseline_score is not None) else None
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
            res = await send_email(user.email, f"Tapeline EOD · {_today_short()}", html)
            if not res.get("skipped", False):
                sent += 1
        except Exception:
            logger.exception("eod_digest.send_failed user=%s", user.id)

    logger.info("eod_digest.sent count=%d", sent)
    return sent


def render_trial_ended_email(user_name: str) -> str:
    """Sent on actual downgrade — soft re-engagement."""
    return _shell(f"""
    <h1 style="margin:0 0 12px;font-size:24px;">Your trial just ended, {user_name}.</h1>
    <p style="color:#d1d5db;margin:0 0 16px;">Your account is now on the Free plan. Your watchlist and settings are intact — only the data feed changes.</p>
    <p style="color:#9ca3af;margin:0 0 20px;">If you want live data + alerts back, the door is always open:</p>
    <a href="https://tapeline.io/app/billing" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:500;">See plans &rarr;</a>
    <p style="color:#6b7280;margin-top:24px;font-size:13px;">No hard feelings if not. The public scorecard stays free for everyone, forever.</p>
    """)


def render_referral_referee_email(user_name: str, referrer_name: str | None) -> str:
    """Sent to a new user who signed up via a referral link."""
    referrer_str = referrer_name or "your friend"
    return _shell(f"""
    <h1 style="margin:0 0 12px;font-size:24px;">Welcome, {user_name}.</h1>
    <p style="color:#d1d5db;margin:0 0 16px;">You signed up via {referrer_str}'s referral link — that earned you <strong style="color:#10b981;">1 free month of Premium</strong> on top of your 14-day trial.</p>
    <div style="background:#0a0a0a;border:1px solid #1f1f23;border-radius:8px;padding:16px 20px;margin:18px 0;">
      <div style="color:#9ca3af;font-size:11px;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">Credit on your account</div>
      <div style="font-size:24px;font-weight:700;color:#10b981;font-family:'JetBrains Mono',ui-monospace,monospace;">1 month Premium</div>
      <div style="color:#9ca3af;font-size:13px;margin-top:6px;">Applied automatically at your next checkout.</div>
    </div>
    <p style="color:#9ca3af;margin:0 0 20px;">Trial today, free month after — your first paid month is on us.</p>
    <a href="https://tapeline.io/app/scanner" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:500;">Open the scanner &rarr;</a>
    """)


def render_referral_referrer_email(user_name: str, referee_email_masked: str) -> str:
    """Sent to an existing user when someone joins via their referral link."""
    return _shell(f"""
    <h1 style="margin:0 0 12px;font-size:24px;">Nice, {user_name} — someone joined.</h1>
    <p style="color:#d1d5db;margin:0 0 16px;"><code style="font-family:'JetBrains Mono',monospace;color:#f4f4f5;">{referee_email_masked}</code> just signed up with your referral link. That earned you <strong style="color:#10b981;">1 free month of Premium</strong>.</p>
    <div style="background:#0a0a0a;border:1px solid #1f1f23;border-radius:8px;padding:16px 20px;margin:18px 0;">
      <div style="color:#9ca3af;font-size:11px;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">Credit applied</div>
      <div style="font-size:24px;font-weight:700;color:#10b981;font-family:'JetBrains Mono',ui-monospace,monospace;">+1 month Premium</div>
      <div style="color:#9ca3af;font-size:13px;margin-top:6px;">Auto-redeems at your next checkout. Stack credits — refer 12, get a free year.</div>
    </div>
    <a href="https://tapeline.io/app/referrals" style="display:inline-block;background:#3b82f6;color:#fff;padding:12px 22px;border-radius:6px;text-decoration:none;font-weight:500;">See your referral page &rarr;</a>
    """)


# Drip orchestration — the worker hooks below. Wiring is intentionally minimal
# until Resend is configured (no API key = send_email() returns {"skipped": True}).
# When the key arrives, add this to signal_publisher.py tick():
#
#   global _last_drip_check
#   if _last_drip_check is None or (started - _last_drip_check).total_seconds() >= 86400:
#       from app.services.email import run_daily_drip
#       async with session_scope() as s:
#           await run_daily_drip(s)
#       _last_drip_check = started
#
# Note: this MVP version may double-send if the worker restarts mid-day.
# To guard against that, add a `drip_state` JSON column to User and check it
# before each send. That's a one-line migration but waits until Resend lands.

async def run_daily_drip(session) -> dict[str, int]:
    """
    Send the full trial-drip series. Returns per-stage counts.

    Stages, all dedup'd via `User.drip_state` (comma-separated tokens):

      Pre-expiry (trial_ends_at in the FUTURE — user is still on trial):
        - "3"   day-3  email   — trial_ends_at in (now+10d, now+11d)
        - "7"   day-7  email   — trial_ends_at in (now+6d,  now+7d )
        - "11"  T-3    email   — trial_ends_at in (now+2d,  now+3d ) [NEW]
        - "13"  T-1    email   — trial_ends_at in (now+0d,  now+1d )

      Post-expiry (trial_ends_at in the PAST — user didn't convert):
        - "expired" T+0  email — trial_ends_at in (now-1d, now)   [NEW]
        - "post3"   T+3  email — trial_ends_at in (now-4d, now-3d) [NEW]

    Tier filter: pre-expiry windows target users still on the trial
    (tier in pro/premium, no Stripe customer). Post-expiry windows drop the
    tier filter because auto-downgrade to Free may have already fired —
    we just need "had a trial that ended recently and never added a card".
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.models import User

    now = datetime.now(UTC)
    counts = {"day3": 0, "day7": 0, "day11": 0, "day13": 0, "expired": 0, "post3": 0}

    # Each entry: (token, count_key, lower, upper, renderer, subject,
    #              personalise, post_expiry_filter)
    # `personalise=True`         → renderer takes a per-user summary dict
    # `post_expiry_filter=True`  → drop the pro/premium tier filter
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
        # Post-expiry — trial_ends_at is in the past
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
        # Pre-expiry stages only target users still labelled as paid-tier
        # (the no-card trial sets tier=premium until trial_ends_at fires).
        # Post-expiry stages need to find users whose tier may have already
        # auto-downgraded to free, so we skip that filter.
        if not post_expiry:
            filters.append(User.tier.in_(["pro", "premium"]))

        result = await session.execute(select(User).where(*filters))
        users = result.scalars().all()

        for user in users:
            sent_tokens = set((user.drip_state or "").split(",")) - {""}
            if token in sent_tokens:
                continue  # already sent this stage to this user
            try:
                if personalise:
                    summary = await trial_summary_for_user(session, user)
                    html = renderer(user.name or "trader", summary)
                else:
                    html = renderer(user.name or "trader")
                res = await send_email(user.email, subject, html)
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
