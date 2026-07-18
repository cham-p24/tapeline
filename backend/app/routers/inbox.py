"""Inbox auto-handler — channel ingress + founder admin endpoints.

Receives inbound messages from external channels and routes them through
`services/inbox_router.handle_inbound()`, which classifies, persists, and
(for Tier 2) renders an auto-reply.

Endpoints:
  - POST /api/inbox/email           — Resend inbound webhook (Svix-signed)
  - GET  /api/inbox                 — admin list view (founder-only)
  - GET  /api/inbox/stats           — observability (spend / queue / latency)
  - POST /api/inbox/{id}/approve    — founder approval; sends synchronously
  - POST /api/inbox/{id}/reject     — founder rejection (terminal)
  - POST /api/inbox/telegram-update — direct Telegram webhook (see the note
                                      on process_telegram_update — the live
                                      path is the unified webhook in
                                      routers/telegram.py)

Reddit ingress is NOT an HTTP endpoint — it's the internal PRAW poller in
`services/reddit_inbox.py`, driven by the worker tick.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook

from app.config import get_settings
from app.db import get_session
from app.models import InboundMessage, User
from app.services import email as email_service
from app.services import telegram as telegram_service
from app.services.auth import current_user_required
from app.services.inbox_router import (
    find_prescriptive_phrase,
    handle_inbound,
    mark_sent,
    send_tier_1_5_ack,
)
from app.services.inbox_telegram_alert import alert_founder

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


def _verify_resend_signature(
    body: bytes,
    header_signature: str | None,
    svix_id: str | None = None,
    svix_timestamp: str | None = None,
) -> bool:
    """Verify an inbound Resend webhook against `RESEND_INBOUND_SECRET`.

    Two signing schemes exist, and each is verified with the scheme that
    actually matches the header it arrived in:

      * **Svix** (`svix-signature: v1,<base64> [v2,<base64> ...]`) — the
        current Resend scheme. Signed content is
        `<svix-id>.<svix-timestamp>.<body>`, digest base64-encoded, and
        the timestamp carries a replay window. Delegated to the `svix`
        library, same as the Resend deliverability webhook in
        `routers/webhooks.py`.
      * **Legacy** (`resend-signature: sha256=<hex>`) — plain
        HMAC-SHA256 over the raw body, hex-encoded. Constant-time
        compared so a leaky signature can't be timing-attacked.

    The hex digest is never compared against the svix header: their
    encodings differ (`v1,<base64>` vs bare hex), so that comparison
    could never match.

    Fails CLOSED in production: when the secret isn't configured the
    request is REJECTED, so an attacker who guesses the URL can't inject
    a fake inbound email. Outside production (development / staging) an
    unset secret is bypassed so the endpoint stays usable for manual
    testing.
    """
    secret = getattr(settings, "resend_inbound_secret", None)
    if not secret:
        if settings.app_env == "production":
            logger.error(
                "inbox.resend_signature.fail_closed — RESEND_INBOUND_SECRET "
                "unset in production; rejecting unsigned inbound webhook"
            )
            return False
        logger.warning(
            "inbox.resend_signature.dev_bypass — RESEND_INBOUND_SECRET not set"
        )
        return True
    if not header_signature:
        return False
    # Svix headers are a space-separated list of `<version>,<base64>`
    # entries. Anything else is treated as the legacy hex form.
    if any(part.startswith("v1,") for part in header_signature.split()):
        try:
            Webhook(secret).verify(
                body,
                {
                    "svix-id": svix_id or "",
                    "svix-timestamp": svix_timestamp or "",
                    "svix-signature": header_signature,
                },
            )
        except Exception as exc:  # malformed secret raises here too
            logger.warning("inbox.resend_signature.svix_invalid — %s", exc)
            return False
        return True
    expected = hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256,
    ).hexdigest()
    # Legacy header is typically `sha256=<hex>` — accept either form
    sig = header_signature.removeprefix("sha256=").strip()
    return hmac.compare_digest(expected, sig)


@router.post("/email")
async def email_inbound(
    request: Request,
    svix_signature: str | None = Header(None, alias="svix-signature"),
    resend_signature: str | None = Header(None, alias="resend-signature"),
    svix_id: str | None = Header(None, alias="svix-id"),
    svix_timestamp: str | None = Header(None, alias="svix-timestamp"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Resend inbound webhook handler.

    Expected payload (Resend's `email.received` event shape):
        {
          "type": "email.received",
          "data": {
            "message_id": "...",
            "from": "sender@example.com",
            "to": ["inbox@tapeline.io"],
            "subject": "...",
            "text": "...",
            "html": "...",
            "received_at": "2026-05-23T..."
          }
        }
    """
    raw_body = await request.body()
    # Resend may use either `svix-signature` (modern, `v1,<base64>` over
    # id.timestamp.body) or `resend-signature` (older, raw-body hex).
    # Accept either — the verifier picks the matching scheme.
    signature = svix_signature or resend_signature
    if not _verify_resend_signature(
        raw_body, signature, svix_id, svix_timestamp
    ):
        raise HTTPException(401, "Invalid webhook signature")

    payload = await request.json()
    event_type = payload.get("type")
    if event_type != "email.received":
        # Acknowledge other event types (e.g. email.delivered for our
        # own outbound) so Resend doesn't retry, but no-op them.
        return {"ok": True, "skipped": event_type}

    data = payload.get("data") or {}
    message_id = data.get("message_id")
    sender = data.get("from")
    subject = data.get("subject")
    # Prefer plain text; fall back to HTML stripped of tags. Most
    # personal replies are text-only anyway.
    body_text = data.get("text") or _strip_html(data.get("html") or "")
    received_at_raw = data.get("received_at")
    if not message_id or not sender or not body_text:
        raise HTTPException(
            400, "Missing required fields: message_id, from, text/html"
        )

    received_at = _parse_iso8601(received_at_raw)

    result = await handle_inbound(
        session,
        channel="email",
        channel_msg_id=str(message_id),
        author=str(sender),
        body=body_text,
        received_at=received_at,
        subject=subject,
    )

    # If already-handled, the channel adapter shouldn't deliver again.
    if result.already_handled:
        return {
            "ok": True,
            "already_handled": True,
            "tier": result.tier,
        }

    # Tier 2 with rendered template → auto-send the reply email.
    # handle_inbound already optimistically set status='auto_replied'; we
    # only flip it to 'sent' once Resend actually accepts the message.
    if result.tier == 2 and result.auto_reply_text:
        # Publisher-safety guard on the auto-send path too: the ticker_score
        # template interpolates a live API `signal` label we don't control
        # char-for-char. If a banned phrase slips in, do NOT auto-send — leave
        # the row at 'auto_replied' (drafted, not delivered) for founder review.
        banned = find_prescriptive_phrase(result.auto_reply_text)
        if banned is not None:
            logger.warning(
                "inbox.email.auto_reply_blocked_prescriptive msg_id=%d phrase=%r",
                result.message.id, banned,
            )
            await session.commit()
            return {
                "ok": True, "auto_replied": False, "blocked": "prescriptive_language",
                "phrase": banned, "tier": 2, "message_id": result.message.id,
            }
        try:
            res = await email_service.send_email(
                to=sender,
                subject=f"Re: {subject or 'your message'}",
                html=_text_to_html(result.auto_reply_text),
                text=result.auto_reply_text,
                persona="default",
            )
        except Exception as e:
            logger.exception("inbox.email.send_failed err=%s", e)
            # No background retry exists. Leave the row at 'auto_replied'
            # (drafted but not delivered) and commit the insert so a Resend
            # webhook redelivery no-ops on idempotency instead of
            # reclassifying. The founder can resend from /app/inbox.
            await session.commit()
            return {
                "ok": True, "auto_replied": False, "send_failed": True,
                "tier": 2, "message_id": result.message.id,
            }

        if res.get("skipped"):
            # No API key / undeliverable address — nothing went out, so don't
            # record it as sent. Leave at 'auto_replied' for manual follow-up.
            logger.warning(
                "inbox.email.auto_reply_skipped reason=%s msg_id=%d",
                res.get("reason"), result.message.id,
            )
            await session.commit()
            return {
                "ok": True, "auto_replied": False, "skipped": res.get("reason"),
                "tier": 2, "message_id": result.message.id,
            }

        await mark_sent(session, result.message.id, when=datetime.now(UTC))
        await session.commit()
        logger.info(
            "inbox.email.auto_replied to=%s tier=2 msg_id=%d",
            sender, result.message.id,
        )
        return {
            "ok": True, "auto_replied": True, "tier": 2,
            "message_id": result.message.id,
        }

    # Tier 1 → route to founder via Telegram. Best-effort: failure
    # leaves the message in 'classified' status; the founder will see
    # it on the next /app/inbox visit (Phase E). Status doesn't change
    # here because no reply has gone out yet.
    if result.tier == 1:
        await session.commit()  # commit before sending so the row is queryable
        # Fire the Tier 1.5 auto-ack first ("I'll get back within 24h") so the
        # sender isn't ghosted while the Melbourne founder is asleep, then the
        # founder alert. Both best-effort — neither blocks the row save.
        await send_tier_1_5_ack(result.message)
        await alert_founder(result.message)
        return {
            "ok": True,
            "tier": 1,
            "status": result.message.status,
            "message_id": result.message.id,
            "founder_alerted": True,
            "tier_1_5_ack_attempted": True,
        }

    # Tier 3 → ignored.
    await session.commit()
    return {
        "ok": True,
        "tier": result.tier,
        "status": result.message.status,
        "message_id": result.message.id,
    }


# --- Admin endpoints (Phase E) ---------------------------------------------

def _require_admin(user: User) -> None:
    """The /app/inbox surface is founder-only — every inbound message is
    sensitive (real DMs, real emails). Non-admins get 403 even if they
    somehow auth into the page."""
    if not getattr(user, "is_admin", False):
        raise HTTPException(403, "Inbox is admin-only")


class InboxListItem(BaseModel):
    id: int
    channel: str
    author: str
    subject: str | None
    body_preview: str
    received_at: str
    tier: int | None
    tier_reason: str | None
    suggested_reply: str | None
    status: str
    handled_at: str | None


class ReplyBody(BaseModel):
    reply_text: str = Field(min_length=1, max_length=4000)


@router.get("/stats")
async def inbox_stats(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user_required),
) -> dict[str, Any]:
    """Observability for the inbox bot — daily spend, classification
    volume, tier/channel distribution, latency percentiles, cache hit
    rate, and queue depth.

    Founder reads this to verify:
      - LLM spend is under the daily cap (otherwise the bot has
        silently downgraded to manual review for everything)
      - Tier mix looks right (Tier 3 dominating = classifier too
        spam-trigger-happy; Tier 1 dominating = too cautious)
      - p95 latency hasn't crept past Telegram's 5s webhook timeout
      - Cache hit rate is high (cached_tokens / input_tokens; should
        be ~0.95 on a warm prompt cache, ~0.0 if the cache_control
        header isn't reaching the API for some reason)

    Cheap to call (4-5 cheap aggregates); polls every 30s from the
    admin UI without straining the DB.
    """
    from datetime import timedelta

    from app.config import get_settings
    from app.models import InboxClassificationLog
    from app.services import inbox_kill_switch

    _require_admin(user)
    settings = get_settings()
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=6)
    day_start = now - timedelta(hours=24)

    # Daily spend SUM(cost_usd) + classification count for today.
    spend_today_row = (await session.execute(
        select(
            func.coalesce(func.sum(InboxClassificationLog.cost_usd), 0),
            func.count(InboxClassificationLog.id),
        ).where(InboxClassificationLog.created_at >= today_start)
    )).one()
    today_spend_usd = float(spend_today_row[0] or 0)
    today_classifications = int(spend_today_row[1] or 0)

    cap_usd = float(settings.inbox_claude_daily_cap_usd)
    cap_tripped = await inbox_kill_switch.cap_exceeded(session)

    # LLM error/failure surfacing. classify_with_llm logs every failed
    # Anthropic call (timeout, 401 on a dead key, parse failure, …) to
    # inbox_classification_log with a non-null `error` and falls back to a
    # Tier-1 manual-review default — silently. On the $0-Anthropic-credit
    # incident EVERY call 401'd but the bot looked "up" because tier counts
    # kept moving. Surface a 24h error count + last-error timestamp so the
    # operator strip turns red the moment classification starts failing.
    error_row = (await session.execute(
        select(
            func.count(InboxClassificationLog.id),
            func.max(InboxClassificationLog.created_at),
        ).where(
            InboxClassificationLog.created_at >= day_start,
            InboxClassificationLog.error.isnot(None),
        )
    )).one()
    llm_errors_24h = int(error_row[0] or 0)
    last_error_at = error_row[1].isoformat() if error_row[1] else None

    # Error RATE over the same 24h window: how many of the LLM-attempted
    # classifications failed. A high rate (→ 1.0) means the LLM path is broadly
    # broken even if absolute volume is low. We count only rows that actually
    # attempted a model call (model name starts with 'claude-') as the
    # denominator — the rule-based / cap-exceeded / no-api-key short-circuits
    # never hit the API, so including them would mask the failure rate.
    llm_attempts_24h = int((await session.execute(
        select(func.count(InboxClassificationLog.id)).where(
            InboxClassificationLog.created_at >= day_start,
            InboxClassificationLog.model.like("claude-%"),
        )
    )).scalar_one() or 0)
    llm_error_rate = (llm_errors_24h / llm_attempts_24h) if llm_attempts_24h > 0 else 0.0

    # Tier counts today + last 7 days (group by tier).
    async def _tier_counts(since: datetime) -> dict[str, int]:
        rows = (await session.execute(
            select(
                InboundMessage.tier, func.count(InboundMessage.id),
            )
            .where(InboundMessage.received_at >= since)
            .group_by(InboundMessage.tier)
        )).all()
        out = {"1": 0, "2": 0, "3": 0, "unclassified": 0}
        for tier, n in rows:
            key = str(tier) if tier in (1, 2, 3) else "unclassified"
            out[key] = int(n or 0)
        return out

    tier_counts_today = await _tier_counts(today_start)
    tier_counts_7d = await _tier_counts(week_start)

    # Channel counts today.
    channel_rows = (await session.execute(
        select(InboundMessage.channel, func.count(InboundMessage.id))
        .where(InboundMessage.received_at >= today_start)
        .group_by(InboundMessage.channel)
    )).all()
    channel_counts_today = {str(ch): int(n or 0) for ch, n in channel_rows}

    # Status counts today.
    status_rows = (await session.execute(
        select(InboundMessage.status, func.count(InboundMessage.id))
        .where(InboundMessage.received_at >= today_start)
        .group_by(InboundMessage.status)
    )).all()
    status_counts_today = {str(s): int(n or 0) for s, n in status_rows}

    # Latency percentiles + cache-hit ratio over the last 24h. We pull the
    # raw values and compute percentiles in Python because SQLite doesn't
    # ship percentile_cont. The 24h window is small enough that a list
    # comprehension is fine.
    latency_rows = (await session.execute(
        select(
            InboxClassificationLog.latency_ms,
            InboxClassificationLog.input_tokens,
            InboxClassificationLog.cached_tokens,
        ).where(
            InboxClassificationLog.created_at >= day_start,
            InboxClassificationLog.latency_ms.isnot(None),
        )
    )).all()

    latencies = sorted(int(r[0]) for r in latency_rows if r[0] is not None)
    p50_ms: int | None = None
    p95_ms: int | None = None
    if latencies:
        p50_ms = latencies[len(latencies) // 2]
        # Index for p95 — floor((n-1) * 0.95). Safe for n=1 (returns idx 0).
        p95_ms = latencies[int((len(latencies) - 1) * 0.95)]

    total_input = sum(int(r[1] or 0) for r in latency_rows)
    total_cached = sum(int(r[2] or 0) for r in latency_rows)
    cache_hit_ratio = (total_cached / total_input) if total_input > 0 else 0.0

    # Pending queue depth — messages awaiting founder attention OR awaiting
    # auto-reply delivery (status='new' or 'classified').
    pending_count = int((await session.execute(
        select(func.count(InboundMessage.id))
        .where(InboundMessage.status.in_(("new", "classified")))
    )).scalar_one() or 0)

    return {
        "today_spend_usd": round(today_spend_usd, 4),
        "today_classifications": today_classifications,
        "cap_usd": cap_usd,
        "cap_tripped": bool(cap_tripped),
        # LLM health — non-zero llm_errors_24h means classification calls are
        # failing and the bot has silently degraded to manual-review-everything.
        "llm_errors_24h": llm_errors_24h,
        "llm_attempts_24h": llm_attempts_24h,
        "llm_error_rate": round(llm_error_rate, 3),
        "last_error_at": last_error_at,
        "tier_counts_today": tier_counts_today,
        "tier_counts_last_7d": tier_counts_7d,
        "channel_counts_today": channel_counts_today,
        "status_counts_today": status_counts_today,
        "latency_p50_ms": p50_ms,
        "latency_p95_ms": p95_ms,
        "cache_hit_ratio": round(cache_hit_ratio, 3),
        "pending_count": pending_count,
        "bot_enabled": inbox_kill_switch.bot_enabled(),
        "dry_run": inbox_kill_switch.dry_run(),
        "now": now.isoformat(),
    }


@router.get("")
async def list_inbox(
    status_filter: str | None = None,
    channel: str | None = None,
    tier: int | None = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user_required),
) -> dict[str, Any]:
    """List recent inbound messages, newest first. Founder-only.

    Filters are AND-combined. `status_filter` is a comma-separated list
    so the UI can show "active queue" (new + classified) vs "history".
    """
    _require_admin(user)
    stmt = select(InboundMessage).order_by(desc(InboundMessage.received_at))
    if status_filter:
        allowed = [s.strip() for s in status_filter.split(",") if s.strip()]
        stmt = stmt.where(InboundMessage.status.in_(allowed))
    if channel:
        stmt = stmt.where(InboundMessage.channel == channel)
    if tier is not None:
        stmt = stmt.where(InboundMessage.tier == tier)
    stmt = stmt.limit(min(max(limit, 1), 500))
    rows = (await session.execute(stmt)).scalars().all()

    items = [
        InboxListItem(
            id=m.id,
            channel=m.channel,
            author=m.author,
            subject=m.subject,
            body_preview=(m.body[:400] + "…") if m.body and len(m.body) > 400 else (m.body or ""),
            received_at=m.received_at.isoformat() if m.received_at else "",
            tier=m.tier,
            tier_reason=m.tier_reason,
            suggested_reply=m.suggested_reply,
            status=m.status,
            handled_at=m.handled_at.isoformat() if m.handled_at else None,
        ).model_dump()
        for m in rows
    ]
    return {"items": items, "count": len(items)}


async def _approve_core(
    session: AsyncSession,
    message_id: int,
    reply_text: str | None,
) -> dict[str, Any]:
    """Shared approve logic — used by both the web UI endpoint and the
    Telegram bot callback handler. Sends the reply synchronously on the
    message's own channel, then marks it 'sent'. Returns a dict the
    caller can forward as JSON / log / format.

    On a send failure (or a skipped email) the row is left at
    status='approved', NOT 'sent' — so re-approving from the UI or
    Telegram simply retries delivery. There is no background drain."""
    row = (await session.execute(
        select(InboundMessage).where(InboundMessage.id == message_id)
    )).scalar_one_or_none()
    if row is None:
        return {"ok": False, "error": "not_found"}
    if row.status == "sent":
        return {"ok": True, "already_sent": True, "id": row.id}

    final_reply = reply_text or row.suggested_reply
    if not final_reply:
        return {"ok": False, "error": "no_reply_text"}

    # Publisher-safety guard — last line of defence before the wire. Refuse to
    # send any reply containing prescriptive advice language ("buy"/"sell"/
    # "you should"/...), even one the founder one-tap-approved, because an
    # LLM-drafted suggested_reply can drift off the system-prompt voice rules.
    # Fail CLOSED: leave the row untouched (status unchanged) so a human edits
    # and re-submits a clean reply rather than the bot shipping advice.
    banned = find_prescriptive_phrase(final_reply)
    if banned is not None:
        logger.warning(
            "inbox.approve.blocked_prescriptive id=%d phrase=%r", row.id, banned,
        )
        return {
            "ok": False, "error": "prescriptive_language",
            "phrase": banned, "id": row.id,
        }

    row.suggested_reply = final_reply
    row.status = "approved"

    # Deliver synchronously on the inbound channel. Each branch returns a
    # failure dict (leaving status='approved' for a retry) or falls through
    # to mark_sent on success. Routing mirrors inbox_router.send_tier_1_5_ack.
    try:
        if row.channel == "email":
            res = await email_service.send_email(
                to=row.author,
                subject=f"Re: {row.subject or 'your message'}",
                html=_text_to_html(final_reply),
                text=final_reply,
                persona="default",
            )
            if res.get("skipped"):
                await session.commit()
                return {
                    "ok": False, "error": "send_skipped",
                    "reason": res.get("reason"), "id": row.id,
                }
        elif row.channel in ("reddit_comment", "reddit_dm"):
            from app.services.reddit_inbox import send_reddit_reply
            ok = await send_reddit_reply(row, final_reply)
            if not ok:
                await session.commit()
                return {"ok": False, "error": "send_failed", "id": row.id, "channel": row.channel}
        elif row.channel == "telegram":
            ok = await telegram_service.send_message(row.author, final_reply)
            if not ok:
                await session.commit()
                return {"ok": False, "error": "send_failed", "id": row.id, "channel": row.channel}
        else:
            await session.commit()
            return {"ok": False, "error": "unsupported_channel", "channel": row.channel, "id": row.id}
    except Exception as e:
        logger.exception("inbox.approve.send_failed id=%d channel=%s err=%s", row.id, row.channel, e)
        await session.commit()
        return {"ok": False, "error": "send_failed", "id": row.id, "channel": row.channel}

    await mark_sent(session, row.id, when=datetime.now(UTC))
    await session.commit()

    # Edit the Telegram alert card in place to show "✅ Approved · sent"
    # so the founder doesn't have to remember which Tier 1s they've
    # handled. Best-effort: failure leaves the card unchanged but the
    # approve itself stays committed.
    try:
        from app.services.inbox_telegram_alert import edit_card_to_done
        await edit_card_to_done(row, action="approved", sent_reply=final_reply)
    except Exception:
        logger.exception("inbox.approve.card_edit_failed id=%d", row.id)

    return {"ok": True, "id": row.id, "status": "sent"}


async def _reject_core(
    session: AsyncSession,
    message_id: int,
) -> dict[str, Any]:
    """Shared reject logic — see _approve_core for the pattern."""
    row = (await session.execute(
        select(InboundMessage).where(InboundMessage.id == message_id)
    )).scalar_one_or_none()
    if row is None:
        return {"ok": False, "error": "not_found"}
    if row.status in ("sent", "ignored"):
        return {"ok": True, "already_final": True, "id": row.id}
    row.status = "ignored"
    row.handled_at = datetime.now(UTC)
    await session.commit()

    # Edit the alert card in place to show "🗑️ Rejected" — same UX
    # affordance as approve. Best-effort; the rejection itself stays
    # committed regardless.
    try:
        from app.services.inbox_telegram_alert import edit_card_to_done
        await edit_card_to_done(row, action="rejected")
    except Exception:
        logger.exception("inbox.reject.card_edit_failed id=%d", row.id)

    return {"ok": True, "id": row.id, "status": "ignored"}


@router.post("/{message_id}/approve")
async def approve_message(
    message_id: int,
    body: ReplyBody | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user_required),
) -> dict[str, Any]:
    """Approve + send a Tier 1 reply. If `body.reply_text` is provided
    it overrides the LLM-drafted suggested_reply (the 'edit' flow).
    Sends via the channel-appropriate adapter."""
    _require_admin(user)
    result = await _approve_core(
        session, message_id, body.reply_text if body else None,
    )
    if result.get("error") == "not_found":
        raise HTTPException(404, "Message not found")
    if result.get("error") == "no_reply_text":
        raise HTTPException(400, "No reply_text provided and no suggested_reply on record")
    return result


@router.post("/{message_id}/reject")
async def reject_message(
    message_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user_required),
) -> dict[str, Any]:
    """Mark a Tier 1 message as rejected — founder decided not to reply.
    No external send happens. Status is terminal."""
    _require_admin(user)
    result = await _reject_core(session, message_id)
    if result.get("error") == "not_found":
        raise HTTPException(404, "Message not found")
    return result


# --- Telegram bot webhook dispatch -----------------------------------------

async def process_telegram_update(
    payload: dict[str, Any],
    session: AsyncSession,
) -> dict[str, Any] | None:
    """Dispatch a Telegram update to the inbox approve/reject logic.

    Returns a result dict when the update WAS an inbox action — an inline
    button tap (`callback_data="inbox:approve:42"` / `"inbox:reject:42"`)
    or a founder `/approve_<id>` / `/reject_<id>` command — or None when it
    wasn't, letting the caller fall through to its own handling (the
    `/start` account-link flow in routers/telegram.py).

    Telegram delivers updates to only ONE webhook URL per bot, so this is
    invoked from the single registered webhook (routers/telegram.py)
    rather than being reachable on its own path. The CALLER is responsible
    for verifying the request actually came from Telegram (path or header
    secret); this function performs no auth itself.

    Only the founder's chat_id (`INBOX_FOUNDER_TELEGRAM_CHAT_ID`) may
    trigger actions. Non-founder messages return None (so they still get
    the link-flow reply); non-founder button taps are acked but no-op'd.
    """
    founder_chat_id = settings.inbox_founder_telegram_chat_id

    def _is_unauthorised(sender_chat_id: str) -> bool:
        # Fail CLOSED in production: an unset founder chat id means nobody is
        # authorised, so every approve/command action is rejected (an attacker
        # who reaches the webhook can't self-approve). Outside production an
        # unset id stays permissive for local testing.
        if not founder_chat_id:
            return settings.app_env == "production"
        return sender_chat_id != founder_chat_id

    # --- Callback query (inline-button tap) ---
    cb = payload.get("callback_query")
    if cb:
        cb_id = cb.get("id")
        from_user = (cb.get("from") or {})
        from_chat_id = str(from_user.get("id") or "")
        data = cb.get("data") or ""
        message_obj = cb.get("message") or {}
        original_message_id = message_obj.get("message_id")
        original_chat_id = str((message_obj.get("chat") or {}).get("id") or "")

        if _is_unauthorised(from_chat_id):
            # Not the founder — ack the button so they don't see a
            # forever-spinner, but don't action anything.
            await telegram_service.answer_callback_query(
                cb_id, "Not authorised."
            )
            return {"ok": True, "ignored": "non_founder", "from": from_chat_id}

        parts = data.split(":")
        if len(parts) != 3 or parts[0] != "inbox":
            await telegram_service.answer_callback_query(cb_id, "Unknown action.")
            return {"ok": True, "ignored": "unknown_callback", "data": data}

        action = parts[1]
        try:
            msg_id = int(parts[2])
        except ValueError:
            await telegram_service.answer_callback_query(cb_id, "Bad message id.")
            return {"ok": True, "ignored": "bad_id"}

        if action == "approve":
            result = await _approve_core(session, msg_id, reply_text=None)
            if result.get("ok"):
                ack = "Sent ✓"
                edit_text = f"✅ <b>Sent</b>\n\nMessage #{msg_id} delivered."
            else:
                ack = f"Failed: {result.get('error', 'unknown')}"
                edit_text = f"⚠️ <b>Approve failed</b>\n\nMessage #{msg_id}: {result.get('error')}"
        elif action == "reject":
            result = await _reject_core(session, msg_id)
            if result.get("ok"):
                ack = "Rejected ✓"
                edit_text = f"❌ <b>Rejected</b>\n\nMessage #{msg_id} ignored."
            else:
                ack = f"Failed: {result.get('error', 'unknown')}"
                edit_text = f"⚠️ <b>Reject failed</b>\n\nMessage #{msg_id}: {result.get('error')}"
        else:
            await telegram_service.answer_callback_query(cb_id, "Unknown action.")
            return {"ok": True, "ignored": "unknown_action", "action": action}

        # Ack the button (clears the loading spinner) and update the
        # original card to show the final state.
        await telegram_service.answer_callback_query(cb_id, ack)
        if original_message_id and original_chat_id:
            await telegram_service.edit_message_text(
                original_chat_id, original_message_id, edit_text,
            )
        return {"ok": True, "action": action, "msg_id": msg_id, "result": result}

    # --- Message (text command) ---
    # Only claim founder /approve_<id> & /reject_<id> commands. Everything
    # else — including /start <token> account-linking and stray DMs —
    # returns None so the caller's link-flow handles it.
    message = payload.get("message")
    if message:
        text = (message.get("text") or "").strip()
        from_chat_id = str((message.get("from") or {}).get("id") or "")
        if _is_unauthorised(from_chat_id):
            return None

        # Match /approve_42 or /reject_42.
        import re as _re
        m = _re.match(r"^/(approve|reject)_(\d+)\b", text)
        if not m:
            return None

        action, msg_id = m.group(1), int(m.group(2))
        if action == "approve":
            result = await _approve_core(session, msg_id, reply_text=None)
        else:
            result = await _reject_core(session, msg_id)

        await telegram_service.send_message(
            from_chat_id,
            f"{'✅' if result.get('ok') else '⚠️'} `{action} {msg_id}`: {result}",
        )
        return {"ok": True, "via": "command", "result": result}

    return None


@router.post("/telegram-update")
async def telegram_update(
    request: Request,
    secret_header: str | None = Header(None, alias="x-telegram-bot-api-secret-token"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Direct Telegram webhook endpoint (header-secret gated).

    NOTE: in production Telegram points at the single unified webhook in
    routers/telegram.py (`/api/telegram/webhook/{secret}`), which calls
    `process_telegram_update()` for us — Telegram supports only one
    webhook URL per bot. This endpoint is retained for direct/manual
    testing and as a fallback if the webhook is ever pointed here.
    """
    expected_secret = settings.telegram_webhook_secret
    if expected_secret and secret_header != expected_secret:
        raise HTTPException(401, "Invalid Telegram webhook secret")

    payload = await request.json()
    result = await process_telegram_update(payload, session)
    return result if result is not None else {"ok": True, "ignored": "no_inbox_action"}


# --- helpers ----------------------------------------------------------------

def _parse_iso8601(value: str | None) -> datetime:
    """Parse the Resend received_at string, falling back to now()."""
    if not value:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.now(UTC)


def _strip_html(html: str) -> str:
    """Minimal HTML → text. Not a full parser — Resend's text field is
    usually populated and this is the fallback. Keeps newlines for
    paragraph breaks but drops everything else."""
    import re as _re
    no_tags = _re.sub(r"<[^>]+>", "", html)
    return _re.sub(r"[ \t]+", " ", no_tags).strip()


def _text_to_html(text: str) -> str:
    """Wrap plain text reply in minimal HTML so Resend renders it
    cleanly in clients that prefer HTML. Single-paragraph; no styling."""
    import html as _html
    escaped = _html.escape(text)
    return f"<div style=\"font-family: -apple-system, sans-serif; font-size: 14px; line-height: 1.5; color: #1d1d1f;\"><p>{escaped}</p></div>"
