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

    # ---- Market data (Polygon — being migrated to Massive) ----
    polygon_api_key: str = Field("", description="Polygon.io API key (legacy)")
    polygon_tier: Literal["starter", "developer", "advanced"] = "starter"
    polygon_feed: str = "sip"

    # ---- Market data (Massive — replaces Polygon for Tapeline) ----
    massive_api_key: str = Field("", description="Massive.com API key")

    # ---- Signal-system sheet (Phase 1: canonical universe + composite score) ----
    # The signal-system at C:\signal-system\ publishes its ranked ticker universe
    # to a Google Sheet ("Live Dashboard - Stocks"). Tapeline pulls the
    # ALL SIGNALS tab as the source of truth for: (a) which tickers to track,
    # (b) the composite 6-factor score per ticker. Without this URL set,
    # services/sheet_feed.refresh_from_workbook() no-ops and the worker
    # falls back to mock_feed (the 112-ticker hardcoded universe).
    #
    # To configure: in the Google Sheet, File → Share → Publish to web →
    # select ALL SIGNALS tab + CSV format → copy URL, set:
    #   fly secrets set SIGNAL_SHEET_CSV_URL="https://docs.google.com/..." -a tapeline-backend
    signal_sheet_csv_url: str = ""
    # Throttle: only pull from the sheet at most every N seconds.
    #
    # 2026-05-24: cut from 300s → 30s. With sheet_feed's SHA-256 hash-dedup
    # in place (services/sheet_feed._CSV_HASH_CACHE), an unchanged sheet
    # costs one HTTP GET + 32-byte hash compare per tab per tick — no
    # parse, no DB writes. A 30s cadence at 5 tabs = 600 published-CSV
    # GETs/hour = trivial vs Google's no-published-quota stance. When the
    # sheet IS edited, the next tick (within 30s) picks it up — gives us
    # near-live refresh without the Apps Script trigger fragility.
    signal_sheet_refresh_seconds: int = 30
    # Phase 2 sheet tabs — each is its own published-CSV URL. The signal-system
    # workbook has one tab per intelligence layer; Tapeline reads them
    # separately so each tab can be cached + parsed + upserted on its own
    # cadence without one slow tab blocking the others.
    #
    # All four use the same 5-min throttle as signal_sheet_refresh_seconds.
    # Dormant when each respective URL is unset; configured independently so
    # the user can light up tabs one at a time as the data quality firms up.
    spike_intelligence_csv_url: str = ""
    market_intelligence_csv_url: str = ""
    smart_money_congress_csv_url: str = ""
    etf_benchmarks_csv_url: str = ""

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
    # Apple Sign-In requires the Services ID + Team ID + Key ID + .p8 private key.
    # The .p8 contents go directly into the env var (multiline, including the
    # `-----BEGIN PRIVATE KEY-----` and `-----END PRIVATE KEY-----` lines).
    # Apple Developer Program membership ($99/yr) required to issue these.
    oauth_apple_client_id: str = ""        # Services ID, e.g. "io.tapeline.signin"
    oauth_apple_team_id: str = ""          # 10-char Apple Developer team ID
    oauth_apple_key_id: str = ""           # 10-char Key ID matching the .p8
    oauth_apple_private_key: str = ""      # full .p8 contents incl. BEGIN/END lines

    # ---- Billing (Stripe) ----
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro_monthly: str = ""
    stripe_price_pro_annual: str = ""
    stripe_price_premium_monthly: str = ""
    stripe_price_premium_annual: str = ""

    # ---- Email (Resend) ----
    # Multiple sender personas so users see a sensible From line per email
    # category. All addresses live under the Resend-verified tapeline.io
    # domain so no per-address DNS work is required.
    #
    #   default       transactional (welcome, referrals, day-3 activation)
    #   sales         conversion-y (trial drip day 7+, re-engagement, win-back)
    #   billing       Stripe payment failures / invoices
    #   alerts        automated (alert rules, EOD digest, daily briefing)
    #
    # Reply-To always points at support@tapeline.io (already routed via
    # Cloudflare Email Routing to tapeline.inbox@gmail.com) so replies
    # never bounce — even if a per-persona alias hasn't been wired into
    # the Cloudflare routing rules yet.
    resend_api_key: str = ""
    # Outbound bounce/complaint webhook (Resend dashboard → Webhooks).
    # When configured, /api/webhooks/resend verifies the Svix signature
    # and processes email.bounced + email.complained events. Without it
    # the endpoint 503s — fine because Resend retries.
    resend_webhook_secret: str = ""
    # Inbound webhook signing secret (Resend dashboard → Webhooks).
    # Without this, POST /api/inbox/email accepts unsigned requests in
    # dev — set it in prod or any attacker who guesses the URL can
    # inject fake emails into the inbox auto-handler.
    resend_inbound_secret: str = ""
    # Founder's Telegram chat_id — destination for Tier 1 inbox
    # alerts requiring approval. Without this, Tier 1 messages get
    # stored but no notification fires (founder will see them next
    # time they open /app/inbox).
    inbox_founder_telegram_chat_id: str = ""
    email_from: str = "hello@tapeline.io"                  # default / transactional
    email_from_sales: str = "christian@tapeline.io"        # conversion-y trial drip + re-engagement
    email_from_billing: str = "billing@tapeline.io"        # Stripe events
    email_from_alerts: str = "alerts@tapeline.io"          # automated digests + alert rules
    email_reply_to: str = "support@tapeline.io"            # bounce-safe reply hub

    # ---- IndexNow (Bing / Yandex / DuckDuckGo / Seznam) ----
    # Static fallback matches the key file shipped at
    # frontend/public/<key>.txt. Override via env var only if rotating.
    # The aggregator at api.indexnow.org fans out to all participating
    # search engines, so this single key serves them all. No account /
    # auth / quota — free.
    indexnow_api_key: str = "7b3f8c5d2a9e4f1b6c8d0a3e5f7b9c2d"

    # ---- Telegram ----
    telegram_bot_token: str = ""
    # Bot username (no @, no t.me/). Used to build the t.me/<username>?start=<token>
    # deep-link for one-click signup. Resolve via getMe API when first wiring.
    telegram_bot_username: str = "Tapeline_Bot"
    # Shared secret in the webhook URL path so only Telegram (and anyone we
    # show the URL to) can post updates. Mint random and set via setWebhook.
    telegram_webhook_secret: str = ""

    # ---- SMS (Twilio, optional) ----
    # Without Twilio configured, the SMS alert channel is a no-op (alerts
    # configured for SMS log a "skipped" line and don't deliver).
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # ---- Web Push (VAPID) ----
    # Generate keys with `python -c "from py_vapid import Vapid; v = Vapid(); v.generate_keys(); print(v.public_key, v.private_key)"`
    # or https://vapidkeys.com/. Frontend also needs NEXT_PUBLIC_VAPID_PUBLIC_KEY.
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:owner@tapeline.io"

    # ---- Quiver QuantData (elite 13F holdings + Congress) ----
    # Free tier available; without a key, smart-money enrichment falls back to mock.
    quiver_api_key: str = ""

    # ---- Finnhub (fundamentals, insider Form 4, earnings + IPO calendars) ----
    # Free tier 60 calls/min covers Tapeline (weekly fundamentals refresh = ~125/day).
    # Without a key, sub_fundamentals stays mock-random and calendars use mock_upcoming_*.
    finnhub_api_key: str = ""

    # ---- Internal alert webhook (cron health checks) ----
    # Random shared secret used by GitHub Actions cron to authenticate
    # to /api/internal/alert. Generate with:
    #   python -c "import secrets; print(secrets.token_urlsafe(32))"
    # Set on Fly + as a NEWS_FRESHNESS_WEBHOOK GitHub repo variable
    # containing the full URL: https://api.tapeline.io/api/internal/alert?token=<secret>
    internal_alert_secret: str = ""

    # ---- Sheet webhook (live-push from signal-system Google Sheet) ----
    # Random shared secret used by the Apps Script onChange trigger on the
    # "Live Dashboard - Stocks" sheet to authenticate against
    # /api/internal/sheet-changed. Generate with the same recipe as above;
    # paste into Fly AND into the sheet's Script properties as
    # TAPELINE_WEBHOOK_SECRET. Until set, the endpoint 503s — the worker's
    # 5-min CSV poll stays the primary refresh path.
    # See docs/PHASE_1_EXECUTION_PLAN.md §A3 + §F1 for the full wire-up.
    sheet_webhook_secret: str = ""

    # ---- Bot protection (Cloudflare Turnstile, optional) ----
    # When secret key is unset, Turnstile verification passes through (dev mode).
    # Honeypot field + disposable-email block always run regardless.
    cloudflare_turnstile_site_key: str = ""
    cloudflare_turnstile_secret_key: str = ""

    # ---- FRED (Federal Reserve Economic Data) — free macro indicators ----
    # Free key at https://fred.stlouisfed.org/docs/api/api_key.html
    # Without a key, fetch_regime falls back to polygon-only / hardcoded values.
    fred_api_key: str = ""

    # ---- Worker cadence ----
    score_refresh_seconds: int = 60

    # ---- Error monitoring (Sentry) — env-gated ----
    # Sign up at https://sentry.io (free 5k events/mo). Drop the DSN in
    # SENTRY_DSN to activate. Inert when blank.
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.0  # 0=off, 0.05=5% perf traces
    sentry_environment: str = ""  # defaults to app_env when blank

    # ---- Inbox auto-handler bot ----
    # Triages inbound messages from Reddit / email / Telegram into Tier 1 /
    # 2 / 3. Tier 2 auto-replies via deterministic templates; Tier 1 is
    # drafted by Claude and routed to the founder's Telegram for one-tap
    # approval; Tier 3 is ignored. See services/inbox_classifier.py and
    # services/inbox_router.py for the orchestration; this block holds the
    # toggles + secrets that gate the whole thing.
    #
    # Global kill switch. When false, the worker still polls but never
    # classifies or sends — useful for an instant "pause everything"
    # without a redeploy.
    inbox_bot_enabled: bool = True
    # Dry-run mode. Classify + decide normally, but channel adapters
    # short-circuit before the actual upstream send. Logs the "would
    # have sent" payload so you can shadow-audit a week of behaviour
    # before going live. Independent of inbox_bot_enabled.
    inbox_dry_run: bool = False
    # Per-channel toggles. Let the operator yank one channel without
    # taking the others down (e.g. Reddit account shadow-banned).
    inbox_reddit_enabled: bool = True
    inbox_email_enabled: bool = True
    inbox_telegram_enabled: bool = True
    # Daily Claude classification spend ceiling. Once today's
    # `inbox_classification_log.cost_usd` sum exceeds the cap, the
    # classifier downgrades every ambiguous message to Tier 1 manual
    # review until UTC midnight. $5/day ≈ 7.5K Haiku calls — plenty of
    # headroom but a hard stop against a runaway feedback loop.
    inbox_claude_daily_cap_usd: float = 5.0
    # Anthropic SDK key. When unset, the LLM path is short-circuited
    # and every ambiguous message defaults to Tier 1 manual review
    # (safe default — never auto-replies without explicit approval).
    anthropic_api_key: str = ""
    # Default Claude model. Haiku 4.5 is cheapest-capable for fixed-
    # schema JSON triage; override to claude-sonnet-4-5 if Haiku
    # misclassifies on your fixture set.
    inbox_claude_model: str = "claude-haiku-4-5"
    # Tier 1.5 auto-acknowledgement toggle. When true (default), the
    # bot fires an immediate "I'll get back within 24h" reply on every
    # Tier 1 inbound so US-business-hours senders aren't ghosted while
    # the Melbourne founder is asleep. Founder's actual reply still
    # waits on Telegram approval.
    inbox_tier1_auto_ack: bool = True
    # Reddit OAuth (script-tier app at https://www.reddit.com/prefs/apps).
    # All four required for the Reddit channel; missing any makes
    # services/reddit_inbox.py a no-op.
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_username: str = ""
    reddit_password: str = ""
    reddit_user_agent: str = "tapeline-inbox-bot/0.1"
    # Subreddits to scan for "tapeline" mentions (alongside DMs +
    # comment-replies on bot's own posts). Comma-separated. Default
    # covers the high-signal finance subs.
    reddit_mention_subreddits: str = "wallstreetbets,stocks,investing,SecurityAnalysis,ValueInvesting"
    # New-account guard. When the configured Reddit account is younger
    # than N days, throttle auto-replies to ≤3/day. Avoids the
    # new-account anti-spam triggers in r/wallstreetbets-style subs.
    # Set to 0 to disable.
    reddit_new_account_throttle_days: int = 30

    # ---- Growth bot (autonomous content + metrics digest) ----
    # The growth bot runs from the worker tick at 22:00 UTC weekdays
    # (~8am Melbourne). It pulls live metrics from Postgres, drafts a
    # daily X tweet, LinkedIn post, and 3 fintwit reply candidates from
    # the priority-1 account list, and emails the package to
    # GROWTH_DIGEST_TO. Defaults to off so a fresh deploy doesn't surprise
    # the founder with daily email — flip to true once they want it.
    growth_bot_enabled: bool = False
    # Recipient for the daily growth digest email. Defaults to the brand
    # inbox if blank.
    growth_digest_to: str = "tapeline.inbox@gmail.com"
    # X handle the bot targets when scanning for fresh fintwit tweets.
    # Comma-separated list; defaults to the priority-1 cohort.
    growth_fintwit_handles: str = (
        "JohnHuber72,TSOH_Investing,HaydenCapital,TidefallCapital,"
        "SuperMugatu,Citrini7,iancassel,FoolAllTheTime"
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Import and call this everywhere."""
    return Settings()  # type: ignore[call-arg]
