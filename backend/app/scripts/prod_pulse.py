"""Weekly prod pulse — first-party funnel + buying-signal report to the founder.

The founder keeps asking the same four questions: how many people arrive, where
from, who's actually engaged, and — the one that matters at $0 revenue — has
ANYONE reached checkout or entered a card. Every answer lives in our own
Postgres. No third-party analytics, no OAuth connector: this reads the User
table directly and emails the founder the answer once a week.

Invoked by the `prod-pulse` GitHub Action, which sources this file from the repo
checkout and execs it inside the prod backend's Python (so it has the DB and the
Resend `send_email` service, and always runs current code without waiting for a
backend deploy).

Report-only by construction: it never emails users. The single recipient is the
founder address (PULSE_TO, default cpiyatilaka@gmail.com). It takes no action on
the account — it only surfaces state, so the founder (or the operator) decides
when a buying signal is worth a personal reply.
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import User
from app.services.email import send_email

try:  # watchlist size is the engagement proxy; degrade gracefully if renamed
    from app.models import WatchlistItem
except Exception:  # pragma: no cover - defensive
    WatchlistItem = None

FOUNDER_EMAIL = os.environ.get("PULSE_TO", "cpiyatilaka@gmail.com")


async def gather() -> dict:
    async with SessionLocal() as s:
        total = (await s.execute(select(func.count()).select_from(User))).scalar() or 0
        by_tier = dict(
            (
                await s.execute(select(User.tier, func.count()).group_by(User.tier))
            ).all()
        )
        cards = (
            await s.execute(
                select(func.count())
                .select_from(User)
                .where(User.stripe_customer_id.isnot(None))
            )
        ).scalar() or 0
        checkouts = (
            await s.execute(
                select(func.count())
                .select_from(User)
                .where(User.checkout_started_at.isnot(None))
            )
        ).scalar() or 0
        activated = (
            await s.execute(
                select(func.count())
                .select_from(User)
                .where(User.activated_at.isnot(None))
            )
        ).scalar() or 0

        # Acquisition channel: utm_source, else referrer host, else "direct".
        ch = func.coalesce(
            func.nullif(User.signup_utm_source, ""),
            func.nullif(User.signup_referrer_host, ""),
            "direct",
        )
        channels = [
            (r[0], r[1], r[2])
            for r in (
                await s.execute(
                    select(ch, func.count(), func.count(User.stripe_customer_id))
                    .group_by(ch)
                    .order_by(func.count().desc())
                )
            ).all()
        ]

        cutoff = datetime.now(UTC) - timedelta(days=7)
        new7 = [
            (r[0], str(r[1])[:10], r[2])
            for r in (
                await s.execute(
                    select(User.email, User.created_at, User.tier)
                    .where(User.created_at >= cutoff)
                    .order_by(User.created_at.desc())
                )
            ).all()
        ]

        # The buying signals that warrant a same-day personal reply.
        checkout_emails = [
            r[0]
            for r in (
                await s.execute(
                    select(User.email).where(User.checkout_started_at.isnot(None))
                )
            ).all()
        ]
        card_emails = [
            r[0]
            for r in (
                await s.execute(
                    select(User.email).where(User.stripe_customer_id.isnot(None))
                )
            ).all()
        ]

        # Hot leads: engaged (activated, has a watchlist) but never paid.
        leads = []
        for r in (
            await s.execute(
                select(User.id, User.email, User.name, User.activated_at)
                .where(
                    User.tier == "free",
                    User.activated_at.isnot(None),
                    User.stripe_customer_id.is_(None),
                )
                .order_by(User.activated_at.desc())
            )
        ).all():
            wl = 0
            if WatchlistItem is not None:
                try:
                    wl = (
                        await s.execute(
                            select(func.count())
                            .select_from(WatchlistItem)
                            .where(WatchlistItem.user_id == r[0])
                        )
                    ).scalar() or 0
                except Exception:
                    wl = -1
            leads.append((r[1], r[2] or "-", str(r[3])[:10], wl))

    return {
        "total": total,
        "by_tier": by_tier,
        "cards": cards,
        "checkouts": checkouts,
        "activated": activated,
        "channels": channels,
        "new7": new7,
        "checkout_emails": checkout_emails,
        "card_emails": card_emails,
        "leads": leads,
    }


def _esc(x: object) -> str:
    return (
        str(x)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def render(d: dict) -> str:
    """Plain, factual founder-facing HTML. No performance or market framing —
    this is an internal status readout, just counts and names."""
    today = datetime.now(UTC).strftime("%b %d, %Y")

    if d["cards"]:
        signal = (
            f'<div style="background:#052e16;border:1px solid #16a34a;border-radius:8px;'
            f'padding:14px 16px;color:#bbf7d0;font-size:15px;">'
            f'<strong>💳 {d["cards"]} card(s) on file.</strong> Someone is paying or '
            f'has entered payment: {_esc(", ".join(d["card_emails"]))}. Reply personally today.'
            f"</div>"
        )
    elif d["checkouts"]:
        signal = (
            f'<div style="background:#3f2d00;border:1px solid #d97706;border-radius:8px;'
            f'padding:14px 16px;color:#fde68a;font-size:15px;">'
            f'<strong>🟡 {d["checkouts"]} reached checkout, no card yet.</strong> '
            f'{_esc(", ".join(d["checkout_emails"]))} — one nudge could close them.'
            f"</div>"
        )
    else:
        signal = (
            '<div style="background:#1f2937;border:1px solid #374151;border-radius:8px;'
            'padding:14px 16px;color:#d1d5db;font-size:15px;">'
            '<strong>No buying signal this week.</strong> Nobody has started checkout '
            'or entered a card. First-dollar blocker remains upstream (arrivals), not the '
            'payment step.</div>'
        )

    tier_bits = " · ".join(f"{_esc(k)} {v}" for k, v in sorted(d["by_tier"].items()))

    ch_rows = "".join(
        f'<tr><td style="padding:4px 12px 4px 0;">{_esc(c)}</td>'
        f'<td style="padding:4px 12px;text-align:right;">{n}</td>'
        f'<td style="padding:4px 0;text-align:right;color:#16a34a;">{paid}</td></tr>'
        for c, n, paid in d["channels"]
    )

    new_rows = (
        "".join(
            f'<li><code>{_esc(email)}</code> — {_esc(tier)} · {_esc(day)}</li>'
            for email, day, tier in d["new7"]
        )
        or "<li>none</li>"
    )

    lead_rows = (
        "".join(
            f'<tr><td style="padding:4px 12px 4px 0;"><code>{_esc(email)}</code></td>'
            f'<td style="padding:4px 12px;">{_esc(name)}</td>'
            f'<td style="padding:4px 12px;">act. {_esc(act)}</td>'
            f'<td style="padding:4px 0;text-align:right;">wl {wl}</td></tr>'
            for email, name, act, wl in d["leads"]
        )
        or '<tr><td colspan="4" style="padding:4px 0;">none</td></tr>'
    )

    return f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:640px;
margin:0 auto;color:#111;line-height:1.5;">
  <div style="font-size:12px;text-transform:uppercase;letter-spacing:0.08em;color:#6b7280;">
    Tapeline weekly pulse · {today}
  </div>
  <h1 style="font-size:22px;margin:6px 0 16px;">
    {d["total"]} users · {d["cards"]} paying · {len(d["leads"])} hot leads
  </h1>

  {signal}

  <h2 style="font-size:14px;text-transform:uppercase;letter-spacing:0.06em;color:#6b7280;
  margin:22px 0 6px;">Funnel</h2>
  <table style="font-size:14px;border-collapse:collapse;">
    <tr><td style="padding:2px 16px 2px 0;">Total users</td><td><strong>{d["total"]}</strong> ({tier_bits})</td></tr>
    <tr><td style="padding:2px 16px 2px 0;">Activated</td><td>{d["activated"]}</td></tr>
    <tr><td style="padding:2px 16px 2px 0;">Ever reached checkout</td><td>{d["checkouts"]}</td></tr>
    <tr><td style="padding:2px 16px 2px 0;">Card on file</td><td>{d["cards"]}</td></tr>
  </table>

  <h2 style="font-size:14px;text-transform:uppercase;letter-spacing:0.06em;color:#6b7280;
  margin:22px 0 6px;">Where signups come from</h2>
  <table style="font-size:14px;border-collapse:collapse;">
    <tr style="color:#6b7280;"><td style="padding:0 12px 4px 0;">channel</td>
    <td style="padding:0 12px 4px;text-align:right;">signups</td>
    <td style="padding:0 0 4px;text-align:right;">paid</td></tr>
    {ch_rows}
  </table>

  <h2 style="font-size:14px;text-transform:uppercase;letter-spacing:0.06em;color:#6b7280;
  margin:22px 0 6px;">New signups (last 7 days)</h2>
  <ul style="font-size:14px;margin:0;padding-left:18px;">{new_rows}</ul>

  <h2 style="font-size:14px;text-transform:uppercase;letter-spacing:0.06em;color:#6b7280;
  margin:22px 0 6px;">Hot leads — engaged, never paid</h2>
  <table style="font-size:14px;border-collapse:collapse;">{lead_rows}</table>

  <p style="font-size:12px;color:#9ca3af;margin-top:24px;">
    Auto-generated from the production database. Report only — no account was
    touched and no user was emailed. Reply to this to have the operator act on a signal.
  </p>
</div>"""


async def main() -> None:
    d = await gather()
    html = render(d)
    subject = (
        f"Tapeline pulse — {d['total']} users, {d['cards']} paying, "
        f"{len(d['leads'])} hot leads"
    )
    res = await send_email(
        FOUNDER_EMAIL,
        subject,
        html,
        persona="default",
        skip_if_undeliverable=False,
    )
    print(f"pulse.sent to={FOUNDER_EMAIL} result={res}")


if __name__ == "__main__":
    asyncio.run(main())
