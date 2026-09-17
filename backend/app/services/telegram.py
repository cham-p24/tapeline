"""Telegram delivery — the Bot API primitives plus the real-time founder
alerts (which fall back to email when Telegram is unset) and the inbox
Approve/Reject card helpers."""
from __future__ import annotations

import enum
import logging
import re
from datetime import datetime

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

TG_API = "https://api.telegram.org"

#: Printed in place of a chat id. These logs reach GitHub Actions run logs on a
#: PUBLIC repository (stale-link-audit.yml, seo-weekly-digest.yml), so a failed
#: send must not print the founder's chat id, or anything that can echo it.
REDACTED = "<redacted>"

# A run of 5+ digits in Telegram's error text could be a chat id, a user id, or
# the numeric half of a bot token ("123456789:AA..."). None of them is needed to
# diagnose a failure.
_LONG_NUMBER = re.compile(r"\d{5,}")


def _failure_detail(r: httpx.Response, chat_id: object) -> str:
    """Telegram's `description` for a failed call, with anything that could
    identify the chat or the bot removed. Never the raw body."""
    try:
        description = str((r.json() or {}).get("description") or "")
    except Exception:
        return "unparseable"
    for secret in (str(chat_id), settings.telegram_bot_token or ""):
        if secret:
            description = description.replace(secret, REDACTED)
    return _LONG_NUMBER.sub(REDACTED, description)[:200]


class SendStatus(enum.Enum):
    DELIVERED = "delivered"
    SKIPPED = "skipped"      # no bot token: nothing was sent
    REFUSED = "refused"      # Telegram answered 4xx: it did not deliver
    UNCERTAIN = "uncertain"  # Telegram answered 5xx after taking the request: it may have


async def send_message_status(
    chat_id: str,
    text: str,
    *,
    parse_mode: str = "Markdown",
    reply_markup: dict | None = None,
) -> SendStatus:
    """Send a single Telegram message and say what is known about delivery.

    Raises what httpx raises. A caller that must not send twice has to treat
    any error after the connection opened (a read timeout, a dropped
    connection) like UNCERTAIN: Telegram may already have delivered.
    """
    if not settings.telegram_bot_token:
        logger.warning("telegram.skipped no_bot_token")
        return SendStatus.SKIPPED
    payload: dict = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{TG_API}/bot{settings.telegram_bot_token}/sendMessage",
            json=payload,
        )
        if r.status_code != 200:
            logger.warning(
                "telegram.send_failed chat=%s status=%d detail=%s",
                REDACTED, r.status_code, _failure_detail(r, chat_id),
            )
            return SendStatus.UNCERTAIN if r.status_code >= 500 else SendStatus.REFUSED
    return SendStatus.DELIVERED


async def send_message(
    chat_id: str,
    text: str,
    *,
    parse_mode: str = "Markdown",
    reply_markup: dict | None = None,
) -> bool:
    """Send a single Telegram message. Returns True on success.

    Pass `reply_markup` to attach inline-keyboard buttons (used by the
    inbox alert flow so the founder can Approve/Reject from their
    phone with one tap rather than typing a command).
    """
    status = await send_message_status(
        chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup,
    )
    return status is SendStatus.DELIVERED


async def deliver_founder_alert(*, subject: str, text: str) -> None:
    """Push a founder alert down whichever channel is actually configured.

    Telegram is instant and preferred, but it needs
    `INBOX_FOUNDER_TELEGRAM_CHAT_ID`, which is not always set — and when it
    isn't, an alert that only knows how to reach Telegram is a silent no-op.
    Resend is configured wherever the app can send mail at all, so it is the
    fallback: the founder learns about a signup or a sale without having to
    provision anything first.

    Exactly ONE channel fires, so setting the chat id later swaps the delivery
    route rather than doubling every notification. NEVER raises — a failed
    notification must not fail the signup or the webhook that triggered it.
    """
    chat_id = getattr(settings, "inbox_founder_telegram_chat_id", "")
    if chat_id and settings.telegram_bot_token:
        try:
            # parse_mode="" => plain text, so emails with _ / * survive intact.
            await send_message(chat_id, text, parse_mode="")
            return
        except Exception:
            logger.exception("telegram.founder_alert_failed subject=%s", subject)
            return
    try:
        from html import escape

        from app.services.email import send_email

        recipient = getattr(settings, "growth_digest_to", "") or "tapeline.inbox@gmail.com"
        body = escape(text).replace("\n", "<br>")
        await send_email(
            to=recipient,
            subject=subject,
            html=f'<div style="font:15px/1.6 ui-monospace,SFMono-Regular,monospace">{body}</div>',
            text=text,
            persona="sales",
        )
    except Exception:
        logger.exception("founder_alert.email_fallback_failed subject=%s", subject)


async def notify_founder_new_signup(
    *,
    email: str,
    tier: str,
    trial_ends_at: datetime | None,
    source: str,
) -> None:
    """Real-time ping to the founder on every new signup.

    Without this, signups (and the live trials they start) land silently in the
    DB and the founder only finds out by manually querying — so a 30-day trial
    can lapse unconverted before anyone reaches out.
    """
    te = trial_ends_at.date().isoformat() if trial_ends_at else "no trial"
    await deliver_founder_alert(
        subject=f"New Tapeline signup — {email}",
        text=(
            "🎉 New Tapeline signup\n"
            f"{email}\n"
            f"tier: {tier} · trial ends: {te}\n"
            f"via: {source}"
        ),
    )


async def notify_founder_new_subscription(
    *,
    email: str,
    tier: str,
    billing_period: str | None,
    amount: float | None,
    currency: str | None,
    plan_price: float | None = None,
) -> None:
    """Real-time ping to the founder when someone actually starts paying.

    The counterpart to `notify_founder_new_signup` and the more important half:
    a signup is a maybe, a subscription is revenue. Called only from
    `routers/webhooks.py:_welcome_on_first_paid_invoice`, on
    `invoice.payment_succeeded` for the subscription's FIRST invoice with
    `amount_paid > 0` — the same once-per-subscription `paid_start:` latch that
    sends the customer their welcome email, so it can't fire twice for one
    subscription. It no longer fires on a subscription turning active: a trial
    goes active about an hour before Stripe attempts the charge.

    `amount` is what the invoice actually charged; `plan_price` is the plan's
    price per billing period. They are printed on separate, labelled lines. The
    old single line ("tier: premium (monthly) · 10.00 USD") read a discounted
    first charge as the monthly price.
    """
    cur = (currency or "usd").upper()
    lines = [
        "💰 New Tapeline subscription — first payment received",
        email or "(no email on the account)",
        f"tier: {tier}" + (f" ({billing_period})" if billing_period else ""),
    ]
    if amount is not None:
        lines.append(f"charged today: {amount:.2f} {cur}")
    if plan_price is not None:
        per = {"annual": " per year", "monthly": " per month"}.get(billing_period or "", "")
        differs = amount is not None and round(amount, 2) != round(plan_price, 2)
        lines.append(
            f"plan price: {plan_price:.2f} {cur}{per}"
            + (" before any discount or credit" if differs else "")
        )
    await deliver_founder_alert(
        subject=f"💰 New Tapeline subscription — {email}",
        text="\n".join(lines),
    )


async def notify_founder_paid_invoice_unannounced(
    *,
    reason: str,
    amount: float,
    currency: str | None,
    email: str | None,
    customer: str | None,
    subscription: str | None,
) -> None:
    """A subscription invoice was PAID, and neither the customer welcome nor
    `notify_founder_new_subscription` went out for it.

    `_welcome_on_first_paid_invoice` refuses to send when it cannot prove the
    charge is a first charge (Stripe's invoice history unavailable) or cannot
    find the account (no linked customer, no user_id in the subscription
    metadata, no Subscription row). Both are the safe call for the customer.
    For the founder they lose revenue silently: no latch is claimed, so at the
    next renewal Stripe's history shows a paid invoice and the latch is then
    claimed WITHOUT an alert — the first sale is never announced at all. This
    says so at the moment it happens, with the amount charged, and claims
    nothing about whether it is a first charge.
    """
    cur = (currency or "usd").upper()
    await deliver_founder_alert(
        subject=f"⚠️ Paid Tapeline invoice, no welcome sent — {amount:.2f} {cur}",
        text=(
            "⚠️ A Tapeline subscription invoice was paid, but no welcome email "
            "and no new-subscription alert went out for it\n"
            f"charged: {amount:.2f} {cur}\n"
            f"why: {reason}\n"
            f"account: {email or 'not matched to a Tapeline account'}\n"
            f"stripe customer: {customer or '-'}\n"
            f"stripe subscription: {subscription or '-'}\n"
            "Check Stripe before contacting the customer: this may be a first "
            "payment or a renewal."
        ),
    )


async def answer_callback_query(callback_query_id: str, text: str = "") -> bool:
    """Acknowledge a callback_query (button tap). Required by Telegram —
    without it the user sees a loading spinner on the button forever."""
    if not settings.telegram_bot_token:
        return False
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{TG_API}/bot{settings.telegram_bot_token}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text},
        )
        return r.status_code == 200


async def send_message_with_id(
    chat_id: str,
    text: str,
    *,
    parse_mode: str = "Markdown",
    reply_markup: dict | None = None,
) -> int | None:
    """Like `send_message` but returns Telegram's new message_id on
    success (None otherwise).

    Used by the inbox alert flow so we can store the alert card's id
    on InboundMessage.telegram_alert_message_id and then editMessageText
    it in place after Approve/Reject (instead of stacking confirmation
    messages on the founder).
    """
    if not settings.telegram_bot_token:
        logger.warning("telegram.skipped no_bot_token")
        return None
    payload: dict = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{TG_API}/bot{settings.telegram_bot_token}/sendMessage",
            json=payload,
        )
        if r.status_code != 200:
            logger.warning(
                "telegram.send_with_id_failed chat=%s status=%d detail=%s",
                REDACTED, r.status_code, _failure_detail(r, chat_id),
            )
            return None
        try:
            data = r.json()
            return int(data.get("result", {}).get("message_id"))
        except Exception:
            logger.exception("telegram.send_with_id_parse_failed chat=%s", REDACTED)
            return None


async def edit_message_text(
    chat_id: str,
    message_id: int,
    text: str,
    *,
    parse_mode: str = "HTML",
) -> bool:
    """Edit an existing message in place. Used to update the inbox
    alert card after the founder taps Approve/Reject so they see
    "Sent ✓" or "Rejected ✗" rather than the original buttons."""
    if not settings.telegram_bot_token:
        return False
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{TG_API}/bot{settings.telegram_bot_token}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
        )
        return r.status_code == 200
