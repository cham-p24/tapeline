"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { trackEvent } from "@/lib/gtag";
import { api, errorMessage } from "@/lib/api";
import { authApi } from "@/lib/auth";
import { TRIAL_DAYS, TRIAL_LENGTH_LABEL } from "@/lib/trial";
import { userLocale } from "@/lib/datetime";
import { trackMetaCompleteRegistration } from "@/lib/metaConversions";
import { PRICING, REFUND, usd, usdCompact } from "@/lib/pricing";
import { safeNext } from "@/lib/safeNext";
import {
  getStoredFbclid,
  getStoredGclid,
  getStoredLandingPath,
  getStoredReferrerHost,
  getStoredUtm,
  readFbpCookie,
} from "@/lib/utm";
import { OAuthButtons } from "@/components/OAuthButtons";
import { deviceFingerprint } from "@/lib/fingerprint";
import {
  FormAlert,
  FormField,
  MIN_PASSWORD_LENGTH,
  validateEmail,
  validateNewPassword,
  type FieldError,
} from "@/components/FormField";

const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "";

/**
 * Long-form first-charge date, mirroring `/app/start`'s `longDate`.
 *
 * WHY THIS PAGE NEEDS IT TOO
 * --------------------------
 * `/app/start` was built to Meta's Subscription Services standard and clears it.
 * But the paid ad that sells the trial points at `/signup?from=trial`, NOT at
 * `/app/start` — so the page Meta's reviewer actually lands on is this one, and
 * it was the page failing the standard. Meta's Advertising Standards say review
 * covers "an ad's associated landing page or other destinations".
 *
 * The ad's own headline is "$0 today. The charge date is on the page." A
 * duration ("14 days away") is not a date, so the literal promise was unmet.
 */
function longDate(d: Date): string {
  return d.toLocaleDateString(userLocale(), {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

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
// /compare/* pages append ?from=<source> to their CTA; we restate that exact
// promise in the H1 here so a visitor who clicked a "Finviz alternative" ad
// doesn't hit a generic form and bounce. Ad → landing message-match is the
// single highest-confidence funnel lever (Unbounce / NN-group information-
// scent research). Unknown/absent `from` falls back to `_default`.
//
// CARD HONESTY (2026-08, revised for the #548 card gate). This copy has been
// wrong twice, in opposite directions, so read both steps before editing it.
//
//   #536 removed the auto-granted trial: signup stopped granting Premium, and
//   the lines here were rewritten to promise a card-free FREE ACCOUNT instead.
//
//   #548 then made THAT false. From CARD_GATE_START (2026-08-22) a new account
//   meets a card wall at /app/start before it can use the logged-in product.
//   So "free account, no card to sign up" is now misleading even though this
//   form still collects no card: the visitor cannot reach the product without
//   one. Promising a free account here and producing a card wall one click
//   later is precisely the bait-and-switch the gate's own grandfather clause
//   exists to avoid.
//
// What is still literally true, and the ONLY place "no card" may appear: the
// PUBLISHED RECORD — /scorecard, /daily-picks, per-ticker pages, the CSV/JSON
// export — needs no account at all. Everything about the account and the trial
// must state the card and the dates. Do not re-couple "free" to either one.
const FROM_COPY: Record<string, { h1: string; sub: string }> = {
  _default: {
    h1: "Create your Tapeline account",
    sub: `Email and password to start. At first sign-in you add a card and your ${TRIAL_LENGTH_LABEL} Premium trial begins — $0 today, cancel in one click.`,
  },
  finviz: {
    h1: "The Finviz alternative.",
    sub: `One composite score per ticker and a public, back-checked track record — the synthesis Finviz doesn't do. ${TRIAL_LENGTH_LABEL} Premium trial — a card at first sign-in, $0 charged that day.`,
  },
  screener: {
    h1: "The scanner that shows its receipts.",
    sub: `One score, one sentence, and every pick logged public vs SPY. ${TRIAL_LENGTH_LABEL} Premium trial — a card at first sign-in, $0 charged that day.`,
  },
  scorecard: {
    h1: "You've seen the record. Now run the scanner.",
    sub: `The full live universe, every name scored. ${TRIAL_LENGTH_LABEL} Premium trial — a card at first sign-in, $0 charged that day, cancel in one click.`,
  },
  compare: {
    h1: "Switching to Tapeline?",
    sub: `One transparent score per ticker plus a public track record. ${TRIAL_LENGTH_LABEL} Premium trial — a card at first sign-in, $0 charged that day.`,
  },
  // Destination for the ad variant that sells the SAFETY of the card trial
  // rather than trying to talk around it (Metrics Bible §7.3, variant 9 —
  // "$0 today. The charge date is on the page."). The H1 restates the ad's
  // promise verbatim, which is the whole point of the ?from= mechanism: a
  // visitor who clicked a card-objection ad and landed on a generic hero is
  // measuring the page's translation of the message, not the message.
  //
  // Every clause below is a fact this codebase can produce on demand, which
  // is the bar this key has to clear:
  //   $0 today + exact first-charge date  → Stripe Checkout, PR #548
  //   one click cancels                   → the billing page's cancel flow
  //   we email before the first charge    → render_trial_precharge_reminder_
  //                                         email, fired T-3 from the
  //                                         customer.subscription.trial_will_
  //                                         end webhook
  //   the record needs no account         → /scorecard, /daily-picks, ticker
  //                                         pages, CSV/JSON exports
  // Nothing here may drift into "no credit card" — the trial takes one. See
  // the CARD HONESTY block above.
  trial: {
    h1: "$0 today. The charge date is on the page.",
    sub: `The ${TRIAL_LENGTH_LABEL} Premium trial takes a card and charges $0 today — the exact date of the first charge is shown before you confirm, we email you three days ahead of it, and one click ends the trial before then. Reading the public record needs no account either way.`,
  },
};

// Outer page wraps the form in Suspense so useSearchParams() doesn't break prerender.
//
// The fallback is NOT null — see the matching note in app/signin/page.tsx.
// `useSearchParams()` makes Next bail out of prerendering this subtree, so a
// null fallback shipped an empty shell: audited 2026-08-29, this page returned
// 570 bytes of visible text and ZERO headings. A visitor on a slow connection
// saw a blank page on the primary conversion route, and a screen reader had no
// heading to announce.
//
// The fallback uses the `_default` FROM_COPY entry deliberately. The variant
// headlines are selected from `?from=`, which is exactly the search param this
// boundary is waiting on — so the default is the only honest thing to render
// before it resolves, and it is also what a crawler hitting the bare URL
// should see. Hydration swaps in the variant when there is one.
export default function SignUpPage() {
  return (
    <Suspense fallback={<SignUpSkeleton />}>
      <SignUpForm />
    </Suspense>
  );
}

/** Server-rendered shell: heading + sub-copy that need no search params.
 *  Kept in sync with FROM_COPY._default by construction — it reads it. */
function SignUpSkeleton() {
  const copy = FROM_COPY._default;
  return (
    <div className="mx-auto w-full max-w-md px-4">
      <h1 className="mt-3 text-3xl font-bold tracking-tight">{copy.h1}</h1>
      <p className="mt-2 text-sm text-muted">{copy.sub}</p>
    </div>
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
  // Post-auth destination, in precedence order:
  //   1. an explicit ?next= (deep link the visitor came in on)
  //   2. a /pricing plan CTA → the billing page with that plan pre-selected
  //   3. otherwise → the TRIAL OFFER, /app/billing?trial=start
  //
  // (3) is new. Signup no longer starts a trial, so if nothing presented the
  // choice the Premium trial would simply never be offered to anyone.
  // The offer screen is a two-option fork — start the trial (card, disclosed
  // in full, user clicks) or continue on the Free plan (one click to the
  // scanner, no card, nothing lost). It is NOT an auto-redirect into Stripe:
  // nothing leaves the site until the user presses the trial button.
  const postAuthNext = qp.get("next")
    ? next
    : planIntent
    ? `/app/billing?intent=${planIntent}&billing=${billingIntent}`
    : "/app/billing?trial=start";
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
  // Email consent — BOTH unchecked by default (explicit opt-in only, never
  // pre-ticked). This is the placement fix for the digest-reach problem: the
  // only prior capture point for weekly-digest consent was an onboarding
  // checkbox a day-1 bouncer never saw, and app signups were never offered
  // the Daily Top 10 at all.
  const [weeklyDigestOptIn, setWeeklyDigestOptIn] = useState(false);
  const [dailyTop10OptIn, setDailyTop10OptIn] = useState(false);
  // Computed once on mount, not per render, so the date cannot shift mid-session
  // and cannot differ between server and client markup.
  const [firstCharge] = useState(() => new Date(Date.now() + TRIAL_DAYS * 86_400_000));
  /**
   * REQUIRED subscription-terms acknowledgement. Unchecked by default, and it
   * blocks submit — both are the point.
   *
   * Meta's Subscription Services standard prohibits, on a page where personal
   * info is entered, "not including an unticked opt-in checkbox" — and names
   * *no checkbox at all* as a failure equal to a pre-ticked one. Accepting terms
   * implicitly by submitting, via a link, is the placement the same policy
   * rejects. This page is the destination of the paid trial ad, so it is the
   * page under review.
   *
   * DO NOT default this to true, and do not "simplify" it into the Terms link
   * below it — that link is a different acknowledgement (Terms + Privacy) and
   * does not state price, interval or cancellation anywhere in its label.
   */
  const [subscriptionTermsAccepted, setSubscriptionTermsAccepted] = useState(false);
  // Self-reported attribution — optional, free text, never required (gap G2).
  // Deliberately NOT a dropdown: a fixed list can only count channels we
  // already thought of, and this field exists to surface the ones we cannot
  // see. AI assistants and dark social arrive with no referrer and no UTM, so
  // every other instrument in lib/utm.ts is blind to them and this self-report
  // is the only thing that will ever credit them.
  //
  // It is ATTRIBUTION, not suitability. It records where someone heard of us
  // and nothing about their money — no capital, holdings, risk tolerance,
  // goals or experience — and it must never change which securities or factor
  // weightings anyone is shown. Keep it that way; compliance Rule 8 is not a
  // style preference.
  const [referralSource, setReferralSource] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const turnstileRef = useRef<HTMLDivElement | null>(null);

  // Per-field validation errors, keyed by input id. Populated on BLUR (the
  // user has finished with the field) and on a failed submit — never while
  // they are still typing. `onChange` only ever clears an error that is
  // already on screen, so nobody gets corrected mid-word.
  const [fieldErrors, setFieldErrors] = useState<Record<string, FieldError>>({});
  const setFieldError = (id: string, msg: FieldError) =>
    setFieldErrors((prev) => ({ ...prev, [id]: msg }));

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
  // Pairs with `sign_up` below to compute drop-off in GA4 (typed event names —
  // see lib/gtag.ts). This used to fire a second, identical Vercel-Analytics
  // `signup_started`; that sink never mounted, and mirroring it into GA4 under
  // a second name would double-count the same form impression.
  useEffect(() => {
    trackEvent("sign_up_started", { next });
  }, [next]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);

    // Re-run every validator on submit — a user can reach the button without
    // ever blurring a field (autofill, Enter from the email input), so blur
    // validation alone is not a complete gate. The form is `noValidate` so
    // these messages are what the user sees, not the browser's generic
    // "Please fill out this field".
    // Nothing here clears any input: on a failed submit the user keeps
    // everything they typed, including the consent checkboxes.
    const nextErrors: Record<string, FieldError> = {
      "signup-email": validateEmail(email),
      "signup-password": validateNewPassword(password),
    };
    setFieldErrors(nextErrors);
    const invalid = Object.keys(nextErrors).filter((id) => nextErrors[id]);
    if (invalid.length > 0) {
      setErr(
        invalid.length === 1
          ? "One field needs fixing before we can create your account — the details are next to it below."
          : `${invalid.length} fields need fixing before we can create your account — the details are next to each one below.`,
      );
      document.getElementById(invalid[0])?.focus();
      return;
    }
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
    // The subscription-terms box is a hard gate, checked before the bot check
    // so a user who missed it is told the real reason rather than being sent
    // to solve a captcha first. Focus is moved to it, because it sits above the
    // button and can be scrolled out of view on a short viewport.
    if (!subscriptionTermsAccepted) {
      setErr(
        "Please confirm you understand the trial's price and billing before we create your account.",
      );
      document.getElementById("signup-subscription-terms")?.focus();
      return;
    }
    if (TURNSTILE_SITE_KEY && !token) {
      // Instrument the friction: how often a real-looking submit is blocked
      // because Turnstile never produced a token (its script blocked by a
      // privacy extension / ad-blocker / corporate proxy, or the challenge
      // failed). The gate is UNCHANGED — this only makes the drop-off
      // measurable so the Cloudflare widget mode (managed vs always-interactive)
      // can be tuned against real numbers instead of guesses.
      trackEvent("signup_turnstile_blocked", { next });
      setErr("Please complete the bot check above.");
      return;
    }
    setBusy(true);
    try {
      // Statically imported. This was a dynamic import(), which put a
      // network fetch for a separate JS chunk in the middle of the signup
      // submit handler: if that chunk 404s — which happens routinely to a
      // user sitting on an old HTML document after a redeploy, and shows up
      // in Sentry as "Failed to load chunk /_next/static/chunks/..." — the
      // whole submit rejects and the would-be user is dead-ended with a raw
      // bundler error. The module is ~2KB, has no dependencies, and guards
      // SSR internally, so the split bought nothing and cost the single most
      // valuable interaction on the site.
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
      // Meta click ID captured on landing. Stored on the User row: it carries
      // the Conversions API's match quality, and because the 14-day trial
      // puts every first charge outside Meta's 7-day click window, joining it
      // to our own Stripe rows is the only honest way to count Meta payers.
      const fbclid = getStoredFbclid();
      // Meta's own `_fbp` cookie, if its pixel wrote one. Not stored anywhere
      // — forwarded once so the server-side registration event carries both
      // unhashed identifiers Meta matches on. Empty whenever the pixel was
      // blocked, which is common in this audience and must not matter.
      const fbp = readFbpCookie();
      // First-touch external referrer HOSTNAME captured on landing — the
      // only attribution trace AI-assistant referrals (Copilot etc.) leave,
      // since they carry no utm_* params. Hostname only, never path/query.
      const referrer = getStoredReferrerHost();
      // First-touch landing PATH — which of our own SEO pages pulled them in
      // (/compare/finviz, /glossary/rsi, a ticker page…). The channel fields
      // above can't answer that. Path only, never query/hash.
      const landing = getStoredLandingPath();
      const created = await authApi.signup(email, password, name, {
        company: honeypot,
        turnstile_token: token || undefined,
        device_fingerprint: device_fp || undefined,
        ref: refCode || undefined,
        // Explicit email consent from the two unchecked-by-default boxes
        // above the submit button. false = the box was left untouched;
        // the backend writes/enrols NOTHING in that case.
        marketing_opt_in: weeklyDigestOptIn,
        daily_top10_opt_in: dailyTop10OptIn,
        // Optional free-text "How did you hear about us?". Omitted entirely
        // when left blank, so an untouched field writes nothing rather than
        // an empty string that would show up as its own aggregation row.
        referral_source: referralSource.trim() || undefined,
        ...utm,
        ...gclid,
        ...fbclid,
        fbp: fbp || undefined,
        ...referrer,
        ...landing,
      });
      // Funnel event: signup landed cleanly. GA4 is the sink, so Search
      // Console can attribute the query → signup chain via Acquisition
      // reports; `sign_up` is also the event that forwards the Google Ads
      // signup conversion.
      //
      // `start_trial` DELIBERATELY DOES NOT FIRE HERE any more. It used to,
      // because signup auto-granted a Premium trial. Since the trial
      // became a separate card-required opt-in, firing it at account creation
      // would report a trial that hasn't started — inflating the trial count
      // and, worse, teaching Smart Bidding that every signup is a trial. It
      // now fires from app/app/billing/page.tsx at the moment the user starts
      // one.
      //
      // The former Vercel-Analytics `signup_completed` twin fired here too. It
      // is gone rather than remapped: `sign_up` already records exactly this
      // moment, and a second GA4 name for the same instant would double-count.
      trackEvent("sign_up", { method: "email" });
      // Meta `CompleteRegistration` — the event the paid burst's ad set
      // OPTIMISES toward, so its absence is not a reporting gap, it is Smart
      // Bidding with nothing to learn from. The server-side copy in
      // `meta_capi.track_complete_registration` is gated on a Conversions API
      // token that is not set, which is why Events Manager held only PageView
      // while the campaign was already spending.
      //
      // Both copies carry the SAME deterministic `event_id`, so when that token
      // is set Meta collapses them into one conversion instead of counting two.
      // Awaited (SubtleCrypto is async) but never allowed to fail the signup —
      // it resolves to null whenever the pixel is off or blocked, which is the
      // common case in this audience.
      await trackMetaCompleteRegistration({
        userId: created.user.id,
        method: "email",
      });
      // Hand off through /app/onboarding, which ASKS NOTHING: it is a silent
      // provisioning route that stamps the account, seeds the day-1 watchlist
      // server-side, and forwards on. It used to be a four-question survey
      // standing between signup and the first working screen — that was the
      // single biggest reason a new account never saw the product; the
      // questions were removed 2026-08-19. Do not send a new user to a form
      // from here. It never captured suitability data (experience, portfolio
      // size, capital, risk tolerance, holdings, goals) — those questions
      // went 2026-07-18 under compliance Rule 8, and this signup form has
      // never collected any of them. Do not reintroduce them here or there.
      // The destination it forwards to is the trial offer by default, or
      // /app/billing with the plan intent restated when the visitor arrived
      // from a /pricing plan CTA, or an explicit ?next= — see postAuthNext.
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

          {/* TWO-STEP SIGNPOST. The card gate at /app/start was arriving as a
              surprise: a visitor filled in email + password believing they
              were done, then met an unannounced ask for a card. Naming both
              steps here costs nothing and means the wall is the step they were
              told about rather than a bait-and-switch — which is also the only
              framing consistent with a product whose pitch is that it does not
              misstate things.

              Factual, not a progress bar with a countdown: no urgency, no
              scarcity, and it does not imply step 2 is optional. */}
          <ol
            aria-label="Sign-up steps"
            className="mt-10 flex items-center gap-2 text-[11px] uppercase tracking-wider text-muted"
          >
            <li aria-current="step" className="font-semibold text-fg">
              1. Your details
            </li>
            <li aria-hidden="true">&rarr;</li>
            <li>2. Card &mdash; starts the {TRIAL_LENGTH_LABEL} trial, $0 today</li>
          </ol>

          <h1 className="mt-3 text-3xl font-bold tracking-tight">{headline.h1}</h1>
          <p className="mt-2 text-sm text-muted">{headline.sub}</p>

          {/* Value strip at the decision point. Post-#548 the honest headline
              fact is the card itself: it goes on at first sign-in, $0 moves
              today, and the first charge is 14 days out. The visitor should
              learn that from us here, before they are anywhere near a card
              field — not discover it at the wall on the next screen. */}
          <p className="mt-4 text-xs text-muted">
            {TRIAL_LENGTH_LABEL} Premium trial &middot; Card added at first sign-in, $0 charged today &middot; Cancel in one click &middot; {REFUND.windowDays}-day money-back on paid plans
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

          {/* These three bullets describe PREMIUM, which is what the optional
              14-day trial opens up — not what the free account includes. They
              used to sit under a "Try Premium free for 14 days" H1 where that
              was implicit; with a free-account H1 it has to be said out loud,
              or the list quietly over-promises the free tier. */}
          <div className="mt-6 text-[11px] uppercase tracking-wider text-subtle">
            What the optional Premium trial opens up
          </div>
          <ul className="mt-2 space-y-2 text-sm text-muted">
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
              <span><span className="text-fg">Watchlist of 200, unlimited alerts</span> — email, browser push</span>
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
          {/* noValidate: we own the messages. Native constraint validation
              would otherwise preempt them with the browser's generic
              "Please fill out this field", which says nothing about how to
              fix it. `required`/`minLength` stay on the inputs for semantics
              and assistive tech. */}
          <form onSubmit={submit} noValidate className="mt-6 space-y-4">
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
            <FormField
              id="signup-email"
              label="Email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(v) => { setEmail(v); setFieldError("signup-email", null); }}
              onBlur={() => setFieldError("signup-email", validateEmail(email))}
              error={fieldErrors["signup-email"]}
              required
            />
            <FormField
              id="signup-password"
              label="Password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(v) => { setPassword(v); setFieldError("signup-password", null); }}
              onBlur={() => setFieldError("signup-password", validateNewPassword(password))}
              error={fieldErrors["signup-password"]}
              required
              minLength={MIN_PASSWORD_LENGTH}
              hint={`At least ${MIN_PASSWORD_LENGTH} characters`}
            />
            {/* Name is optional, so it has no validator — an optional field
                that can still fail validation is just a required field with
                extra steps. */}
            <FormField
              id="signup-name"
              label="Name (optional)"
              type="text"
              autoComplete="name"
              value={name}
              onChange={setName}
            />

            {/* Self-reported attribution. Optional, free text, no validator,
                and the form submits fine when it's blank — it must never be
                a reason someone fails to create an account.

                Free text on purpose: a dropdown can only count the channels
                we already listed, and the channels worth finding are the ones
                we can't see. AI assistants and dark social (a DM, a group
                chat, a forwarded link) arrive with no referrer and no UTM, so
                every automatic capture in lib/utm.ts is blind to them and
                this answer is the only signal that will ever credit them.

                It asks where someone HEARD of us and nothing else. It is not
                a suitability question and must never become one — no capital,
                holdings, risk tolerance, goals or experience, and the answer
                never changes which securities or factor weightings anyone is
                shown (compliance Rule 8).

                maxLength matches users.referral_source (40 chars) so the cap
                is visible at the keyboard rather than a silent truncation
                after submit. */}
            <FormField
              id="signup-referral-source"
              label="How did you hear about us? (optional)"
              type="text"
              autoComplete="off"
              maxLength={40}
              value={referralSource}
              onChange={setReferralSource}
              hint="A few words is plenty. It's the only way we can tell which channels actually reach people."
            />

            {/* Email consent — descriptive labels, UNCHECKED by default, and
                signup never depends on them (pure opt-in, no dark patterns).
                Every send both boxes govern carries one-click unsubscribe. */}
            <div className="space-y-2">
              <ConsentCheckbox
                checked={weeklyDigestOptIn}
                onChange={setWeeklyDigestOptIn}
                label="Email me the weekly market digest"
                hint="One email every Monday — the week's top score movers, market regime, and scorecard update. Opt out anytime."
              />
              <ConsentCheckbox
                checked={dailyTop10OptIn}
                onChange={setDailyTop10OptIn}
                label="Send me the Daily Top 10 email each trading morning"
                hint="The 10 highest-scoring US tickers before the open. One-click unsubscribe in every email."
              />
            </div>

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

            {/* REQUIRED subscription acknowledgement — deliberately styled as a
                bordered panel so it reads as a gate, not as one more optional
                email box. The two above it are opt-ins; this one is not.

                The terms are IN THE LABEL, not behind the Terms link below.
                Meta's standard rejects price/interval that sit "behind a
                separate link", and the acknowledgement has to be of the thing
                being acknowledged — so the amount, the interval, the date and
                the way out are all in the sentence the user ticks. */}
            <div className="rounded-md border border-border bg-panel/40 p-3">
              <label
                className="flex cursor-pointer items-start gap-2.5 text-sm"
                htmlFor="signup-subscription-terms"
              >
                <input
                  id="signup-subscription-terms"
                  type="checkbox"
                  checked={subscriptionTermsAccepted}
                  onChange={(e) => setSubscriptionTermsAccepted(e.target.checked)}
                  aria-required="true"
                  className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-accent"
                />
                <span className="text-fg">
                  I understand my {TRIAL_LENGTH_LABEL} Premium trial charges{" "}
                  <strong className="font-semibold">$0 today</strong>, then{" "}
                  <strong className="font-semibold">
                    {usd(PRICING.premium.monthly)}/month or{" "}
                    {usdCompact(PRICING.premium.annual)}/year
                  </strong>{" "}
                  from <strong className="font-semibold">{longDate(firstCharge)}</strong>,
                  recurring until I cancel &mdash; and that I can cancel in one click
                  before then and pay nothing.
                </span>
              </label>
            </div>

            <FormAlert message={err} />

            <button
              type="submit"
              disabled={busy}
              className="flex h-11 w-full items-center justify-center rounded-md bg-gradient-to-r from-accent to-accent2 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-50"
            >
              {busy ? "Creating your account…" : "Create my account"}
            </button>
            {/* Reassurance adjacent to the highest-intent click — kills the
                "will I be charged?" objection right where hesitation happens,
                not only in the H1 subhead far above. It must not say "no card":
                this button does not collect one, but the very next screen does,
                so the true reassurance is the AMOUNT, not the absence. */}
            <p className="text-center text-xs text-muted">
              $0 charged today &mdash; the first charge is on {longDate(firstCharge)}
            </p>

            <p className="text-xs text-subtle">
              By signing up you agree to our{" "}
              <Link href="/legal/terms" className="link">Terms</Link>{" "}and{" "}
              <Link href="/legal/privacy" className="link">Privacy Policy</Link>.
            </p>
          </form>

          {/* Card transparency footer. The single most common pre-signup
              objection is "am I going to get auto-charged?" — and now that the
              Premium trial takes a card, the only acceptable answer is
              to state the whole rule BEFORE the account exists, not after.
              What the card does, when it charges, how to leave, and what you can
              still read without an account at all. */}
          {/* PRICE AND BILLING INTERVAL — DELIBERATELY `text-sm text-fg`.
              Meta's Subscription Services standard requires price and billing
              interval to be "clearly shown", and names fine print at the page
              bottom, text buried in a privacy statement, and anything behind a
              separate link as failures. This block previously rendered the whole
              disclosure at `text-xs text-muted` with the refund line at
              `text-[11px] text-subtle` — a near-literal instance of the
              prohibited example.

              It also quoted THE WRONG PLAN: "Pro from $8.25/mo", when the trial
              converts to PREMIUM and `/app/start` defaults to ANNUAL, making the
              real first charge $199. A misleading interval is a heavier failure
              than a missing one, and it was simply untrue.

              Always derive from `PRICING.premium` — never hardcode, and never
              reach for `PRICING.pro.annualPerMonth` here again. */}
          <div className="mt-8 rounded-md border border-border bg-panel/40 p-4 text-sm text-fg">
            <div className="font-medium text-fg">What the card costs, and when</div>
            <ul className="mt-2 space-y-1.5">
              <li>
                <strong className="font-semibold">$0 today.</strong> This form takes
                an email and a password. The card comes at first sign-in.
              </li>
              <li>
                <strong className="font-semibold">
                  Then {usd(PRICING.premium.monthly)}/month, or{" "}
                  {usdCompact(PRICING.premium.annual)}/year
                </strong>{" "}
                for Premium, recurring until you cancel. Annual is the default and
                works out at {usd(PRICING.premium.annualPerMonth)}/month.
              </li>
              <li>
                <strong className="font-semibold">
                  Your first charge is on {longDate(firstCharge)}
                </strong>{" "}
                &mdash; {TRIAL_DAYS} days from today. We email you three days before it.
              </li>
              <li>
                <strong className="font-semibold">Cancel in one click</strong> from
                your billing page any time before then, and nothing is taken.
              </li>
            </ul>
          </div>

          <div className="mt-4 rounded-md border border-border bg-panel/40 p-4 text-xs text-muted">
            <div className="font-medium text-fg">Where the card comes in</div>
            {/* Numbers derive from lib/pricing (PRICING / REFUND)
                — the single source of truth checkout + every other surface
                uses — so this prose can never drift from the real price or
                the real Free-tier caps again (it previously hardcoded all
                three and had already drifted once). */}
            <p className="mt-1.5">
              This form takes an email and a password. At first sign-in you add a card, and
              that starts your <span className="text-fg">{TRIAL_LENGTH_LABEL} Premium trial</span>:{" "}
              <span className="text-fg">$0 is charged today</span>, the first charge is on{" "}
              <span className="text-fg">{longDate(firstCharge)}</span> at the plan you pick, we
              email you three days before, and one click ends it before then with nothing taken.
              Your bank may briefly show a $0 or $1 authorisation while it checks the card &mdash;
              a hold, not a charge, and it clears on its own.
              Cheaper plans exist if Premium is more than you need &mdash;{" "}
              <span className="text-fg">Pro is {usd(PRICING.pro.monthly)}/mo</span> or{" "}
              <span className="text-fg">{usdCompact(PRICING.pro.annual)}/yr</span>.
            </p>
            <p className="mt-2">
              You do not need an account &mdash; or a card &mdash; to read the record: the daily
              Top 10, the whole back-checked scorecard, a page per scored ticker and the raw
              CSV/JSON export are open to everyone. Accounts created before 22 August 2026 keep
              the free access they signed up for and are never asked for a card.
            </p>
            <p className="mt-2 text-[11px] text-subtle">
              <span className="text-muted">{REFUND.short}</span> if you change your mind ·
              Cancel in one click ·{" "}
              <Link href={REFUND.policyPath} className="link">Full refund policy</Link>
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

function ConsentCheckbox({
  checked, onChange, label, hint,
}: {
  checked: boolean; onChange: (v: boolean) => void; label: string; hint: string;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-2.5 text-sm">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-accent"
      />
      <span className="text-fg">
        {label}{" "}
        <span className="text-xs text-muted">{hint}</span>
      </span>
    </label>
  );
}
