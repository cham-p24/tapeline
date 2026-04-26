const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
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

export type HoldingItem = {
  id: number;
  fund_name: string;
  manager: string;
  cik: string;
  symbol: string;
  value_usd: number;
  shares: number;
  percent_portfolio: number;
  fetched_at: string;
};

export type TrackedFund = {
  name: string;
  manager: string;
  cik: string;
  slug: string;
};

async function post<T>(path: string, body: unknown, token?: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function del<T>(path: string, token?: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function getAuth<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// For dev: all authenticated calls use "dev-bypass" to hit the premium dev user.
// Production swaps this for the Clerk session token.
const DEV_TOKEN = "dev-bypass";

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
  news: (symbol?: string, limit = 20) => {
    const qs = new URLSearchParams({ limit: String(limit), ...(symbol ? { symbol } : {}) });
    return get<{ count: number; items: Array<{ id: string; title: string; publisher: string; published_at: string; url: string; description: string | null; tickers: string[]; sentiment: number | null }> }>(`/api/news?${qs}`);
  },
  heatmap: () => get<{ sectors: HeatmapSector[] }>("/api/heatmap"),
  scorecard: (days = 30) => get<{ summary: { days_tracked: number; entries_scored: number; avg_1d_return: number | null; avg_alpha_vs_spy: number | null; hit_rate_beat_spy: number | null }; days: Record<string, ScorecardEntry[]> }>(`/api/scorecard?days=${days}`),
  watchlist: () => getAuth<{ count: number; items: WatchlistItem[] }>("/api/watchlist", DEV_TOKEN),
  watchlistAdd: (symbol: string, alert_threshold_delta = 10) =>
    post<{ id: number; symbol: string; baseline_score: number | null }>("/api/watchlist", { symbol, alert_threshold_delta }, DEV_TOKEN),
  watchlistRemove: (id: number) => del<{ ok: boolean }>(`/api/watchlist/${id}`, DEV_TOKEN),
  holdings: (params: { symbol?: string; fund?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.symbol) qs.set("symbol", params.symbol);
    if (params.fund) qs.set("fund", params.fund);
    if (params.limit) qs.set("limit", String(params.limit));
    return getAuth<{ count: number; items: HoldingItem[] }>(`/api/holdings?${qs}`, DEV_TOKEN);
  },
  holdingsFunds: () => getAuth<{ items: TrackedFund[] }>("/api/holdings/funds", DEV_TOKEN),
};
