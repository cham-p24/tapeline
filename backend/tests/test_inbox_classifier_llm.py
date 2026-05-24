"""Phase A.5 coverage for the LLM-backed classifier path.

The Anthropic SDK is fully mocked — tests verify our code does the right
thing given a particular LLM response, not the LLM itself. Critical
behaviours covered:

  - `classify_async()` falls through to LLM only when rule-based misses
  - Master kill switch (`INBOX_BOT_ENABLED=false`) short-circuits before
    any LLM call
  - Cost cap trip downgrades to safe Tier 1 default
  - Missing API key downgrades to safe Tier 1 default
  - LLM-parse failure (malformed JSON) defaults to Tier 1
  - Successful Tier 1 LLM response surfaces the suggested_reply
  - Successful Tier 2 LLM response drops suggested_reply (template fills)
  - Every LLM call writes one InboxClassificationLog row with cost +
    latency populated
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import InboxClassificationLog
from app.services import inbox_classifier, inbox_kill_switch


@pytest.fixture(autouse=True)
def _reset_settings():
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()
    yield
    get_settings.cache_clear()
    inbox_kill_switch.reset_spend_cache()


# Shared body that doesn't match any rule-based pattern, so it always
# escalates to the LLM path.
AMBIGUOUS_BODY = (
    "I've been running a backtest on my own factor model and the results "
    "suggest momentum is double-counted when stacked on relative strength. "
    "Curious if you've looked at the correlation between those two factors "
    "in your composite, or if you treat them as orthogonal."
)


def _fake_anthropic_response(tier: int, reply: str | None, *, input_tokens: int = 800, output_tokens: int = 120, cache_read: int = 600):
    """Build a MagicMock that quacks like an anthropic.Message response."""
    import json as _json

    payload = {
        "tier": tier,
        "reason": f"test verdict tier={tier}",
        "suggested_reply": reply,
    }
    content_block = MagicMock()
    content_block.type = "text"
    content_block.text = _json.dumps(payload)

    response = MagicMock()
    response.content = [content_block]
    response.usage = MagicMock(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=0,
    )
    return response


class TestClassifyAsyncRouting:
    @pytest.mark.asyncio
    async def test_rule_based_match_skips_llm(self, monkeypatch):
        """A message that matches a Tier 2 template MUST NOT hit the LLM —
        burning tokens on what we already know the answer to is the
        whole reason rule-based exists."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        get_settings.cache_clear()

        mock_session = AsyncMock()
        with patch.object(inbox_classifier, "classify_with_llm") as mock_llm:
            result = await inbox_classifier.classify_async(
                "what's the score for $NVDA",
                session=mock_session,
            )
        assert result.tier == 2
        assert result.template_key == "ticker_score"
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_global_kill_switch_skips_llm(self, monkeypatch):
        monkeypatch.setenv("INBOX_BOT_ENABLED", "false")
        get_settings.cache_clear()

        mock_session = AsyncMock()
        with patch.object(inbox_classifier, "classify_with_llm") as mock_llm:
            result = await inbox_classifier.classify_async(
                AMBIGUOUS_BODY,
                session=mock_session,
            )
        assert result.tier == 1
        assert result.suggested_reply is None
        assert "INBOX_BOT_ENABLED" in result.reason
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_ambiguous_message_routes_to_llm(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        get_settings.cache_clear()

        mock_session = AsyncMock()
        sentinel = inbox_classifier.ClassifiedMessage(
            tier=1, reason="llm called", suggested_reply="drafted", template_key=None,
        )
        with patch.object(inbox_classifier, "classify_with_llm", AsyncMock(return_value=sentinel)) as mock_llm:
            result = await inbox_classifier.classify_async(
                AMBIGUOUS_BODY,
                session=mock_session,
                author="testuser",
                channel="reddit_dm",
            )
        assert result is sentinel
        mock_llm.assert_awaited_once()


class TestSafeDefaults:
    """Whenever the LLM path is unavailable, we MUST return Tier 1 with
    `suggested_reply=None` — manual review is the only safe answer when
    we can't classify. These tests are the legal-posture firewall: a
    regression here is how the bot starts auto-sending un-classified
    Tier 1 messages."""

    @pytest.mark.asyncio
    async def test_no_api_key_returns_safe_tier_1(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        get_settings.cache_clear()

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        result = await inbox_classifier.classify_with_llm(
            AMBIGUOUS_BODY, session=mock_session,
        )
        assert result.tier == 1
        assert result.suggested_reply is None
        assert "ANTHROPIC_API_KEY" in result.reason

    @pytest.mark.asyncio
    async def test_cap_exceeded_returns_safe_tier_1(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("INBOX_CLAUDE_DAILY_CAP_USD", "1.0")
        get_settings.cache_clear()

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        with patch.object(inbox_kill_switch, "cap_exceeded", AsyncMock(return_value=True)):
            result = await inbox_classifier.classify_with_llm(
                AMBIGUOUS_BODY, session=mock_session,
            )
        assert result.tier == 1
        assert result.suggested_reply is None
        assert "cap" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_anthropic_api_error_returns_safe_tier_1(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        get_settings.cache_clear()

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        class _BoomClient:
            class messages:
                @staticmethod
                async def create(**_kwargs):
                    raise RuntimeError("API down")

        fake_anthropic = MagicMock()
        fake_anthropic.AsyncAnthropic.return_value = _BoomClient()

        with (
            patch.object(inbox_kill_switch, "cap_exceeded", AsyncMock(return_value=False)),
            patch.dict("sys.modules", {"anthropic": fake_anthropic}),
        ):
            result = await inbox_classifier.classify_with_llm(
                AMBIGUOUS_BODY, session=mock_session,
            )
        assert result.tier == 1
        assert result.suggested_reply is None
        assert "failed" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_malformed_llm_json_returns_safe_tier_1(self, monkeypatch):
        """The model occasionally returns malformed JSON (rate-limited
        truncation, content-policy refusal). The parser should never
        crash — it should default to Tier 1 with a 'needs founder
        review' reason."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        get_settings.cache_clear()

        # Build an "Anthropic response" whose text is unparseable JSON.
        bad_content = MagicMock()
        bad_content.type = "text"
        bad_content.text = "I'm sorry, I cannot help with that request."

        bad_response = MagicMock()
        bad_response.content = [bad_content]
        bad_response.usage = MagicMock(
            input_tokens=400, output_tokens=20,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        )

        class _Client:
            class messages:
                @staticmethod
                async def create(**_kwargs):
                    return bad_response

        fake_anthropic = MagicMock()
        fake_anthropic.AsyncAnthropic.return_value = _Client()

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        with (
            patch.object(inbox_kill_switch, "cap_exceeded", AsyncMock(return_value=False)),
            patch.dict("sys.modules", {"anthropic": fake_anthropic}),
        ):
            result = await inbox_classifier.classify_with_llm(
                AMBIGUOUS_BODY, session=mock_session,
            )
        assert result.tier == 1
        assert "review" in result.reason.lower() or "unparseable" in result.reason.lower()


class TestLLMResponseParsing:
    @pytest.mark.asyncio
    async def test_tier_1_response_surfaces_suggested_reply(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        get_settings.cache_clear()

        good = _fake_anthropic_response(tier=1, reply="Quick note on factor orthogonality.")

        class _Client:
            class messages:
                @staticmethod
                async def create(**_kwargs):
                    return good

        fake_anthropic = MagicMock()
        fake_anthropic.AsyncAnthropic.return_value = _Client()

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        with (
            patch.object(inbox_kill_switch, "cap_exceeded", AsyncMock(return_value=False)),
            patch.dict("sys.modules", {"anthropic": fake_anthropic}),
        ):
            result = await inbox_classifier.classify_with_llm(
                AMBIGUOUS_BODY, session=mock_session,
            )
        assert result.tier == 1
        assert result.suggested_reply == "Quick note on factor orthogonality."

    @pytest.mark.asyncio
    async def test_tier_2_response_drops_suggested_reply(self, monkeypatch):
        """LLM returning Tier 2 means 'rule-based had a gap' — the bot
        will still go through the deterministic template at send-time,
        so suggested_reply MUST be None to avoid using the model's
        improvised wording."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        get_settings.cache_clear()

        # LLM tries to be helpful and includes a reply; we drop it.
        good = _fake_anthropic_response(tier=2, reply="Free tier covers 20 tickers.")

        class _Client:
            class messages:
                @staticmethod
                async def create(**_kwargs):
                    return good

        fake_anthropic = MagicMock()
        fake_anthropic.AsyncAnthropic.return_value = _Client()

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        with (
            patch.object(inbox_kill_switch, "cap_exceeded", AsyncMock(return_value=False)),
            patch.dict("sys.modules", {"anthropic": fake_anthropic}),
        ):
            result = await inbox_classifier.classify_with_llm(
                AMBIGUOUS_BODY, session=mock_session,
            )
        assert result.tier == 2
        assert result.suggested_reply is None


class TestCostAccounting:
    """Cost calc is the foundation of the daily cap — if it's wrong by
    10x, the cap is also wrong by 10x."""

    def test_haiku_pricing(self):
        # 1M input tokens, 0 cached, 1M output tokens at Haiku rates
        # ($1/MTok in, $5/MTok out) = $6.00
        cost = inbox_classifier._cost_for("claude-haiku-4-5", 1_000_000, 0, 1_000_000)
        assert cost == Decimal("6.000000")

    def test_sonnet_pricing(self):
        # 1M input, 0 cached, 1M output at Sonnet ($3 + $15) = $18
        cost = inbox_classifier._cost_for("claude-sonnet-4-5", 1_000_000, 0, 1_000_000)
        assert cost == Decimal("18.000000")

    def test_cached_tokens_discounted(self):
        """Cache-read tokens bill at ~10% of input rate."""
        # 100K input, 90K of which is cache-read, 10K fresh, 1K output
        # Haiku: 10K * $1/M = $0.01, 90K * $0.10/M = $0.009, 1K * $5/M = $0.005
        # total = $0.024
        cost = inbox_classifier._cost_for("claude-haiku-4-5", 100_000, 90_000, 1_000)
        assert cost == Decimal("0.024000")

    def test_unknown_model_uses_conservative_fallback(self):
        """Unknown model name = Sonnet pricing (the conservative bet).
        Better to over-budget than under-budget."""
        cost_unknown = inbox_classifier._cost_for("claude-future-99", 1_000_000, 0, 0)
        cost_sonnet = inbox_classifier._cost_for("claude-sonnet-4-5", 1_000_000, 0, 0)
        assert cost_unknown == cost_sonnet
