"""Daily briefing email — scheduled job + template."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RegimeState, SqueezeSetup, Ticker, User
from app.services.email import send_email

logger = logging.getLogger(__name__)


async def generate_briefing_html(session: AsyncSession, user_name: str) -> str:
    """Render today's briefing: regime + top 3 scores + top 3 squeezes."""
    top = await session.execute(
        select(Ticker).where(Ticker.score.isnot(None)).order_by(desc(Ticker.score)).limit(3)
    )
    top_tickers = top.scalars().all()

    sq = await session.execute(
        select(SqueezeSetup).order_by(desc(SqueezeSetup.spike_score)).limit(3)
    )
    top_squeezes = sq.scalars().all()

    regime_result = await session.execute(select(RegimeState).where(RegimeState.id == 1))
    regime = regime_result.scalar_one_or_none()

    date_str = datetime.now(UTC).strftime("%A, %B %d, %Y")

    def _row(sym, score, signal, reason):
        return f"""
        <tr style="border-top:1px solid #1f1f23;">
          <td style="padding:12px 0;font-family:'JetBrains Mono',monospace;font-weight:600;">{sym}</td>
          <td style="padding:12px 0;text-align:right;color:#10b981;font-weight:600;">{score:.1f}</td>
          <td style="padding:12px 0;text-align:right;color:#9ca3af;font-size:13px;">{signal}</td>
        </tr>
        <tr><td colspan="3" style="padding-bottom:12px;color:#9ca3af;font-size:13px;">{reason or ''}</td></tr>
        """

    top_rows = "".join(
        _row(t.symbol, t.score or 0, t.signal or "", t.reason or "") for t in top_tickers
    )
    squeeze_rows = "".join(
        f"""<tr style="border-top:1px solid #1f1f23;">
              <td style="padding:10px 0;font-family:'JetBrains Mono',monospace;font-weight:600;">{s.symbol}</td>
              <td style="padding:10px 0;text-align:right;">{s.spike_score:.0f}</td>
              <td style="padding:10px 0;text-align:right;color:#9ca3af;">{s.suggested_window}</td>
            </tr>""" for s in top_squeezes
    )

    regime_html = ""
    if regime:
        tone = {
            "BULL": "#10b981", "NEUTRAL": "#3b82f6", "CAUTIOUS": "#eab308", "BEAR": "#ef4444",
        }.get(regime.regime, "#9ca3af")
        regime_html = f"""
        <div style="background:#0a0a0a;border-radius:8px;padding:16px;border:1px solid #1f1f23;margin-bottom:24px;">
          <div style="font-size:12px;text-transform:uppercase;color:#9ca3af;">Market regime</div>
          <div style="font-size:28px;font-weight:700;color:{tone};margin-top:4px;">{regime.regime}</div>
          <div style="color:#9ca3af;font-size:13px;margin-top:6px;">
            VIX {regime.vix:.2f} · 10Y {regime.yield_10y:.2f}% · Breadth {regime.breadth_pct:.0f}%
          </div>
        </div>"""

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
      <h2 style="font-size:15px;text-transform:uppercase;color:#9ca3af;letter-spacing:0.05em;margin:0 0 8px;">Top 3 by composite score</h2>
      <table style="width:100%;border-collapse:collapse;">{top_rows}</table>
    </div>

    <div style="margin-bottom:24px;">
      <h2 style="font-size:15px;text-transform:uppercase;color:#9ca3af;letter-spacing:0.05em;margin:0 0 8px;">Squeeze setups</h2>
      <table style="width:100%;border-collapse:collapse;">{squeeze_rows}</table>
    </div>

    <a href="https://tapeline.io/app/scanner" style="display:inline-block;background:#3b82f6;color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none;font-weight:500;">Open scanner &rarr;</a>

    <hr style="border:0;border-top:1px solid #1f1f23;margin:32px 0 16px;">
    <p style="color:#9ca3af;font-size:12px;margin:0;">
      <strong>Not investment advice.</strong> For informational purposes only.
      <a href="https://tapeline.io/app/settings" style="color:#9ca3af;">Unsubscribe</a>
    </p>
  </div>
</body></html>"""


async def send_daily_briefing_to_all(session: AsyncSession) -> int:
    """Send this morning's briefing to every Pro/Premium subscriber."""
    result = await session.execute(select(User).where(User.tier.in_(["pro", "premium"])))
    users = result.scalars().all()
    sent = 0
    for u in users:
        try:
            html = await generate_briefing_html(session, u.name or "trader")
            await send_email(u.email, "Your Tapeline briefing", html)
            sent += 1
        except Exception:
            logger.exception("briefing.send_failed user=%s", u.id)
    logger.info("briefing.sent count=%d", sent)
    return sent
