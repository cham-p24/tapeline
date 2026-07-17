"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { track } from "@vercel/analytics";
import { trackEvent } from "@/lib/gtag";
import { useUser } from "@/components/UserContext";
import { Paywall } from "@/components/Paywall";
import { ComparisonTable } from "@/components/ComparisonTable";
import { CancelInterceptModal } from "@/components/CancelInterceptModal";
import {
  getWebPushStatus,
  subscribeToWebPush,
  testWebPush,
  unsubscribeFromWebPush,
} from "@/lib/webPush";
import { userLocale } from "@/lib/datetime";
import { handle401, errorMessage } from "@/lib/api";
import { PRICING, usd, annualSaving } from "@/lib/pricing";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// Tier metadata used by the hero + upgrade flow. Prices come from the shared
// single source of truth in lib/pricing.ts so this page, the comparison/pricing
// tables, the page metadata, and the JSON-LD Offer blocks can never drift apart.
const TIER_META = {
  free: {
    name: "Free",
    monthly: 0,
    annual: 0,
    annualMonthly: 0,
    blurb: "Live scores, top-10 scanner, 5 look-ups/day",
  },
  pro: {
    name: "Pro",
    monthly: PRICING.pro.monthly,
    annual: PRICING.pro.annual,
    annualMonthly: PRICING.pro.annualPerMonth,
    blurb: "Live scanner. Daily edge.",
  },
  premium: {
    name: "Premium",
    monthly: PRICING.premium.monthly,
    annual: PRICING.premium.annual,
    annualMonthly: PRICING.premium.annualPerMonth,
    blurb: "Everything, no limits.",
  },
} as const;

type TierKey = keyof typeof TIER_META;

export default function BillingPage() {
  const { user, refresh } = useUser();
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ kind: "info" | "ok" | "err"; text: string } | null>(null);
  // Monthly is the default — the smaller first yes. Annual stays one click
  // away with its saving flagged on the toggle. ?billing= intent from
  // /pricing still overrides this below.
  const [billingPeriod, setBillingPeriod] = useState<"monthly" | "annual">("monthly");
  const [showPlans, setShowPlans] = useState(false);
  const [showCancel, setShowCancel] = useState(false);
  const [winbackOffer, setWinbackOffer] = useState(false);
  // Whether a Stripe customer record exists behind this account. null =
  // unknown (fetch in flight). Sourced from GET /api/billing/retention-options
  // (`has_subscription` = bool(stripe_customer_id) server-side) because the
  // session payload doesn't carry stripe_customer_id. Trial users have NO
  // customer record — the Stripe portal 400s ("No billing account yet") for
  // them, so portal/cancel actions are gated on this being true.
  const [hasBilling, setHasBilling] = useState<boolean | null>(null);
  // Plan intent carried over from /pricing via /signup?plan=…&billing=…
  // (billing page reads it back as ?intent=…&billing=…). Pre-selects the
  // toggle + highlights the intended card; never auto-fires checkout.
  const [intentPlan, setIntentPlan] = useState<"pro" | "premium" | null>(null);

  const tier = (user?.tier || "free") as TierKey;
  const meta = TIER_META[tier] ?? TIER_META.free;
  const trialEndsAt = user?.trial_ends_at ? new Date(user.trial_ends_at) : null;
  const trialDaysLeft = trialEndsAt
    ? Math.max(0, Math.ceil((trialEndsAt.getTime() - Date.now()) / 86_400_000))
    : 0;
  const isOnTrial = !!trialEndsAt && trialDaysLeft > 0;
  // The no-card 14-day Premium trial every signup gets. These users hold
  // tier="premium" but own nothing yet — the whole point of this page is to
  // get a card from them, so the Premium card must stay CLICKABLE for them
  // (the old `disabled={tier === "premium"}` dead-ended every trial user's
  // conversion path). hasBilling === true flips this off for the rare user
  // who already added a card mid-trial.
  const isCardlessTrial = tier === "premium" && isOnTrial && hasBilling !== true;

  // Free users AND cardless trial users see the upgrade picker by default —
  // both groups arrive here to pick a plan (every conversion surface points
  // at /app/billing). Paid users see a tucked "Change plan" button — they're
  // not here to be sold to every visit.
  useEffect(() => {
    if (tier === "free" || isOnTrial) setShowPlans(true);
  }, [tier, isOnTrial]);

  // Does a Stripe customer record exist? Only relevant for non-free tiers
  // (free users have no portal/cancel UI). Failure leaves null → the
  // portal/cancel buttons stay hidden, which can never 400.
  useEffect(() => {
    if (!user || tier === "free") return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/billing/retention-options`, {
          credentials: "include",
          cache: "no-store",
        });
        if (!res.ok || cancelled) return;
        const body = await res.json();
        if (!cancelled) {
          // Sticky-true: the ?checkout=success handler below sets true
          // optimistically; a racing fetch that beat the Stripe webhook
          // must not flip it back to false.
          setHasBilling((prev) => (prev === true ? true : !!body.has_subscription));
        }
      } catch {
        // Network blip — leave unknown; portal/cancel simply stay hidden.
      }
    })();
    return () => { cancelled = true; };
  }, [user, tier]);

  // Funnel event: pricing-page impression. Pairs with `checkout_started`
  // (already wired in startCheckout below) to compute click-rate on the
  // upgrade buttons. `surface: "app"` distinguishes the in-app upgrade
  // flow from the marketing /pricing page, which fires the same event
  // with surface="marketing".
  useEffect(() => {
    track("pricing_page_viewed", { surface: "app", tier });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Funnel event: trial → paid conversion. Stripe's success_url redirects
  // back to /app/billing?checkout=success&tier={tier}&billing_period={period}.
  // We read the search params via `window.location.search` (inside the
  // browser-only useEffect) rather than next/navigation's useSearchParams —
  // that hook forces the whole page into a Suspense boundary for prerender,
  // and a billing page is too central to bury behind a Suspense skeleton.
  // Effect fires once on mount per navigation.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const qp = new URLSearchParams(window.location.search);
    if (qp.get("checkout") === "success") {
      const paidTier = qp.get("tier") || tier;
      const period = qp.get("billing_period") || "annual";
      track("trial_converted", { tier: paidTier, billing_period: period });
      // GA4 + Google Ads "Subscribe" (revenue) conversion. Stripe's success_url
      // brings the customer back here right after the first charge, so this is
      // the correct client-side moment to fire it. Value = the tier's
      // first-charge price (annual total or monthly) in USD — Stripe charges USD
      // (see priceCurrency in lib/jsonld.ts). This lets Smart Bidding optimise
      // the paid-search campaign toward paying customers, not just signups.
      const meta = TIER_META[paidTier as keyof typeof TIER_META];
      const value = meta ? (period === "annual" ? meta.annual : meta.monthly) : undefined;
      trackEvent("subscribe", {
        tier: paidTier,
        billing_period: period,
        ...(value ? { value, currency: "USD" } : {}),
      });
      // Visible confirmation — previously the redirect back from Stripe landed
      // on a page that looked identical to before paying. Also refresh the
      // session (tier may have already been bumped by the webhook) and flip
      // hasBilling optimistically so trial-conversion UI ("add a card") and
      // the hidden portal/cancel buttons update without waiting on a refetch.
      setMsg({ kind: "ok", text: "Payment received — your plan is active." });
      setHasBilling(true);
      refresh();
    }
    // Plan intent from the marketing /pricing page, carried through
    // /signup?plan=…&billing=… → onboarding → here. Open the picker,
    // pre-select the billing toggle and highlight the intended plan.
    // Deliberately does NOT auto-fire checkout — the user clicks.
    const intent = (qp.get("intent") || "").toLowerCase();
    if (intent === "pro" || intent === "premium") {
      setIntentPlan(intent);
      setShowPlans(true);
      const period = (qp.get("billing") || "").toLowerCase();
      if (period === "monthly" || period === "annual") setBillingPeriod(period);
    }
    // Win-back landing — the day-90 cancellation email links here with
    // ?winback=1. Surface the returning-customer banner + open the plan
    // picker. The 40%-off coupon itself is minted server-side at checkout,
    // gated on "actually churned" (tier=free + canceled_at set) — the param
    // is just the UX hint, never the source of the discount.
    if (qp.get("winback") === "1") {
      setWinbackOffer(true);
      setShowPlans(true);
      track("winback_landing", {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Funnel event: trial -> free downgrade (the other side of trial_converted).
  // The downgrade itself runs server-side via the hourly _downgrade_expired_trials
  // job, which Vercel Analytics can't see directly. Instead we detect the
  // post-downgrade state when the user next lands on /app/billing: tier is
  // "free", trial_ends_at is set (so we know they HAD a trial), and the trial
  // is in the past. localStorage dedupes per user so we don't double-count on
  // every billing-page visit.
  useEffect(() => {
    if (!user || typeof window === "undefined") return;
    if (user.tier !== "free") return;
    if (!user.trial_ends_at) return;
    const trialEnd = new Date(user.trial_ends_at).getTime();
    if (!Number.isFinite(trialEnd) || trialEnd > Date.now()) return;
    try {
      const key = `tapeline_trial_downgraded_${user.id || user.email}`;
      if (window.localStorage.getItem(key) === "1") return;
      window.localStorage.setItem(key, "1");
      track("trial_downgraded", {
        days_since_downgrade: Math.floor((Date.now() - trialEnd) / 86_400_000),
      });
    } catch {
      // localStorage failures are non-fatal — analytics must never break the page.
    }
  }, [user]);

  async function startCheckout(target: "pro" | "premium") {
    setBusy(target);
    setMsg(null);
    // Funnel event: user clicked Upgrade. Fired before the fetch so we capture
    // intent even if the network round-trip or Stripe redirect fails.
    track("checkout_started", {
      target_tier: target,
      billing_period: billingPeriod,
      current_tier: tier,
      on_trial: isOnTrial,
    });
    try {
      const res = await fetch(`${API_BASE}/api/billing/checkout`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tier: target, billing_period: billingPeriod }),
      });
      const body = await res.json();
      if (res.ok && body.url) {
        window.location.href = body.url;
      } else if (res.status === 401) {
        handle401(res.status);
      } else if (res.status === 502 || res.status === 503 || body.detail?.includes("not configured")) {
        setMsg({ kind: "info", text: "Checkout isn't live yet — Stripe activation pending. Email support@tapeline.io if you want to upgrade in the meantime." });
      } else {
        setMsg({ kind: "err", text: body.detail || `Checkout failed (${res.status})` });
      }
    } catch (e: unknown) {
      setMsg({ kind: "err", text: errorMessage(e) || "Checkout failed" });
    } finally {
      setBusy(null);
    }
  }

  /** Open the plan picker and bring it into view (it renders below the fold). */
  function openPlanPicker() {
    setShowPlans(true);
    // Wait a frame so the section exists before scrolling to it. Both calls
    // are defensive-optional for jsdom (tests) and ancient browsers.
    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(() => {
        document.getElementById("plan-picker")?.scrollIntoView?.({ behavior: "smooth", block: "start" });
      });
    }
  }

  async function openPortal() {
    try {
      const res = await fetch(`${API_BASE}/api/billing/portal`, {
        method: "POST",
        credentials: "include",
      });
      const body = await res.json();
      if (res.ok && body.url) window.location.href = body.url;
      else if (res.status === 401) handle401(res.status);
      else setMsg({ kind: "err", text: body.detail || "Portal not available — Stripe activation pending." });
    } catch (e: unknown) {
      setMsg({ kind: "err", text: errorMessage(e) });
    }
  }

  return (
    <div className="space-y-10">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header>
        <div className="flex items-center gap-2 text-xs text-subtle">
          <Link href="/app/scanner" className="hover:text-fg transition-colors">App</Link>
          <span>›</span>
          <span className="text-muted">Billing</span>
        </div>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Billing &amp; plan</h1>
        <p className="mt-1 text-sm text-muted">
          Your current subscription, usage at a glance, and how to change it.
        </p>
      </header>

      {msg && (
        <div className={`rounded-lg border p-4 text-sm ${
          msg.kind === "err"
            ? "border-down/40 bg-down/5 text-down"
            : msg.kind === "ok"
            ? "border-up/30 bg-up/5 text-up"
            : "border-warn/30 bg-warn/5 text-warn"
        }`}>
          {msg.text}
        </div>
      )}

      {/* Win-back landing banner (?winback=1 from the day-90 email). The 40%
          discount is applied server-side at checkout for genuinely churned
          accounts — this is purely the welcome-back framing. */}
      {winbackOffer && tier === "free" && (
        <div className="rounded-lg border border-accent/40 bg-accent/5 p-4 text-sm">
          <div className="font-semibold text-fg">Welcome back — your first 3 months are 40% off.</div>
          <p className="mt-1 text-muted">
            Pick a plan below and the returning-customer discount applies automatically at checkout.
            Your saved watchlist, scans and alerts come back with you.
          </p>
        </div>
      )}

      {/* ── Hero: current plan + next charge + trial countdown ────────────── */}
      <section className="grid gap-4 md:grid-cols-5">
        {/* Plan summary — spans 3 of 5 cols */}
        <div className={`md:col-span-3 relative overflow-hidden rounded-2xl border p-6 ${
          tier === "premium"
            ? "border-accent/40 bg-gradient-to-br from-accent/15 via-panel to-panel"
            : tier === "pro"
            ? "border-fg/30 bg-gradient-to-br from-fg/8 via-panel to-panel"
            : "border-border bg-panel"
        }`}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-muted">Current plan</div>
              <div className="mt-1 flex items-baseline gap-3">
                <span className="text-3xl font-bold tracking-tight">{meta.name}</span>
                {isCardlessTrial && (
                  <span className="rounded-full bg-accent/15 px-2.5 py-0.5 text-[11px] font-semibold uppercase text-accent">
                    Trial · {trialDaysLeft} day{trialDaysLeft === 1 ? "" : "s"} left
                  </span>
                )}
              </div>
              <p className="mt-1.5 text-sm text-muted">{meta.blurb}</p>
            </div>
            <div className="text-right text-xs">
              <div className="text-subtle">Signed in as</div>
              <div className="mt-0.5 text-muted nums break-all">{user?.email}</div>
            </div>
          </div>

          {tier !== "free" && (
            <div className="mt-6 flex flex-wrap gap-2">
              {/* Portal + cancel need a Stripe customer record behind the
                  account. Trial users don't have one — the portal endpoint
                  400s ("No billing account yet") — so both stay hidden until
                  /api/billing/retention-options confirms has_subscription. */}
              {hasBilling === true && (
                <button onClick={openPortal} className="btn-ghost text-xs">
                  Manage payment in Stripe portal →
                </button>
              )}
              <button
                onClick={() => setShowPlans((v) => !v)}
                className="btn-ghost text-xs"
              >
                {showPlans ? "Hide plans" : "Change plan"}
              </button>
              {hasBilling === true && (
                <button
                  onClick={() => setShowCancel(true)}
                  className="btn-ghost text-xs text-muted hover:text-down"
                >
                  Cancel subscription
                </button>
              )}
            </div>
          )}
          {tier === "free" && (
            <div className="mt-6">
              {/* Authenticated free users already HAVE an account — the old
                  <Link href="/signup"> dead-ended on a duplicate-signup
                  rejection. Open the in-page plan picker instead. */}
              <button onClick={openPlanPicker} className="btn-accent text-sm">
                Re-activate Premium →
              </button>
            </div>
          )}
        </div>

        {/* Next charge / trial preview — spans 2 of 5 cols */}
        <div className="md:col-span-2 rounded-2xl border border-border bg-panel p-6">
          <div className="text-[11px] uppercase tracking-wider text-muted">
            {isCardlessTrial ? "When the trial ends" : tier === "free" ? "What you get on Premium" : "Next charge"}
          </div>

          {isCardlessTrial ? (
            <>
              <div className="mt-2 text-2xl font-bold nums">
                {trialEndsAt!.toLocaleDateString(userLocale(), { month: "short", day: "numeric", year: "numeric" })}
              </div>
              <p className="mt-2 text-xs text-muted leading-relaxed">
                Add a card before then to lock in {meta.name} access. Otherwise your account moves to Free
                forever — live scores, top-10 scanner, 12 look-ups/day, 5-ticker watchlist.
              </p>
              <button onClick={openPlanPicker} className="mt-4 text-xs text-accent hover:underline">
                Pick a plan to keep it →
              </button>
            </>
          ) : tier === "free" ? (
            <>
              <div className="mt-2 text-2xl font-bold nums">$0 <span className="text-sm font-normal text-muted">today</span></div>
              <ul className="mt-3 space-y-1 text-xs text-muted">
                <li>· Full 2,500-ticker live universe</li>
                <li>· Watchlist of 200 with smart alerts</li>
                <li>· Congressional trades + insider buys (SEC Form 4)</li>
                <li>· Telegram alerts unlimited</li>
              </ul>
            </>
          ) : (
            <>
              <div className="mt-2 text-2xl font-bold nums">
                ${billingPeriod === "annual" ? meta.annual : meta.monthly}
                <span className="text-sm font-normal text-muted"> / {billingPeriod === "annual" ? "year" : "month"}</span>
              </div>
              <p className="mt-2 text-xs text-muted">
                {billingPeriod === "annual"
                  ? `Effective $${meta.annualMonthly}/mo · 30-day money back, cancel in one click.`
                  : "Switch to annual to save ~17% — same plan, lower effective rate."}
              </p>
            </>
          )}
        </div>
      </section>

      {/* ── Usage at a glance ─────────────────────────────────────────────── */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">Plan limits</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {/* Caps mirror backend services/tier.py TIER_LIMITS — free is
              watchlist 5 / top-10 scanner rows after the freemium retune. */}
          <UsageTile
            label="Watchlist tickers"
            limit={tier === "free" ? 5 : tier === "pro" ? 50 : 200}
            unit="tickers"
          />
          <UsageTile
            label="Email alerts / day"
            limit={tier === "free" ? 0 : tier === "pro" ? 10 : 10000}
            unit={tier === "premium" ? "unlimited" : "per day"}
            unlimited={tier === "premium"}
          />
          <UsageTile
            label="Saved scans"
            limit={tier === "free" ? 0 : tier === "pro" ? 10 : 100}
            unit="scans"
          />
          <UsageTile
            label="Scanner rows"
            limit={tier === "free" ? 10 : 2500}
            unit="rows"
          />
        </div>
      </section>

      {/* ── Plan picker (collapsible for paid users) ──────────────────────── */}
      {showPlans && (
        <section id="plan-picker" className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold">{tier === "free" ? "Pick a plan" : "Change plan"}</h2>
              <p className="mt-1 text-sm text-muted">
                30-day money back, no questions. Cancel in one click. Founding pricing — your rate is locked in while you stay subscribed. All prices in USD.
              </p>
            </div>
            <div className="inline-flex rounded-full border border-border bg-panel p-1">
              {(["monthly", "annual"] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setBillingPeriod(p)}
                  className={`relative rounded-full px-4 py-1.5 text-xs font-medium transition-all ${
                    billingPeriod === p ? "bg-fg text-background" : "text-muted hover:text-fg"
                  }`}
                >
                  {p === "annual" ? "Annual" : "Monthly"}
                  {p === "annual" && billingPeriod !== "annual" && (
                    <span className="absolute -right-2 -top-2 rounded-full bg-up px-1.5 py-0.5 text-[9px] font-bold text-background">save</span>
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <Plan
              name="Free"
              price="$0"
              note="Forever free"
              items={[
                "Live scores, top-10 scanner, 12 look-ups/day",
                "Public scorecard + basic regime",
                "Watchlist of 5, no alerts",
              ]}
              highlight={tier === "free"}
            />
            <Plan
              name="Pro"
              price={billingPeriod === "annual" ? usd(TIER_META.pro.annualMonthly) : usd(TIER_META.pro.monthly)}
              note={billingPeriod === "annual" ? `${usd(TIER_META.pro.annual)}/yr · billed annually · save $${annualSaving(TIER_META.pro)}` : "billed monthly"}
              items={[
                "Full ~2,500 ticker universe, live",
                "Score breakdown + Why on every row",
                "Squeeze Watch + Regime + Heatmap",
                "Watchlist (50) with smart alerts",
                "TradingView charts + news",
                "IPO + Earnings calendars",
                "10 email alerts/day · CSV export",
              ]}
              cta={tier === "premium" ? "Switch to Pro" : "Upgrade to Pro"}
              highlight={tier === "pro"}
              intent={intentPlan === "pro" && tier !== "pro"}
              disabled={tier === "pro"}
              busy={busy === "pro"}
              onUpgrade={() => startCheckout("pro")}
            />
            <Plan
              name="Premium"
              price={billingPeriod === "annual" ? usd(TIER_META.premium.annualMonthly) : usd(TIER_META.premium.monthly)}
              note={billingPeriod === "annual" ? `${usd(TIER_META.premium.annual)}/yr · billed annually · save $${annualSaving(TIER_META.premium)}` : "billed monthly"}
              proPlus
              items={[
                "Congressional trades feed (House + Senate)",
                "Recent insider buys — live SEC Form 4 across ~2,500 tickers",
                "Telegram alerts · unlimited (Pro: none)",
                "Email alerts · unlimited (Pro: 10/day)",
                "Watchlist 200 · saved scans 100 (Pro: 50 · 10)",
                "Priority support · same-day reply",
              ]}
              // THE P0 fix: trial users hold tier="premium" but own nothing —
              // the old disabled={tier === "premium"} rendered a dead
              // "Current plan" button for the entire 14-day trial, so no
              // human could ever reach /api/billing/checkout. A cardless
              // trial keeps the button live with an add-a-card CTA; only a
              // genuinely-paid Premium sees the disabled Current state.
              cta={isCardlessTrial ? "Keep Premium — add a card" : "Upgrade to Premium"}
              highlight={tier === "premium" && !isCardlessTrial}
              intent={intentPlan === "premium" && (tier !== "premium" || isCardlessTrial)}
              disabled={tier === "premium" && !isCardlessTrial}
              busy={busy === "premium"}
              onUpgrade={() => startCheckout("premium")}
            />
          </div>

          {/* Payment-security trust badge — directly under the upgrade buttons,
              the highest-value placement (signup takes no card; the first card
              entry happens at Stripe Checkout from here). Card details are never
              handled by Tapeline. Descriptive only, no security claims of our own. */}
          <div className="flex items-center justify-center gap-1.5 text-[11px] text-subtle">
            <svg className="h-3 w-3 flex-shrink-0" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path
                d="M8 1.5l5 1.8v3.4c0 3.2-2.1 5.3-5 6.3-2.9-1-5-3.1-5-6.3V3.3L8 1.5z"
                stroke="currentColor"
                strokeWidth="1.2"
                strokeLinejoin="round"
              />
              <path d="M5.8 8l1.6 1.6L10.4 6.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span>Payments secured by <span className="text-muted font-medium">Stripe</span></span>
          </div>

          <div>
            <details className="group rounded-xl border border-border bg-panel/40">
              <summary className="flex cursor-pointer items-center justify-between gap-3 p-5 list-none">
                <div>
                  <h3 className="font-semibold">Compare every feature</h3>
                  <p className="mt-0.5 text-xs text-muted">Six sections · every limit · no asterisks</p>
                </div>
                <span className="text-muted transition-transform group-open:rotate-45">+</span>
              </summary>
              <div className="p-5 pt-2">
                <ComparisonTable />
              </div>
            </details>
          </div>
        </section>
      )}

      {/* ── Why Tapeline (sales reinforcement only on the change-plan view) ─ */}
      {showPlans && tier !== "premium" && (
        <section className="rounded-2xl border border-border bg-panel/30 p-6">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">Why people pay</h2>
          <div className="mt-4 grid gap-5 md:grid-cols-3">
            <Selling
              title="One live data spine"
              body="Live market data, macro indicators, fundamentals, SEC filings — the same shape of inputs quant desks work from, refreshed sub-60s during market hours."
            />
            <Selling
              title="Public scorecard, day 1"
              body="Every score we publish is back-checked against next-day prices and shown on /scorecard. No newsletter shop publishes its losses. We do it automatically."
            />
            <Selling
              title="Open formula"
              body="The 6-factor weights are on /how-it-works. TipRanks, Zacks, Kavout, WallStreetZen all hide theirs. Ours is the only one you can audit."
            />
          </div>
        </section>
      )}

      {/* ── Alert delivery channels ───────────────────────────────────────── */}
      <section>
        <div className="flex items-baseline justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold">Alert delivery channels</h2>
            <p className="mt-1 text-sm text-muted">
              Email is the default. Add any channel below for richer or faster delivery.
            </p>
          </div>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <Paywall feature="alerts.web_push" title="Browser push">
            <WebPushCard />
          </Paywall>
          <Paywall feature="alerts.telegram" title="Telegram">
            <NotificationsCard />
          </Paywall>
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────────────────────── */}
      <footer className="pt-6 text-xs text-muted">
        Questions about a charge or want to cancel?
        Email <a href="mailto:support@tapeline.io" className="text-accent hover:underline">support@tapeline.io</a>
        — usually replied to within a business day.
      </footer>

      <CancelInterceptModal
        open={showCancel}
        onClose={() => setShowCancel(false)}
        onChanged={refresh}
        tier={tier}
      />
    </div>
  );
}

/**
 * Single-stat tile — label + the cap allowed on the current tier. We don't
 * surface live "used" counts yet (would need a per-user usage endpoint); the
 * limit alone is the most-asked-about question on the billing page anyway.
 */
function UsageTile({
  label,
  limit,
  unit,
  unlimited = false,
}: {
  label: string;
  limit: number;
  unit: string;
  unlimited?: boolean;
}) {
  const display = unlimited ? "∞" : limit === 0 ? "—" : limit.toLocaleString();
  return (
    <div className="rounded-xl border border-border bg-panel p-4">
      <div className="text-[11px] uppercase tracking-wider text-subtle">{label}</div>
      <div className="mt-1.5 flex items-baseline gap-1.5">
        <span className="text-2xl font-bold nums">{display}</span>
        <span className="text-xs text-muted">{unit}</span>
      </div>
    </div>
  );
}

function Selling({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <div className="flex items-center gap-2">
        <span className="h-1 w-6 rounded-full bg-accent" />
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      <p className="mt-2 text-xs text-muted leading-relaxed">{body}</p>
    </div>
  );
}

function NotificationsCard() {
  const { user, refresh } = useUser();
  const [chatId, setChatId] = useState(user?.telegram_chat_id ?? "");
  const [busy, setBusy] = useState<"connect" | "save" | "test" | "clear" | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [polling, setPolling] = useState(false);

  // Poll /api/me every 3s while a deep-link connect is in progress so the card
  // flips to "Connected" the moment the webhook lands the chat_id. Stops after
  // 10 minutes (token TTL) or as soon as we see a chat_id appear.
  useEffect(() => {
    if (!polling) return;
    const startedAt = Date.now();
    const handle = window.setInterval(async () => {
      if (Date.now() - startedAt > 10 * 60 * 1000) {
        setPolling(false); return;
      }
      try {
        const r = await fetch(`${API_BASE}/api/me`, { credentials: "include" });
        if (!r.ok) return;
        const me = await r.json();
        if (me?.telegram_chat_id) {
          await refresh();
          setMsg({ kind: "ok", text: "Connected. Hourly digests will start at the top of the hour." });
          setPolling(false);
        }
      } catch {
        // Network blips during a deploy / Wi-Fi flap shouldn't kill the poll
      }
    }, 3000);
    return () => window.clearInterval(handle);
  }, [polling, refresh]);

  async function connect() {
    setBusy("connect"); setMsg(null);
    try {
      const r = await fetch(`${API_BASE}/api/me/telegram/start-token`, {
        method: "POST", credentials: "include",
      });
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail || `Connect failed (${r.status})`);
      // Open Telegram deep-link in a new tab — desktop app, mobile app, or web
      window.open(body.deep_link, "_blank", "noopener,noreferrer");
      setMsg({ kind: "ok", text: "Tap Start in Telegram. We'll auto-detect the connection." });
      setPolling(true);
    } catch (e: unknown) {
      setMsg({ kind: "err", text: errorMessage(e) });
    } finally { setBusy(null); }
  }

  async function save() {
    setBusy("save"); setMsg(null);
    try {
      const r = await fetch(`${API_BASE}/api/me/telegram`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: chatId.trim() }),
      });
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail || `Save failed (${r.status})`);
      setMsg({ kind: "ok", text: "Saved. Hit Test to verify the wiring." });
      await refresh();
    } catch (e: unknown) {
      setMsg({ kind: "err", text: errorMessage(e) });
    } finally { setBusy(null); }
  }

  async function test() {
    setBusy("test"); setMsg(null);
    try {
      const r = await fetch(`${API_BASE}/api/me/telegram/test`, {
        method: "POST", credentials: "include",
      });
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail || `Test failed (${r.status})`);
      setMsg({ kind: "ok", text: "Sent. Check your Telegram." });
    } catch (e: unknown) {
      setMsg({ kind: "err", text: errorMessage(e) });
    } finally { setBusy(null); }
  }

  async function clear() {
    setBusy("clear"); setMsg(null);
    try {
      const r = await fetch(`${API_BASE}/api/me/telegram`, {
        method: "DELETE", credentials: "include",
      });
      if (!r.ok) throw new Error("Disconnect failed");
      setChatId("");
      setMsg({ kind: "ok", text: "Disconnected. Hourly digest stopped." });
      await refresh();
    } catch (e: unknown) {
      setMsg({ kind: "err", text: errorMessage(e) });
    } finally { setBusy(null); }
  }

  const connected = !!user?.telegram_chat_id;

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Telegram</h3>
        <span className={`rounded-full px-2 py-0.5 text-xs ${connected ? "bg-up/10 text-up" : "bg-muted/20 text-muted"}`}>
          {connected ? "Connected" : "Not connected"}
        </span>
      </div>

      {!connected && (
        <>
          <p className="mt-3 text-sm text-muted">
            One click. We&rsquo;ll open Telegram, you tap <span className="text-fg">Start</span>, and you&rsquo;re wired up.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              onClick={connect}
              disabled={busy !== null || polling}
              className="btn-primary text-sm disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy === "connect" ? "Opening Telegram…" : polling ? "Waiting for Telegram…" : "Connect Telegram"}
            </button>
          </div>
          <button
            onClick={() => setShowAdvanced((v) => !v)}
            className="mt-4 text-xs text-subtle underline-offset-2 hover:text-muted hover:underline"
          >
            {showAdvanced ? "Hide manual setup" : "I already have my chat ID"}
          </button>
          {showAdvanced && (
            <div className="mt-3 rounded-md border border-border/40 p-4">
              <label className="block text-xs font-medium text-muted">Telegram chat ID</label>
              <input
                type="text"
                inputMode="numeric"
                value={chatId}
                onChange={(e) => setChatId(e.target.value)}
                placeholder="e.g. 123456789"
                className="mt-1.5 block h-10 w-full rounded-md border border-border bg-panel px-3 text-sm focus:border-accent focus:outline-none nums"
              />
              <button
                onClick={save}
                disabled={busy !== null || !chatId.trim()}
                className="btn-ghost mt-3 text-sm disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy === "save" ? "Saving…" : "Save chat ID"}
              </button>
            </div>
          )}
        </>
      )}

      {connected && (
        <div className="mt-5 flex flex-wrap gap-2">
          <button
            onClick={test}
            disabled={busy !== null}
            className="btn-ghost text-sm disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy === "test" ? "Sending…" : "Send test message"}
          </button>
          <button
            onClick={clear}
            disabled={busy !== null}
            className="btn-ghost text-sm text-down hover:text-down disabled:opacity-50"
          >
            {busy === "clear" ? "Disconnecting…" : "Disconnect"}
          </button>
        </div>
      )}

      {msg && (
        <div className={`mt-4 rounded-md border p-3 text-sm ${
          msg.kind === "ok"
            ? "border-up/30 bg-up/5 text-up"
            : "border-down/30 bg-down/5 text-down"
        }`}>
          {msg.text}
        </div>
      )}
    </div>
  );
}

function WebPushCard() {
  const [status, setStatus] = useState<"loading" | "granted" | "denied" | "default" | "unsupported">("loading");
  const [busy, setBusy] = useState<"enable" | "test" | "disable" | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    getWebPushStatus().then((s) => setStatus(s as any));
  }, []);

  async function enable() {
    setBusy("enable"); setMsg(null);
    const r = await subscribeToWebPush();
    if (r.ok) {
      setStatus("granted");
      setMsg({ kind: "ok", text: "Subscribed. Hit Test to verify." });
    } else {
      setMsg({ kind: "err", text: r.reason });
    }
    setBusy(null);
  }

  async function test() {
    setBusy("test"); setMsg(null);
    const r = await testWebPush();
    if (r.ok) setMsg({ kind: "ok", text: `Sent to ${r.delivered}/${r.total} subscribed device${r.total === 1 ? "" : "s"}.` });
    else setMsg({ kind: "err", text: r.reason });
    setBusy(null);
  }

  async function disable() {
    setBusy("disable"); setMsg(null);
    await unsubscribeFromWebPush();
    setStatus("default");
    setMsg({ kind: "ok", text: "Disabled on this browser." });
    setBusy(null);
  }

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Browser push</h3>
        <span className={`rounded-full px-2 py-0.5 text-xs ${
          status === "granted" ? "bg-up/10 text-up"
          : status === "denied" ? "bg-down/10 text-down"
          : status === "unsupported" ? "bg-muted/20 text-muted"
          : "bg-muted/20 text-muted"
        }`}>
          {status === "granted" ? "Connected" : status === "denied" ? "Blocked" : status === "unsupported" ? "Unsupported" : "Not connected"}
        </span>
      </div>

      <p className="mt-3 text-sm text-muted leading-relaxed">
        Lock-screen notifications on desktop and Android. iOS requires the PWA to be installed.
        Free at any volume, one click to enable.
      </p>

      {status === "denied" && (
        <p className="mt-3 text-xs text-down">
          You blocked notifications for this site. Re-enable in browser settings (lock icon → Permissions → Notifications → Allow), then refresh.
        </p>
      )}
      {status === "unsupported" && (
        <p className="mt-3 text-xs text-subtle">
          Your browser doesn't support Web Push. Try Chrome, Firefox, or Edge on desktop.
        </p>
      )}

      <div className="mt-5 flex flex-wrap gap-2">
        {status !== "granted" && status !== "unsupported" && (
          <button
            onClick={enable}
            disabled={busy !== null || status === "denied"}
            className="btn-primary text-sm disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy === "enable" ? "Subscribing…" : "Enable browser push"}
          </button>
        )}
        {status === "granted" && (
          <>
            <button
              onClick={test}
              disabled={busy !== null}
              className="btn-ghost text-sm disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy === "test" ? "Sending…" : "Send test notification"}
            </button>
            <button
              onClick={disable}
              disabled={busy !== null}
              className="btn-ghost text-sm text-down hover:text-down disabled:opacity-50"
            >
              {busy === "disable" ? "Disabling…" : "Disable on this browser"}
            </button>
          </>
        )}
      </div>

      {msg && (
        <div className={`mt-4 rounded-md border p-3 text-sm ${
          msg.kind === "ok" ? "border-up/30 bg-up/5 text-up" : "border-down/30 bg-down/5 text-down"
        }`}>
          {msg.text}
        </div>
      )}
    </div>
  );
}


function Plan({
  name, price, items, note, cta, highlight, intent, disabled, busy, onUpgrade, proPlus,
}: {
  name: string; price: string; items: string[]; note?: string;
  cta?: string; highlight?: boolean; intent?: boolean; disabled?: boolean; busy?: boolean;
  onUpgrade?: () => void; proPlus?: boolean;
}) {
  // `highlight` = the plan the user actually owns ("Current" badge).
  // `intent` = the plan they arrived meaning to buy (?intent= from /pricing)
  // — same visual emphasis, but labelled "Selected" so a trial/free user is
  // never told they already own something they haven't paid for.
  return (
    <div className={`card p-6 ${highlight || intent ? "ring-2 ring-accent" : ""}`}>
      <div className="flex items-baseline justify-between">
        <h3 className="text-lg font-semibold">{name}</h3>
        {highlight && <span className="rounded-full bg-up/10 px-2 py-0.5 text-xs text-up">Current</span>}
        {!highlight && intent && <span className="rounded-full bg-accent/15 px-2 py-0.5 text-xs text-accent">Selected</span>}
      </div>
      <div className="mt-2 flex items-baseline gap-1"><span className="text-3xl font-bold">{price}</span><span className="text-muted">/mo</span></div>
      {note && <p className="mt-1 text-xs text-muted">{note}</p>}
      {/* "Everything in Pro" anchor strip — makes the upgrade reason
          obviously the additions, not a duplicated bullet list. */}
      {proPlus && (
        <div className="mt-4 flex items-center gap-2 rounded-md border border-border bg-panel px-2.5 py-1.5 text-[11px] text-muted">
          <span className="text-up">✓</span>
          <span>Everything in Pro</span>
          <span className="ml-auto text-accent font-medium">+ all of:</span>
        </div>
      )}
      <ul className={`${proPlus ? "mt-3" : "mt-4"} space-y-1 text-sm`}>
        {items.map((i) => <li key={i} className="flex gap-2"><span className="text-accent">✓</span><span>{i}</span></li>)}
      </ul>
      {cta && (
        <button
          disabled={disabled || busy}
          onClick={onUpgrade}
          className="btn-primary mt-6 w-full text-sm disabled:cursor-not-allowed disabled:opacity-50"
        >
          {disabled ? "Current plan" : busy ? "Redirecting…" : cta}
        </button>
      )}
    </div>
  );
}
