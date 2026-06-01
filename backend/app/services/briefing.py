"""Daily briefing email — scheduled job + template.

Two modes:

1. **Personalised** (user has at least one watchlist item):
   - Market regime block (unchanged — applies to everyone)
   - "Your watchlist" section: current score per ticker + delta since added
     (baseline_score captured on add via /api/watchlist), sorted by current
     score descending. Highlights meaningful drift (|delta| >= alert threshold).
   - Squeeze setups intersected with the watchlist when any qualify; otherwise
     site-wide top 3 (squeezes are sparse — better to show context than nothing).
   - CTA: open the user's watchlist directly.

2. **Site-wide** (no user / empty watchlist):
   - Original layout: regime + site-wide top 3 by score + top 3 squeezes
   - CTA changes to "Add tickers to your watchlist" so the next briefing is
     personalised instead of generic.

The function used to take only `user_name: str`. The new signature is
backwards-compatible — pass a User and you get personalisation; pass anything
truthy in the string slot (or None) and you get the site-wide layout.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RegimeState, SqueezeSetup, Ticker, User, WatchlistItem
from app.services.email import send_email

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
async def generate_briefing_html(
    session: AsyncSession,
    user_or_name: User | str | None,
) -> str:
    """Render today's briefing HTML.

    `user_or_name`:
        - A User instance → personalised briefing (watchlist-scoped)
        - A bare string   → legacy site-wide briefing addressed to that name
        - None            → legacy site-wide briefing addressed to "trader"
    """
    if isinstance(user_or_name, User):
        return await _generate_personalised(session, user_or_name)
    name = user_or_name if isinstance(user_or_name, str) and user_or_name else "trader"
    return await _generate_sitewide(session, name)


# ---------------------------------------------------------------------------
# Personalised path
# ---------------------------------------------------------------------------
async def _generate_personalised(session: AsyncSession, user: User) -> str:
    """Watchlist-scoped briefing. Falls through to site-wide if watchlist empty."""
    items = (
        await session.execute(
            select(WatchlistItem).where(WatchlistItem.user_id == user.id)
        )
    ).scalars().all()

    if not items:
        # Watchlist empty → use site-wide content but keep a "personalise me"
        # CTA so the next briefing is genuinely personalised.
        return await _generate_sitewide(
            session,
            user.name or "trader",
            personalise_cta=True,
        )

    symbols = [w.symbol.upper() for w in items]
    baseline_by_symbol = {w.symbol.upper(): w.baseline_score for w in items}
    threshold_by_symbol = {w.symbol.upper(): w.alert_threshold_delta for w in items}

    # Pull current ticker rows for the watchlist (latest snapshot).
    rows = (
        await session.execute(
            select(Ticker).where(Ticker.symbol.in_(symbols))
        )
    ).scalars().all()

    # Sort: by absolute delta-since-added descending so "movers" lead.
    # Tickers with no baseline (added before baseline_score column existed)
    # fall back to current score sort.
    def _key(t: Ticker) -> tuple[float, float]:
        base = baseline_by_symbol.get(t.symbol)
        cur  = t.score or 0.0
        delta = abs(cur - base) if base is not None else -1.0
        return (delta, cur)

    rows_sorted = sorted(rows, key=_key, reverse=True)
    # Cap at 6 rows — keeps the email scannable
    top_rows = rows_sorted[:6]

    regime = (
        await session.execute(select(RegimeState).where(RegimeState.id == 1))
    ).scalar_one_or_none()

    # Squeeze setups intersected with the watchlist
    sq_in_watchlist = (
        await session.execute(
            select(SqueezeSetup)
            .where(SqueezeSetup.symbol.in_(symbols))
            .order_by(desc(SqueezeSetup.spike_score))
            .limit(3)
        )
    ).scalars().all()
    if sq_in_watchlist:
        squeeze_label = "Squeeze setups in your watchlist"
        squeeze_rows = sq_in_watchlist
    else:
        # Fall back to site-wide top 3 squeezes — better than an empty section
        squeeze_rows = (
            await session.execute(
                select(SqueezeSetup).order_by(desc(SqueezeSetup.spike_score)).limit(3)
            )
        ).scalars().all()
        squeeze_label = "Squeeze setups (market-wide)"

    return _render_html(
        user_name=user.name or "trader",
        regime=regime,
        watchlist_rows=top_rows,
        baselines=baseline_by_symbol,
        thresholds=threshold_by_symbol,
        squeezes=squeeze_rows,
        squeeze_label=squeeze_label,
        cta_href="https://tapeline.io/app/watchlist",
        cta_label="Open your watchlist →",
        watchlist_total=len(items),
    )


# ---------------------------------------------------------------------------
# Site-wide fallback path
# ---------------------------------------------------------------------------
async def _generate_sitewide(
    session: AsyncSession,
    user_name: str,
    personalise_cta: bool = False,
) -> str:
    """Original briefing layout — site-wide top scores + squeezes."""
    from app.services.ticker_freshness import live_clauses

    # Freshness + data-quality floor — keep stale ghost rows AND corrupt
    # (score>100 / emoji-symbol / <2-factor) rows out of the briefing.
    # (score IS NOT NULL is part of the floor.) See app.services.ticker_freshness.
    _top_stmt = select(Ticker)
    for _clause in await live_clauses(session):
        _top_stmt = _top_stmt.where(_clause)
    top = (
        await session.execute(
            _top_stmt.order_by(desc(Ticker.score)).limit(3)
        )
    ).scalars().all()

    sq = (
        await session.execute(
            select(SqueezeSetup).order_by(desc(SqueezeSetup.spike_score)).limit(3)
        )
    ).scalars().all()

    regime = (
        await session.execute(select(RegimeState).where(RegimeState.id == 1))
    ).scalar_one_or_none()

    if personalise_cta:
        cta_href  = "https://tapeline.io/app/watchlist"
        cta_label = "Add tickers to your watchlist →"
    else:
        cta_href  = "https://tapeline.io/app/scanner"
        cta_label = "Open the scanner →"

    return _render_html(
        user_name=user_name,
        regime=regime,
        watchlist_rows=top,
        baselines={},          # no baselines in site-wide mode
        thresholds={},
        squeezes=sq,
        squeeze_label="Squeeze setups",
        cta_href=cta_href,
        cta_label=cta_label,
        watchlist_total=None,  # signals "site-wide mode" to the template
    )


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------
def _render_html(
    *,
    user_name: str,
    regime: RegimeState | None,
    watchlist_rows: Sequence[Ticker],
    baselines: dict[str, float | None],
    thresholds: dict[str, float],
    squeezes: Sequence[SqueezeSetup],
    squeeze_label: str,
    cta_href: str,
    cta_label: str,
    watchlist_total: int | None,
) -> str:
    date_str = datetime.now(UTC).strftime("%A, %B %d, %Y")

    # Top-section heading + sub-copy adapt to personalised vs site-wide
    if watchlist_total is not None:
        ticker_heading = f"Your watchlist · {watchlist_total} ticker{'s' if watchlist_total != 1 else ''}"
        ticker_sub     = "Sorted by movement since you added each name."
    else:
        ticker_heading = "Top 3 by composite score"
        ticker_sub     = "Across the live universe."

    # Per-ticker rows — show baseline delta only when baseline exists
    def _ticker_row(t: Ticker) -> str:
        base = baselines.get(t.symbol)
        thresh = thresholds.get(t.symbol, 10.0)
        cur = t.score or 0.0
        signal = t.signal or "—"
        reason = t.reason or ""
        delta_html = ""
        if base is not None:
            delta = cur - base
            color = "#10b981" if delta >= 0 else "#ef4444"
            arrow = "▲" if delta >= 0 else "▼"
            tag = " · ALERT" if abs(delta) >= thresh else ""
            delta_html = (
                f'<span style="color:{color};font-size:12px;font-weight:600;margin-left:8px;">'
                f'{arrow} {abs(delta):.1f}{tag}</span>'
            )
        return (
            '<tr style="border-top:1px solid #1f1f23;">'
              '<td style="padding:12px 0;font-family:\'JetBrains Mono\',monospace;font-weight:600;">'
              f'{t.symbol}{delta_html}'
              '</td>'
              f'<td style="padding:12px 0;text-align:right;color:#10b981;font-weight:600;">{cur:.1f}</td>'
              f'<td style="padding:12px 0;text-align:right;color:#9ca3af;font-size:13px;">{signal}</td>'
            '</tr>'
            f'<tr><td colspan="3" style="padding-bottom:12px;color:#9ca3af;font-size:13px;">{reason}</td></tr>'
        )

    ticker_rows_html = "".join(_ticker_row(t) for t in watchlist_rows)

    squeeze_rows_html = "".join(
        '<tr style="border-top:1px solid #1f1f23;">'
          f'<td style="padding:10px 0;font-family:\'JetBrains Mono\',monospace;font-weight:600;">{s.symbol}</td>'
          f'<td style="padding:10px 0;text-align:right;">{s.spike_score:.0f}</td>'
          f'<td style="padding:10px 0;text-align:right;color:#9ca3af;">{s.suggested_window}</td>'
        '</tr>'
        for s in squeezes
    )
    squeezes_block = ""
    if squeeze_rows_html:
        squeezes_block = (
            '<div style="margin-bottom:24px;">'
            f'<h2 style="font-size:15px;text-transform:uppercase;color:#9ca3af;letter-spacing:0.05em;margin:0 0 8px;">{squeeze_label}</h2>'
            f'<table style="width:100%;border-collapse:collapse;">{squeeze_rows_html}</table>'
            '</div>'
        )

    regime_html = ""
    if regime:
        tone = {
            "BULL": "#10b981", "NEUTRAL": "#3b82f6", "CAUTIOUS": "#eab308", "BEAR": "#ef4444",
        }.get(regime.regime, "#9ca3af")
        regime_html = (
            '<div style="background:#0a0a0a;border-radius:8px;padding:16px;border:1px solid #1f1f23;margin-bottom:24px;">'
            '<div style="font-size:12px;text-transform:uppercase;color:#9ca3af;">Market regime</div>'
            f'<div style="font-size:28px;font-weight:700;color:{tone};margin-top:4px;">{regime.regime}</div>'
            '<div style="color:#9ca3af;font-size:13px;margin-top:6px;">'
            f'VIX {regime.vix:.2f} · 10Y {regime.yield_10y:.2f}% · Breadth {regime.breadth_pct:.0f}%'
            '</div>'
            '</div>'
        )

    return f"""<!doctype html>
<html><body style="font-family:Inter,system-ui,sans-serif;background:#0a0a0a;color:#f4f4f5;padding:24px;margin:0;">
  <div style="max-width:560px;margin:0 auto;background:#121214;border-radius:12px;padding:32px;border:1px solid #1f1f23;">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
      <div style="width:24px;height:8px;border-radius:999px;background:#3b82f6;"></div>
      <strong style="font-size:18px;">Tapeline</strong>
    </div>
    <div style="color:#9ca3af;font-size:13px;margin-bottom:24px;">{date_str} · Morning briefing</div>

    <h1 style="margin:0 0 16px;font-size:22px;">Good morning, {user_name}.</h1>

    {regime_html}

    <div style="margin-bottom:24px;">
      <h2 style="font-size:15px;text-transform:uppercase;color:#9ca3af;letter-spacing:0.05em;margin:0 0 4px;">{ticker_heading}</h2>
      <p style="color:#6b7280;font-size:12px;margin:0 0 8px;">{ticker_sub}</p>
      <table style="width:100%;border-collapse:collapse;">{ticker_rows_html}</table>
    </div>

    {squeezes_block}

    <a href="{cta_href}" style="display:inline-block;background:#3b82f6;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none;font-weight:500;">{cta_label}</a>

    <hr style="border:0;border-top:1px solid #1f1f23;margin:32px 0 16px;">
    <p style="color:#9ca3af;font-size:12px;margin:0;">
      <strong>Not investment advice.</strong> For informational purposes only.
      <a href="https://tapeline.io/app/settings" style="color:#9ca3af;">Unsubscribe</a>
    </p>
  </div>
</body></html>"""


# ---------------------------------------------------------------------------
# Send-all entry point
# ---------------------------------------------------------------------------
async def send_daily_briefing_to_all(session: AsyncSession) -> int:
    """Send this morning's briefing to every Pro/Premium subscriber.

    Each user gets a personalised briefing now (their watchlist) instead of
    the same site-wide content. Falls back to site-wide for users with empty
    watchlists, with a "Add tickers" CTA to drive watchlist adoption.
    """
    result = await session.execute(select(User).where(User.tier.in_(["pro", "premium"])))
    users = result.scalars().all()
    sent = 0
    for u in users:
        try:
            html = await generate_briefing_html(session, u)
            await send_email(u.email, "Your Tapeline briefing", html, persona="alerts")
            sent += 1
        except Exception:
            logger.exception("briefing.send_failed user=%s", u.id)
    logger.info("briefing.sent count=%d", sent)
    return sent
