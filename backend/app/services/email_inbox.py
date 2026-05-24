"""Inbox bot — email channel adapter (Phase B).

Implements the Resend inbound webhook handler + the outbound reply path.
Inbound is driven by `routers/inbox.py:POST /api/inbox/email`; outbound
is `send_email_reply()`, called by `services/inbox_reply.dispatch_reply`.

Resend's inbound webhook receives an HTTP POST whenever an email lands
at any configured address. We've pointed `inbound@tapeline.io` and any
`reply+...@tapeline.io` (via MX records → Resend) at this endpoint.
Each delivery is signed with `RESEND_INBOUND_SECRET` so we can ignore
unsigned junk.

Outbound replies use the existing `services/email.py:send_email` machinery
with `persona="default"` (hello@tapeline.io). The Reply-To header is
`support@tapeline.io` so the conversation thread stays sane regardless
of which persona the bot replied from.

Phase A.6 ships only the adapter scaffold so the dispatcher in
`services/inbox_reply.py` can import without crashing. Phase B fills in
the inbound parsing + HMAC verification + threading details.
"""
from __future__ import annotations

import logging

from app.models import InboundMessage
from app.services.email import send_email

logger = logging.getLogger(__name__)


async def send_email_reply(message: InboundMessage, body: str):
    """Outbound adapter — send `body` as an email reply to `message.author`.

    Imports the shared dataclass lazily to avoid a circular dependency
    (`inbox_reply` imports this module via lazy lookup).
    """
    from app.services.inbox_reply import ReplyResult

    to_addr = (message.author or "").strip()
    if not to_addr or "@" not in to_addr:
        return ReplyResult(sent=False, error=f"invalid_email_addr:{to_addr!r}")

    # Subject: "Re: <original>" if we have one, else a sensible default.
    subject = (
        f"Re: {message.subject}"
        if message.subject and not message.subject.lower().startswith("re:")
        else (message.subject or "Re: your message to Tapeline")
    )

    # Plain-text + minimal HTML. Inbound replies are conversational, not
    # marketing — no design-system shell, no logo banner. Just the body
    # in a readable wrapper so it doesn't render as one wall of text in
    # Gmail's compose-pane preview.
    html = (
        f'<div style="font-family:-apple-system,Segoe UI,Helvetica,sans-serif;'
        f'font-size:14px;line-height:1.55;color:#111;max-width:560px;">'
        f'{body.replace(chr(10), "<br>")}'
        f'</div>'
    )

    try:
        res = await send_email(
            to=to_addr,
            subject=subject,
            html=html,
            text=body,
            persona="default",
        )
    except Exception as exc:
        logger.exception("inbox.email.send_failed to=%s", to_addr)
        return ReplyResult(sent=False, error=f"resend_exception:{type(exc).__name__}:{exc}")

    if res.get("skipped"):
        return ReplyResult(sent=False, error="resend_skipped:no_api_key")

    upstream_id = res.get("id") or res.get("message_id")
    return ReplyResult(sent=True, error=None, upstream_id=upstream_id)


__all__ = ["send_email_reply"]
