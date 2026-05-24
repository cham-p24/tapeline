"""Inbox bot — reply templates + dispatcher.

For Tier 2 messages, this is the WHOLE reply path: pick a deterministic
template, fill in any live data (ticker scores), and hand off to the
channel adapter. For Tier 1, the founder approves a draft via Telegram
and THIS module is what actually sends it once approved.

Hard rules (also baked into the system prompt for the LLM):
  - First-person founder voice ("I built Tapeline because...", not "we")
  - Unsigned (no "— Christian" / "— Chamara" — the reply body IS the voice)
  - Descriptive language only ("constructive setup", "high conviction",
    "weak") — never "buy" / "sell" / "you should". Australian publisher-
    exemption posture from AFSL depends on this.
  - Tight: 2-4 sentences for Tier 1; one clean paragraph for Tier 2

Templates are HARDCODED functions, NOT LLM calls. Burning tokens on
"what's the score for $NVDA" — a deterministic answer — would be silly.
Only Tier 1 drafting goes through the LLM.

Tier 1.5 auto-acknowledgement
─────────────────────────────
Founder is in Melbourne — US-business-hours inbounds sit overnight before
he can approve. To stop Tier 1 senders feeling ghosted, the Tier 1 routing
fires an immediate "Thanks — I'll get back to you within 24h" auto-ack
through the same channel. The full draft still queues for approval.
Toggled via `INBOX_TIER1_AUTO_ACK` (default on).

Dispatcher contract
───────────────────
`dispatch_reply(message, body)` is channel-agnostic — it looks at
`message.channel` and routes to the right adapter. Adapters live in
the channel-specific service modules (`reddit_inbox.py`, `email_inbox.py`,
`telegram_inbox.py`) and accept `(message: InboundMessage, body: str)`.
Each returns a `ReplyResult(sent: bool, error: str | None)`.

`status` + `handled_at` are updated by `dispatch_reply`, NOT by the
adapter, so the state machine stays in one place.

Dry-run mode (`INBOX_DRY_RUN=true`) intercepts at the dispatch layer:
classification + DB writes still happen, but the adapter call is
replaced with a log line ("would have sent: ..."). Use this to shadow
the bot for a week before going live.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import InboundMessage, Ticker
from app.services import inbox_kill_switch
from app.services.inbox_classifier import TICKER_RE

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReplyResult:
    sent: bool
    error: str | None = None
    # Upstream message id where the reply was posted. Reddit gives back
    # `t1_xyz`, Telegram gives back the new message_id; email gives back
    # the Resend submission id. Used for spot-checking + linking from
    # the admin UI.
    upstream_id: str | None = None


# ── Templates ───────────────────────────────────────────────────────────────

def render_ticker_score(symbol: str, ticker: Ticker | None) -> str:
    """Tier 2 template for "what's the score for $TICKER" questions.

    Pulls the live score + 6-factor breakdown from the Ticker row that
    the worker keeps fresh every tick. When the ticker isn't in the
    universe (delisted, typo, futures), returns a polite "not in the
    universe" message that doesn't pretend to know anything.

    Voice rule reminder: descriptive only. "currently scores X/100" is
    fine; "you should buy" is not. The (HIGH CONVICTION) label is
    descriptive — see `services/sheet_feed.score_to_signal` for why.
    """
    sym = symbol.upper().lstrip("$")
    if ticker is None or ticker.score is None:
        return (
            f"${sym} isn't in the Tapeline universe right now — could be a "
            f"delisted name, a futures contract (not covered by the Starter "
            f"tier data feed), or a ticker that just hasn't been picked up "
            f"by the discovery worker yet. Drop a different symbol and I'll "
            f"pull its breakdown."
        )

    # Build the 6-factor line. Each sub-score may be null if the underlying
    # feed didn't return data; skip nulls instead of printing "None".
    parts: list[str] = []
    for label, value in [
        ("Trend",        ticker.sub_trend),
        ("RS",           ticker.sub_rs),
        ("Fundamentals", ticker.sub_fundamentals),
        ("Smart Money",  ticker.sub_smart_money),
        ("Macro",        ticker.sub_macro),
        ("Momentum",     ticker.sub_momentum),
    ]:
        if value is not None:
            parts.append(f"{label} {value:.0f}")
    breakdown = " · ".join(parts) if parts else "(sub-scores still loading)"

    signal_label = ticker.signal or "no signal"

    return (
        f"${sym} currently scores {ticker.score:.1f}/100 ({signal_label}). "
        f"Breakdown: {breakdown}. "
        f"Full chart + factor history at https://tapeline.io/t/{sym}. "
        f"Drop another ticker if you want me to pull it."
    )


def render_pricing() -> str:
    """Tier 2 template for "how does pricing work" / "what does it cost"."""
    return (
        "Three tiers. Free covers the top 20 tickers (24h delayed) plus the "
        "public scorecard and a 5-ticker watchlist. Pro is $24.99/mo billed "
        "annually ($29.99 monthly) for the full ~2,500-ticker live scan, "
        "smart watchlist alerts, squeeze + regime, daily briefing. Premium "
        "is $39.99/mo billed annually ($49.99 monthly) for everything in Pro "
        "plus congressional trades, insider Form 4 buys, unlimited Telegram "
        "alerts, and a 200-ticker watchlist. Every signup gets 14 days of "
        "Premium free, no card. tapeline.io/pricing has the full comparison."
    )


def render_trial() -> str:
    """Tier 2 template for "is there a free trial" / "can I try premium"."""
    return (
        "Yep — every signup gets 14 days of Premium free, no card required. "
        "tapeline.io/signup gets you in. Full ~2,500-ticker universe, the "
        "live scorecard, watchlist alerts, congressional + insider feeds, "
        "all unlocked for the trial window. At day 14 it drops to Free "
        "automatically if you haven't added a card."
    )


def render_thanks() -> str:
    """Tier 2 template for generic positive sentiment with no question."""
    return (
        "Thanks for the kind words. If you want to put it through its paces, "
        "drop a ticker and I'll send you its current score plus the 6-factor "
        "breakdown — the formula's public at tapeline.io/how-it-works."
    )


def render_tier_1_5_ack() -> str:
    """Tier 1.5 — sent immediately when a Tier 1 inbound classifies, so
    the sender isn't ghosted while the founder is asleep.

    Deliberately vague on timing ("within 24h") rather than promising a
    specific reply window we can't always meet. Voice rule: still
    descriptive, still first-person, still unsigned.
    """
    return (
        "Thanks for reaching out — I've got this in my queue and will reply "
        "within 24h. Tapeline is solo so I read every message myself, but "
        "the response time depends on time zones (I'm in Melbourne)."
    )


# Template key → renderer for the deterministic Tier 2 path. The classifier
# emits one of these keys; the dispatcher looks up the renderer here.
#
# `ticker_score` is special-cased in `render_template_for()` because it
# needs the symbol extracted from the body + a DB lookup.
_TEMPLATE_RENDERERS: dict[str, Callable[[], str]] = {
    "pricing":  render_pricing,
    "trial":    render_trial,
    "thanks":   render_thanks,
}


async def render_template_for(
    template_key: str,
    body: str,
    session: AsyncSession,
) -> str | None:
    """Resolve a template_key (from the classifier) into the rendered
    reply body. Returns None if the key is unknown — caller should fall
    through to Tier 1 manual review rather than send something
    half-baked."""
    if template_key == "ticker_score":
        # Extract the first cashtag from the body. If none, the classifier
        # made a mistake — fall through to manual review.
        m = TICKER_RE.search(body)
        if m is None:
            logger.warning(
                "inbox.template.ticker_score_no_cashtag body=%s", body[:120],
            )
            return None
        symbol = m.group(1).upper()
        ticker = await session.get(Ticker, symbol)
        return render_ticker_score(symbol, ticker)

    renderer = _TEMPLATE_RENDERERS.get(template_key)
    if renderer is None:
        logger.warning("inbox.template.unknown key=%s", template_key)
        return None
    return renderer()


# ── Adapter registry ────────────────────────────────────────────────────────
#
# Channel name → async adapter. Each adapter takes the InboundMessage +
# the rendered reply body, performs the actual upstream send, and returns
# a ReplyResult. Adapters are imported lazily (string keys) so the
# dispatcher doesn't bring in PRAW / Telegram / Resend at module-load
# time — important for the test suite, which mocks individual channels.

ChannelKey = Literal[
    "reddit_comment", "reddit_dm", "reddit_mention",
    "email", "telegram",
]


async def _adapter_for(channel: str) -> Callable[[InboundMessage, str], Awaitable[ReplyResult]]:
    """Look up the async adapter for a channel. Lazy imports so this
    module stays cheap to load and channel modules can be swapped /
    mocked individually."""
    if channel in ("reddit_comment", "reddit_dm", "reddit_mention"):
        from app.services.reddit_inbox import send_reddit_reply
        return send_reddit_reply
    if channel == "email":
        from app.services.email_inbox import send_email_reply
        return send_email_reply
    if channel == "telegram":
        from app.services.telegram_inbox import send_telegram_reply
        return send_telegram_reply
    raise ValueError(f"Unknown inbox channel: {channel!r}")


async def dispatch_reply(
    message: InboundMessage,
    body: str,
    session: AsyncSession,
    *,
    new_status: str = "auto_replied",
) -> ReplyResult:
    """Send `body` as a reply on `message.channel`, update DB state.

    Honours both kill switches:
      - `INBOX_BOT_ENABLED=false`  → no-op, log "skipped: bot disabled"
      - `INBOX_DRY_RUN=true`       → log "would send" + body, no upstream call
      - `INBOX_<CHANNEL>_ENABLED=false` → skip this channel only

    On success, sets `status=new_status`, `handled_at=now()` and commits.
    On failure, leaves status untouched so the next worker tick retries.
    """
    if not inbox_kill_switch.bot_enabled():
        logger.info(
            "inbox.dispatch.skipped reason=bot_disabled msg=%s channel=%s",
            message.id, message.channel,
        )
        return ReplyResult(sent=False, error="bot_disabled")

    if not inbox_kill_switch.channel_enabled(message.channel):
        logger.info(
            "inbox.dispatch.skipped reason=channel_disabled msg=%s channel=%s",
            message.id, message.channel,
        )
        return ReplyResult(sent=False, error=f"channel_disabled:{message.channel}")

    if inbox_kill_switch.dry_run():
        logger.info(
            "inbox.dispatch.dry_run msg=%s channel=%s author=%s body=%s",
            message.id, message.channel, message.author, body[:200],
        )
        message.status = f"dry_run_{new_status}"
        message.handled_at = datetime.now(UTC)
        await session.commit()
        return ReplyResult(sent=True, error=None, upstream_id="dry-run")

    try:
        adapter = await _adapter_for(message.channel)
    except ValueError as exc:
        logger.exception("inbox.dispatch.no_adapter channel=%s", message.channel)
        return ReplyResult(sent=False, error=str(exc))

    try:
        result = await adapter(message, body)
    except Exception as exc:
        logger.exception(
            "inbox.dispatch.adapter_failed msg=%s channel=%s",
            message.id, message.channel,
        )
        return ReplyResult(sent=False, error=f"adapter_exception:{type(exc).__name__}:{exc}")

    if result.sent:
        message.status = new_status
        message.handled_at = datetime.now(UTC)
        await session.commit()
        logger.info(
            "inbox.dispatch.sent msg=%s channel=%s status=%s upstream=%s",
            message.id, message.channel, new_status, result.upstream_id,
        )
    else:
        logger.warning(
            "inbox.dispatch.send_failed msg=%s channel=%s error=%s",
            message.id, message.channel, result.error,
        )
    return result


async def maybe_send_tier_1_5_ack(
    message: InboundMessage, session: AsyncSession,
) -> None:
    """Fire the immediate "I'll get back to you within 24h" auto-ack.

    Called by the routing layer ONLY for Tier 1 inbounds, ONLY when the
    sender hasn't been ack'd before in this conversation. We don't track
    cross-conversation ack history (premature optimisation — Tapeline DM
    volume is low and a duplicate ack is far less bad than a missing one).

    Does NOT change the InboundMessage.status — that stays at 'new' so
    the Tier 1 approval flow can still send the real reply later.
    """
    settings = get_settings()
    # `inbox_tier1_auto_ack_enabled` doesn't exist as a setting yet because
    # the Phase A.5 settings batch was already large. Default-on by reading
    # an env var lazily — promote to a proper Settings field when the
    # config grows again. Setting it to "false" disables the auto-ack.
    import os
    enabled = os.environ.get("INBOX_TIER1_AUTO_ACK", "true").lower() not in (
        "0", "false", "no", "off",
    )
    if not enabled:
        return
    if not inbox_kill_switch.bot_enabled():
        return
    if not inbox_kill_switch.channel_enabled(message.channel):
        return

    body = render_tier_1_5_ack()
    if inbox_kill_switch.dry_run():
        logger.info(
            "inbox.tier1_5_ack.dry_run msg=%s channel=%s body=%s",
            message.id, message.channel, body[:120],
        )
        return

    try:
        adapter = await _adapter_for(message.channel)
        result = await adapter(message, body)
        if result.sent:
            logger.info(
                "inbox.tier1_5_ack.sent msg=%s channel=%s",
                message.id, message.channel,
            )
        else:
            logger.warning(
                "inbox.tier1_5_ack.failed msg=%s channel=%s error=%s",
                message.id, message.channel, result.error,
            )
    except Exception:
        logger.exception(
            "inbox.tier1_5_ack.exception msg=%s channel=%s",
            message.id, message.channel,
        )


async def send_tier_2_auto_reply(
    message: InboundMessage,
    template_key: str,
    session: AsyncSession,
) -> ReplyResult:
    """End-to-end Tier 2 path: render the template, dispatch.

    Status guard — only auto-sends when status is 'new' or 'classified'.
    Already-handled messages are no-ops (idempotent against worker
    re-ticks).
    """
    if message.status not in ("new", "classified"):
        return ReplyResult(
            sent=False, error=f"already_handled:status={message.status}",
        )

    body = await render_template_for(template_key, message.body, session)
    if body is None:
        # Classifier promised a template but we can't render it (unknown
        # key, or ticker_score with no extractable cashtag). Safer to
        # downgrade to Tier 1 manual review than send something wrong.
        logger.warning(
            "inbox.tier2.fallback_to_tier1 msg=%s template=%s",
            message.id, template_key,
        )
        message.tier = 1
        message.tier_reason = (
            f"Tier 2 template '{template_key}' couldn't render — needs founder review"
        )
        await session.commit()
        return ReplyResult(sent=False, error=f"template_render_failed:{template_key}")

    message.suggested_reply = body
    return await dispatch_reply(message, body, session, new_status="auto_replied")


__all__ = [
    "ChannelKey",
    "ReplyResult",
    "dispatch_reply",
    "maybe_send_tier_1_5_ack",
    "render_pricing",
    "render_template_for",
    "render_thanks",
    "render_ticker_score",
    "render_tier_1_5_ack",
    "render_trial",
    "send_tier_2_auto_reply",
]


# ── Channel-adapter shims (Phase A.6) ──────────────────────────────────────
#
# Phases B (email), C (Reddit), D (Telegram) replace each of these with
# the real upstream call. Until then, they log "would send" and report
# success — same as dry-run mode but per-channel — so the rest of the
# pipeline can be built and tested end-to-end.
#
# When the real adapter lands, it OVERWRITES the function in its own
# module; nothing else in the codebase needs to change.

async def _phase_a6_stub_adapter(
    message: InboundMessage, body: str,
) -> ReplyResult:
    """Default Phase A.6 stub used until the channel-specific adapter ships."""
    logger.info(
        "inbox.adapter.stub channel=%s msg=%s author=%s body=%s",
        message.channel, message.id, message.author, body[:200],
    )
    return ReplyResult(sent=True, error=None, upstream_id="stub")
