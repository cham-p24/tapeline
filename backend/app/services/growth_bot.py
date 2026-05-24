"""Autonomous growth bot — daily content drafting + metrics digest.

Single entry point: `run_daily_growth_tick(session)`. The worker calls
this at 22:00 UTC weekdays (~8am Melbourne) and the function:

  1. Pulls live conversion / engagement metrics from Postgres
  2. Drafts the day's X tweet from current Top 5 picks
  3. Drafts the day's LinkedIn post (rotates through topic queue)
  4. Drafts 3 fintwit reply candidates anchored on current composites
  5. Emails the package to `growth_digest_to` (default tapeline.inbox@gmail.com)
     so the founder has copy-paste-ready content in 60 seconds

What this DOES NOT do: post to X / LinkedIn directly. Auto-posting
requires the X API tokens (see docs/setup/X_API_SETUP.md) and partner
LinkedIn access (effectively impossible for indie founders). Until
those tokens exist the bot's output is a queue, not a publisher.

Kill switch: set `GROWTH_BOT_ENABLED=false` in Fly secrets. Worker
checks the flag on every tick and skips the function entirely.

Dedupe: a per-UTC-day token is checked against an in-memory state. The
DB-side dedupe lives in the worker (`_last_growth_tick_date` global).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import NewsletterSubscriber, Ticker, User
from app.services.email import send_email

logger = logging.getLogger(__name__)
settings = get_settings()


# -----------------------------------------------------------------------------
# Metrics
# -----------------------------------------------------------------------------


@dataclass
class GrowthMetrics:
    """Snapshot of the conversion funnel at one moment in time.

    Generated once per growth tick. The deltas vs. the prior tick are
    computed by the caller — we don't store history here, we just
    expose current numbers + the structure callers need to do deltas
    against last run's output.
    """

    as_of: datetime
    users_total: int
    users_non_owner: int
    users_signed_up_24h: int
    users_paid: int
    users_on_trial: int
    newsletter_subs_total: int
    newsletter_subs_24h: int
    top_utm_sources_24h: list[tuple[str, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of.isoformat(),
            "users_total": self.users_total,
            "users_non_owner": self.users_non_owner,
            "users_signed_up_24h": self.users_signed_up_24h,
            "users_paid": self.users_paid,
            "users_on_trial": self.users_on_trial,
            "newsletter_subs_total": self.newsletter_subs_total,
            "newsletter_subs_24h": self.newsletter_subs_24h,
            "top_utm_sources_24h": self.top_utm_sources_24h,
        }


async def pull_growth_metrics(session: AsyncSession) -> GrowthMetrics:
    """Snapshot the conversion funnel. Safe for production read access."""
    now = datetime.now(UTC)
    cutoff_24h = now - timedelta(hours=24)

    users_total = (await session.execute(select(func.count(User.id)))).scalar() or 0
    users_non_owner = (
        await session.execute(
            select(func.count(User.id)).where(User.email != "owner@tapeline.io"),
        )
    ).scalar() or 0
    users_signed_up_24h = (
        await session.execute(
            select(func.count(User.id)).where(
                User.created_at >= cutoff_24h,
                User.email != "owner@tapeline.io",
            ),
        )
    ).scalar() or 0
    users_paid = (
        await session.execute(
            select(func.count(User.id)).where(User.stripe_customer_id.is_not(None)),
        )
    ).scalar() or 0
    users_on_trial = (
        await session.execute(
            select(func.count(User.id)).where(
                User.trial_ends_at.is_not(None),
                User.trial_ends_at > now,
                User.stripe_customer_id.is_(None),
            ),
        )
    ).scalar() or 0
    newsletter_subs_total = (
        await session.execute(
            select(func.count(NewsletterSubscriber.id)).where(
                NewsletterSubscriber.status == "confirmed",
            ),
        )
    ).scalar() or 0
    newsletter_subs_24h = (
        await session.execute(
            select(func.count(NewsletterSubscriber.id)).where(
                NewsletterSubscriber.created_at >= cutoff_24h,
                NewsletterSubscriber.status == "confirmed",
            ),
        )
    ).scalar() or 0

    # Top UTM sources in the last 24h across both signup paths
    utm_rows = (
        await session.execute(
            select(
                User.signup_utm_source,
                func.count(User.id),
            )
            .where(
                User.created_at >= cutoff_24h,
                User.signup_utm_source.is_not(None),
            )
            .group_by(User.signup_utm_source)
            .order_by(desc(func.count(User.id)))
            .limit(5),
        )
    ).all()
    top_utm_sources_24h = [(src, count) for src, count in utm_rows]

    return GrowthMetrics(
        as_of=now,
        users_total=users_total,
        users_non_owner=users_non_owner,
        users_signed_up_24h=users_signed_up_24h,
        users_paid=users_paid,
        users_on_trial=users_on_trial,
        newsletter_subs_total=newsletter_subs_total,
        newsletter_subs_24h=newsletter_subs_24h,
        top_utm_sources_24h=top_utm_sources_24h,
    )


# -----------------------------------------------------------------------------
# Content drafting
# -----------------------------------------------------------------------------


@dataclass
class TopPick:
    symbol: str
    name: str
    score: float
    signal: str
    reason: str | None


async def pull_top_picks(session: AsyncSession, limit: int = 5) -> list[TopPick]:
    """Top N tickers by current composite score, score-not-null only."""
    rows = (
        await session.execute(
            select(
                Ticker.symbol, Ticker.name, Ticker.score, Ticker.signal, Ticker.reason,
            )
            .where(Ticker.score.is_not(None))
            .order_by(desc(Ticker.score))
            .limit(limit),
        )
    ).all()
    return [
        TopPick(
            symbol=s,
            name=n or s,
            score=float(sc),
            signal=sg or "",
            reason=r,
        )
        for s, n, sc, sg, r in rows
    ]


def draft_daily_tweet(picks: list[TopPick]) -> str:
    """Compose the day's @tapeline_io tweet.

    280-char budget, leads with the highest-scoring 5 tickers, links to
    /scorecard with UTM tag. Falls back to a brand-only tweet when no
    picks are available (e.g. fresh DB, score worker hasn't run).
    """
    if not picks:
        return (
            "Tapeline is scoring every US ticker on a public 6-factor formula "
            "right now. Tomorrow's Top 10 ranks at tapeline.io/scorecard."
        )

    today = date.today().strftime("%b %d")
    picks_for_tweet = picks[:5]
    line = " · ".join(
        f"${p.symbol} {int(p.score)}" for p in picks_for_tweet
    )
    url_tag = date.today().strftime("daily_%Y%m%d")
    url = (
        f"tapeline.io/scorecard?"
        f"utm_source=x&utm_medium=social&utm_campaign={url_tag}"
    )
    # Compose with room for ~30 chars of URL
    body = f"Top 5 by composite this morning ({today}):\n\n{line}\n\nFull ranks → {url}"
    if len(body) > 280:
        # Trim the picks line itself; the URL has to stay
        line = " · ".join(f"${p.symbol} {int(p.score)}" for p in picks_for_tweet[:3])
        body = f"Top 3 by composite ({today}):\n\n{line}\n\nFull → {url}"
    return body


# Rotating LinkedIn topic queue. Cycles through these by ISO weekday so
# the bot doesn't post the same theme two days running. Order is
# intentional: factor-explainer (Mon, depth) → win/miss (Tue, evidence)
# → methodology (Wed, contrast) → factor (Thu, depth) → trust (Fri,
# soft close).
_LINKEDIN_TOPIC_ROTATION: list[tuple[str, str]] = [
    (
        "Why we publish the 6-factor formula",
        "Most stock scanners hide their methodology behind 'proprietary'. "
        "Tapeline publishes the exact weights — Trend 25%, RS 20%, "
        "Fundamentals 15%, Smart Money 15%, Macro 15%, Momentum 10%. "
        "The full breakdown lives at tapeline.io/how-it-works.",
    ),
    (
        "Today's largest factor divergence",
        "When trend and fundamentals point opposite directions on the "
        "same ticker, that's a setup worth investigating. Today's most "
        "divergent name + the read at tapeline.io/scorecard.",
    ),
    (
        "What the public scorecard actually shows",
        "Every top-10 daily pick is logged with next-day return vs SPY. "
        "Append-only. Every miss stays on the page. tapeline.io/scorecard.",
    ),
    (
        "The Smart Money sub-score explained",
        "Smart Money is 15% of the Tapeline composite. It filters out "
        "10b5-1 plan sales and ranks cluster Form 4 buys. The 90% noise "
        "filter is the work; one number is the output.",
    ),
    (
        "How to evaluate any stock scanner before paying",
        "Five tests: visible-losers scorecard, named benchmark, public "
        "methodology, data-freshness check, cancel friction. The vague "
        "answer to each tells you what isn't being said.",
    ),
]


def draft_linkedin_post(weekday: int) -> dict[str, str]:
    """Pick a LinkedIn topic from the rotation by weekday (Mon=0..Fri=4).

    Weekends fall back to Monday's topic but are flagged for the caller
    so they can decide whether to send the digest at all on Sat/Sun.
    """
    idx = weekday if 0 <= weekday < len(_LINKEDIN_TOPIC_ROTATION) else 0
    headline, body = _LINKEDIN_TOPIC_ROTATION[idx]
    return {
        "headline": headline,
        "body": body,
        "weekday_index": idx,
    }


def draft_fintwit_reply_candidates(picks: list[TopPick]) -> list[dict[str, str]]:
    """Sketch 3 candidate fintwit replies anchored on current composites.

    These are TEMPLATE drafts — they assume a fresh tweet from the target
    account that mentions one of the top picks. The cloud-scheduled
    Claude session (which has web-fetch access) takes these templates,
    finds matching fresh tweets, and fills in the specific tweet
    reference + handle. Until that session runs, the templates sit
    here as ready-to-personalise content.
    """
    if len(picks) < 3:
        return []
    candidates = []
    for pick in picks[:3]:
        score_int = int(pick.score)
        signal = pick.signal or "—"
        reason = (pick.reason or "").strip().rstrip(".") or "factor confluence"
        body = (
            f"${pick.symbol} on our composite right now: {score_int} {signal}. "
            f"{reason.capitalize()}. Public formula + back-checked scorecard at "
            f"tapeline.io/t/{pick.symbol}."
        )
        # Tight cap — fintwit replies live or die under 280
        if len(body) > 270:
            body = body[:267].rstrip() + "..."
        candidates.append({
            "symbol": pick.symbol,
            "score": str(score_int),
            "signal": signal,
            "body": body,
        })
    return candidates


# -----------------------------------------------------------------------------
# Digest email
# -----------------------------------------------------------------------------


def render_growth_digest_html(
    metrics: GrowthMetrics,
    daily_tweet: str,
    linkedin: dict[str, str],
    fintwit_candidates: list[dict[str, str]],
) -> tuple[str, str]:
    """Render the daily growth-digest email as (html, text)."""
    date_label = metrics.as_of.strftime("%a %b %d, %Y")

    utm_block = "—"
    if metrics.top_utm_sources_24h:
        utm_block = ", ".join(
            f"{src}={count}" for src, count in metrics.top_utm_sources_24h
        )

    fintwit_html = "".join(
        f"""<li style="margin:8px 0;padding:12px;background:#0a0a0a;border:1px solid #27272a;border-radius:6px;">
              <div style="color:#fb923c;font-weight:600;font-size:13px;margin-bottom:4px;">${c['symbol']} — {c['score']} {c['signal']}</div>
              <div style="color:#d4d4d8;font-size:13px;line-height:1.5;font-family:'JetBrains Mono',monospace;">{c['body']}</div>
            </li>"""
        for c in fintwit_candidates
    ) or '<li style="color:#6b7280;">No picks above threshold today.</li>'

    fintwit_text = "\n".join(
        f"  ${c['symbol']} ({c['score']} {c['signal']}):\n    {c['body']}\n"
        for c in fintwit_candidates
    ) or "  (none)"

    html = f"""<!doctype html><html><body style="font-family:Inter,system-ui,sans-serif;background:#0a0a0a;color:#f4f4f5;padding:24px;margin:0;">
  <div style="max-width:680px;margin:0 auto;background:#121214;border-radius:12px;padding:32px;border:1px solid #1f1f23;">
    <div style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#9ca3af;margin-bottom:8px;">Tapeline · Growth tick</div>
    <h1 style="margin:6px 0 24px;font-size:22px;font-weight:600;">{date_label}</h1>

    <h2 style="margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:#9ca3af;font-weight:500;">Conversion funnel</h2>
    <table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;font-size:13px;color:#d4d4d8;">
      <tr><td style="padding:6px 0;border-bottom:1px solid #27272a;">Total users (excl. owner)</td><td style="padding:6px 0;border-bottom:1px solid #27272a;text-align:right;font-family:'JetBrains Mono',monospace;">{metrics.users_non_owner}</td></tr>
      <tr><td style="padding:6px 0;border-bottom:1px solid #27272a;">Signed up last 24h</td><td style="padding:6px 0;border-bottom:1px solid #27272a;text-align:right;font-family:'JetBrains Mono',monospace;color:{'#22c55e' if metrics.users_signed_up_24h else '#6b7280'};">{metrics.users_signed_up_24h:+d}</td></tr>
      <tr><td style="padding:6px 0;border-bottom:1px solid #27272a;">On trial right now</td><td style="padding:6px 0;border-bottom:1px solid #27272a;text-align:right;font-family:'JetBrains Mono',monospace;">{metrics.users_on_trial}</td></tr>
      <tr><td style="padding:6px 0;border-bottom:1px solid #27272a;">Paid (stripe customer)</td><td style="padding:6px 0;border-bottom:1px solid #27272a;text-align:right;font-family:'JetBrains Mono',monospace;color:{'#22c55e' if metrics.users_paid else '#6b7280'};">{metrics.users_paid}</td></tr>
      <tr><td style="padding:6px 0;border-bottom:1px solid #27272a;">Newsletter subscribers</td><td style="padding:6px 0;border-bottom:1px solid #27272a;text-align:right;font-family:'JetBrains Mono',monospace;">{metrics.newsletter_subs_total} ({metrics.newsletter_subs_24h:+d} 24h)</td></tr>
      <tr><td style="padding:6px 0;">UTM sources 24h</td><td style="padding:6px 0;text-align:right;font-family:'JetBrains Mono',monospace;color:#9ca3af;">{utm_block}</td></tr>
    </table>

    <h2 style="margin:28px 0 12px;font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:#9ca3af;font-weight:500;">Today's X tweet (copy-paste, post anytime today)</h2>
    <pre style="margin:0;padding:14px;background:#0a0a0a;border:1px solid #27272a;border-radius:6px;color:#d4d4d8;font-size:13px;line-height:1.5;white-space:pre-wrap;font-family:'JetBrains Mono',monospace;">{daily_tweet}</pre>

    <h2 style="margin:28px 0 12px;font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:#9ca3af;font-weight:500;">Today's LinkedIn post</h2>
    <div style="padding:14px;background:#0a0a0a;border:1px solid #27272a;border-radius:6px;">
      <div style="color:#fb923c;font-weight:600;font-size:14px;margin-bottom:8px;">{linkedin['headline']}</div>
      <div style="color:#d4d4d8;font-size:13px;line-height:1.55;">{linkedin['body']}</div>
    </div>

    <h2 style="margin:28px 0 12px;font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:#9ca3af;font-weight:500;">Fintwit reply candidates (paste under fresh tweet from any priority-1 handle)</h2>
    <ul style="margin:0;padding:0;list-style:none;">{fintwit_html}</ul>

    <p style="margin:32px 0 0;padding-top:16px;border-top:1px solid #1f1f23;color:#6b7280;font-size:11px;line-height:1.55;">
      This digest fires daily from the Tapeline growth bot worker. To disable, set <code>GROWTH_BOT_ENABLED=false</code> in Fly secrets.
      Sent from the brand inbox, not user-facing email.
    </p>
  </div></body></html>"""

    text = f"""Tapeline growth tick — {date_label}
==========================================

Conversion funnel
  Total users (excl. owner): {metrics.users_non_owner}
  Signed up last 24h:        {metrics.users_signed_up_24h:+d}
  On trial right now:        {metrics.users_on_trial}
  Paid (Stripe customer):    {metrics.users_paid}
  Newsletter subs:           {metrics.newsletter_subs_total} ({metrics.newsletter_subs_24h:+d} 24h)
  UTM sources 24h:           {utm_block}

Today's X tweet
---------------
{daily_tweet}

Today's LinkedIn post — {linkedin['headline']}
-----------------------
{linkedin['body']}

Fintwit reply candidates
------------------------
{fintwit_text}

To disable, set GROWTH_BOT_ENABLED=false in Fly secrets.
"""

    return html, text


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------


async def run_daily_growth_tick(session: AsyncSession) -> dict[str, Any]:
    """Top-level entry point for the daily growth tick.

    Idempotent in the sense that re-running on the same day will
    regenerate slightly different drafts (since ticker scores tick
    every minute) — but the worker enforces a per-UTC-day token so
    this is called at most once per calendar day.
    """
    if not settings.growth_bot_enabled:
        logger.info("growth_bot.disabled reason=growth_bot_enabled=false")
        return {"ok": True, "skipped": True, "reason": "disabled"}

    metrics = await pull_growth_metrics(session)
    picks = await pull_top_picks(session, limit=5)
    daily_tweet = draft_daily_tweet(picks)
    linkedin = draft_linkedin_post(weekday=metrics.as_of.weekday())
    fintwit_candidates = draft_fintwit_reply_candidates(picks)

    html, text = render_growth_digest_html(
        metrics, daily_tweet, linkedin, fintwit_candidates,
    )

    recipient = settings.growth_digest_to or "tapeline.inbox@gmail.com"
    subject = f"Tapeline growth tick · {metrics.as_of.strftime('%a %b %d')}"

    try:
        send_result = await send_email(
            to=recipient,
            subject=subject,
            html=html,
            text=text,
            persona="sales",
        )
    except Exception:
        logger.exception("growth_bot.digest_send_failed")
        send_result = {"error": True}

    logger.info(
        "growth_bot.tick_ran picks=%d fintwit=%d subs=%d users=%d send=%s",
        len(picks), len(fintwit_candidates),
        metrics.newsletter_subs_total, metrics.users_non_owner,
        "ok" if not send_result.get("error") else "failed",
    )

    return {
        "ok": True,
        "skipped": False,
        "metrics": metrics.to_dict(),
        "picks_count": len(picks),
        "daily_tweet": daily_tweet,
        "linkedin": linkedin,
        "fintwit_candidates_count": len(fintwit_candidates),
        "send_result": send_result,
    }
