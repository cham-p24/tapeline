"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { track } from "@vercel/analytics";
import { trackEvent } from "@/lib/gtag";
import { api, errorMessage } from "@/lib/api";
import { authApi } from "@/lib/auth";
import { safeNext } from "@/lib/safeNext";
import { getStoredGclid, getStoredUtm } from "@/lib/utm";
import { OAuthButtons } from "@/components/OAuthButtons";

const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "";

declare global {
  interface Window {
    onTapelineTurnstile?: (token: string) => void;
  }
}

// Module-scope Turnstile callback wiring. Registering at module scope (instead
// of inside the component's useEffect) means the callback exists as soon as
// the JS bundle parses — BEFORE React mounts. Cloudflare's widget script can
// auto-solve and invoke the callback before useEffect runs; with the previous
// effect-scoped registration, that auto-solved token was silently dropped on
// the React-state side. The queue + live-setter pattern below buffers any
// pre-mount token and drains it once the component subscribes.
let _turnstileTokenQueue: string | null = null;
let _setTurnstileTokenLive: ((t: string) => void) | null = null;

if (typeof window !== "undefined") {
  (window as { onTapelineTurnstile?: (token: string) => void }).onTapelineTurnstile = (token: string) => {
    if (_setTurnstileTokenLive) {
      _setTurnstileTokenLive(token);
    } else {
      _turnstileTokenQueue = token;
    }
  };
}

// Source-aware signup headlines (message-match). Paid landing pages and the
// /compare/* pages append ?from=<source> to their "Try Premium free" CTA; we
// restate that exact promise in the H1 here so a visitor who clicked a "Finviz
// alternative" ad doesn't hit a generic "Try Premium free" form and bounce.
// Ad → landing message-match is the single highest-confidence funnel lever
// (Unbounce / NN-group information-scent research). Unknown/absent `from`
// falls back to `_default` (the original generic copy — never worse).
const FROM_COPY: Record<string, { h1: string; sub: string }> = {
  _default: {
    h1: "Try Premium free for 14 days",
    sub: "No credit card. Cancel anytime.",
  },
  finviz: {
    h1: "The Finviz alternative — free for 14 days.",
    sub: "One composite score per ticker and a public, back-checked track record — the synthesis Finviz doesn't do. No credit card.",
  },
  screener: {
    h1: "The scanner that shows its receipts.",
    sub: "One score, one sentence, and every pick logged public vs SPY. 14 days of Premium free — no credit card.",
  },
  scorecard: {
    h1: "You've seen the record. Now run the scanner.",
    sub: "The full live universe, every name scored. 14-day Premium trial, no credit card.",
  },
  compare: {
    h1: "Switching to Tapeline? Start free.",
    sub: "One transparent score per ticker plus a public track record. 14 days of Premium free — no credit card.",
  },
};

// Outer page wraps the form in Suspense so useSearchParams() doesn't break prerender.
export default function SignUpPage() {
  return (
    <Suspense fallback={null}>
      <SignUpForm />
    </Suspense>
  );
}

function SignUpForm() {
  const router = useRouter();
  const qp = useSearchParams();
  // Sanitize at the source: `next` is forwarded into /app/onboarding?next=…
  // and the /signin?next=… link below, so guarding here covers every use.
  // Rejects open-redirect payloads (//evil.com, https://evil.com).
  const next = safeNext(qp.get("next"));
  // Plan intent from the marketing /pricing page: its CTAs link to
  // /signup?plan=pro|premium&billing=monthly|annual. Previously these params
  // were silently discarded — a visitor who clicked "Upgrade to Premium —
  // annual" on /pricing was dumped on the scanner post-signup with their
  // purchase intent lost. When a valid plan is present (and no explicit
  // ?next= overrides it), route them to /app/billing after onboarding with
  // the intent restated so the billing page can pre-select it. Checkout is
  // never auto-fired — the user still clicks.
  const planRaw = (qp.get("plan") || "").toLowerCase();
  const planIntent = planRaw === "pro" || planRaw === "premium" ? planRaw : null;
  const billingRaw = (qp.get("billing") || "").toLowerCase();
  const billingIntent = billingRaw === "monthly" || billingRaw === "annual" ? billingRaw : "annual";
  const postAuthNext =
    planIntent && !qp.get("next")
      ? `/app/billing?intent=${planIntent}&billing=${billingIntent}`
      : next;
  // Referral code from /signup?ref=ABCDEFGH. Backend grants both parties
  // 1 free month of Premium when this resolves to a valid existing user.
  const refCode = (qp.get("ref") || "").trim().toUpperCase();
  // Restate the source's promise in the headline (see FROM_COPY above).
  const headline = FROM_COPY[(qp.get("from") || "").toLowerCase()] ?? FROM_COPY._default;

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  // Honeypot — bots fill this, humans never see it. Submitted as `company`.
  const [honeypot, setHoneypot] = useState("");
  // Turnstile token — populated by Cloudflare's widget callback. Empty until solved.
  const [turnstileToken, setTurnstileToken] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const turnstileRef = useRef<HTMLDivElement | null>(null);

  // Live scorecard proof block — fetched once on mount. We surface the one
  // thing that is unambiguously true and on-brand at the moment of decision:
  // the SIZE and DISCIPLINE of the public record (days tracked, same-day, no
  // edits). We deliberately do NOT anchor the buy decision on the hit-rate /
  // median-alpha headline numbers — over a short single-regime sample those
  // are weak and would argue against converting; the full record (winners AND
  // losers) is one click away on /scorecard for anyone who wants to audit.
  // That keeps us honest (nothing hidden) without leading the pitch with our
  // weakest metric. `days_tracked` is tier-invariant so anonymous visitors
  // get it; the block renders nothing until the back-check has logged a day.
  const [proof, setProof] = useState<{ days: number } | null>(null);
  useEffect(() => {
    let cancelled = false;
    api.scorecard(30).then((d) => {
      if (cancelled) return;
      const s = d.summary;
      if (typeof s.days_tracked === "number" && s.days_tracked > 0) {
        setProof({ days: s.days_tracked });
      }
    }).catch(() => { /* silent — no proof block is better than a broken one */ });
    return () => { cancelled = true; };
  }, []);

  // Subscribe React state into the module-scope Turnstile callback. The
  // window.onTapelineTurnstile handler was already registered at module load
  // (see top of file) — here we just point it at our setter and drain any
  // token that arrived before this component mounted (auto-solve race).
  useEffect(() => {
    _setTurnstileTokenLive = setTurnstileToken;
    if (_turnstileTokenQueue) {
      setTurnstileToken(_turnstileTokenQueue);
      _turnstileTokenQueue = null;
    }
    return () => { _setTurnstileTokenLive = null; };
  }, []);

  // Funnel event: fired once on mount when a real human sees the signup form.
  // Pairs with `signup_completed` below to compute drop-off in Vercel Analytics
  // + GA4 (typed event names — see lib/gtag.ts).
  useEffect(() => {
    track("signup_started", { next });
    trackEvent("sign_up_started", { next });
  }, [next]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (password.length < 8) { setErr("Password must be at least 8 characters."); return; }
    // Race: Cloudflare Turnstile can auto-solve BEFORE the useEffect above
    // registers `window.onTapelineTurnstile`. When that happens, React state
    // `turnstileToken` stays empty even though the widget rendered "Success"
    // and populated its hidden `cf-turnstile-response` input. Read from the
    // DOM as a fallback so the user isn't blocked by the race.
    let token = turnstileToken;
    if (TURNSTILE_SITE_KEY && !token && typeof document !== "undefined") {
      const hidden = document.querySelector<HTMLInputElement>(
        'input[name="cf-turnstile-response"]',
      );
      token = hidden?.value || "";
    }
    if (TURNSTILE_SITE_KEY && !token) {
      setErr("Please complete the bot check above.");
      return;
    }
    setBusy(true);
    try {
      const { deviceFingerprint } = await import("@/lib/fingerprint");
      const device_fp = await deviceFingerprint();
      // First-touch UTM attribution. lib/utm.ts persisted these on the
      // landing visit with a 30-day TTL; we forward whatever's stored so
      // the User row carries the channel that originally brought them in
      // (not whatever URL they happened to be on at submit time).
      const utm = getStoredUtm();
      // Google Ads click IDs captured on landing (gclid/gbraid/wbraid).
      // Stored on the User row so the founder-gated offline-conversion
      // upload to Google can later tie this subscriber back to the click.
      const gclid = getStoredGclid();
      await authApi.signup(email, password, name, {
        company: honeypot,
        turnstile_token: token || undefined,
        device_fingerprint: device_fp || undefined,
        ref: refCode || undefined,
        ...utm,
        ...gclid,
      });
      // Funnel events: signup landed cleanly. Trial auto-starts on signup
      // (14-day Premium, no card — see tier.py:_start_trial), so we fire the
      // trial event on the same beat. Property `oauth: false` lets us segment
      // form-vs-OAuth conversion later when OAuth tracking lands.
      // Mirror to GA4 so Search Console can attribute the query → signup
      // chain via Acquisition reports.
      track("signup_completed", { method: "email", next });
      track("trial_started", { tier: "premium", days: 14, method: "email" });
      trackEvent("sign_up", { method: "email" });
      trackEvent("start_trial", { tier: "premium", days: 14, method: "email" });
      // Route through /app/onboarding first — captures investor profile +
      // attribution + marketing-opt-in before they hit the product. The
      // onboarding page redirects to the post-auth destination after submit
      // or skip: /app/billing (with plan intent restated) when the visitor
      // arrived from a /pricing plan CTA, otherwise the default `next`.
      // Existing users (signin) never pass through here.
      router.push(`/app/onboarding?next=${encodeURIComponent(postAuthNext)}`);
      router.refresh();
    } catch (e: unknown) {
      setErr(errorMessage(e) || "Sign up failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main" className="relative min-h-screen">
      <div className="pointer-events-none absolute inset-0 bg-hero opacity-60" />

      <div className="relative flex min-h-screen items-center justify-center px-6 py-10">
        <div className="w-full max-w-sm">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-2 w-6 rounded-full bg-gradient-to-r from-accent to-accent2" />
            <span className="text-lg font-semibold tracking-tight">Tapeline</span>
          </Link>

          <h1 className="mt-10 text-3xl font-bold tracking-tight">{headline.h1}</h1>
          <p className="mt-2 text-sm text-muted">{headline.sub}</p>

          {/* Value strip at the decision point — coherent with what the landing
              pages now promise (free-forever + 30-day money-back), not just the
              14-day trial the page used to over-emphasise. Descriptive only. */}
          <p className="mt-4 text-xs text-muted">
            Free forever &middot; No credit card &middot; 14-day Premium trial &middot; 30-day money-back on paid plans
          </p>

          {/* PRIMARY signup path: Google-first, above the fold, first thing the
              visitor sees. Most visitors are already logged into Google, so a
              one-click path converts far better than a forced email/password
              form. OAuthButtons feature-detects via /api/auth/oauth/providers
              and renders nothing when no provider is enabled — when that
              happens this whole block collapses and the email form below
              becomes the (fully usable) primary path, so the page is never
              broken. postAuthNext carries the same plan/next intent the email
              path carries (see postAuthNext above), so a visitor from /pricing
              keeps their context through Google signup. */}
          <div className="mt-6">
            <OAuthButtons
              position="top"
              variant="primary"
              postAuthNext={postAuthNext}
              onProviderClick={(provider) => {
                // Mirror the email path's funnel start so OAuth conversion is
                // measurable alongside it. sign_up (completed) fires backend-
                // side on the OAuth callback; here we only mark intent.
                track("signup_started", { next, method: provider });
                trackEvent("sign_up_started", { next, method: provider });
              }}
            />
          </div>

          {/* Public-record proof — leads with the SIZE + DISCIPLINE of the
              track record (true, on-brand, decision-safe) rather than the
              short-sample hit-rate/alpha headline. The "winners and losers"
              link sends anyone who wants the full performance breakdown to
              /scorecard, so nothing is hidden — we just don't anchor the buy
              on our weakest metric. Renders nothing until a day is logged. */}
          {proof && (
            <Link
              href="/scorecard"
              className="mt-6 block rounded-md border border-accent/20 bg-accent/5 p-3 transition-colors hover:border-accent/40 hover:bg-accent/10"
            >
              <div className="flex items-center justify-between gap-3 text-[11px] uppercase tracking-wider text-muted">
                <span>Public track record</span>
                <span className="text-subtle">audit →</span>
              </div>
              <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1 nums">
                <span className="text-fg">
                  <span className="text-base font-semibold">{proof.days}</span>
                  <span className="ml-1 text-xs text-muted">days on the record</span>
                </span>
                <span className="text-fg">
                  <span className="text-base font-semibold">every pick</span>
                  <span className="ml-1 text-xs text-muted">logged same-day, never edited</span>
                </span>
              </div>
              <div className="mt-2 text-xs text-muted">
                See every call and how it did vs SPY — winners and losers &rarr;
              </div>
            </Link>
          )}

          <ul className="mt-6 space-y-2 text-sm text-muted">
            <li className="flex items-start gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
              <span><span className="text-fg">Full universe, live scores</span> — not the top-10-row free view</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
              <span><span className="text-fg">Smart-money signals</span> — Congressional trades + recent insider buys (SEC Form 4)</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
              <span><span className="text-fg">Watchlist of 200, unlimited alerts</span> — email, browser push, Telegram</span>
            </li>
          </ul>

          {refCode && (
            <div className="mt-6 rounded-md border border-up/30 bg-up/5 p-3 text-sm text-up">
              You&apos;re signing up with a referral code — you&apos;ll get <strong>1 free month of Premium</strong> credited at your next checkout.
            </div>
          )}

          {/* Secondary email path. Some visitors prefer email; it stays fully
              usable. When OAuth is enabled, the "or sign up with email" divider
              rendered by OAuthButtons (position="top") already sits above this
              form; when OAuth is disabled, OAuthButtons renders nothing and
              this becomes the primary path with no orphaned divider. */}
          <form onSubmit={submit} className="mt-6 space-y-4">
            {/* Honeypot field — offscreen, hidden from real users (and screen readers).
                Bots that auto-fill every input will populate it; if non-empty, the
                backend silently rejects the signup. */}
            <input
              type="text"
              name="company"
              value={honeypot}
              onChange={(e) => setHoneypot(e.target.value)}
              tabIndex={-1}
              autoComplete="off"
              aria-hidden="true"
              className="absolute left-[-9999px] top-[-9999px] h-0 w-0 opacity-0"
            />

            {/* Name is optional backend-side (SignupBody.name: str | None), so
                we keep it — some users want it — but label it optional and put
                it last so email + password (the only required fields) come
                first. Fewer required fields = higher completion. */}
            <Field label="Email" type="email" autoComplete="email" value={email} onChange={setEmail} required />
            <Field label="Password" type="password" autoComplete="new-password" value={password} onChange={setPassword} required minLength={8} hint="At least 8 characters" />
            <Field label="Name (optional)" type="text" autoComplete="name" value={name} onChange={setName} />

            {/* Cloudflare Turnstile widget — auto-rendered by the script tag in
                root layout. data-callback names a window function that receives
                the token. Hidden entirely if no site key is configured. */}
            {TURNSTILE_SITE_KEY && (
              <div
                ref={turnstileRef}
                className="cf-turnstile"
                data-sitekey={TURNSTILE_SITE_KEY}
                data-callback="onTapelineTurnstile"
                data-theme="dark"
              />
            )}

            {err && (
              <div className="rounded-md border border-down/30 bg-down/5 p-3 text-sm text-down">
                {err}
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="flex h-11 w-full items-center justify-center rounded-md bg-gradient-to-r from-accent to-accent2 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-50"
            >
              {busy ? "Starting your trial…" : "Start my free trial"}
            </button>
            {/* Reassurance adjacent to the highest-intent click — kills the
                "will I be charged?" objection right where hesitation happens,
                not only in the H1 subhead far above. */}
            <p className="text-center text-xs text-muted">
              No credit card &middot; cancel in one click
            </p>

            <p className="text-xs text-subtle">
              By signing up you agree to our{" "}
              <Link href="/legal/terms" className="link">Terms</Link>{" "}and{" "}
              <Link href="/legal/privacy" className="link">Privacy Policy</Link>.
            </p>
          </form>

          {/* After-trial transparency footer. The single most common pre-signup
              objection is "what happens at day 14 — will I get auto-charged?"
              Spelling out the off-ramp here defuses that anxiety. Wording is
              kept tight: free fallback first (loss-aversion-light), upgrade
              path second, explicit no-charge guarantee third. */}
          <div className="mt-8 rounded-md border border-border bg-panel/40 p-4 text-xs text-muted">
            <div className="font-medium text-fg">After your 14 days</div>
            <p className="mt-1.5">
              Stay on Free forever (live scores, top-10 scanner, 12 look-ups/day) — or upgrade to{" "}
              <span className="text-fg">Pro from $8.25/mo</span> for the full
              real-time universe with unlimited look-ups. No card on file means no surprise charge.
            </p>
            <p className="mt-2 text-[11px] text-subtle">
              <span className="text-muted">30-day money back</span> if you change your mind ·
              Cancel in one click ·{" "}
              <Link href="/legal/refund" className="link">Full refund policy</Link>
            </p>
          </div>

          {/* Carry the plan intent through the signin path too — an existing
              user who clicked a /pricing plan CTA should land on the billing
              page with their pick pre-selected, not on the scanner. */}
          <p className="mt-6 text-center text-sm text-muted">
            Already have an account?{" "}
            <Link href={`/signin?next=${encodeURIComponent(postAuthNext)}`} className="link">Sign in</Link>
          </p>
        </div>
      </div>
    </main>
  );
}

function Field({
  label, type, value, onChange, autoComplete, required, minLength, hint,
}: {
  label: string; type: string; value: string; onChange: (v: string) => void;
  autoComplete?: string; required?: boolean; minLength?: number; hint?: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-muted">{label}</span>
      <input
        type={type}
        autoComplete={autoComplete}
        required={required}
        minLength={minLength}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1.5 block h-11 w-full rounded-md border border-border bg-panel px-3 text-base transition-colors focus:border-accent focus:outline-none"
      />
      {hint && <span className="mt-1 block text-xs text-subtle">{hint}</span>}
    </label>
  );
}
