"""Newsletter signup business logic.

Two surfaces:

  subscribe(...)    — accepts an email + source + UTMs, upserts a
                      `newsletter_subscribers` row, fires a welcome
                      email via Resend. Idempotent: re-subscribing an
                      existing-confirmed email is a no-op (don't spam
                      them with a second welcome); re-subscribing a
                      previously-unsubscribed email flips the status
                      back to confirmed.

  unsubscribe_by_token(...) — looks up by token (never by id), marks
                              unsubscribed_at + flips status. One-click
                              flow.

The daily-digest worker that sends Top 10 picks to confirmed
subscribers lives elsewhere (added in a follow-up PR); this service
only ships the capture half so the email-capture component on
tapeline.io has a backing endpoint immediately.

DB sessions are AsyncSession — the rest of the codebase is async, so
matching it here keeps the dependency-injection chain consistent.
"""
from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.newsletter import NewsletterSubscriber
from app.services.email import send_email

logger = logging.getLogger(__name__)
settings = get_settings()


def _normalise_email(raw: str) -> str:
    return raw.strip().lower()


def _new_token() -> str:
    # 32 bytes = 64 hex chars. Fits in the String(64) column exactly.
    return secrets.token_hex(32)


async def subscribe(
    session: AsyncSession,
    *,
    email: str,
    source: str | None = None,
    utm_source: str | None = None,
    utm_medium: str | None = None,
    utm_campaign: str | None = None,
    utm_term: str | None = None,
    utm_content: str | None = None,
) -> dict[str, Any]:
    """Idempotent newsletter signup.

    Returns {"ok": True, "status": "new" | "already_subscribed" | "resubscribed"}.

    `status="new"` and `status="resubscribed"` both fire the welcome email.
    `status="already_subscribed"` does NOT — we don't want to spam confirmed
    subscribers if a user double-clicks the signup button or revisits the
    homepage and submits again.
    """
    email = _normalise_email(email)

    q = await session.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == email),
    )
    existing = q.scalar_one_or_none()

    if existing and existing.status == "confirmed":
        logger.info("newsletter.already_subscribed email=%s", email)
        return {"ok": True, "status": "already_subscribed"}

    if existing:
        # Resubscribe path — flip back to confirmed, clear unsub timestamp.
        existing.status = "confirmed"
        existing.unsubscribed_at = None
        existing.confirmed_at = datetime.now(UTC)
        # Keep the original UTM/source so we don't overwrite the channel
        # that originally converted them — but update if it was previously
        # blank.
        existing.source = existing.source or source
        existing.utm_source = existing.utm_source or utm_source
        existing.utm_medium = existing.utm_medium or utm_medium
        existing.utm_campaign = existing.utm_campaign or utm_campaign
        existing.utm_term = existing.utm_term or utm_term
        existing.utm_content = existing.utm_content or utm_content
        await session.commit()
        status_label = "resubscribed"
        token = existing.unsubscribe_token
    else:
        row = NewsletterSubscriber(
            email=email,
            status="confirmed",
            source=source,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            utm_term=utm_term,
            utm_content=utm_content,
            unsubscribe_token=_new_token(),
            confirmed_at=datetime.now(UTC),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        status_label = "new"
        token = row.unsubscribe_token

    # Welcome email — best-effort, never throw. If Resend's down, the user
    # is already in the DB and the next daily digest will reach them.
    try:
        await _send_welcome(email=email, token=token)
    except Exception:
        logger.exception("newsletter.welcome_send_failed email=%s", email)

    logger.info(
        "newsletter.subscribed email=%s status=%s source=%s utm_source=%s utm_campaign=%s",
        email, status_label, source, utm_source, utm_campaign,
    )
    return {"ok": True, "status": status_label}


async def unsubscribe_by_token(session: AsyncSession, token: str) -> bool:
    """Mark a subscriber unsubscribed. Returns True if a row was flipped."""
    if not token:
        return False
    q = await session.execute(
        select(NewsletterSubscriber).where(
            NewsletterSubscriber.unsubscribe_token == token,
        ),
    )
    row = q.scalar_one_or_none()
    if not row:
        return False
    if row.status == "unsubscribed":
        return True  # idempotent; one-click can be retried safely
    row.status = "unsubscribed"
    row.unsubscribed_at = datetime.now(UTC)
    await session.commit()
    logger.info("newsletter.unsubscribed email=%s", row.email)
    return True


async def _send_welcome(*, email: str, token: str) -> None:
    """Brand-aligned welcome email.

    Sent from `christian@tapeline.io` (sales persona — see
    services/email._persona_addresses) because the daily digest is a
    growth/sales channel, not a billing or transactional one.
    """
    base = settings.app_url or "https://tapeline.io"
    unsub_url = f"{base}/api/newsletter/unsubscribe?token={token}"
    scorecard_url = (
        f"{base}/scorecard"
        "?utm_source=newsletter&utm_campaign=welcome&utm_medium=email"
    )
    how_url = (
        f"{base}/how-it-works"
        "?utm_source=newsletter&utm_campaign=welcome&utm_medium=email"
    )

    text = (
        "Welcome to the Tapeline daily Top 10.\n\n"
        "Every market day morning we send the 10 highest-scoring US tickers "
        "from our public 6-factor composite — same numbers anyone can see on "
        "tapeline.io/scorecard, just delivered straight to your inbox before "
        "the open.\n\n"
        f"Today's scorecard: {scorecard_url}\n"
        f"How the scoring works: {how_url}\n\n"
        "No tip-sheet hype, no \"BUY NOW\" labels — just the composite score, "
        "the one-sentence read, and the back-checked track record vs SPY. "
        "If a stock is up there one day and gone the next, you'll see it "
        "happen in public.\n\n"
        "— Christian\n"
        "Founder, Tapeline\n\n"
        f"Unsubscribe: {unsub_url}\n"
    )

    html = f"""<!doctype html><html><body style="font-family:Inter,system-ui,sans-serif;background:#0a0a0a;color:#f4f4f5;padding:24px;margin:0;">
  <div style="max-width:560px;margin:0 auto;background:#121214;border-radius:12px;padding:32px;border:1px solid #1f1f23;">
    <div style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#9ca3af;margin-bottom:8px;">Tapeline · Daily Top 10</div>
    <h1 style="margin:0 0 16px;font-size:22px;font-weight:600;">You're in.</h1>
    <p style="margin:0 0 16px;line-height:1.55;color:#d4d4d8;">
      Every market day morning, we send the 10 highest-scoring US tickers
      from our public 6-factor composite — same numbers anyone can see on
      <a href="{scorecard_url}" style="color:#fb923c;">tapeline.io/scorecard</a>,
      delivered straight to your inbox before the open.
    </p>
    <p style="margin:0 0 16px;line-height:1.55;color:#d4d4d8;">
      No tip-sheet hype, no "BUY NOW" labels — just the composite score,
      the one-sentence read, and the back-checked track record vs SPY.
      If a stock is up there one day and gone the next, you see it happen
      in public.
    </p>
    <div style="margin:24px 0;padding:16px;background:#0a0a0a;border:1px solid #27272a;border-radius:8px;">
      <div style="font-size:12px;color:#9ca3af;margin-bottom:8px;">Want to dig in now?</div>
      <a href="{scorecard_url}" style="display:inline-block;background:#fb923c;color:#0a0a0a;padding:10px 16px;border-radius:6px;text-decoration:none;font-weight:600;margin-right:8px;font-size:14px;">View today's scorecard →</a>
      <a href="{how_url}" style="color:#fb923c;font-size:13px;">How scoring works</a>
    </div>
    <p style="margin:24px 0 0;color:#9ca3af;font-size:13px;line-height:1.55;">
      — Christian<br>Founder, Tapeline
    </p>
    <p style="margin:32px 0 0;padding-top:16px;border-top:1px solid #1f1f23;color:#6b7280;font-size:11px;line-height:1.55;">
      You received this because you signed up for the Tapeline daily Top 10 on tapeline.io.
      <a href="{unsub_url}" style="color:#6b7280;">Unsubscribe</a>
      &middot; Not investment advice. Past performance does not guarantee future results.
    </p>
  </div></body></html>"""

    await send_email(
        to=email,
        subject="Welcome to the Tapeline daily Top 10",
        html=html,
        text=text,
        persona="sales",
    )


# ---------------------------------------------------------------------------
# Daily Top 10 digest send
# ---------------------------------------------------------------------------
#
# Triggered by the worker once per US market day. Pulls the current top-10
# tickers by composite score and sends each confirmed newsletter
# subscriber a single email containing the picks, a one-sentence read on
# each, and an upgrade-to-Pro CTA tagged with today's date so we can
# attribute conversions back to a specific edition.
#
# Dedupe: process-token guards against worker restarts firing the digest
# twice within a UTC day, and per-row `last_sent_at` is the DB-of-record
# (set after send succeeds) so the digest is idempotent across deploys.


async def run_daily_digest(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> int:
    """Send the Daily Top 10 to every confirmed subscriber.

    Returns the number of emails actually sent (skipped re-sends and
    Resend-skipped no-op responses are not counted).

    A subscriber receives at most one digest per UTC date — enforced by
    comparing `last_sent_at::date` to today. Worker restarts mid-day
    therefore replay safely. If `send_email` returns `{"skipped": True}`
    (no API key configured), we do NOT bump `last_sent_at` so the next
    real run will retry the same subscriber.
    """
    from datetime import UTC
    from datetime import datetime as _dt

    from sqlalchemy import or_, select

    now = now or _dt.now(UTC)
    today = now.date()

    # Pull the top 10 from the Ticker table. Excluding ETFs etc. is left
    # to the marketing-clear rendering layer below; the SELECT keeps it
    # simple so we never accidentally exclude something legitimate.
    from sqlalchemy import desc

    from app.models import Ticker
    from app.services.ticker_freshness import live_clauses

    # Freshness + data-quality floor — don't email subscribers stale ghost
    # picks or corrupt (score>100 / emoji-symbol / <2-factor) artifacts.
    # (score IS NOT NULL is part of the floor.) See app.services.ticker_freshness.
    _top_stmt = select(
        Ticker.symbol, Ticker.name, Ticker.score, Ticker.signal,
        Ticker.reason, Ticker.price, Ticker.change_pct_1d,
    )
    for _clause in await live_clauses(session):
        _top_stmt = _top_stmt.where(_clause)
    top_q = await session.execute(
        _top_stmt.order_by(desc(Ticker.score)).limit(10)
    )
    picks = [
        {
            "symbol": symbol,
            "name": name or symbol,
            "score": score,
            "signal": signal,
            "reason": reason,
            "price": price,
            "change_pct_1d": change_pct_1d,
        }
        for (symbol, name, score, signal, reason, price, change_pct_1d) in top_q.all()
    ]

    if not picks:
        logger.warning("newsletter.digest_skipped reason=no_picks")
        return 0

    # Subscribers who are confirmed AND have either never been sent today
    # or last sent before today. last_sent_at is a UTC timestamp; today's
    # boundary is the UTC midnight before `now`.
    midnight_utc = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
    sub_q = await session.execute(
        select(NewsletterSubscriber).where(
            NewsletterSubscriber.status == "confirmed",
            or_(
                NewsletterSubscriber.last_sent_at.is_(None),
                NewsletterSubscriber.last_sent_at < midnight_utc,
            ),
        )
    )
    subscribers = sub_q.scalars().all()

    if not subscribers:
        logger.info("newsletter.digest_no_eligible_subscribers")
        return 0

    date_label = today.strftime("%b %d, %Y")
    campaign_tag = f"daily_{today.strftime('%Y%m%d')}"
    sent = 0
    any_commits = False

    for sub in subscribers:
        try:
            html, text = _render_daily_digest(
                picks=picks,
                date_label=date_label,
                campaign_tag=campaign_tag,
                unsubscribe_token=sub.unsubscribe_token,
            )
            res = await send_email(
                to=sub.email,
                subject=f"Tapeline Top 10 · {date_label}",
                html=html,
                text=text,
                persona="sales",
            )
            if not res.get("skipped", False):
                sub.last_sent_at = now
                sent += 1
                any_commits = True
        except Exception:
            logger.exception("newsletter.digest_send_failed email=%s", sub.email)

    if any_commits:
        await session.commit()

    logger.info(
        "newsletter.digest_sent count=%d eligible=%d picks=%d date=%s",
        sent, len(subscribers), len(picks), date_label,
    )
    return sent


def _render_daily_digest(
    *,
    picks: list[dict],
    date_label: str,
    campaign_tag: str,
    unsubscribe_token: str,
) -> tuple[str, str]:
    """Build the (html, text) pair for the daily Top 10 email.

    Each link is tagged with the per-edition `campaign_tag` so GA4 can
    attribute conversions to a specific day's send. The Pro upgrade CTA
    is the primary monetisation lever — every reader hits it whether or
    not they click any individual ticker.
    """
    base = settings.app_url or "https://tapeline.io"
    unsub_url = f"{base}/api/newsletter/unsubscribe?token={unsubscribe_token}"

    def utm(path: str) -> str:
        return (
            f"{base}{path}"
            f"?utm_source=newsletter&utm_medium=email&utm_campaign={campaign_tag}"
        )

    scorecard_url = utm("/scorecard")
    pricing_url = utm("/pricing")

    # HTML table rows for the picks
    rows_html: list[str] = []
    for i, p in enumerate(picks, start=1):
        ticker_url = utm(f"/t/{p['symbol']}")
        score_str = f"{int(p['score'])}" if p["score"] is not None else "—"
        signal = (p["signal"] or "").upper()
        reason = (p["reason"] or "").strip()
        # Hard-cap the reason so a single row doesn't blow the email height
        if len(reason) > 140:
            reason = reason[:137].rstrip() + "…"
        rows_html.append(f"""
          <tr>
            <td style="padding:14px 8px 14px 0;border-bottom:1px solid #1f1f23;width:32px;color:#6b7280;font-size:12px;vertical-align:top;">#{i}</td>
            <td style="padding:14px 8px;border-bottom:1px solid #1f1f23;vertical-align:top;">
              <a href="{ticker_url}" style="color:#fb923c;text-decoration:none;font-weight:600;font-size:15px;">${p['symbol']}</a>
              <div style="color:#9ca3af;font-size:12px;margin-top:2px;">{(p['name'] or p['symbol'])[:40]}</div>
            </td>
            <td style="padding:14px 8px;border-bottom:1px solid #1f1f23;text-align:right;vertical-align:top;">
              <div style="color:#f4f4f5;font-weight:600;font-size:18px;font-family:'JetBrains Mono',monospace;">{score_str}</div>
              <div style="color:#9ca3af;font-size:10px;text-transform:uppercase;letter-spacing:.05em;margin-top:2px;">{signal}</div>
            </td>
            <td style="padding:14px 0 14px 8px;border-bottom:1px solid #1f1f23;vertical-align:top;color:#d4d4d8;font-size:13px;line-height:1.45;">{reason or '—'}</td>
          </tr>""")

    html = f"""<!doctype html><html><body style="font-family:Inter,system-ui,sans-serif;background:#0a0a0a;color:#f4f4f5;padding:24px;margin:0;">
  <div style="max-width:640px;margin:0 auto;background:#121214;border-radius:12px;padding:32px;border:1px solid #1f1f23;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
      <div>
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#9ca3af;">Tapeline · Daily Top 10</div>
        <h1 style="margin:6px 0 0;font-size:22px;font-weight:600;">{date_label}</h1>
      </div>
      <a href="{scorecard_url}" style="color:#fb923c;font-size:13px;text-decoration:none;">Full scorecard →</a>
    </div>
    <p style="margin:0 0 20px;color:#9ca3af;font-size:13px;line-height:1.55;">
      The 10 highest-scoring US tickers from the public 6-factor composite,
      pre-open. Score is 0–100, blended from trend / RS / fundamentals /
      smart-money / macro / momentum at <a href="{utm('/how-it-works')}" style="color:#fb923c;">published weights</a>.
    </p>
    <table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;">
      <thead>
        <tr>
          <th style="padding:8px 0;text-align:left;color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:.05em;font-weight:500;">#</th>
          <th style="padding:8px 0;text-align:left;color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:.05em;font-weight:500;">Ticker</th>
          <th style="padding:8px 0;text-align:right;color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:.05em;font-weight:500;">Score</th>
          <th style="padding:8px 0 8px 8px;text-align:left;color:#6b7280;font-size:10px;text-transform:uppercase;letter-spacing:.05em;font-weight:500;">Read</th>
        </tr>
      </thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>

    <div style="margin:28px 0;padding:20px;background:#0a0a0a;border:1px solid #27272a;border-radius:8px;">
      <div style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#fb923c;margin-bottom:8px;">Live, sub-60s scoring on every US ticker</div>
      <div style="font-size:15px;font-weight:600;color:#f4f4f5;line-height:1.45;">
        See your watchlist scored the same way. Set alerts when one of these
        composites crosses your threshold.
      </div>
      <a href="{pricing_url}" style="display:inline-block;background:#fb923c;color:#0a0a0a;padding:11px 18px;border-radius:6px;text-decoration:none;font-weight:600;margin-top:14px;font-size:14px;">Start 14-day Premium trial — no card →</a>
      <div style="color:#6b7280;font-size:11px;margin-top:8px;">Free for 14 days · Cancel in one click · 7-day refund</div>
    </div>

    <p style="margin:28px 0 0;padding-top:16px;border-top:1px solid #1f1f23;color:#6b7280;font-size:11px;line-height:1.55;">
      Tapeline scores every US-listed ticker from a publicly documented 6-factor formula.
      Composite labels (HIGH CONVICTION / STRONG SETUP / CONSTRUCTIVE / NEUTRAL / CAUTION / WEAK)
      are descriptive readings of the score, not buy/sell recommendations.
      Tapeline operates under the publisher exemption from AFSL requirements; we do not hold
      an Australian Financial Services Licence. Not investment advice. Past performance does
      not guarantee future results.
      <br><br>
      You received this because you subscribed to the Tapeline daily Top 10 on tapeline.io.
      <a href="{unsub_url}" style="color:#6b7280;">Unsubscribe</a>.
    </p>
  </div></body></html>"""

    # Plain-text fallback for clients that block HTML
    text_rows = "\n".join(
        f"  #{i:2d}  ${p['symbol']:<6} {int(p['score']) if p['score'] else 0:>3}  "
        f"{(p['signal'] or '').upper():<16}  {(p['reason'] or '')[:80]}"
        for i, p in enumerate(picks, start=1)
    )
    text = (
        f"Tapeline Daily Top 10 — {date_label}\n\n"
        f"{text_rows}\n\n"
        f"Full scorecard: {scorecard_url}\n"
        f"Start your 14-day Premium trial (no card): {pricing_url}\n\n"
        "Not investment advice. Unsubscribe: " + unsub_url + "\n"
    )
    return html, text
