/**
 * UTM capture + persistence.
 *
 * Marketing-attribution gap we're closing: when a visitor lands from a
 * podcast / fintwit reply / cold email / Reddit post with a tagged URL
 * (`?utm_source=podcast&utm_campaign=acquirers&utm_medium=podcast`) and
 * doesn't sign up immediately, the UTM is gone by the time they come back
 * the next day. Without persistence the signup looks "direct" and we
 * can't attribute revenue to the channel that actually converted them.
 *
 * Flow:
 *   1. captureUtmFromLocation() — runs on every page load in the root
 *      layout's client-side bootstrap. If the current URL has any
 *      `utm_*` query params, write them to localStorage with a 30-day
 *      TTL. Don't overwrite an existing capture (first-touch
 *      attribution — first paid channel that brought them wins, not
 *      the last refresh from a direct visit).
 *   2. getStoredUtm() — read back the captured triplet. Returns an
 *      empty object if nothing's stored or storage is unavailable
 *      (Safari private mode, blocked storage, SSR).
 *   3. Signup page + NewsletterCapture component both call
 *      getStoredUtm() and forward the keys to their POST bodies.
 *
 * No PII. The five UTM fields are the standard Google/Bing/Facebook
 * marketing attribution params — `utm_source`, `utm_medium`,
 * `utm_campaign`, `utm_term`, `utm_content`. Nothing identifiable.
 */

const STORAGE_KEY = "tapeline_utm_v1";
const TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30 days

export type UtmPayload = {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_term?: string;
  utm_content?: string;
};

type StoredUtm = UtmPayload & { captured_at: number };

const UTM_KEYS: (keyof UtmPayload)[] = [
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_term",
  "utm_content",
];

function isStorageAvailable(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const probe = "__tl_utm_probe__";
    window.localStorage.setItem(probe, "1");
    window.localStorage.removeItem(probe);
    return true;
  } catch {
    return false;
  }
}

/**
 * Read the persisted UTM. Returns {} if nothing's stored, the stored
 * value is malformed, the TTL has expired, or storage is unavailable.
 *
 * Safe to call from SSR — returns {} on the server.
 */
export function getStoredUtm(): UtmPayload {
  if (!isStorageAvailable()) return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as StoredUtm;
    if (typeof parsed !== "object" || parsed === null) return {};
    if (
      typeof parsed.captured_at !== "number" ||
      Date.now() - parsed.captured_at > TTL_MS
    ) {
      // Expired — clear so we don't return stale data on later visits.
      window.localStorage.removeItem(STORAGE_KEY);
      return {};
    }
    const out: UtmPayload = {};
    for (const k of UTM_KEYS) {
      const v = parsed[k];
      if (typeof v === "string" && v.length > 0) {
        out[k] = v;
      }
    }
    return out;
  } catch {
    return {};
  }
}

/**
 * If the current URL has any utm_* params, capture them to localStorage.
 * First-touch wins: if a capture already exists and hasn't expired, this
 * is a no-op. That way the podcast that brought the user gets credit
 * over the direct refresh that converted them.
 *
 * Returns the captured (or already-stored) UTM payload for convenience.
 */
export function captureUtmFromLocation(): UtmPayload {
  if (typeof window === "undefined") return {};
  if (!isStorageAvailable()) return {};

  // If we already have a fresh capture, don't overwrite — first-touch.
  const existing = getStoredUtm();
  if (Object.keys(existing).length > 0) return existing;

  let url: URL;
  try {
    url = new URL(window.location.href);
  } catch {
    return {};
  }

  const captured: UtmPayload = {};
  for (const k of UTM_KEYS) {
    const v = url.searchParams.get(k);
    if (v && v.length > 0) {
      // Cap length defensively — backend cols are 80–120 chars.
      captured[k] = v.slice(0, 120);
    }
  }

  if (Object.keys(captured).length === 0) return {};

  try {
    const toStore: StoredUtm = { ...captured, captured_at: Date.now() };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(toStore));
  } catch {
    // Best-effort. If storage threw, return the captured payload anyway
    // so the caller can still forward it to the backend in-flight.
  }
  return captured;
}

/**
 * Reset the captured UTM. Called after a successful signup so a user
 * who later signs up a friend on the same device starts a fresh
 * attribution chain.
 */
export function clearStoredUtm(): void {
  if (!isStorageAvailable()) return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/**
 * Google click-ID capture + persistence — same mechanism as the UTM block
 * above, kept here so both attribution captures share one storage helper.
 *
 * Why this exists (Growth Playbook §3.7 "subscriber-quality unlock"): Google
 * Ads stamps every paid click with a click identifier — `gclid` for Search/
 * Display, `gbraid` / `wbraid` for the iOS-privacy app/web variants. Uploading
 * that identifier back to Google with the eventual conversion (the offline
 * conversion import / value-based-bidding loop) is what lets Smart Bidding
 * optimise toward *subscribers* rather than raw signups. The upload itself is
 * founder-gated (needs Ads API credentials), so this file's only job is to
 * CAPTURE + STORE the click ID at landing so it's AVAILABLE on the User row
 * when the upload pipeline is later turned on.
 *
 * Same persistence contract as UTM: capture on landing, localStorage with a
 * 30-day TTL, first-touch wins, forward on the signup POST. No PII — these are
 * opaque Google-issued click tokens.
 */

const GCLID_STORAGE_KEY = "tapeline_gclid_v1";

export type GclidPayload = {
  gclid?: string;
  gbraid?: string;
  wbraid?: string;
};

type StoredGclid = GclidPayload & { captured_at: number };

const GCLID_KEYS: (keyof GclidPayload)[] = ["gclid", "gbraid", "wbraid"];

/**
 * Read the persisted Google click IDs. Returns {} if nothing's stored, the
 * stored value is malformed, the TTL has expired, or storage is unavailable.
 * Safe to call from SSR — returns {} on the server.
 */
export function getStoredGclid(): GclidPayload {
  if (!isStorageAvailable()) return {};
  try {
    const raw = window.localStorage.getItem(GCLID_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as StoredGclid;
    if (typeof parsed !== "object" || parsed === null) return {};
    if (
      typeof parsed.captured_at !== "number" ||
      Date.now() - parsed.captured_at > TTL_MS
    ) {
      // Expired — clear so we don't return stale data on later visits.
      window.localStorage.removeItem(GCLID_STORAGE_KEY);
      return {};
    }
    const out: GclidPayload = {};
    for (const k of GCLID_KEYS) {
      const v = parsed[k];
      if (typeof v === "string" && v.length > 0) {
        out[k] = v;
      }
    }
    return out;
  } catch {
    return {};
  }
}

/**
 * If the current URL has a gclid/gbraid/wbraid param, capture it to
 * localStorage. First-touch wins: if a fresh capture already exists, this is a
 * no-op so the original paid click keeps credit over a later direct refresh.
 *
 * Returns the captured (or already-stored) payload for convenience.
 */
export function captureGclidFromLocation(): GclidPayload {
  if (typeof window === "undefined") return {};
  if (!isStorageAvailable()) return {};

  // First-touch: don't overwrite an existing fresh capture.
  const existing = getStoredGclid();
  if (Object.keys(existing).length > 0) return existing;

  let url: URL;
  try {
    url = new URL(window.location.href);
  } catch {
    return {};
  }

  const captured: GclidPayload = {};
  for (const k of GCLID_KEYS) {
    const v = url.searchParams.get(k);
    if (v && v.length > 0) {
      // Cap defensively — backend cols are 200 chars (gclids are long).
      captured[k] = v.slice(0, 200);
    }
  }

  if (Object.keys(captured).length === 0) return {};

  try {
    const toStore: StoredGclid = { ...captured, captured_at: Date.now() };
    window.localStorage.setItem(GCLID_STORAGE_KEY, JSON.stringify(toStore));
  } catch {
    // Best-effort — return the captured payload anyway so the caller can
    // still forward it to the backend in-flight.
  }
  return captured;
}

/**
 * Reset the captured Google click IDs. Called after a successful signup so a
 * later signup on the same device starts a fresh attribution chain.
 */
export function clearStoredGclid(): void {
  if (!isStorageAvailable()) return;
  try {
    window.localStorage.removeItem(GCLID_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/**
 * Meta click-ID capture + persistence — the same mechanism as the gclid block
 * above, for the other paid-click platform.
 *
 * Why this exists (Paid Ads Metrics Bible §7.1, gap G4). Meta stamps every
 * paid click with `?fbclid=`. Two things depend on us keeping it:
 *
 *   1. **Event Match Quality.** The Conversions API otherwise sees only a
 *      hashed email and a hashed user id, which caps EMQ around 5-6 — at
 *      Meta's "good" floor and well short of what a high-intent event wants.
 *      `fbc`, derived from this value, is the cheapest available upgrade and
 *      requires NO new personal data. (Do not chase EMQ by collecting phone
 *      or date of birth: a scanner signup has no legitimate reason to hold
 *      them.)
 *   2. **Counting Meta payers at all.** The trial is 14 days, so the first
 *      charge always lands outside Meta's 7-day click window and the
 *      in-platform Purchase column reads ~0 no matter what really happened.
 *      Joining this click ID to our own Stripe rows is the only honest count.
 *
 * We store the RAW fbclid. Meta's wire format is `fb.1.<ms>.<fbclid>` and a
 * bare fbclid is rejected — but that string is built server-side by
 * `services/meta_capi.fbc_value()`, so one function owns the format for both
 * the signup event and the webhook-fired events days later, where no browser
 * exists to have built it.
 *
 * Same persistence contract as the rest: capture on landing, localStorage
 * with a 30-day TTL, first-touch wins, forward on the signup POST. No PII —
 * an fbclid is an opaque Meta-issued click token.
 */

const FBCLID_STORAGE_KEY = "tapeline_fbclid_v1";

export type FbclidPayload = {
  fbclid?: string;
};

type StoredFbclid = FbclidPayload & { captured_at: number };

/**
 * Read the persisted Meta click ID. Returns {} if nothing's stored, the
 * stored value is malformed, the TTL has expired, or storage is unavailable.
 * Safe to call from SSR — returns {} on the server.
 */
export function getStoredFbclid(): FbclidPayload {
  if (!isStorageAvailable()) return {};
  try {
    const raw = window.localStorage.getItem(FBCLID_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as StoredFbclid;
    if (typeof parsed !== "object" || parsed === null) return {};
    if (
      typeof parsed.captured_at !== "number" ||
      Date.now() - parsed.captured_at > TTL_MS
    ) {
      // Expired — clear so we don't return stale data on later visits.
      window.localStorage.removeItem(FBCLID_STORAGE_KEY);
      return {};
    }
    const v = parsed.fbclid;
    if (typeof v === "string" && v.length > 0) return { fbclid: v };
    return {};
  } catch {
    return {};
  }
}

/**
 * If the current URL has an `?fbclid=` param, capture it to localStorage.
 * First-touch wins: if a fresh capture already exists this is a no-op, so the
 * paid click that originally brought the visitor keeps credit over a later
 * direct refresh.
 *
 * Returns the captured (or already-stored) payload for convenience.
 */
export function captureFbclidFromLocation(): FbclidPayload {
  if (typeof window === "undefined") return {};
  if (!isStorageAvailable()) return {};

  // First-touch: don't overwrite an existing fresh capture.
  const existing = getStoredFbclid();
  if (Object.keys(existing).length > 0) return existing;

  let url: URL;
  try {
    url = new URL(window.location.href);
  } catch {
    return {};
  }

  const v = url.searchParams.get("fbclid");
  if (!v || v.length === 0) return {};
  // Cap defensively — backend col is 200 chars, same as the gclid family.
  const captured: FbclidPayload = { fbclid: v.slice(0, 200) };

  try {
    const toStore: StoredFbclid = { ...captured, captured_at: Date.now() };
    window.localStorage.setItem(FBCLID_STORAGE_KEY, JSON.stringify(toStore));
  } catch {
    // Best-effort — return the captured payload anyway so the caller can
    // still forward it to the backend in-flight.
  }
  return captured;
}

/**
 * Reset the captured Meta click ID. Called after a successful signup so a
 * later signup on the same device starts a fresh attribution chain.
 */
export function clearStoredFbclid(): void {
  if (!isStorageAvailable()) return;
  try {
    window.localStorage.removeItem(FBCLID_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/**
 * Read Meta's `_fbp` first-party browser cookie, if the pixel has written
 * one. Unlike the captures above this is NOT ours to persist: the pixel owns
 * the cookie, its own TTL and its own value, and there is no column for it —
 * it is read at submit time and forwarded straight onto the server-side
 * CompleteRegistration event as the second unhashed identifier Meta matches
 * on. Returns "" whenever the pixel was blocked or never ran, which is
 * common in this audience and must degrade silently.
 */
export function readFbpCookie(): string {
  if (typeof document === "undefined") return "";
  try {
    for (const part of document.cookie.split(";")) {
      const [rawName, ...rest] = part.split("=");
      if (rawName.trim() !== "_fbp") continue;
      const value = decodeURIComponent(rest.join("=").trim());
      return value.slice(0, 200);
    }
  } catch {
    /* cookies unavailable — the event just goes without it */
  }
  return "";
}

/**
 * Referrer-host capture + persistence — same mechanism as the UTM and gclid
 * blocks above, kept here so all attribution captures share one storage
 * helper.
 *
 * Why this exists: AI-assistant referrals (Copilot, ChatGPT, Perplexity, …)
 * carry NO utm_* params — the only trace is `document.referrer`. Without
 * capturing it, a real Copilot-referred signup lands as "direct" and the
 * channel is uncountable. A confirmed Premium-trial signup arrived from
 * copilot.com exactly this way.
 *
 * Privacy: we store the referrer HOSTNAME ONLY — never the path or query
 * string (which can carry the user's search/chat text). No PII.
 *
 * Same persistence contract as UTM: capture on landing, localStorage with a
 * 30-day TTL, first-touch wins, forward on the signup POST. Internal
 * navigation (tapeline.io → tapeline.io, or same-host in dev) is skipped so
 * a page-to-page hop can't claim credit.
 */

const REFERRER_STORAGE_KEY = "tapeline_ref_host_v1";

export type ReferrerHostPayload = {
  signup_referrer_host?: string;
};

type StoredReferrerHost = ReferrerHostPayload & { captured_at: number };

/** True when `host` is our own site (or the page's own host in dev). */
function isOwnHost(host: string): boolean {
  const own = window.location.hostname.toLowerCase();
  const h = host.toLowerCase();
  return h === own || h === "tapeline.io" || h.endsWith(".tapeline.io");
}

/**
 * Read the persisted referrer host. Returns {} if nothing's stored, the
 * stored value is malformed, the TTL has expired, or storage is unavailable.
 * Safe to call from SSR — returns {} on the server.
 */
export function getStoredReferrerHost(): ReferrerHostPayload {
  if (!isStorageAvailable()) return {};
  try {
    const raw = window.localStorage.getItem(REFERRER_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as StoredReferrerHost;
    if (typeof parsed !== "object" || parsed === null) return {};
    if (
      typeof parsed.captured_at !== "number" ||
      Date.now() - parsed.captured_at > TTL_MS
    ) {
      // Expired — clear so we don't return stale data on later visits.
      window.localStorage.removeItem(REFERRER_STORAGE_KEY);
      return {};
    }
    const v = parsed.signup_referrer_host;
    if (typeof v === "string" && v.length > 0) {
      return { signup_referrer_host: v };
    }
    return {};
  } catch {
    return {};
  }
}

/**
 * If the document has an EXTERNAL referrer, capture its hostname to
 * localStorage. First-touch wins: if a fresh capture already exists, this is
 * a no-op so the site that originally brought the user keeps credit over a
 * later visit's referrer.
 *
 * Skipped entirely when the referrer is empty (direct traffic) or points at
 * our own host — internal navigation must never claim attribution.
 *
 * Returns the captured (or already-stored) payload for convenience.
 */
export function captureReferrerHostFromLocation(): ReferrerHostPayload {
  if (typeof window === "undefined") return {};
  if (!isStorageAvailable()) return {};

  // First-touch: don't overwrite an existing fresh capture.
  const existing = getStoredReferrerHost();
  if (Object.keys(existing).length > 0) return existing;

  const ref = typeof document !== "undefined" ? document.referrer : "";
  if (!ref) return {};

  let host: string;
  try {
    // Hostname ONLY — the path/query of an AI-chat referrer can contain the
    // user's prompt text. We never read or store it.
    host = new URL(ref).hostname;
  } catch {
    return {};
  }

  if (!host || isOwnHost(host)) return {};

  // Cap defensively — backend col is 100 chars.
  const captured: ReferrerHostPayload = {
    signup_referrer_host: host.slice(0, 100),
  };

  try {
    const toStore: StoredReferrerHost = {
      ...captured,
      captured_at: Date.now(),
    };
    window.localStorage.setItem(REFERRER_STORAGE_KEY, JSON.stringify(toStore));
  } catch {
    // Best-effort — return the captured payload anyway so the caller can
    // still forward it to the backend in-flight.
  }
  return captured;
}

/**
 * Reset the captured referrer host. Called after a successful signup so a
 * later signup on the same device starts a fresh attribution chain.
 */
export function clearStoredReferrerHost(): void {
  if (!isStorageAvailable()) return;
  try {
    window.localStorage.removeItem(REFERRER_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/**
 * Landing-PATH capture + persistence — same mechanism as the UTM, gclid and
 * referrer-host blocks above.
 *
 * Why this exists: the captures above answer "which CHANNEL brought this
 * user" (organic / copilot.com / a paid click). They cannot answer "which
 * PAGE earned them". Tapeline publishes ~4,750 SEO URLs — ticker pages,
 * /compare/*, /best-stocks-for/*, /sectors, /glossary/* — so "organic search
 * brought 6 signups" is unactionable on its own: you can't tell whether
 * /compare/finviz, /glossary/rsi or a ticker page did the work, and so you
 * can't double down on the format that converts. Storing the first-touch
 * pathname turns the channel readout into a content readout.
 *
 * Privacy: PATH ONLY. The query string and hash are never read or stored —
 * they can carry search terms, session tokens or other identifiers, and they
 * explode cardinality. `window.location.pathname` already excludes both; we
 * additionally normalise (lowercase, drop a trailing slash) so /Glossary/RSI/
 * and /glossary/rsi aggregate as one row instead of three.
 *
 * Same persistence contract as the rest: capture on landing, localStorage
 * with a 30-day TTL, first-touch wins (the page that originally brought them
 * keeps credit over whatever page they happened to convert on), forward on
 * the signup POST.
 */

const LANDING_PATH_STORAGE_KEY = "tapeline_landing_path_v1";

/** Matches the backend column width (users.signup_landing_path). */
const LANDING_PATH_MAX = 200;

export type LandingPathPayload = {
  signup_landing_path?: string;
};

type StoredLandingPath = LandingPathPayload & { captured_at: number };

/**
 * Normalise a pathname for stable aggregation:
 *   - strip anything from the first `?` or `#` (defensive — pathname never
 *     contains them, but a caller could hand us a full href)
 *   - lowercase, so /Glossary/RSI and /glossary/rsi are one bucket
 *   - drop a trailing slash (but keep the root "/")
 *   - cap at the column width
 * Returns "" for anything that isn't a rooted path.
 */
function normaliseLandingPath(raw: string): string {
  let p = (raw || "").trim();
  const cut = Math.min(
    ...[p.indexOf("?"), p.indexOf("#")].filter((i) => i >= 0).concat([p.length]),
  );
  p = p.slice(0, cut).toLowerCase();
  // Must be a site-relative path. "//host" is protocol-relative (i.e. an
  // external URL) — reject it rather than storing someone else's domain.
  if (!p.startsWith("/") || p.startsWith("//")) return "";
  if (p.length > 1 && p.endsWith("/")) p = p.slice(0, -1);
  return p.slice(0, LANDING_PATH_MAX);
}

/**
 * Read the persisted landing path. Returns {} if nothing's stored, the stored
 * value is malformed, the TTL has expired, or storage is unavailable.
 * Safe to call from SSR — returns {} on the server.
 */
export function getStoredLandingPath(): LandingPathPayload {
  if (!isStorageAvailable()) return {};
  try {
    const raw = window.localStorage.getItem(LANDING_PATH_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as StoredLandingPath;
    if (typeof parsed !== "object" || parsed === null) return {};
    if (
      typeof parsed.captured_at !== "number" ||
      Date.now() - parsed.captured_at > TTL_MS
    ) {
      // Expired — clear so we don't return stale data on later visits.
      window.localStorage.removeItem(LANDING_PATH_STORAGE_KEY);
      return {};
    }
    const v = parsed.signup_landing_path;
    if (typeof v === "string" && v.length > 0) {
      return { signup_landing_path: v };
    }
    return {};
  } catch {
    return {};
  }
}

/**
 * Capture the current pathname to localStorage. First-touch wins: if a fresh
 * capture already exists this is a no-op, so the article/comparison page that
 * originally pulled the visitor in keeps credit over /signup — the page they
 * were merely standing on when they converted.
 *
 * Path only — the query string and hash are never read.
 *
 * Returns the captured (or already-stored) payload for convenience.
 */
export function captureLandingPathFromLocation(): LandingPathPayload {
  if (typeof window === "undefined") return {};
  if (!isStorageAvailable()) return {};

  // First-touch: don't overwrite an existing fresh capture.
  const existing = getStoredLandingPath();
  if (Object.keys(existing).length > 0) return existing;

  // pathname excludes search + hash by construction; normalise anyway.
  const path = normaliseLandingPath(window.location.pathname || "");
  if (!path) return {};

  const captured: LandingPathPayload = { signup_landing_path: path };

  try {
    const toStore: StoredLandingPath = { ...captured, captured_at: Date.now() };
    window.localStorage.setItem(
      LANDING_PATH_STORAGE_KEY,
      JSON.stringify(toStore),
    );
  } catch {
    // Best-effort — return the captured payload anyway so the caller can
    // still forward it to the backend in-flight.
  }
  return captured;
}

/**
 * Reset the captured landing path. Called after a successful signup so a
 * later signup on the same device starts a fresh attribution chain.
 */
export function clearStoredLandingPath(): void {
  if (!isStorageAvailable()) return;
  try {
    window.localStorage.removeItem(LANDING_PATH_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}
