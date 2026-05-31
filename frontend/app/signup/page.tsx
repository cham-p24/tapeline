"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { track } from "@vercel/analytics";
import { trackEvent } from "@/lib/gtag";
import { api, errorMessage } from "@/lib/api";
import { authApi } from "@/lib/auth";
import { getStoredUtm } from "@/lib/utm";
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
  const next = qp.get("next") || "/app/scanner";
  // Referral code from /signup?ref=ABCDEFGH. Backend grants both parties
  // 1 free month of Premium when this resolves to a valid existing user.
  const refCode = (qp.get("ref") || "").trim().toUpperCase();

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

  // Live scorecard proof block — fetched once on mount. The summary stats
  // (days_tracked, hit_rate_beat_spy, median_alpha_vs_spy) are tier-invariant
  // so we get them even though the visitor is anonymous. If the fetch fails
  // or returns nulls (e.g. no back-checked entries yet), the block silently
  // renders nothing — the page should never show "—%" placeholders that look
  // broken. This is the highest-leverage copy lever on /signup: turning the
  // bullet promises above into measurable receipts.
  const [proof, setProof] = useState<{
    days: number;
    hit_rate: number;
    median_alpha: number;
  } | null>(null);
  useEffect(() => {
    let cancelled = false;
    api.scorecard(30).then((d) => {
      if (cancelled) return;
      const s = d.summary;
      if (
        typeof s.days_tracked === "number" &&
        s.days_tracked > 0 &&
        typeof s.hit_rate_beat_spy === "number" &&
        typeof s.median_alpha_vs_spy === "number"
      ) {
        setProof({
          days: s.days_tracked,
          hit_rate: s.hit_rate_beat_spy,
          median_alpha: s.median_alpha_vs_spy,
        });
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
      await authApi.signup(email, password, name, {
        company: honeypot,
        turnstile_token: token || undefined,
        device_fingerprint: device_fp || undefined,
        ref: refCode || undefined,
        ...utm,
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
      // onboarding page redirects to `next` after submit or skip. Existing
      // users (signin) never pass through here.
      router.push(`/app/onboarding?next=${encodeURIComponent(next)}`);
      router.refresh();
    } catch (e: unknown) {
      setErr(errorMessage(e) || "Sign up failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative min-h-screen">
      <div className="pointer-events-none absolute inset-0 bg-hero opacity-60" />

      <div className="relative flex min-h-screen items-center justify-center px-6 py-10">
        <div className="w-full max-w-sm">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-2 w-6 rounded-full bg-gradient-to-r from-accent to-accent2" />
            <span className="text-lg font-semibold tracking-tight">Tapeline</span>
          </Link>

          <h1 className="mt-10 text-3xl font-bold tracking-tight">Try Premium free for 14 days</h1>
          <p className="mt-2 text-sm text-muted">No credit card. Cancel anytime.</p>

          {/* Live scorecard proof — the only block on this page where the
              numbers update with real data. Bullets below promise features;
              this block surfaces actual track record. Renders nothing when
              the back-check hasn't accumulated enough entries yet, so the
              page never shows a "broken" empty state.
              Tap-target — full row links to /scorecard so the curious
              visitor can audit the receipts before signing up. */}
          {proof && (
            <Link
              href="/scorecard"
              className="mt-6 block rounded-md border border-up/20 bg-up/5 p-3 transition-colors hover:border-up/40 hover:bg-up/10"
            >
              <div className="flex items-center justify-between gap-3 text-[11px] uppercase tracking-wider text-muted">
                <span>Public scorecard</span>
                <span className="text-subtle">audit →</span>
              </div>
              <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1 nums">
                <span className="text-fg">
                  <span className="text-base font-semibold">{proof.days}</span>
                  <span className="ml-1 text-xs text-muted">days tracked</span>
                </span>
                <span className="text-up">
                  <span className="text-base font-semibold">{proof.hit_rate.toFixed(0)}%</span>
                  <span className="ml-1 text-xs text-muted">beat SPY</span>
                </span>
                <span className={proof.median_alpha >= 0 ? "text-up" : "text-down"}>
                  <span className="text-base font-semibold">
                    {proof.median_alpha >= 0 ? "+" : ""}{proof.median_alpha.toFixed(2)}%
                  </span>
                  <span className="ml-1 text-xs text-muted">median alpha</span>
                </span>
              </div>
            </Link>
          )}

          <ul className="mt-6 space-y-2 text-sm text-muted">
            <li className="flex items-start gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
              <span><span className="text-fg">Full universe, live scores</span> — not the 20-ticker, 24-hour-delayed free view</span>
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

          {/* OAuth above the email form. One-click signup is the highest-leverage
              conversion lever on this page; we used to bury it below. The
              OAuthButtons component renders nothing if no provider is configured
              so the layout collapses cleanly in environments without OAuth. */}
          <div className="mt-8">
            <OAuthButtons position="top" />
          </div>

          <form onSubmit={submit} className="space-y-4">
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

            <Field label="Name" type="text" autoComplete="name" value={name} onChange={setName} />
            <Field label="Email" type="email" autoComplete="email" value={email} onChange={setEmail} required />
            <Field label="Password" type="password" autoComplete="new-password" value={password} onChange={setPassword} required minLength={8} hint="At least 8 characters" />

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
              {busy ? "Creating account…" : "Create account"}
            </button>

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
              Stay on Free (top 20 tickers, 24-hour delayed) — or upgrade to{" "}
              <span className="text-fg">Pro from $24.99/mo</span> for the full
              live universe. No card on file means no surprise charge.
            </p>
            <p className="mt-2 text-[11px] text-subtle">
              <span className="text-muted">7-day money back</span> if you change your mind ·
              Cancel in one click ·{" "}
              <Link href="/legal/refund" className="link">Full refund policy</Link>
            </p>
          </div>

          <p className="mt-6 text-center text-sm text-muted">
            Already have an account?{" "}
            <Link href={`/signin?next=${encodeURIComponent(next)}`} className="link">Sign in</Link>
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
