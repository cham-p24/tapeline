"""Coverage for the inbox kill-switch + spend-cap helpers.

Critical behaviours:
  - `bot_enabled()` reads INBOX_BOT_ENABLED from settings
  - `dry_run()` reads INBOX_DRY_RUN
  - `channel_enabled()` maps channel name → per-channel toggle
  - `spend_today()` SUMs InboxClassificationLog.cost_usd for the UTC day
  - `cap_exceeded()` trips once spend hits INBOX_CLAUDE_DAILY_CAP_USD

A regression here = the bot keeps burning the API bill after the cap is
hit, or the master kill switch fails to disable everything.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.config import get_settings
from app.services import inbox_kill_switch


@pytest.fixture(autouse=True)
def _clear_spend_cache():
    inbox_kill_switch.reset_spend_cache()
    yield
    inbox_kill_switch.reset_spend_cache()


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestEnableSwitches:
    def test_bot_enabled_defaults_true(self):
        assert inbox_kill_switch.bot_enabled() is True

    def test_bot_enabled_false_via_env(self, monkeypatch):
        monkeypatch.setenv("INBOX_BOT_ENABLED", "false")
        get_settings.cache_clear()
        assert inbox_kill_switch.bot_enabled() is False

    def test_dry_run_defaults_false(self):
        assert inbox_kill_switch.dry_run() is False

    def test_dry_run_true_via_env(self, monkeypatch):
        monkeypatch.setenv("INBOX_DRY_RUN", "true")
        get_settings.cache_clear()
        assert inbox_kill_switch.dry_run() is True

    @pytest.mark.parametrize("channel,setting", [
        ("reddit_comment", "INBOX_REDDIT_ENABLED"),
        ("reddit_dm", "INBOX_REDDIT_ENABLED"),
        ("reddit_mention", "INBOX_REDDIT_ENABLED"),
        ("email", "INBOX_EMAIL_ENABLED"),
        ("telegram", "INBOX_TELEGRAM_ENABLED"),
    ])
    def test_channel_disable_routes_to_right_setting(self, monkeypatch, channel, setting):
        monkeypatch.setenv(setting, "false")
        get_settings.cache_clear()
        assert inbox_kill_switch.channel_enabled(channel) is False

    def test_unknown_channel_defaults_enabled(self):
        """A typo in a future channel name should NOT silently drop
        messages. Default-enabled means the bug is loud, not silent."""
        assert inbox_kill_switch.channel_enabled("nonexistent_channel") is True


class TestSpendCap:
    @pytest.mark.asyncio
    async def test_cap_not_exceeded_when_spend_below(self, monkeypatch):
        monkeypatch.setenv("INBOX_CLAUDE_DAILY_CAP_USD", "5.0")
        get_settings.cache_clear()

        async def _fake_spend(_session):
            return Decimal("2.50")

        with patch.object(inbox_kill_switch, "spend_today", _fake_spend):
            assert await inbox_kill_switch.cap_exceeded(None) is False  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_cap_exceeded_when_spend_above(self, monkeypatch):
        monkeypatch.setenv("INBOX_CLAUDE_DAILY_CAP_USD", "5.0")
        get_settings.cache_clear()

        async def _fake_spend(_session):
            return Decimal("6.00")

        with patch.object(inbox_kill_switch, "spend_today", _fake_spend):
            assert await inbox_kill_switch.cap_exceeded(None) is True  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_cap_exceeded_when_spend_exactly_at_cap(self, monkeypatch):
        """At the cap is treated as exceeded — better to under-shoot
        than burn one final classification past the line."""
        monkeypatch.setenv("INBOX_CLAUDE_DAILY_CAP_USD", "5.0")
        get_settings.cache_clear()

        async def _fake_spend(_session):
            return Decimal("5.00")

        with patch.object(inbox_kill_switch, "spend_today", _fake_spend):
            assert await inbox_kill_switch.cap_exceeded(None) is True  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_cap_disabled_when_set_to_zero(self, monkeypatch):
        """Cap = 0 means 'no cap' — operator opted out. Should never trip."""
        monkeypatch.setenv("INBOX_CLAUDE_DAILY_CAP_USD", "0")
        get_settings.cache_clear()

        async def _fake_spend(_session):
            return Decimal("999.99")

        with patch.object(inbox_kill_switch, "spend_today", _fake_spend):
            assert await inbox_kill_switch.cap_exceeded(None) is False  # type: ignore[arg-type]
