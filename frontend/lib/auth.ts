/**
 * Client-side auth helpers. Uses httpOnly cookies (set by the backend),
 * so the frontend never touches raw tokens. All we do here is call the API
 * and cache the resulting user object in React state.
 */

export type SessionUser = {
  id: string;
  email: string;
  name: string | null;
  tier: "free" | "pro" | "premium";
  is_admin?: boolean;
  is_lifetime?: boolean;
  trial_ends_at?: string | null;
  referral_code?: string | null;
  telegram_chat_id?: string | null;
  phone_number?: string | null;
  discord_webhook_url?: string | null;
  created_at: string | null;
  // Null until the user has submitted (or skipped) /app/onboarding. The
  // frontend post-signup redirect uses this to decide whether to bounce
  // through onboarding before /app/scanner.
  onboarding_completed_at?: string | null;
  // Null until the user clicks the link in their verification email.
  // OAuth signups are auto-verified at the moment of account creation.
  // The /app/* layout uses this to render a "verify your email" banner.
  email_verified_at?: string | null;
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
  company?: string;             // honeypot — must be empty for humans
  turnstile_token?: string;     // Cloudflare Turnstile token (if configured)
  device_fingerprint?: string;  // 16-char hex hash from lib/fingerprint.ts
  // Marketing-attribution UTMs — read from localStorage on submit via
  // lib/utm.ts:getStoredUtm(). Backend writes them once to the User
  // row's signup_utm_* columns; never updated. Optional everywhere
  // since direct/un-tagged traffic is a legitimate signup path.
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_term?: string;
  utm_content?: string;
  // Google Ads click IDs — read from localStorage on submit via
  // lib/utm.ts:getStoredGclid(). Backend writes them once to the User
  // row's signup_gclid/gbraid/wbraid columns so the (founder-gated)
  // offline-conversion upload to Google has the click ID available.
  // Optional — only paid Google clicks carry these.
  gclid?: string;
  gbraid?: string;
  wbraid?: string;
};

// Signin can resolve two ways: a normal success (session cookie set, user
// returned) or a 2FA challenge — the account has TOTP enabled, so instead of
// a session we get a short-lived `mfa_token` to exchange at /api/auth/2fa
// along with an authenticator code. The signin page narrows on the
// `mfa_required` discriminant.
export type SigninResult =
  | { user: SessionUser }
  | { mfa_required: true; mfa_token: string };

export const authApi = {
  session: () => req<{ user: SessionUser | null }>("/api/auth/session"),
  signup: (email: string, password: string, name?: string, extras?: SignupExtras) =>
    req<{ user: SessionUser }>("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password, name, ...extras }),
    }),
  signin: (email: string, password: string) =>
    req<SigninResult>("/api/auth/signin", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  // Second step of a 2FA signin. `code` is a 6-digit TOTP or a recovery code.
  signin2fa: (mfa_token: string, code: string) =>
    req<{ user: SessionUser }>("/api/auth/2fa", {
      method: "POST",
      body: JSON.stringify({ mfa_token, code }),
    }),
  signout: () => req<{ ok: boolean }>("/api/auth/signout", { method: "POST" }),
};

// Feature-gating helpers mirroring backend tier.py
const TIER_ORDER: Record<SessionUser["tier"], number> = { free: 0, pro: 1, premium: 2 };

export function hasMinTier(user: SessionUser | null, minTier: SessionUser["tier"]): boolean {
  if (!user) return minTier === "free";
  return TIER_ORDER[user.tier] >= TIER_ORDER[minTier];
}

export const FEATURE_TIERS = {
  "scanner.full":       "pro" as const,
  "scanner.live":       "pro" as const,
  // Watchlist is a FREE feature — it's the #1 activation on-ramp, so the
  // "★ Add to watchlist" control must never be hidden from Free users. The
  // real gate is the count cap (Free=5), enforced server-side at add-time.
  // Smart ALERTS on watchlist items remain paid (see alerts.* below).
  // Mirrors backend tier.FEATURES["watchlist"] = Tier.FREE.
  "watchlist":          "free" as const,
  "squeeze":            "pro" as const,
  "regime.full":        "pro" as const,
  "heatmap":            "pro" as const,
  "alerts.email":       "pro" as const,
  "ticker.full":        "pro" as const,
  "congress":           "premium" as const,
  "alerts.telegram":    "premium" as const,
  "alerts.web_push":    "pro" as const,
  "briefing":           "premium" as const,
  "api":                "premium" as const,
  "holdings.elite":     "premium" as const,
  "csv_export":         "pro" as const,
  "ratings.analyst":    "premium" as const,
  "insider.form4":      "premium" as const,
};

export function canUse(user: SessionUser | null, feature: keyof typeof FEATURE_TIERS): boolean {
  return hasMinTier(user, FEATURE_TIERS[feature]);
}
