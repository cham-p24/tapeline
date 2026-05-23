"""Inbox auto-handler — Tier 1 / 2 / 3 classifier.

Reads an inbound message (Reddit comment, email, Telegram DM) and
returns a tier + reason + suggested reply. Backed by the Anthropic
Claude API for Tier 1 drafting; Tier 2 / 3 paths are deterministic
rule-checks first so we don't burn tokens on obvious cases.

Tier definitions (also documented in models/inbox.py):
  - 1 = high-value, needs founder voice. Real retail trader with a
    specific ticker question, FinTwit account with >5K followers,
    journalist, newsletter or podcast pitch, long thoughtful
    methodology critique. Bot DRAFTS the reply, routes to founder's
    Telegram for one-tap approval. NEVER auto-sends.
  - 2 = templatable. "What's $TICKER score?", "How does the free tier
    work?", "Thanks for building this." Bot uses a hardcoded template
    (filled with live API data for ticker questions) and auto-sends.
  - 3 = ignore. Crypto shillers, bot accounts, off-platform paid
    signal services, hostile trolls. Bot marks status='ignored', does
    nothing.

Phase A (this file) ships:
  - `classify_rule_based(message)` — deterministic fast-path that
    catches the obvious Tier 2 / Tier 3 cases without an LLM call.
  - `classify(message)` — full classifier (rule-based first, falls
    through to Anthropic Claude API for ambiguous cases). The LLM
    integration is stubbed; Phase B wires it once `ANTHROPIC_API_KEY`
    is confirmed as a Fly secret.

Cost model: a typical inbound day at current Tapeline volume is
~10-30 messages. Rule-based catches ~70% (most Tier 3 spam +
templatable Tier 2). Remaining ~5-10 messages/day hit the LLM at
~1K input tokens each = $0.003/day at Sonnet 4.5 pricing. Acceptable
even if volume 10×s.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

Tier = Literal[1, 2, 3]


@dataclass(frozen=True)
class ClassifiedMessage:
    """Result of running classify() on an InboundMessage body."""
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
    # "how does pricing work" / "what are your prices" / "what are the plans"
    (
        "pricing",
        re.compile(
            r"\b(?:pricing|how\s+much|cost|monthly|annually|tiers?|plans?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "trial",
        re.compile(
            r"\b(?:trial|free trial|premium trial|try premium|sign up free)\b",
            re.IGNORECASE,
        ),
    ),
    # Generic "great work" / "love this" — short positive sentiment with no
    # specific question.
    (
        "thanks",
        re.compile(
            r"^.{0,80}\b(?:love|great|cool|nice|awesome|impressive|solid)\b",
            re.IGNORECASE,
        ),
    ),
]

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
    doesn't match any known pattern (i.e. needs the LLM)."""
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
    # `classify()`'s LLM path.
    return None


def classify(body: str, *, author: str | None = None, channel: str | None = None) -> ClassifiedMessage:
    """Full classifier. Tries rule-based first, falls through to LLM.

    LLM path is stubbed in Phase A — returns Tier 1 with a placeholder
    reason. Phase B wires the actual Anthropic SDK call.
    """
    fast = classify_rule_based(body)
    if fast is not None:
        return fast

    # LLM stub. Phase B: wire `anthropic.Anthropic().messages.create(...)`
    # with the system prompt from docs/launch/TAPELINE_BOT_PROMPT.md.
    # Until then, ambiguous messages get the safe default — Tier 1, no
    # auto-reply, founder reviews via Telegram.
    logger.info(
        "inbox.classify.llm_stub channel=%s author=%s body_len=%d",
        channel, author, len(body),
    )
    return ClassifiedMessage(
        tier=1,
        reason="rule-based classifier didn't match; needs founder review (LLM stub)",
        suggested_reply=None,
        template_key=None,
    )


__all__ = ["ClassifiedMessage", "Tier", "classify", "classify_rule_based"]
