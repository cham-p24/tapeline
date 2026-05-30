const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// Only attach the dev-bypass bearer when the API base is local. In production
// the backend ignores it (auth.py only accepts it when app_env=development),
// so sending it cross-origin is harmless but pointless — and it's the kind
// of token-shaped string that's confusing to see in prod request logs.
const IS_DEV_API = /localhost|127\.0\.0\.1/.test(API_BASE);
const DEV_TOKEN = IS_DEV_API ? "dev-bypass" : "";

/**
 * Every fetch in this file passes `credentials: "include"` so the
 * `tapeline_session` cookie travels with the request.
 *
 * Why this matters: the frontend lives at `tapeline.io` and the API at
 * `api.tapeline.io`. Even though the cookie is set with Domain=tapeline.io
 * (which makes it visible to both), `fetch()` defaults to
 * `credentials: "same-origin"` — which considers `api.*` subdomain a
 * different origin from `tapeline.io` and DROPS the cookie. Result:
 * every authenticated POST/DELETE/GET-with-auth returned 401 in production
 * even though the user was clearly signed in. Live bug observed
 * 2026-05-17 on "Add to watchlist" and "Notify me on news" buttons.
 *
 * 401 handling: centralised in `handle401()` below — every helper in this
 * file routes through it. When an authed call returns 401 (cookie expired,
 * tampered, or the user was signed out elsewhere), the user is bounced to
 * /signin?next=<current path> automatically. Previously only 5 pages
 * detected 401 string-matched on the thrown error; ~15 others let the
 * raw 'Failed: 401 Unauthorized' fall through to the UI. This handler
 * fixes that everywhere at once.
 */

// Routes where 401 should NOT redirect — public marketing surfaces calling
// optional auth-aware endpoints (e.g. /api/auth/session returning null
// when signed out, which is the expected response, not an error). Without
// this allowlist a signed-out homepage visit would loop /signin → / → /signin.
const NO_REDIRECT_PATHS = ["/signin", "/signup", "/verify-email"];

export function handle401(status: number) {
  if (status !== 401) return;
  if (typeof window === "undefined") return; // SSR: just throw, no redirect
  const path = window.location.pathname;
  // Don't redirect from public surfaces (homepage, marketing, /signin
  // itself). Only redirect from authed app surfaces — these are the ones
  // where 401 means 'your session is gone' not 'this is a public read'.
  const isAppSurface = path.startsWith("/app");
  const isSignAuthPage = NO_REDIRECT_PATHS.some((p) => path.startsWith(p));
  if (!isAppSurface || isSignAuthPage) return;
  // Already redirecting (e.g. multiple concurrent 401s on the same page)?
  // Skip — first one wins.
  if (window.location.pathname === "/signin") return;
  const next = encodeURIComponent(path + window.location.search);
  window.location.href = `/signin?next=${next}`;
}

/**
 * Normalise a caught `unknown` to a display string. Lets call sites use
 * `catch (e: unknown)` — strict, no implicit `any` — while keeping the terse
 * `setError(errorMessage(e))` shape. `Error` (incl. TierGateError) → its
 * `.message`; anything else → `String()`. Type-safe replacement for the old
 * `String(e.message || e)` idiom that was repeated across ~10 catch blocks.
 */
export function errorMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}

/**
 * Typed 403 — tier-gate. Thrown by every helper in this file when the
 * backend returns 403 (Pro / Premium feature attempted from a lower
 * tier). Carries the backend's human message + an inferred `requiredTier`
 * so callers can render a Paywall directly without string-matching the
 * 'Failed: 403 Forbidden' format.
 *
 * Detection: `if (e instanceof TierGateError) { ... }`. The backend's
 * 403 messages are stable phrases like "Squeeze scanner is a Pro feature"
 * — we parse `Pro` / `Premium` out for the tier label. Falls back to
 * 'pro' if the phrase shape changes.
 */
export class TierGateError extends Error {
  readonly status = 403;
  readonly requiredTier: "pro" | "premium";
  constructor(message: string) {
    super(message);
    this.name = "TierGateError";
    this.requiredTier = /premium/i.test(message) ? "premium" : "pro";
  }
}

/**
 * Parse the FastAPI error envelope. Backend returns `{ detail: "<msg>" }`
 * on HTTPException — extract that. Falls back to status text when the
 * response isn't JSON.
 */
async function extractDetail(res: Response): Promise<string> {
  try {
    const body = await res.clone().json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    // not JSON
  }
  return `${res.status} ${res.statusText}`;
}

/**
 * Centralised non-2xx handling — call from every helper after handle401()
 * but before throwing. Throws TierGateError on 403 (with the backend's
 * actual feature-required message); throws plain Error otherwise.
 */
async function throwForStatus(res: Response): Promise<never> {
  if (res.status === 403) {
    throw new TierGateError(await extractDetail(res));
  }
  throw new Error(await extractDetail(res));
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!res.ok) {
    handle401(res.status);
    await throwForStatus(res);
  }
  return res.json();
}

export type ScannerRow = {
  symbol: string;
  name: string;
  sector: string | null;
  asset_class: string;
  score: number;
  signal: string;
  price: number;
  change_pct_1d: number;
  change_pct_5d: number;
  change_pct_1m: number;
  volume: number;
  sub_trend?: number | null;
  sub_rs?: number | null;
  sub_fundamentals?: number | null;
  sub_momentum?: number | null;
  sub_macro?: number | null;
  sub_smart_money?: number | null;
  confidence_pct?: number | null;
  reason?: string | null;
  updated_at: string | null;
};

export type TickerDetail = {
  symbol: string;
  name: string;
  sector: string | null;
  asset_class: string;
  price: number;
  score: number;
  signal: string;
  confidence_pct: number | null;
  change_pct_1d: number;
  change_pct_5d: number;
  change_pct_1m: number;
  volume: number;
  reason: string | null;
  breakdown: Record<string, { value: number; weight: number; label: string }>;
  squeeze: null | {
    spike_score: number;
    squeeze_days: number;
    volume_multiple: number;
    obv_trend: string;
    breakout_type: string;
    suggested_window: string;
    reason: string;
  };
  news: Array<{
    id: string;
    title: string;
    publisher: string;
    published_at: string;
    url: string;
    sentiment: number | null;
  }>;
  updated_at: string | null;
};

export type WatchlistItem = {
  id: number;
  symbol: string;
  // Phase A: which named list this item belongs to. Null only for
  // items that pre-date migration 0022's backfill (no such rows in
  // production after the deploy ran); allowed null in the type for
  // safety.
  watchlist_id: number | null;
  note: string | null;
  baseline_score: number | null;
  alert_threshold_delta: number;
  added_at: string;
  current_score: number | null;
  signal: string | null;
  price: number | null;
  change_pct_1d: number | null;
  reason: string | null;
  score_delta: number | null;
  alert_triggered: boolean;
};

// Phase A — one row returned by /api/watchlists (the LIST CRUD, not the
// per-item watchlist). `item_count` is the number of WatchlistItems
// currently attached to this list (computed server-side).
export type WatchlistRow = {
  id: number;
  name: string;
  sort_order: number;
  item_count: number;
  created_at: string | null;
};

// Phase A — one row returned by /api/presets. `filters_json` is an opaque
// blob the scanner page serialises via JSON.stringify on save and parses
// back on apply.
export type ScannerPresetRow = {
  id: number;
  name: string;
  filters_json: string;
  created_at: string | null;
};

export type ScorecardEntry = {
  rank: number;
  symbol: string;
  score_at_flag: number;
  price_at_flag: number;
  price_next_day: number | null;
  change_pct_1d_after: number | null;
  spy_change_pct_1d: number | null;
  alpha_vs_spy: number | null;
};

export type HeatmapSector = {
  sector: string;
  tickers: Array<{
    symbol: string;
    score: number;
    price: number;
    change_pct_1d: number;
    volume: number;
    signal: string;
  }>;
};

export type SqueezeRow = {
  symbol: string;
  spike_score: number;
  squeeze_days: number;
  volume_multiple: number;
  obv_trend: string;
  breakout_type: string;
  suggested_window: string;
  reason: string;
  updated_at: string | null;
};

export type Regime = {
  regime: string;
  vix: number;
  dxy: number;
  yield_10y: number;
  rate_direction: string;
  breadth_pct: number;
  sector_leaders: string;
  updated_at: string | null;
  fear_greed?: {
    score: number;
    label: string;
    color: string;
    components: {
      vix:     { score: number; input: number | null };
      breadth: { score: number; input: number | null };
      regime:  { score: number; input: string | null };
      spy_5d:  { score: number; input: number | null };
    };
  };
};

export type AnalystRatings = {
  symbol: string;
  consensus: { bull: number; bear: number; neutral: number; total: number };
  avg_pt: number | null;
  events: Array<{
    date: string;
    firm: string | null;
    analyst: string | null;
    action_pt: string | null;          // "Raises" | "Lowers" | "Maintains" | "Announces" | null
    rating_current: string | null;
    rating_prior: string | null;
    pt_current: number | null;
    pt_prior: number | null;
    url: string | null;
  }>;
  source: "benzinga" | "empty";
};

export type TickerFinancials = {
  symbol: string;
  available: boolean;
  metrics: {
    pe?: number | null;
    margin?: number | null;
    roe?: number | null;
    eps_growth?: number | null;
    revenue_growth?: number | null;
    debt_to_equity?: number | null;
  };
};

export type TickerInsiderRow = {
  filer_name: string;
  transaction_date: string;
  share_change: number;
  transaction_price: number;
  code: string;   // SEC Form 4 transaction code (P/S/A/M/G/F)
};

export type TickerInsiderResponse = {
  symbol: string;
  days_back: number;
  transactions: TickerInsiderRow[];
};

export type EmailPrefKey =
  | "trial_drip"
  | "re_engagement"
  | "daily_digest"
  | "alert_emails";

export type EmailPrefsResponse = {
  prefs: Record<EmailPrefKey, boolean>;
  categories: Array<{
    key: EmailPrefKey;
    label: string;
    description: string;
  }>;
};

export type CongressTrade = {
  id: number;
  politician: string;
  chamber: string;
  party: string;
  symbol: string;
  direction: string;
  amount_min: number;
  amount_max: number;
  trade_date: string;
  disclosed_at: string;
};

/**
 * One row of the Recent Insider Buys feed (SEC Form 4 via Finnhub).
 * Replaces the legacy 13F HoldingItem shape — see /api/holdings router
 * for the schema change rationale.
 */
export type InsiderTxn = {
  symbol: string;
  insider_name: string;
  transaction_date: string; // YYYY-MM-DD
  share_change: number;     // negative = sale, positive = buy
  transaction_price: number;
  transaction_value: number; // abs(shares * price), pre-computed
  code: string;              // SEC Form 4 code: P=open-market buy, S=sale, A=grant, M=option exercise, G=gift
};

// Re-exported for backwards-compat with components that imported the old name.
// New code should import `InsiderTxn` directly.
export type HoldingItem = InsiderTxn;

export type TrackedFund = {
  name: string;
  manager: string;
  cik: string;
  slug: string;
};

export type AlertRule = {
  id: number;
  name: string;
  rule_type: "score" | "squeeze" | "regime" | "congress" | "news";
  symbol: string | null;
  threshold: number | null;
  channel: "email" | "telegram" | "web_push";
  enabled: boolean;
  last_fired_at: string | null;
  created_at: string;
};

export type AlertEvent = {
  id: number;
  rule_id: number;
  symbol: string | null;
  message: string;
  channel: string;
  delivered: boolean;
  created_at: string;
};

async function post<T>(path: string, body: unknown, token?: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    handle401(res.status);
    await throwForStatus(res);
  }
  return res.json();
}

async function del<T>(path: string, token?: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    credentials: "include",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    handle401(res.status);
    await throwForStatus(res);
  }
  return res.json();
}

async function patch<T>(path: string, body: unknown, token?: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    handle401(res.status);
    await throwForStatus(res);
  }
  return res.json();
}

async function getAuth<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    credentials: "include",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    handle401(res.status);
    await throwForStatus(res);
  }
  return res.json();
}

export const api = {
  scanner: (params: Record<string, string | number> = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)]))
    );
    return get<{ count: number; items: ScannerRow[] }>(`/api/scanner?${qs}`);
  },
  squeeze: () => get<{ count: number; items: SqueezeRow[] }>("/api/squeeze"),
  regime: () => get<Regime>("/api/regime"),
  congress: () => get<{ count: number; items: CongressTrade[] }>("/api/congress"),
  ticker: (symbol: string) => get<TickerDetail>(`/api/ticker/${symbol}`),
  tickerRatings: (symbol: string) => get<AnalystRatings>(`/api/ticker/${symbol}/ratings`),
  tickerFinancials: (symbol: string) =>
    get<TickerFinancials>(`/api/ticker/${symbol}/financials`),
  tickerInsider: (symbol: string, daysBack = 90) =>
    get<TickerInsiderResponse>(`/api/ticker/${symbol}/insider?days_back=${daysBack}`),
  emailPrefsGet: () =>
    get<EmailPrefsResponse>(`/api/me/email-prefs`),
  emailPrefsPatch: async (partial: Partial<Record<EmailPrefKey, boolean>>) => {
    const res = await fetch(`${API_BASE}/api/me/email-prefs`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(partial),
    });
    if (!res.ok) {
      handle401(res.status);
      await throwForStatus(res);
    }
    return res.json() as Promise<{ prefs: Record<EmailPrefKey, boolean> }>;
  },
  news: (symbol?: string, limit = 20) => {
    const qs = new URLSearchParams({ limit: String(limit), ...(symbol ? { symbol } : {}) });
    return get<{ count: number; items: Array<{ id: string; title: string; publisher: string; published_at: string; url: string; description: string | null; tickers: string[]; sentiment: number | null }> }>(`/api/news?${qs}`);
  },
  inboxList: (params: { status?: string; channel?: string; tier?: number; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status_filter", params.status);
    if (params.channel) qs.set("channel", params.channel);
    if (params.tier !== undefined) qs.set("tier", String(params.tier));
    if (params.limit) qs.set("limit", String(params.limit));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return get<{
      count: number;
      items: Array<{
        id: number;
        channel: string;
        author: string;
        subject: string | null;
        body_preview: string;
        received_at: string;
        tier: number | null;
        tier_reason: string | null;
        suggested_reply: string | null;
        status: string;
        handled_at: string | null;
      }>;
    }>(`/api/inbox${suffix}`);
  },
  inboxApprove: async (id: number, replyText?: string) => {
    const res = await fetch(`${API_BASE}/api/inbox/${id}/approve`, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: replyText ? JSON.stringify({ reply_text: replyText }) : undefined,
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },
  inboxReject: async (id: number) => {
    const res = await fetch(`${API_BASE}/api/inbox/${id}/reject`, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },
  heatmap: (q?: string) => {
    const qs = new URLSearchParams(q ? { q } : {});
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return get<{
      sectors: HeatmapSector[];
      available_sectors: string[];
      query: string | null;
      freshness?: {
        newest_updated_at: string | null;
        oldest_updated_at: string | null;
        max_stale_minutes: number;
        ticker_count: number;
      };
    }>(`/api/heatmap${suffix}`);
  },
  scorecard: (days = 30) => get<{ summary: { days_tracked: number; entries_scored: number; entries_excluded_outliers: number; avg_1d_return: number | null; median_1d_return: number | null; avg_alpha_vs_spy: number | null; median_alpha_vs_spy: number | null; hit_rate_beat_spy: number | null; is_delayed: boolean; delay_days: number }; days: Record<string, ScorecardEntry[]> }>(`/api/scorecard?days=${days}`),
  popularTickers: (n = 8) => get<{ items: Array<{ symbol: string; name: string | null; sector: string | null; score: number | null }>; cached: boolean }>(`/api/scanner/popular?n=${n}`),
  scorecardSymbol: (symbol: string) => get<{
    summary: {
      symbol: string;
      in_universe: boolean;
      name: string | null;
      sector: string | null;
      current_score: number | null;
      current_signal: string | null;
      appearances: number;
      appearances_scored: number;
      entries_excluded_outliers: number;
      avg_1d_return: number | null;
      median_1d_return: number | null;
      avg_alpha_vs_spy: number | null;
      median_alpha_vs_spy: number | null;
      hit_rate_beat_spy: number | null;
      best_alpha: number | null;
      worst_alpha: number | null;
      is_delayed: boolean;
      delay_days: number;
    };
    rows: Array<{
      as_of: string;
      rank: number;
      score_at_flag: number;
      price_at_flag: number;
      price_next_day: number | null;
      change_pct_1d_after: number | null;
      spy_change_pct_1d: number | null;
      alpha_vs_spy: number | null;
    }>;
  }>(`/api/scorecard/symbol/${encodeURIComponent(symbol.toUpperCase())}`),
  // `list_id` (Phase A): when set, narrows the result to one named list.
  // Omitted → all of the caller's items (matches pre-Phase-A behaviour).
  watchlist: (list_id?: number | null) => {
    const qs = list_id != null ? `?list_id=${list_id}` : "";
    return getAuth<{ count: number; items: WatchlistItem[] }>(`/api/watchlist${qs}`, DEV_TOKEN);
  },
  // Phase A: optional list_id. When provided, the new item lands in
  // that list; when omitted, the backend resolves to the user's default
  // list (auto-creates "My Watchlist" on first add for new users).
  watchlistAdd: (symbol: string, alert_threshold_delta = 10, list_id?: number | null) =>
    post<{ id: number; symbol: string; watchlist_id: number | null; baseline_score: number | null }>(
      "/api/watchlist",
      { symbol, alert_threshold_delta, ...(list_id != null ? { list_id } : {}) },
      DEV_TOKEN,
    ),
  // Move an existing item to a different named list.
  watchlistMove: (id: number, watchlist_id: number) =>
    patch<{ id: number; symbol: string; watchlist_id: number }>(
      `/api/watchlist/${id}`,
      { watchlist_id },
      DEV_TOKEN,
    ),
  watchlistRemove: (id: number) => del<{ ok: boolean }>(`/api/watchlist/${id}`, DEV_TOKEN),

  // --- Phase A: multi-watchlists (lists CRUD) + scanner presets ----------
  // Pluralised /api/watchlists is the LIST CRUD; the singular /api/watchlist
  // above remains the ITEM CRUD. Two routers, one tier (`watchlists` cap
  // Free=1 / Pro=5 / Premium=20 enforced server-side; the matching frontend
  // cap is read off /api/me's `tier` field).
  watchlists: () => getAuth<{ count: number; items: WatchlistRow[] }>("/api/watchlists", DEV_TOKEN),
  watchlistCreate: (name: string) =>
    post<WatchlistRow>("/api/watchlists", { name }, DEV_TOKEN),
  watchlistRename: (id: number, name: string) =>
    patch<{ id: number; name: string }>(`/api/watchlists/${id}`, { name }, DEV_TOKEN),
  watchlistDelete: (id: number) =>
    del<{ ok: boolean }>(`/api/watchlists/${id}`, DEV_TOKEN),

  presets: () => getAuth<{ count: number; items: ScannerPresetRow[] }>("/api/presets", DEV_TOKEN),
  presetCreate: (name: string, filters_json: string) =>
    post<ScannerPresetRow>("/api/presets", { name, filters_json }, DEV_TOKEN),
  presetDelete: (id: number) =>
    del<{ ok: boolean }>(`/api/presets/${id}`, DEV_TOKEN),
  /**
   * Recent Insider Buys feed. Backed by SEC Form 4 filings via Finnhub.
   * Replaces the legacy 13F holdings call; URL `/api/holdings` is unchanged
   * for backwards-compat but the response schema is now InsiderTxn[].
   */
  holdings: (params: { symbol?: string; days?: number; buys_only?: boolean; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.symbol) qs.set("symbol", params.symbol);
    if (params.days) qs.set("days", String(params.days));
    if (params.buys_only) qs.set("buys_only", "true");
    if (params.limit) qs.set("limit", String(params.limit));
    return getAuth<{ count: number; items: InsiderTxn[]; feed_size: number }>(`/api/holdings?${qs}`, DEV_TOKEN);
  },
  // Legacy endpoint kept for compatibility; returns empty list now.
  holdingsFunds: () => getAuth<{ items: TrackedFund[] }>("/api/holdings/funds", DEV_TOKEN),
  roadmap: {
    votes: () => get<{ counts: Record<string, number>; my_votes: string[] }>("/api/roadmap/votes"),
    vote: (item_slug: string) => post<{ ok: boolean; duplicate?: boolean }>("/api/roadmap/vote", { item_slug }, DEV_TOKEN),
    unvote: (item_slug: string) => del<{ ok: boolean }>(`/api/roadmap/vote?item_slug=${encodeURIComponent(item_slug)}`, DEV_TOKEN),
  },
  alertRuleCreate: (body: {
    name: string;
    rule_type: AlertRule["rule_type"];
    symbol?: string | null;
    threshold?: number | null;
    channel?: AlertRule["channel"];
  }) => post<AlertRule>("/api/alerts/rules", body, DEV_TOKEN),
  alertRules: () => getAuth<{ count: number; items: AlertRule[] }>(
    "/api/alerts/rules", DEV_TOKEN,
  ),
  alertRuleDelete: (id: number) =>
    del<{ ok: boolean }>(`/api/alerts/rules/${id}`, DEV_TOKEN),
  alertEvents: (limit = 50) => getAuth<{ count: number; items: AlertEvent[] }>(
    `/api/alerts/events?limit=${limit}`, DEV_TOKEN,
  ),

  // --- Two-factor auth (TOTP) — all tiers, /app/settings/security ----------
  twoFAStatus: () => get<{ enabled: boolean }>("/api/me/2fa"),
  twoFASetup: () =>
    post<{ secret: string; otpauth_uri: string; qr_svg: string }>("/api/me/2fa/setup", {}, DEV_TOKEN),
  twoFAEnable: (code: string) =>
    post<{ ok: boolean; recovery_codes: string[] }>("/api/me/2fa/enable", { code }, DEV_TOKEN),
  twoFADisable: (password: string) =>
    post<{ ok: boolean }>("/api/me/2fa/disable", { password }, DEV_TOKEN),
};
