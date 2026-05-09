"""
Tier gating — three-tier model (Free / Pro / Premium).

- Free: preview only (top 10 tickers, 15-min delayed)
- Pro $29/mo: live scanner, full universe, squeeze + regime + heatmap,
  watchlist with smart alerts, email alerts, CSV export
- Premium $49/mo: everything in Pro + Congressional trades, unlimited
  Telegram alerts, unlimited email alerts, public API (1,000/day),
  priority support

Team / Enterprise / Lifetime sales map to 'premium' in the DB; per-account
overrides handle larger seat counts or API caps if needed.
"""
from __future__ import annotations

from enum import StrEnum


class Tier(StrEnum):
    FREE = "free"
    PRO = "pro"
    PREMIUM = "premium"


# Feature -> minimum tier required.
FEATURES: dict[str, Tier] = {
    # Pro tier features
    "scanner.full_universe": Tier.PRO,
    "scanner.live_updates": Tier.PRO,
    "regime.full": Tier.PRO,
    "squeeze.full": Tier.PRO,
    "watchlist": Tier.PRO,
    "ticker.full_detail": Tier.PRO,
    "news.full": Tier.PRO,
    "ipos.full": Tier.PRO,
    "earnings.full": Tier.PRO,
    "heatmap": Tier.PRO,
    "alerts.email": Tier.PRO,
    "briefing.daily": Tier.PRO,
    "export.csv": Tier.PRO,
    # Pro-tier alert channels (free to deliver, low friction)
    "alerts.web_push": Tier.PRO,      # Browser push notifications (free, one click)
    # Premium-only features
    "congress.feed": Tier.PREMIUM,
    "alerts.telegram": Tier.PREMIUM,
    "api.access": Tier.PREMIUM,
    "holdings.elite": Tier.PREMIUM,   # Quiver elite-fund 13F holdings
    "ratings.analyst": Tier.PREMIUM,  # Benzinga + Finnhub analyst consensus widget
    # Removed 2026-05-04: alerts.discord (low usage, webhook setup friction
    # turned out to be a real conversion blocker) and alerts.sms (Twilio
    # billing overhead per send made the unit economics ugly at low volume).
    # Service files left in app/services/{discord,sms}.py and DB columns
    # left intact so the channels can be re-enabled by re-adding the
    # entries above without a migration.
}


_ORDER = {Tier.FREE: 0, Tier.PRO: 1, Tier.PREMIUM: 2}


def has_feature(user_tier: Tier | str, feature: str) -> bool:
    if feature not in FEATURES:
        return True
    required = FEATURES[feature]
    actual = Tier(user_tier) if isinstance(user_tier, str) else user_tier
    return _ORDER[actual] >= _ORDER[required]


# Usage caps — aligned with docs/PRICING.md.
TIER_LIMITS: dict[Tier, dict[str, int]] = {
    Tier.FREE: {
        # Hardened 2026-04-27: 20 tickers, 24-hour delay.
        # Trial expiry now drops to a meaningfully worse experience (yesterday's
        # data, narrow universe) so loss aversion does the conversion work.
        # Watchlist of 5 stays — alerts can't fire on stale data anyway, so this
        # is a frustration vector that nudges toward upgrade rather than utility.
        "scanner_rows": 20,
        "watchlist_tickers": 5,
        "email_alerts_per_day": 0,
        "telegram_alerts_per_day": 0,
        "api_requests_per_day": 0,
        "saved_scans": 0,
        "data_delay_minutes": 1440,  # 24 hours
    },
    Tier.PRO: {
        "scanner_rows": 1000,
        "watchlist_tickers": 50,
        "email_alerts_per_day": 10,
        "telegram_alerts_per_day": 0,
        "api_requests_per_day": 0,
        "saved_scans": 10,
        "data_delay_minutes": 0,
    },
    Tier.PREMIUM: {
        "scanner_rows": 1000,
        "watchlist_tickers": 200,
        "email_alerts_per_day": 10_000,    # effectively unlimited
        "telegram_alerts_per_day": 10_000, # effectively unlimited
        "api_requests_per_day": 1_000,
        "saved_scans": 100,
        "data_delay_minutes": 0,
    },
}


def limit(user_tier: Tier | str, key: str) -> int:
    actual = Tier(user_tier) if isinstance(user_tier, str) else user_tier
    return TIER_LIMITS[actual].get(key, 0)
