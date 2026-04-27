/**
 * Client-side auth helpers. Uses httpOnly cookies (set by the backend),
 * so the frontend never touches raw tokens. All we do here is call the API
 * and cache the resulting user object in React state.
 */

export type SessionUser = {
  id: string;
  email: string;
  name: string | null;
  tier: "free" | "starter" | "pro" | "premium";
  is_admin?: boolean;
  is_lifetime?: boolean;
  trial_ends_at?: string | null;
  referral_code?: string | null;
  telegram_chat_id?: string | null;
  phone_number?: string | null;
  created_at: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({} as any));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

type SignupExtras = {
  ref?: string;
  company?: string;          // honeypot — must be empty for humans
  turnstile_token?: string;  // Cloudflare Turnstile token (if configured)
};

export const authApi = {
  session: () => req<{ user: SessionUser | null }>("/api/auth/session"),
  signup: (email: string, password: string, name?: string, extras?: SignupExtras) =>
    req<{ user: SessionUser }>("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password, name, ...extras }),
    }),
  signin: (email: string, password: string) =>
    req<{ user: SessionUser }>("/api/auth/signin", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  signout: () => req<{ ok: boolean }>("/api/auth/signout", { method: "POST" }),
};

// Feature-gating helpers mirroring backend tier.py
const TIER_ORDER: Record<SessionUser["tier"], number> = { free: 0, starter: 1, pro: 2, premium: 3 };

export function hasMinTier(user: SessionUser | null, minTier: SessionUser["tier"]): boolean {
  if (!user) return minTier === "free";
  return TIER_ORDER[user.tier] >= TIER_ORDER[minTier];
}

export const FEATURE_TIERS = {
  "scanner.full":       "pro" as const,
  "scanner.live":       "pro" as const,
  "watchlist":          "pro" as const,
  "squeeze":            "pro" as const,
  "regime.full":        "pro" as const,
  "heatmap":            "pro" as const,
  "alerts.email":       "pro" as const,
  "ticker.full":        "pro" as const,
  "congress":           "premium" as const,
  "alerts.telegram":    "premium" as const,
  "alerts.sms":         "premium" as const,
  "briefing":           "premium" as const,
  "api":                "premium" as const,
  "holdings.elite":     "premium" as const,
  "csv_export":         "pro" as const,
};

export function canUse(user: SessionUser | null, feature: keyof typeof FEATURE_TIERS): boolean {
  return hasMinTier(user, FEATURE_TIERS[feature]);
}
