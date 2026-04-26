"""Runtime configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings. All values must come from env vars."""

    # Look for .env in both backend/ and the project root (one level up)
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    app_name: str = "Tapeline"
    app_env: Literal["development", "staging", "production"] = "development"
    app_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"

    # ---- Database ----
    database_url: str = Field(..., description="Postgres connection string")

    # ---- Market data (Polygon) ----
    polygon_api_key: str = Field("", description="Polygon.io API key")
    polygon_tier: Literal["starter", "developer", "advanced"] = "starter"
    polygon_feed: str = "sip"

    # ---- Auth (Clerk) ----
    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""
    clerk_webhook_secret: str = ""
    clerk_issuer_url: str = ""
    admin_api_key: str = ""
    session_secret: str = ""

    # ---- OAuth (Google + Microsoft) ----
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    oauth_microsoft_client_id: str = ""
    oauth_microsoft_client_secret: str = ""

    # ---- Billing (Stripe) ----
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro_monthly: str = ""
    stripe_price_premium_monthly: str = ""

    # ---- Email (Resend) ----
    resend_api_key: str = ""
    email_from: str = "alerts@tapeline.io"

    # ---- Telegram ----
    telegram_bot_token: str = ""

    # ---- Quiver QuantData (elite 13F holdings + Congress) ----
    # Free tier available; without a key, smart-money enrichment falls back to mock.
    quiver_api_key: str = ""

    # ---- Worker cadence ----
    score_refresh_seconds: int = 60
    snapshot_refresh_seconds: int = 30

    # ---- Feature flags ----
    feature_congress_tab: bool = True
    feature_telegram_alerts: bool = True
    feature_csv_export: bool = True


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Import and call this everywhere."""
    return Settings()  # type: ignore[call-arg]
