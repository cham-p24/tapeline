"""Inbox auto-handler — Tier 1 / 2 / 3 classifier.

Reads an inbound message (Reddit comment, email, Telegram DM) and returns
a tier + reason + suggested reply. Two paths:

  - `classify_rule_based(body)` — sync, no DB, no network. Catches the
    obvious cases (empty body, spam patterns, ticker-score / pricing /
    trial / thanks templates) without burning tokens. ~70% of typical
    inbound volume.
  - `classify_async(body, ...)` — async, requires a DB session. Runs the
    rule-based path first, then escalates to the Anthropic Claude API
    for ambiguous messages. Writes one row to `inbox_classification_log`
    per LLM call (audit + spend-cap accounting).

Both paths return a `ClassifiedMessage`. Tier 2 carries a `template_key`
identifying which deterministic reply to use. Tier 1 has the LLM-drafted
reply in `suggested_reply` (or None if the LLM was unavailable — then
the founder drafts manually via the Telegram approval card).

`classify(body, ...)` is the sync compatibility wrapper retained for
callers (and existing tests) that can't await a session. It runs the
rule-based fast path and returns Tier 1 with a safe-default reason for
anything ambiguous. Use `classify_async()` for the real LLM path.

Defensive defaults: when the LLM is unreachable (no key, cap exceeded,
API error, malformed JSON), we ALWAYS return Tier 1 with
`suggested_reply=None`. Founder reviews manually. We never auto-send a
reply we couldn't classify.

System prompt is prompt-cached (`cache_control: ephemeral`) so the
~600-token instruction block doesn't get re-billed on every call —
worth ~85% input savings on a warm cache.

Tier definitions (also documented in models/inbox.py):
  - 1 = high-value, needs founder voice. Real retail trader with a
    specific ticker question, FinTwit account with >5K followers,
    journalist, newsletter or podcast pitch, long thoughtful methodology
    critique. Bot DRAFTS the reply, routes to founder's Telegram for
    one-tap approval. NEVER auto-sends.
  - 2 = templatable. "What's $TICKER score?", "How does the free tier
    work?", "Thanks for building this." Bot uses a hardcoded template
    (filled with live API data for ticker questions) and auto-sends.
  - 3 = ignore. Crypto shillers, bot accounts, off-platform paid signal
    services, hostile trolls. Bot marks status='ignored', does nothing.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import InboxClassificationLog
from app.services import inbox_kill_switch

logger = logging.getLogger(__name__)

Tier = Literal[1, 2, 3]


@dataclass(frozen=True)
class ClassifiedMessage:
    """Result of running classify_*() on an InboundMessage body."""
    tier: Tier
    reason: str
    suggested_reply: str | None
    template_key: str | None  # if Tier 2, which template to use


# --- Rule-based fast path ---------------------------------------------------

# Tickers in the form $AAPL / $TSLA / $NVDA. Two-or-more cashtags in a
# message that's otherwise short = ticker score question.
TICKER_RE = re.compile(r"\$([A-Z]{1,6})\b")

# Templatable Tier 2 questions — keyword pattern matchers. Keep these
# tight enough that a Tier 1 message ("can you walk me through how the
# free tier handles 200 tickers a week?") doesn't false-match the
# generic "free tier" template.
TIER_2_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # Cashtag-only ticker match. Modern stock-Twitter / Reddit users
    # write "$NVDA" / "$AAPL" when asking about a name, and that's an
    # unambiguous signal. The previous looser pattern (verb + any 1-6
    # letter word) false-positived on "what's the monthly cost?" by
    # capturing "the" as a ticker. Cashtag-only is the safe call —
    # non-cashtag ticker questions fall through to the LLM for
    # judgment instead of getting an auto-reply.
    (
        "ticker_score",
        re.compile(r"\$([A-Z]{1,6})\b"),
    ),
    # "how does pricing work" / "what are your prices" / "what are the plans".
    # Bare keywords are NOT enough: "cost", "monthly", "plan" and "tier" all
    # appear incidentally in ordinary trading talk ("I plan to hold through
    # earnings", "the cost of being wrong", "my monthly rebalance"), and a
    # bare-keyword match auto-sent a pricing template at those. Every
    # alternative below needs an explicit pricing framing.
    (
        "pricing",
        re.compile(
            r"\bpricing\b"
            r"|\bhow\s+much\s+(?:is|are|does|do|would|for)\b"
            r"|\b(?:what|how)(?:'s|\s+is|\s+are|\s+do|\s+does)?\s+(?:the\s+|your\s+|it\s+)?"
            r"(?:price|prices|plans?|tiers?)\b"
            r"|\b(?:monthly|annual|yearly|subscription)\s+(?:cost|price|fee|plan|tier)s?\b"
            r"|\bprice\s+(?:point|list)s?\b"
            r"|\bpaid\s+(?:plan|tier)s?\b",
            re.IGNORECASE,
        ),
    ),
    # Trial questions. "trial" alone is too loose (clinical trial, trial and
    # error, "trial by fire"), so it has to sit in a signup framing.
    (
        "trial",
        re.compile(
            r"\bfree\s+trial\b"
            r"|\bpremium\s+trial\b"
            r"|\btrial\s+(?:period|account|version)\b"
            r"|\b(?:start|get|have|offer|is\s+there|do\s+you\s+(?:have|offer)|can\s+i\s+get)"
            r"\s+(?:a\s+)?trial\b"
            r"|\btry\s+premium\b"
            r"|\bsign\s+up\s+free\b",
            re.IGNORECASE,
        ),
    ),
    # Generic "great work" / "love this" — SHORT positive sentiment with no
    # specific question. The whole body must be short and question-free:
    # the old first-80-chars scan fired the thanks template at "I have a
    # great deal of trouble with your momentum weighting…", i.e. it
    # auto-thanked people who were actually critiquing the methodology.
    (
        "thanks",
        re.compile(
            r"^(?=[\s\S]{0,120}$)(?![\s\S]*\?)[\s\S]*"
            r"\b(?:thanks|thank\s+you"
            r"|love\s+(?:this|it|the|your)"
            r"|(?:this|it|that|tapeline)(?:'s|\s+is|\s+looks)\s+"
            r"(?:great|cool|nice|awesome|impressive|solid)"
            r"|(?:great|cool|nice|awesome|impressive|solid)(?:\s+\w+){0,2}\s+"
            r"(?:work|job|product|tool|stuff|build|app|site))\b",
            re.IGNORECASE,
        ),
    ),
]

# Escalation signals — these take PRECEDENCE over the Tier 2 fast path.
# A message carrying any of them is never safe to answer with a canned
# template, even when it also contains a cashtag or the word "pricing"
# (press asking "what's your pricing model?", a fund evaluating seats, a
# 300-word factor-model critique that happens to mention $NVDA). Matching
# here returns None so the caller escalates to the LLM, which can still
# land on Tier 2/3 with full context.
ESCALATION_PATTERNS: list[re.Pattern[str]] = [
    # Press / podcast / partnership — always needs the founder's voice.
    re.compile(
        r"\b(?:journalist|reporter|editor|press\s+(?:enquiry|inquiry|request)|"
        r"podcast|newsletter|interview|writing\s+(?:a\s+)?(?:piece|story|article)|"
        r"partnership|affiliate|sponsor|sponsorship|collaborate|collaboration)\b",
        re.IGNORECASE,
    ),
    # Evaluating for an organisation rather than one retail seat — a very
    # different pricing conversation from the pricing-101 template.
    re.compile(
        r"\b(?:my|our)\s+(?:team|fund|firm|desk|shop|clients?)\b"
        r"|\b(?:enterprise|institutional|procurement|invoice|purchase\s+order|"
        r"volume\s+discount|bulk\s+licen[sc]e|seats?\s+for)\b",
        re.IGNORECASE,
    ),
    # Methodology / factor-model discussion — the "long thoughtful critique"
    # in the tier definitions.
    re.compile(
        r"\b(?:methodolog\w*|factor\s+model|back-?test\w*|weightings?|"
        r"look-?ahead\s+bias|survivorship|sharpe|drawdown|out-?of-?sample|"
        r"walk\s+me\s+through)\b",
        re.IGNORECASE,
    ),
]

# Bodies at least this long are, per the tier definitions above ("Long
# thoughtful (200+ char) methodology critique"), out of templatable
# territory regardless of which keywords they happen to contain.
ESCALATION_MIN_LENGTH = 200

# Tier 3 — obvious spam / bot / hostile patterns. Match against the
# whole body; any hit drops to ignore-without-LLM.
TIER_3_PATTERNS: list[re.Pattern[str]] = [
    # Crypto shillers and pump-and-dump bait. "join my channel" / "DM me
    # for signals" / "100x gem" / "exclusive trading group"
    re.compile(
        r"\b(?:join my (?:channel|group)|dm me|telegram me|exclusive (?:signals?|group)|"
        r"100x|moon shot|next gem|guaranteed (?:returns|profit))\b",
        re.IGNORECASE,
    ),
    # Off-platform paid signal services
    re.compile(
        r"\b(?:paid signals?|premium signals?|insider tips?|whatsapp group|"
        r"signal service|copy trading|verified trader)\b",
        re.IGNORECASE,
    ),
    # Hostile / accusation one-liners (Tier 3 because there's nothing
    # productive to reply to; founder's standing posture is to link to
    # /scorecard and move on, which the bot can't do meaningfully)
    re.compile(
        r"^.{0,160}\b(?:scam|fake|fraud|bullshit|garbage|trash)\b",
        re.IGNORECASE,
    ),
]


def classify_rule_based(body: str) -> ClassifiedMessage | None:
    """Fast deterministic classifier. Returns None when the message
    doesn't match any known pattern, or when it carries an escalation
    signal that outranks the Tier 2 templates (i.e. needs the LLM).

    Order is deliberate: Tier 3 spam → escalation → Tier 2 templates.
    Tier 2 is the only auto-sending tier, so it is checked last."""
    if not body or not body.strip():
        # Empty body = no signal. Treat as Tier 3 ignore.
        return ClassifiedMessage(
            tier=3,
            reason="empty body",
            suggested_reply=None,
            template_key=None,
        )

    # Tier 3 patterns FIRST — we don't want a crypto-shiller message that
    # happens to mention "$NVDA score" to be classified as a ticker query.
    for pat in TIER_3_PATTERNS:
        if pat.search(body):
            return ClassifiedMessage(
                tier=3,
                reason=f"matched spam/hostile pattern: {pat.pattern[:60]}",
                suggested_reply=None,
                template_key=None,
            )

    # Escalation check BEFORE the Tier 2 fast path. Tier 2 is the only
    # tier that auto-sends, so anything carrying a founder-review signal
    # must get out ahead of it — otherwise a journalist asking about the
    # pricing model, or a fund evaluating seats for a desk, gets a canned
    # template instead of a human. Returning None (not Tier 1) keeps the
    # existing semantics: the caller escalates to the LLM, which can still
    # settle on Tier 2 or 3 once it has the full context.
    stripped = body.strip()
    if len(stripped) >= ESCALATION_MIN_LENGTH:
        logger.info(
            "inbox.classify.escalated reason=length len=%d", len(stripped),
        )
        return None
    for pat in ESCALATION_PATTERNS:
        if pat.search(body):
            logger.info(
                "inbox.classify.escalated reason=pattern pat=%s",
                pat.pattern[:60],
            )
            return None

    # Tier 2 patterns. First match wins; order matters (ticker_score
    # before pricing before thanks).
    for template_key, pat in TIER_2_PATTERNS:
        m = pat.search(body)
        if m:
            return ClassifiedMessage(
                tier=2,
                reason=f"matched template '{template_key}'",
                suggested_reply=None,  # template fills at send time
                template_key=template_key,
            )

    # No rule fired — needs LLM judgment. Caller should fall through to
    # `classify_async()`'s LLM path.
    return None


def classify(body: str, *, author: str | None = None, channel: str | None = None) -> ClassifiedMessage:
    """Sync compatibility wrapper — rule-based path only.

    Kept so existing callers (and tests) that pre-date `classify_async`
    keep compiling. Ambiguous messages return Tier 1 with a safe default
    reason; the real LLM call lives in `classify_async()`.
    """
    fast = classify_rule_based(body)
    if fast is not None:
        return fast
    logger.info(
        "inbox.classify.sync_fallthrough channel=%s author=%s body_len=%d",
        channel, author, len(body),
    )
    return ClassifiedMessage(
        tier=1,
        reason="rule-based classifier didn't match; needs founder review (sync fallthrough — async path skipped)",
        suggested_reply=None,
        template_key=None,
    )


# --- LLM path ---------------------------------------------------------------

# System prompt for the Anthropic classifier call. Cached at the API layer
# via `cache_control: ephemeral` — ~600 tokens that we don't want to re-bill
# on every classification. Keep it stable; any edit invalidates the cache
# for the first call after deploy.
SYSTEM_PROMPT = """You are an inbox triage assistant for Tapeline — a SaaS stock-scanning tool run solo by founder "Christian Piyatilaka" (Melbourne, Australia). You classify each inbound message into one of three tiers and, for Tier 1 only, draft a reply in Christian's voice.

VOICE RULES for Tier 1 draft replies:
- First person ("I built Tapeline because...", "I think the cleanest way to..."), never "we"
- Unsigned — no "— Christian" or "— Chamara" at the end
- Descriptive language only: "high conviction", "constructive setup", "weak". NEVER "buy", "sell", "you should", or any prescriptive recommendation (Australian publisher-exemption legal posture)
- Concrete + tight. No filler ("Great question!", "Hope this helps!"). 2-4 sentences typical.
- If the sender asks about a specific ticker, surface its current score + factor breakdown if useful, but always frame as "what the scanner shows right now", not "buy/sell"

TIER DEFINITIONS:

Tier 1 = high-value, NEEDS FOUNDER VOICE. Examples:
- FinTwit account with 5K+ followers asking about methodology
- Real retail trader (real name, finance title, thoughtful question) with specific ticker / strategy question
- Newsletter / podcaster / YouTuber inquiry about coverage or interview
- Journalist from reputable outlet
- Long thoughtful (200+ char) methodology critique or factor-model discussion
- Anyone asking about pricing in a way that implies they're evaluating for a team / fund / firm

Tier 2 = templatable, AUTO-REPLY SAFE (but most Tier 2 is caught by rule-based — only escalates here when ambiguous). Examples:
- Casual "what's the score for $TICKER?" without surrounding context
- "How does the free tier work?" / pricing 101 questions
- Generic "cool product" / "interesting tool" with no follow-up
- "Can I get a free trial?" / "How do I sign up?"

Tier 3 = IGNORE. Examples:
- Crypto shillers / pump-and-dump bait
- Bot accounts (newly created, generic profile, follow count <50, copy-paste replies)
- Off-platform paid-signal-service offers
- Hostile / accusatory one-liners ("this is fake", "no track record")
- Off-topic spam (SEO link drops, "great post check out my blog")

Return JSON only, no markdown or prose:

{
  "tier": 1,
  "reason": "<one-line explanation, <120 chars>",
  "suggested_reply": "<2-4 sentence draft in founder's voice, or null for Tier 2/3>"
}

For Tier 2 set suggested_reply to null — the bot will fill from a template. For Tier 3 set suggested_reply to null — nothing gets sent.
"""

# Token costs ($ per million tokens) per Anthropic model. Used to compute
# `cost_usd` for the classification log + the daily cap. The lookup key is
# the *configured* model string (settings.inbox_claude_model), not the
# model the API echoes back, so both the alias and the dated snapshot a
# founder might pin INBOX_CLAUDE_MODEL to need an entry — otherwise the
# dated form falls through to the Sonnet fallback and ~3x over-bills the cap.
# Conservative fallback (Sonnet pricing) for an unlisted model: fine for
# Haiku/Sonnet-class overrides (over-estimates), but would under-estimate an
# Opus-class override — add an explicit row before pointing the bot at Opus.
#
# Format: model_name -> (input_per_mtok, output_per_mtok, cache_read_per_mtok)
_MODEL_COSTS_USD_PER_MTOK: dict[str, tuple[float, float, float]] = {
    "claude-haiku-4-5":            (1.00,  5.00,  0.10),
    "claude-haiku-4-5-20251001":   (1.00,  5.00,  0.10),  # dated snapshot alias
    "claude-sonnet-4-5":           (3.00, 15.00,  0.30),
    "claude-opus-4-5":            (15.00, 75.00,  1.50),
}

_DEFAULT_COST = _MODEL_COSTS_USD_PER_MTOK["claude-sonnet-4-5"]


def _cost_for(model: str, input_tokens: int, cached_tokens: int, output_tokens: int) -> Decimal:
    """Approximate USD cost for a single classification call. Uses the
    Sonnet pricing table as a conservative fallback for unknown models."""
    in_rate, out_rate, cache_rate = _MODEL_COSTS_USD_PER_MTOK.get(model, _DEFAULT_COST)
    # Anthropic's API counts cached_tokens as part of input_tokens; subtract
    # so we don't double-bill the cached portion at the full input rate.
    uncached = max(0, input_tokens - cached_tokens)
    total = (uncached * in_rate + cached_tokens * cache_rate + output_tokens * out_rate) / 1_000_000
    return Decimal(str(round(total, 6)))


def _hash_body(body: str) -> str:
    """SHA-256 of a normalised body. Used as a log key for dedup checks."""
    normalised = " ".join(body.lower().split())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


async def _log_classification(
    session: AsyncSession,
    *,
    inbound_message_id: int | None,
    input_hash: str,
    model: str,
    input_tokens: int = 0,
    cached_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: Decimal = Decimal("0"),
    latency_ms: int | None = None,
    tier: int | None = None,
    reason: str | None = None,
    error: str | None = None,
) -> None:
    """Insert one row into inbox_classification_log. Never raises — a
    logging failure must not crash the classifier path."""
    try:
        session.add(InboxClassificationLog(
            inbound_message_id=inbound_message_id,
            input_hash=input_hash,
            model=model,
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            tier=tier,
            reason=(reason or "")[:500] or None,
            error=(error or "")[:240] or None,
        ))
        await session.commit()
    except Exception:
        logger.exception("inbox.classification_log.insert_failed model=%s", model)


def _safe_default(reason: str) -> ClassifiedMessage:
    """The safe default whenever the LLM path is unavailable: Tier 1
    with no suggested reply. Founder reviews manually via Telegram."""
    return ClassifiedMessage(
        tier=1,
        reason=reason,
        suggested_reply=None,
        template_key=None,
    )


def _parse_llm_response(raw: str) -> tuple[Tier, str, str | None]:
    """Pull tier + reason + suggested_reply out of the model's JSON.
    Falls back to Tier 1 on any parse failure."""
    try:
        # The model is instructed to return raw JSON, but defensive: strip
        # any ```json fence if it slipped in.
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        data = json.loads(text)
        tier_raw = int(data.get("tier", 1))
        if tier_raw not in (1, 2, 3):
            tier_raw = 1
        reason = str(data.get("reason", ""))[:500]
        reply = data.get("suggested_reply")
        if reply is not None:
            reply = str(reply).strip() or None
        return tier_raw, reason or "(no reason supplied)", reply  # type: ignore[return-value]
    except Exception:
        logger.exception("inbox.llm.parse_failed raw=%s", raw[:200])
        return 1, "LLM response unparseable; needs founder review", None


async def classify_with_llm(
    body: str,
    *,
    session: AsyncSession,
    author: str | None = None,
    channel: str | None = None,
    inbound_message_id: int | None = None,
) -> ClassifiedMessage:
    """Call the Anthropic API to classify an ambiguous message. Logs cost
    + latency + tier to inbox_classification_log.

    Cost-cap, missing-key, and API-error paths all return the safe
    default (Tier 1, no reply) and log the reason for it.
    """
    settings = get_settings()
    input_hash = _hash_body(body)

    if not settings.anthropic_api_key:
        await _log_classification(
            session,
            inbound_message_id=inbound_message_id,
            input_hash=input_hash,
            model="no-api-key",
            tier=1,
            reason="ANTHROPIC_API_KEY unset — defaulted to Tier 1",
        )
        return _safe_default(
            "ANTHROPIC_API_KEY unset — defaulted to Tier 1 (founder reviews via Telegram)"
        )

    if await inbox_kill_switch.cap_exceeded(session):
        cap = settings.inbox_claude_daily_cap_usd
        await _log_classification(
            session,
            inbound_message_id=inbound_message_id,
            input_hash=input_hash,
            model="cap-exceeded",
            tier=1,
            reason=f"daily Claude cap ${cap:.2f} exceeded — defaulted to Tier 1",
        )
        return _safe_default(
            f"daily Claude cap ${cap:.2f} exceeded — defaulted to Tier 1 (resets at UTC midnight)"
        )

    # Header for the model — gives it the author + channel context that
    # the system prompt asks about (account age, follower count).
    user_block = f"Channel: {channel or 'unknown'}\nAuthor: {author or 'unknown'}\n\n---\n{body[:4000]}"

    model = settings.inbox_claude_model
    started = time.perf_counter()
    try:
        # Import inline so the SDK is only loaded when actually needed —
        # keeps startup fast for the rest of the API and lets the test
        # suite mock it cleanly.
        import anthropic  # type: ignore[import-not-found]

        # Bound the call so we never hold the pooled DB connection across a
        # hung LLM request (SDK default timeout is ~600s). The SDK timeout
        # caps the underlying HTTP request; asyncio.wait_for is a backstop in
        # case the SDK itself stalls. Both a TimeoutError and the SDK's
        # APITimeoutError fail closed into the except-path below (Tier 1).
        client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key, timeout=20.0
        )
        response = await asyncio.wait_for(
            client.messages.create(
                model=model,
                max_tokens=512,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_block}],
            ),
            timeout=25,
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        await _log_classification(
            session,
            inbound_message_id=inbound_message_id,
            input_hash=input_hash,
            model=model,
            latency_ms=latency_ms,
            tier=1,
            reason="Anthropic API call failed — defaulted to Tier 1",
            error=str(exc)[:240],
        )
        logger.exception("inbox.llm.call_failed model=%s", model)
        return _safe_default(
            f"Anthropic API call failed ({type(exc).__name__}) — defaulted to Tier 1"
        )

    latency_ms = int((time.perf_counter() - started) * 1000)

    # Pull the text response — first content block, type=text.
    raw_text = ""
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "text":
            raw_text = getattr(block, "text", "") or ""
            break

    # Token accounting. Cache-creation tokens are billed at the input
    # rate (first write to the cache); cache_read tokens at the discounted
    # cached rate.
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)

    tier_val, reason, reply = _parse_llm_response(raw_text)
    cost = _cost_for(model, input_tokens, cache_read, output_tokens)

    await _log_classification(
        session,
        inbound_message_id=inbound_message_id,
        input_hash=input_hash,
        model=model,
        input_tokens=input_tokens,
        cached_tokens=cache_read,
        output_tokens=output_tokens,
        cost_usd=cost,
        latency_ms=latency_ms,
        tier=tier_val,
        reason=reason,
    )

    # Tier 2 / 3 from the LLM means the rule-based classifier had a gap.
    # Suggested_reply is intentionally None for those — Tier 2 goes
    # through the deterministic templates at send-time; Tier 3 gets no
    # reply at all.
    if tier_val == 2:
        return ClassifiedMessage(
            tier=2, reason=reason, suggested_reply=None, template_key=None,
        )
    if tier_val == 3:
        return ClassifiedMessage(
            tier=3, reason=reason, suggested_reply=None, template_key=None,
        )
    return ClassifiedMessage(
        tier=1, reason=reason, suggested_reply=reply, template_key=None,
    )


async def classify_async(
    body: str,
    *,
    session: AsyncSession,
    author: str | None = None,
    channel: str | None = None,
    inbound_message_id: int | None = None,
) -> ClassifiedMessage:
    """Full classifier. Rule-based fast path first; LLM for ambiguous.

    Honours the global kill switch — when `INBOX_BOT_ENABLED=false`,
    every message is treated as Tier 1 (founder reviews manually) with
    no LLM call so we never silently pile up cost behind the off
    switch.
    """
    if not inbox_kill_switch.bot_enabled():
        return _safe_default(
            "INBOX_BOT_ENABLED=false — defaulted to Tier 1 (worker passive)"
        )

    fast = classify_rule_based(body)
    if fast is not None:
        return fast

    return await classify_with_llm(
        body,
        session=session,
        author=author,
        channel=channel,
        inbound_message_id=inbound_message_id,
    )


__all__ = [
    "SYSTEM_PROMPT",
    "ClassifiedMessage",
    "Tier",
    "classify",
    "classify_async",
    "classify_rule_based",
    "classify_with_llm",
]
