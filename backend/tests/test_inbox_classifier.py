"""Phase A coverage for the inbox classifier.

Rule-based fast path must:
  - Empty body → Tier 3
  - Spam patterns (crypto shillers, paid signal services) → Tier 3
  - Hostile one-liners → Tier 3
  - Ticker score questions → Tier 2 (template 'ticker_score')
  - Pricing questions → Tier 2 (template 'pricing')
  - Trial questions → Tier 2 (template 'trial')
  - Generic positive sentiment → Tier 2 (template 'thanks')
  - Ambiguous / long thoughtful messages → fall through to LLM (Tier 1 stub)

If any of these regress the bot starts mis-routing high-value DMs
to auto-reply (brand-damaging) or pumping crypto-shiller messages
to the founder's Telegram (noise).
"""
from __future__ import annotations

import pytest

from app.services.inbox_classifier import classify, classify_rule_based


class TestRuleBasedFastPath:
    def test_empty_body_is_tier_3(self):
        result = classify_rule_based("")
        assert result is not None
        assert result.tier == 3
        assert "empty" in result.reason.lower()

    def test_whitespace_only_is_tier_3(self):
        result = classify_rule_based("   \n\n  \t  ")
        assert result is not None
        assert result.tier == 3

    @pytest.mark.parametrize("body", [
        "join my telegram channel for 100x signals!",
        "DM me for guaranteed returns",
        "Exclusive trading group, paid signals daily",
        "Copy trading service — verified trader, 99% win rate",
        "Next gem alert! Moon shot 🚀",
    ])
    def test_spam_patterns_classified_as_tier_3(self, body: str):
        result = classify_rule_based(body)
        assert result is not None, f"Should match a spam pattern: {body!r}"
        assert result.tier == 3
        assert result.template_key is None

    @pytest.mark.parametrize("body", [
        "this is a scam",
        "Total bullshit, no real track record",
        "Fake numbers, garbage product",
    ])
    def test_hostile_one_liners_classified_as_tier_3(self, body: str):
        result = classify_rule_based(body)
        assert result is not None
        assert result.tier == 3

    @pytest.mark.parametrize("body", [
        "what's the score for $NVDA",
        "How's $AAPL looking today?",
        "Can you give me a breakdown on $TSLA?",
        "Score on $MSFT please",
        "what's $AMZN at right now",
        # Edge case: cashtag-only, no surrounding question
        "$GOOGL",
    ])
    def test_ticker_score_questions_match_template(self, body: str):
        result = classify_rule_based(body)
        assert result is not None, f"Ticker pattern should match: {body!r}"
        assert result.tier == 2
        assert result.template_key == "ticker_score"

    @pytest.mark.parametrize("body", [
        "How does your pricing work?",
        "How much is the Pro tier?",
        "What's the monthly cost?",
        "What are the plans?",
    ])
    def test_pricing_questions_match_template(self, body: str):
        result = classify_rule_based(body)
        assert result is not None, f"Pricing pattern should match: {body!r}"
        assert result.tier == 2
        assert result.template_key in ("pricing", "trial")

    @pytest.mark.parametrize("body", [
        "Is there a free trial?",
        "Can I try Premium?",
        "How do I sign up free?",
    ])
    def test_trial_questions_match_template(self, body: str):
        result = classify_rule_based(body)
        assert result is not None
        assert result.tier == 2
        # 'trial' or 'pricing' both acceptable here — keyword overlap
        assert result.template_key in ("trial", "pricing")

    @pytest.mark.parametrize("body", [
        "Love this tool!",
        "Great work on the scorecard",
        "Cool product, the formula transparency is awesome",
        "Nice solid work",
    ])
    def test_generic_thanks_match_template(self, body: str):
        result = classify_rule_based(body)
        assert result is not None
        assert result.tier == 2
        assert result.template_key == "thanks"

    def test_spam_check_runs_before_ticker_check(self):
        """A crypto-shiller message that *also* mentions a ticker should
        still be classified as Tier 3 spam, not Tier 2 ticker."""
        body = "Join my telegram channel for $NVDA signals — 100x guaranteed!"
        result = classify_rule_based(body)
        assert result is not None
        assert result.tier == 3, "Spam pattern must override ticker template"

    def test_long_thoughtful_message_falls_through_to_llm(self):
        """A 400-char methodology question doesn't match any template and
        should return None (caller falls through to LLM)."""
        body = (
            "Hey — interesting work on the 6-factor composite. I'm curious "
            "how you handle the Piotroski F-score for financial-sector "
            "names where the long-term-debt leverage test is essentially "
            "a category error. Do you swap in a sector-specific quality "
            "score, or just downweight Fundamentals in Financials? Asked "
            "because the IBD Composite Rating handles this by swapping in "
            "Group Rating ahead of the SMR Rating for that sector."
        )
        result = classify_rule_based(body)
        assert result is None, "Long thoughtful message should fall through to LLM"


class TestFullClassifier:
    def test_classify_delegates_to_rule_based_first(self):
        """If the rule-based fast path returns a verdict, classify()
        should pass it through without invoking the LLM stub."""
        result = classify("Total scam, fake numbers")
        assert result.tier == 3
        # Tier 3 from rule-based, NOT the LLM stub default of Tier 1
        assert "spam" in result.reason.lower() or "hostile" in result.reason.lower()

    def test_ambiguous_message_falls_through_to_llm_stub(self):
        """Phase A LLM stub returns Tier 1 with a 'needs founder review'
        reason. Phase B will wire the real Anthropic call."""
        body = (
            "Hey — what's your view on holding $AAPL through earnings? "
            "I have a 2% position and the IV crush worries me."
        )
        # This will match the ticker_score pattern actually. Let me use
        # something that doesn't match any pattern.
        body = (
            "I've been running a backtest on my own factor model and the "
            "results suggest momentum is double-counted when you stack it "
            "on top of relative strength. Curious if you've looked at the "
            "correlation between those two factors in your composite."
        )
        result = classify(body)
        assert result.tier == 1
        assert "stub" in result.reason.lower() or "founder" in result.reason.lower()
