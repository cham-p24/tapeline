"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { trackEvent, trackEventOnce } from "@/lib/gtag";
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
import { PRICING, FREE_LIMITS, REFUND, usd, usdCompact, annualSaving, DEFAULT_BILLING_PERIOD, freeHasWatchlist, freeScannerRows } from "@/lib/pricing";
import { BillingPeriodProvider } from "@/components/BillingToggle";
import { useChargeDisclosure, chargeDisclosureLine } from "@/lib/chargeDisclosure";
import { errorText } from "@/lib/errorText";

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
    blurb: `Live scores, top-${FREE_LIMITS.scannerRows} scanner, ${FREE_LIMITS.dailyLookups} look-ups/day`,
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

/**
 * Length of the Premium trial. Mirrors the backend grant and every "14-day"
 * figure on the pricing surfaces. The first-charge date shown on the offer
 * below is derived from this, so it is the same arithmetic the Stripe session
 * performs (`subscription_data.trial_end = now + TRIAL_DAYS`).
 */
const TRIAL_DAYS = 14;

/**
 * Local record that the checkout we are about to leave for is a TRIAL start,
 * not a purchase.
 *
 * The primary signal is `trial=1` on the success_url, which the backend owns.
 * This is the belt-and-braces half, and it exists because the failure mode is
 * expensive and silent: if a $0 trial start comes back looking like an ordinary
 * success, the page fires `subscribe` with the full plan price, booking revenue
 * nobody paid and feeding Google Ads Smart Bidding a conversion worth $199 for
 * a customer who has been charged nothing. Written immediately before the
 * redirect, read once on the way back, and cleared either way.
 *
 * Scoped tightly so it cannot mislabel a later real purchase: it carries the
 * tier it was minted for and expires after two hours.
 */
const TRIAL_CHECKOUT_INTENT_KEY = "tapeline_trial_checkout_intent";
const TRIAL_INTENT_TTL_MS = 2 * 3_600_000;

function rememberTrialCheckout(tier: string) {
  try {
    window.sessionStorage.setItem(
      TRIAL_CHECKOUT_INTENT_KEY,
      JSON.stringify({ tier, at: Date.now() }),
    );
  } catch {
    // Storage blocked — we simply fall back to the `trial=1` URL param.
  }
}

/** Consume the flag. Returns true only for a fresh, tier-matching record. */
function takeTrialCheckoutIntent(tier: string): boolean {
  try {
    const raw = window.sessionStorage.getItem(TRIAL_CHECKOUT_INTENT_KEY);
    window.sessionStorage.removeItem(TRIAL_CHECKOUT_INTENT_KEY);
    if (!raw) return false;
    const rec = JSON.parse(raw) as { tier?: string; at?: number };
    if (rec.tier !== tier) return false;
    return typeof rec.at === "number" && Date.now() - rec.at < TRIAL_INTENT_TTL_MS;
  } catch {
    return false;
  }
}

/** Long-form date for the disclosure, e.g. "4 September 2026". */
function longDate(d: Date): string {
  return d.toLocaleDateString(userLocale(), {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default function BillingPage() {
  const { user, refresh, mustAddCard } = useUser();
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ kind: "info" | "ok" | "err"; text: string } | null>(null);
  // ANNUAL is the default (founder decision 2026-07-18) — monthly stays one
  // click away, and every annual per-month figure carries its billed-annually
  // total on the card note. ?billing= intent from /pricing still overrides
  // this below.
  const [billingPeriod, setBillingPeriod] = useState<"monthly" | "annual">(DEFAULT_BILLING_PERIOD);
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
  // Stripe's cancel_url lands here with ?checkout=cancelled&tier=…&billing_period=….
  // Two pieces of state, deliberately separate: the panel must render on the
  // BARE ?checkout=cancelled too. Links minted before the tier params were
  // added (and the email-checkout path) carry no tier, and "nothing was
  // charged" is the reassurance that matters — it must not be conditional on
  // knowing which plan they were buying.
  const [checkoutCancelled, setCheckoutCancelled] = useState(false);
  // Which tier they were part-way through, when we know it — upgrades the
  // resume button from "pick a plan" to one click back into the same checkout.
  const [cancelledTier, setCancelledTier] = useState<"pro" | "premium" | null>(null);
  // TRIAL-START INTENT (?trial=start). Set by the post-signup hand-off and by
  // any surface that wants to present the 14-day Premium trial. It opens the
  // picker pre-armed on Premium and renders the offer panel at the top of the
  // page — a two-option fork the user resolves themselves. It NEVER redirects
  // into Stripe on its own: the panel's button is the only thing that starts a
  // checkout, exactly like every other plan CTA on this page.
  const [trialIntent, setTrialIntent] = useState(false);
  // The date Stripe will take the first charge if the trial starts right now.
  // Computed once per mount so it can't drift mid-session, and mirrors the
  // trial_end the backend sets on the Checkout session.
  const [trialFirstCharge] = useState(
    () => new Date(Date.now() + TRIAL_DAYS * 86_400_000),
  );
  // Failed-renewal state from GET /api/billing/retention-options (mirrors the
  // billing.past_due that /api/me feeds the global DunningBanner). Drives the
  // in-page recovery panel and suppresses the "Next charge" quote, which is
  // actively misleading while a charge is failing.
  const [pastDue, setPastDue] = useState(false);
  // What Stripe actually charges — currency, and whether anything is added on
  // top. Derived server-side from the live Price plus the session kwargs.
  const disclosure = useChargeDisclosure();

  const tier = (user?.tier || "free") as TierKey;
  const meta = TIER_META[tier] ?? TIER_META.free;
  const trialEndsAt = user?.trial_ends_at ? new Date(user.trial_ends_at) : null;
  const trialDaysLeft = trialEndsAt
    ? Math.max(0, Math.ceil((trialEndsAt.getTime() - Date.now()) / 86_400_000))
    : 0;
  const isOnTrial = !!trialEndsAt && trialDaysLeft > 0;
  // LEGACY no-card trial: accounts auto-granted a 14-day Premium trial at
  // signup, before the trial required a card (changed 2026-08). They hold
  // tier="premium" but own nothing, so the Premium card must stay CLICKABLE
  // for them (the old `disabled={tier === "premium"}` dead-ended every trial
  // user's conversion path). hasBilling === true flips this off.
  const isCardlessTrial = tier === "premium" && isOnTrial && hasBilling !== true;
  // The CURRENT shape of a trial: started through Stripe Checkout, so a card
  // is on file and a real first charge is scheduled for the trial-end date.
  // This is a billing event and the page owes the user its date and amount.
  const isCardTrial = tier === "premium" && isOnTrial && hasBilling === true;
  // Who may be offered a trial. Deliberately conservative on the client — the
  // authoritative "has this account already had its trial?" gate lives in the
  // backend checkout path; this only decides whether to render the offer.
  const trialEligible = tier === "free" && !user?.trial_ends_at && hasBilling !== true;
  // Render the offer when it was asked for AND the account can actually take
  // it. An already-trialled or paying account that lands on ?trial=start just
  // sees the normal billing page rather than an offer it cannot accept.
  const showTrialOffer = trialIntent && trialEligible;

  // Stripe defers the first charge to the trial-end date ONLY when that date is
  // >= 48h out (backend routers/billing.py); inside 48h it falls back to a
  // charge-now session. So a cardless-trial user is billed TODAY iff < 48h left.
  // Surface this honestly so "add a card" never implies a free continuation
  // that actually charges immediately.
  const chargesToday =
    !!trialEndsAt && trialEndsAt.getTime() - Date.now() < 48 * 3_600_000;

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
          // Dunning state rides along on this same request — no second
          // round-trip for a field the page needs on every paid render.
          setPastDue(Boolean(body.past_due));
        }
      } catch {
        // Network blip — leave unknown; portal/cancel simply stay hidden.
      }
    })();
    return () => { cancelled = true; };
  }, [user, tier]);

  // Funnel event: pricing-page impression. Pairs with `begin_checkout`
  // (wired in startCheckout below) to compute click-rate on the upgrade
  // buttons. `surface: "app"` distinguishes the in-app upgrade flow from
  // the marketing /pricing page, which fires the same event with
  // surface="marketing".
  useEffect(() => {
    trackEvent("pricing_page_viewed", { surface: "app", tier });
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
      // TRIAL START, not a purchase. The backend appends `trial=1` to the
      // success_url when the session was minted with subscription_data
      // .trial_end for a NEW trial, because $0 moved: firing `subscribe` here
      // would report revenue that does not exist and feed Google Ads a
      // conversion worth $199 for a customer who has paid nothing yet. Fire
      // `start_trial` instead — the trial genuinely did start — and let the
      // real `subscribe` fire when the first charge lands 14 days later.
      //
      // Two signals, either of which is enough: the URL param the backend
      // appends, and the local record this page wrote before redirecting. The
      // second exists so a backend that has not (yet) added the param cannot
      // silently turn every trial start into $199 of phantom GA4/Ads revenue.
      // `takeTrialCheckoutIntent` is called unconditionally so the record is
      // always consumed, never left to colour a later purchase.
      const localTrialIntent = takeTrialCheckoutIntent(paidTier);
      if (qp.get("trial") === "1" || localTrialIntent) {
        const sid = qp.get("session_id") || "";
        const fire = () =>
          trackEvent("start_trial", {
            tier: paidTier,
            billing_period: period,
            days: TRIAL_DAYS,
            method: "checkout",
          });
        if (sid) {
          trackEventOnce(`tapeline_start_trial_fired_${sid}`, "start_trial", {
            tier: paidTier,
            billing_period: period,
            days: TRIAL_DAYS,
            method: "checkout",
          });
        } else {
          fire();
        }
        setMsg({
          kind: "ok",
          text: `Your ${TRIAL_DAYS}-day Premium trial is running — nothing was charged. Your first charge is on ${longDate(
            trialFirstCharge,
          )}, and Cancel subscription below ends it before then with nothing taken.`,
        });
        setHasBilling(true);
        refresh();
        // Drop the payment identifier from the address bar, same as the paid
        // path below, so a shared/bookmarked link carries no session id.
        qp.delete("session_id");
        const qs = qp.toString();
        window.history.replaceState(
          null,
          "",
          `${window.location.pathname}${qs ? `?${qs}` : ""}`,
        );
        return;
      }
      // Stripe's checkout session id, injected by the success_url template in
      // backend/app/routers/billing.py. Doubles as the GA4/Ads transaction_id
      // AND the dedupe key: without it, every reload/bookmark of this success
      // URL re-fired `subscribe`, inflating GA4 revenue and feeding Smart
      // Bidding conversions that never happened.
      const sessionId = qp.get("session_id") || "";
      // GA4 + Google Ads "Subscribe" (revenue) conversion. Stripe's success_url
      // brings the customer back here right after the first charge, so this is
      // the correct client-side moment to fire it. Value = the tier's
      // first-charge price (annual total or monthly) in USD — Stripe charges USD
      // (see priceCurrency in lib/jsonld.ts). This lets Smart Bidding optimise
      // the paid-search campaign toward paying customers, not just signups.
      const meta = TIER_META[paidTier as keyof typeof TIER_META];
      const value = meta ? (period === "annual" ? meta.annual : meta.monthly) : undefined;
      const subscribeParams = {
        tier: paidTier,
        billing_period: period,
        ...(value ? { value, currency: "USD" } : {}),
        ...(sessionId ? { transaction_id: sessionId } : {}),
      };
      if (sessionId) {
        if (
          trackEventOnce(
            `tapeline_subscribe_fired_${sessionId}`,
            "subscribe",
            subscribeParams,
          )
        ) {
          // Funnel mirror only — deliberately carries NO value/currency and has
          // no Google Ads label, so the revenue conversion stays exclusively on
          // the `subscribe` event fired immediately above.
          trackEvent("trial_converted", { tier: paidTier, billing_period: period });
        }
        // Drop session_id from the address bar now the event is settled, so a
        // shared or bookmarked link carries no payment identifier.
        qp.delete("session_id");
        const qs = qp.toString();
        window.history.replaceState(
          null,
          "",
          `${window.location.pathname}${qs ? `?${qs}` : ""}`,
        );
      } else {
        // No session id (legacy link / Stripe didn't substitute) — fall back to
        // the previous un-deduped behaviour rather than losing the conversion.
        trackEvent("subscribe", subscribeParams);
        trackEvent("trial_converted", { tier: paidTier, billing_period: period });
      }
      // Visible confirmation — previously the redirect back from Stripe landed
      // on a page that looked identical to before paying. Also refresh the
      // session (tier may have already been bumped by the webhook) and flip
      // hasBilling optimistically so trial-conversion UI ("add a card") and
      // the hidden portal/cancel buttons update without waiting on a refetch.
      setMsg({ kind: "ok", text: "Payment received — your plan is active." });
      setHasBilling(true);
      refresh();
    }
    // Stripe's cancel_url. The backend has always sent ?checkout=cancelled and
    // this page has always ignored it, so backing out of Stripe dropped the
    // user on a billing page that looked exactly like the one they left —
    // no acknowledgement, no answer to the only question they have ("did that
    // charge me?"), and no way back in short of re-navigating the whole plan
    // grid. Read it, answer the question first, and offer one resume button.
    //
    // Deliberately NOT an error: backing out of a checkout is a normal thing to
    // do. It renders in the calm neutral panel, never the red error style, and
    // carries no deadline, no expiring-spot language and no second ask. If the
    // user wants to leave, the panel is dismissible and that is the end of it.
    if (qp.get("checkout") === "cancelled") {
      const t = (qp.get("tier") || "").toLowerCase();
      const period = (qp.get("billing") || qp.get("billing_period") || "").toLowerCase();
      if (period === "monthly" || period === "annual") setBillingPeriod(period);
      setCheckoutCancelled(true);
      setCancelledTier(t === "pro" || t === "premium" ? t : null);
      setShowPlans(true);
      trackEvent("checkout_cancelled", { tier: t || "unknown", billing_period: period || "unknown" });
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
    // Trial-start intent (?trial=start, or ?intent=trial). Arms the picker on
    // Premium and renders the offer panel. Nothing is fired, nothing is
    // redirected — the user reads the terms and presses one of two buttons.
    if (qp.get("trial") === "start" || intent === "trial") {
      setTrialIntent(true);
      setIntentPlan("premium");
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
      trackEvent("winback_landing", {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Funnel event: trial -> free downgrade (the other side of trial_converted).
  // The downgrade itself runs server-side via the hourly _downgrade_expired_trials
  // job, which client-side analytics can't see directly. Instead we detect the
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
      trackEvent("trial_downgraded", {
        days_since_downgrade: Math.floor((Date.now() - trialEnd) / 86_400_000),
      });
    } catch {
      // localStorage failures are non-fatal — analytics must never break the page.
    }
  }, [user]);

  /**
   * Open Stripe Checkout for `target`.
   *
   * `startTrial` asks the backend to mint the SAME session shape the mid-trial
   * add-a-card flow already uses — mode=subscription with
   * subscription_data.trial_end — dated TRIAL_DAYS out instead of at an
   * existing trial's expiry. That is the whole mechanism: $0 authorised today,
   * first charge on the trial-end date, cancellable in one click from this
   * page or the Stripe portal, and every webhook / dunning / portal behaviour
   * a normal subscription has. (Setup-mode would need a cron + a
   * SetupIntent→Subscription path and would lose all of that.)
   */
  async function startCheckout(
    target: "pro" | "premium",
    opts: { startTrial?: boolean } = {},
  ) {
    const startTrial = opts.startTrial === true;
    setBusy(target);
    setMsg(null);
    // Funnel event: user clicked Upgrade. Fired before the fetch so we capture
    // intent even if the network round-trip or Stripe redirect fails.
    //
    // ONE event for this moment, on purpose. The old Vercel-Analytics
    // `checkout_started` call that used to sit alongside this one is gone: it
    // was a dead sink (<Analytics /> never mounted — see lib/gtag.ts), and its
    // payload was a strict subset of what `begin_checkout` already carries, so
    // re-firing it into GA4 under a second name would only double-count
    // checkout intent. `begin_checkout` is the GA4 standard name for this
    // moment; value is the price the user is about to be charged (Stripe bills
    // USD), so GA4's funnel exploration can weight checkout intent by plan.
    //
    // `start_trial` is NOT fired here. A click is not a trial: the user can
    // still abandon the Stripe page. It fires on the confirmed return
    // (?checkout=success&trial=1), deduped on the Stripe session id.
    const targetMeta = TIER_META[target];
    trackEvent("begin_checkout", {
      tier: target,
      billing_period: billingPeriod,
      current_tier: tier,
      on_trial: isOnTrial,
      start_trial: startTrial,
      value: billingPeriod === "annual" ? targetMeta.annual : targetMeta.monthly,
      currency: "USD",
    });
    try {
      const res = await fetch(`${API_BASE}/api/billing/checkout`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tier: target,
          billing_period: billingPeriod,
          // Backend contract: when true, mint the session with
          // subscription_data.trial_end = now + 14d and append `trial=1` to
          // the success_url so the return handler above reports a trial
          // start rather than a purchase.
          start_trial: startTrial,
        }),
      });
      const body = await res.json();
      if (res.ok && body.url) {
        // Record the trial intent BEFORE navigating away — see
        // TRIAL_CHECKOUT_INTENT_KEY. Only ever set for a trial start.
        if (startTrial) rememberTrialCheckout(target);
        window.location.href = body.url;
      } else if (res.status === 401) {
        handle401(res.status);
      } else if (res.status === 502 || res.status === 503 || body.detail?.includes("not configured")) {
        setMsg({ kind: "info", text: "Checkout isn't live yet — Stripe activation pending. Email support@tapeline.io if you want to upgrade in the meantime." });
      } else {
        setMsg({ kind: "err", text: errorText(body, `Checkout failed (${res.status})`) });
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
      else setMsg({ kind: "err", text: errorText(body, "Portal not available — Stripe activation pending.") });
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

      {/* ── Trial offer (?trial=start) ─────────────────────────────────────
          The one place the 14-day Premium trial is actually offered. It is a
          fork, not a funnel: two same-sized buttons, the full charge terms in
          plain body text above them, and no way for the page to walk into
          Stripe on its own. See TrialOfferPanel for the rules it has to obey. */}
      {showTrialOffer && (
        <TrialOfferPanel
          billingPeriod={billingPeriod}
          onBillingPeriod={setBillingPeriod}
          firstCharge={trialFirstCharge}
          busy={busy === "premium"}
          onStartTrial={() => startCheckout("premium", { startTrial: true })}
        />
      )}

      {/* ── Failed-renewal recovery ────────────────────────────────────────
          A card declined on renewal. Stripe is mid-retry and the customer
          keeps their tier for the duration of that grace window, so the honest
          framing is "this needs a fix", not "your account is suspended". The
          global DunningBanner says the same thing in one line from the app
          shell; this panel is the destination version — it explains what
          happens next and what happens if nothing changes, because an
          involuntary failure the user never understood is how a payment
          problem quietly becomes a cancellation. */}
      {pastDue && (
        <div className="rounded-lg border border-warn/40 bg-warn/5 p-5">
          <div className="font-semibold text-fg">Your last renewal payment didn&rsquo;t go through.</div>
          <p className="mt-1.5 text-sm text-muted leading-relaxed">
            This is usually an expired card or a bank declining an online
            charge, not a problem with your account. Stripe will retry it
            automatically over the next few days, and you keep full {meta.name}{" "}
            access while it does. Updating your card fixes it immediately; if
            every retry fails, the plan drops to Free and you can re-subscribe
            whenever you like.
          </p>
          {hasBilling === true && (
            <button onClick={openPortal} className="btn-accent mt-4 text-sm">
              Update payment method →
            </button>
          )}
          <p className="mt-3 text-xs text-subtle">
            Card details are updated on Stripe&rsquo;s own portal &mdash; they never
            reach a Tapeline server. Questions: support@tapeline.io.
          </p>
        </div>
      )}

      {/* ── Cancelled-checkout recovery ────────────────────────────────────
          Answers "was I charged?" before anything else, then offers exactly
          one way back. No urgency, no expiring reservation, no discount
          rescue-offer — the plan and price are the same as they were a minute
          ago, and saying so is the whole point. */}
      {checkoutCancelled && !pastDue && (
        <div className="rounded-lg border border-border bg-panel p-5">
          <div className="font-semibold text-fg">Checkout cancelled &mdash; nothing was charged.</div>
          <p className="mt-1.5 text-sm text-muted leading-relaxed">
            You came back from Stripe without completing the payment, so no card
            was charged and your plan is unchanged.{" "}
            {cancelledTier
              ? `The ${TIER_META[cancelledTier].name} plan is still here at the same price whenever you want it.`
              : "The plans below are unchanged and still here whenever you want them."}
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            {/* One obvious way to resume. With a known tier that's a single
                click straight back into the same Stripe session; without one
                we scroll to the picker rather than guessing a plan for them. */}
            {cancelledTier ? (
              <button
                onClick={() => startCheckout(cancelledTier)}
                disabled={busy === cancelledTier}
                className="btn-accent text-sm disabled:opacity-60"
              >
                {busy === cancelledTier
                  ? "Opening…"
                  : `Resume ${TIER_META[cancelledTier].name} checkout →`}
              </button>
            ) : (
              <a href="#plan-picker" className="btn-accent text-sm">
                Pick up where you left off →
              </a>
            )}
            <button
              onClick={() => setCheckoutCancelled(false)}
              className="text-xs text-muted hover:text-fg"
            >
              Not now
            </button>
          </div>
          <p className="mt-3 text-xs text-subtle">
            Ran into a problem paying? Email support@tapeline.io and we&rsquo;ll sort it.
          </p>
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
        <div className={`md:col-span-3 relative overflow-hidden rounded-2xl p-6 ${
          tier === "premium"
            ? "border border-accent/40 bg-gradient-to-br from-accent/15 via-panel to-panel"
            : tier === "pro"
            ? "border border-fg/30 bg-gradient-to-br from-fg/8 via-panel to-panel"
            : "bg-panel"
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
                  rejection. Open the in-page plan picker instead. The label
                  splits on whether they have ever held Premium: "Re-activate"
                  is nonsense to a brand-new free account that never had it. */}
              <button onClick={openPlanPicker} className="btn-accent text-sm">
                {trialEligible ? "See plans and the 14-day trial →" : "Re-activate Premium →"}
              </button>
            </div>
          )}
        </div>

        {/* Next charge / trial preview — spans 2 of 5 cols */}
        <div className="md:col-span-2 rounded-2xl bg-panel p-6">
          <div className="text-[11px] uppercase tracking-wider text-muted">
            {isCardlessTrial
              ? "When the trial ends"
              : isCardTrial
              ? "First charge"
              : tier === "free"
              ? "What you get on Premium"
              : pastDue
              ? "Payment status"
              : "Next charge"}
          </div>

          {/* A failing renewal makes "Next charge $99/year" a statement the
              user has already seen fail. Say what's actually true instead —
              the recovery panel above carries the detail and the fix. */}
          {pastDue && !isCardlessTrial && tier !== "free" ? (
            <>
              <div className="mt-2 text-lg font-semibold text-warn">Retrying your card</div>
              <p className="mt-2 text-xs text-muted leading-relaxed">
                The last renewal charge didn&rsquo;t complete. Your next charge date
                depends on when it succeeds, so there isn&rsquo;t a reliable one to
                show yet.
              </p>
            </>
          ) : isCardTrial ? (
            /* Card-on-file trial. A real charge is scheduled, so this tile
               states the date, the amount, and the one-click exit — never a
               bare "Next charge $199/year", which would read as though the
               money is already moving. */
            <>
              <div className="mt-2 text-2xl font-bold nums">
                {trialEndsAt!.toLocaleDateString(userLocale(), { month: "short", day: "numeric", year: "numeric" })}
              </div>
              <p className="mt-2 text-xs text-muted leading-relaxed">
                Nothing has been charged yet. On that date your card is charged
                for the {meta.name} plan you started &mdash;{" "}
                {usdCompact(meta.annual)}/yr on annual billing, or{" "}
                {usd(meta.monthly)}/mo on monthly; the Stripe portal shows which
                one is on your subscription. Cancel any time before then and you
                are not charged at all &mdash; the trial ends and the account
                moves to Free.
              </p>
            </>
          ) : isCardlessTrial ? (
            <>
              <div className="mt-2 text-2xl font-bold nums">
                {trialEndsAt!.toLocaleDateString(userLocale(), { month: "short", day: "numeric", year: "numeric" })}
              </div>
              <p className="mt-2 text-xs text-muted leading-relaxed">
                {chargesToday ? (
                  <>
                    Your trial ends within 48 hours, so adding a card now starts
                    your {meta.name} subscription and the first charge is today.
                  </>
                ) : (
                  <>
                    Adding a card now doesn&rsquo;t charge you today — the first
                    charge is only on this date, and you can cancel any time
                    before then and never be billed.
                  </>
                )}{" "}
                Skip it and your account stays on the Free plan, with no expiry — live scores,
                top-{FREE_LIMITS.scannerRows}{" "}scanner, {FREE_LIMITS.dailyLookups}{" "}look-ups/day{freeHasWatchlist() ? `, ${FREE_LIMITS.watchlistTickers}-ticker watchlist` : ""}.
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
                  ? `Effective $${meta.annualMonthly}/mo · ${REFUND.windowDays}-day prorated refund, cancel in one click.`
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
          {/* Caps mirror backend services/tier.py TIER_LIMITS — free caps
              derive from FREE_LIMITS (lib/pricing.ts). */}
          <UsageTile
            label="Watchlist tickers"
            // Free watchlist cap is date-gated → 0 after the 2026-08-02 Pro
            // cutover, matching the Email-alerts / Saved-scans tiles that
            // already show 0 for free-locked features.
            limit={tier === "free" ? (freeHasWatchlist() ? FREE_LIMITS.watchlistTickers : 0) : tier === "pro" ? 50 : 200}
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
            // Free is FREE_LIMITS.savedScans (1), not 0 — this tile contradicted
            // the Free plan card 55 lines below on this same page.
            limit={tier === "free" ? FREE_LIMITS.savedScans : tier === "pro" ? 10 : 100}
            unit="scans"
          />
          <UsageTile
            label="Scanner rows"
            // This tile states the signed-in user's OWN current cap, so it is
            // one of the two surfaces that must follow the open-access lift
            // (freeScannerRows, lib/pricing.ts). Everything else on this page
            // describes the steady-state plan and stays on FREE_LIMITS.
            limit={tier === "free" ? freeScannerRows({ authenticated: true }) : 2500}
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
                {REFUND.short}, no questions — full on monthly, prorated on annual. Cancel in one click. Founding pricing — your rate is locked in while you stay subscribed.
              </p>
              {/* Currency + tax, from the live Stripe config rather than a
                  hardcoded "All prices in USD" that nobody re-checks. Stated
                  before the redirect so the hosted page can't surprise. */}
              <p className="mt-1 text-xs text-subtle">{chargeDisclosureLine(disclosure)}</p>
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
              note="No monthly charge"
              items={[
                `Live scores, top-${FREE_LIMITS.scannerRows} scanner, ${FREE_LIMITS.dailyLookups} look-ups/day`,
                "Public scorecard + basic regime",
                `${freeHasWatchlist() ? `Watchlist of ${FREE_LIMITS.watchlistTickers} · ` : ""}${FREE_LIMITS.savedScans} saved screen`,
                // #683 took Free to zero alerts on EVERY channel, push
                // included. Name the absence; never render "0 alerts".
                FREE_LIMITS.webPushAlerts > 0
                  ? `${FREE_LIMITS.webPushAlerts} browser push alerts`
                  : "No alerts — email or push",
              ]}
              highlight={tier === "free"}
            />
            <Plan
              name="Pro"
              price={billingPeriod === "annual" ? usd(TIER_META.pro.annualMonthly) : usd(TIER_META.pro.monthly)}
              note={billingPeriod === "annual" ? `${usd(TIER_META.pro.annual)}/yr · billed annually · save $${annualSaving(TIER_META.pro)}${isCardlessTrial ? ` · or ${usd(TIER_META.pro.monthly)}/mo monthly` : ""}` : "billed monthly"}
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
              note={billingPeriod === "annual" ? `${usd(TIER_META.premium.annual)}/yr · billed annually · save $${annualSaving(TIER_META.premium)}${isCardlessTrial ? ` · or ${usd(TIER_META.premium.monthly)}/mo monthly` : ""}` : "billed monthly"}
              proPlus
              items={[
                "Congressional trades feed (House + Senate)",
                "Recent insider buys — live SEC Form 4 across ~2,500 tickers",
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
              //
              // A trial-eligible free account gets the TRIAL from this card
              // rather than an immediate charge, so the picker and the offer
              // panel above can never mean two different things. The
              // disclosure below the button carries the same four facts the
              // panel does, because this card is reachable without it.
              cta={
                trialEligible
                  ? `Start the ${TRIAL_DAYS}-day trial`
                  : isCardlessTrial
                  ? "Keep Premium — add a card"
                  : "Upgrade to Premium"
              }
              disclosure={
                trialEligible
                  ? `$0 today · first charge ${longDate(trialFirstCharge)} (${
                      billingPeriod === "annual"
                        ? `${usdCompact(TIER_META.premium.annual)}/yr`
                        : `${usd(TIER_META.premium.monthly)}/mo`
                    }) · cancel in one click before then and you are never charged`
                  : undefined
              }
              highlight={tier === "premium" && !isCardlessTrial}
              intent={intentPlan === "premium" && (tier !== "premium" || isCardlessTrial)}
              disabled={tier === "premium" && !isCardlessTrial}
              busy={busy === "premium"}
              onUpgrade={() => startCheckout("premium", { startTrial: trialEligible })}
            />
          </div>

          {/* Money-back as a MECHANISM at the annual decision point. An annual
              buyer commits 12 months up front; the useful reassurance is the
              procedure and the timing, not a seal. Numbers come from the
              REFUND constant (single-sourced from /legal/refund). */}
          {billingPeriod === "annual" && (
            <div className="mx-auto max-w-2xl rounded-lg bg-panel/60 px-5 py-4">
              <div className="text-xs font-medium text-fg">
                How the {REFUND.short.toLowerCase()} actually works
              </div>
              <p className="mt-1.5 text-xs text-muted leading-relaxed">
                Email support@tapeline.io from your account address within{" "}
                {REFUND.windowDays}{" "}days of your first charge — no form, no
                reason required. We process it within 3 business days and Stripe
                returns the money to the card or wallet you paid with, usually
                landing in 3&ndash;10 business days depending on your bank.
                Annual plans get a {REFUND.annual}.{" "}
                <Link href={REFUND.policyPath} className="text-accent hover:underline">
                  Full policy
                </Link>
                .
              </p>
            </div>
          )}

          {/* Payment security in plain language, directly under the upgrade
              buttons — the highest-value placement, since a new account is walled
              until it adds one, and every card entry happens at Stripe Checkout.
              Factual and verifiable; no badge, no certification claim. */}
          <p className="mx-auto max-w-2xl text-center text-[11px] leading-relaxed text-subtle">
            Card details are entered on Stripe&rsquo;s own checkout page, not on
            Tapeline. Your card number never reaches a Tapeline server &mdash; we
            receive only the subscription status Stripe reports back.
          </p>

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
                {/* The embedded comparison header follows THIS page's toggle
                    so the plan cards above and this table can never show
                    different billing periods on one screen. */}
                <BillingPeriodProvider value={billingPeriod}>
                  <ComparisonTable />
                </BillingPeriodProvider>
              </div>
            </details>
          </div>
        </section>
      )}

      {/* ── Why Tapeline (sales reinforcement only on the change-plan view) ─ */}
      {showPlans && tier !== "premium" && (
        <section className="border-t border-border/60 pt-8">
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
              title="Named factors, shown per ticker"
              body="All six factors are named on /how-it-works — weighted most toward Trend and Relative Strength, least toward Momentum — with each factor's contribution shown per ticker."
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
 * The 14-day Premium trial offer — the ONE surface that asks for a card in
 * exchange for a trial, and therefore the one that has to be beyond reproach.
 *
 * NON-NEGOTIABLES, all enforced by __tests__/TrialStartOffer.test.tsx:
 *
 *   1. FULL DISCLOSURE BEFORE THE CARD. Four facts as real body text (not an
 *      image, not a tooltip, not behind a <details>): $0 charged today, the
 *      exact calendar date of the first charge, the amount that will be
 *      charged, and that one click cancels before then. If the user only reads
 *      the buttons they have still been told the price and the date.
 *   2. THE DECLINE IS EQUAL, AND TRUE. The decline is the same size and the
 *      same typographic weight as the trial button, sits beside it, is not a
 *      greyed-out afterthought, and is not preceded by a guilt line.
 *
 *      It must also DESCRIBE WHAT ACTUALLY HAPPENS. This has been wrong in
 *      both directions, so the history is worth keeping:
 *
 *      The panel shipped with one unconditional decline reading "Continue on
 *      the Free plan → /app/scanner", promising "live scores, top-N scanner, N
 *      look-ups a day". From CARD_GATE_START (2026-08-22) every word of that
 *      was false for a new account: /app/scanner was not in
 *      CARD_GATE_PASSTHROUGH, so app/app/layout.tsx replaced it with the card
 *      wall the instant they clicked. So the decline was FORKED on
 *      `cardRequired` (the server's `must_add_card`): a gated account was told
 *      the signed-in app stays locked without a card and was pointed at the
 *      public record instead.
 *
 *      #683 (2026-08-30) removed the wall, which made the FORK the lie — it
 *      was telling every card-free account the app was locked when the free
 *      scanner was one click away, and routing them off the product to say so.
 *      The fork is gone and the decline is unconditional again: everyone
 *      continues on the Free plan, to /app/scanner, which is now true for
 *      every account that can see this panel.
 *
 *      THE RULE, which outlived both mistakes: the decline must describe the
 *      destination it actually leads to. Never promise a Free tier the reader
 *      cannot reach, and never withhold one they can.
 *   3. NO DARK PATTERNS. No auto-redirect into Stripe (the button is the only
 *      thing that navigates), nothing pre-ticked, no countdown, no scarcity,
 *      no "N spots left", no fake discount. Compliance rule 6 — and the copy
 *      linter (scripts/lint-copy-compliance.mjs) will fail the build for most
 *      of them anyway.
 *   4. KEYBOARD OPERABLE. Everything interactive is a real <button> or <a>,
 *      in reading order, with the global :focus-visible ring plus an explicit
 *      focus ring here so it stays visible on the tinted panel.
 *
 * The billing-period choice lives inside the panel because the AMOUNT in the
 * disclosure has to be the amount for the period actually selected. It shares
 * state with the plan picker's toggle below, so the two can never disagree.
 */
function TrialOfferPanel({
  billingPeriod,
  onBillingPeriod,
  firstCharge,
  busy,
  onStartTrial,
}: {
  billingPeriod: "monthly" | "annual";
  onBillingPeriod: (p: "monthly" | "annual") => void;
  firstCharge: Date;
  busy: boolean;
  onStartTrial: () => void;
}) {
  const chargeDate = longDate(firstCharge);
  const amount =
    billingPeriod === "annual"
      ? `${usdCompact(PRICING.premium.annual)} for the year`
      : `${usd(PRICING.premium.monthly)} for the month`;
  const FOCUS =
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background";

  return (
    <section
      data-testid="trial-offer"
      aria-labelledby="trial-offer-heading"
      className="rounded-2xl border border-border bg-panel p-6"
    >
      <h2 id="trial-offer-heading" className="text-xl font-semibold">
        Start your {TRIAL_DAYS}-day Premium trial &mdash; or don&rsquo;t
      </h2>
      <p className="mt-1.5 text-sm text-muted">
        Every Premium feature for {TRIAL_DAYS} days: the full ~2,500-ticker live
        universe, score breakdowns, Congressional trades and insider buys,
        watchlist of 200 and unlimited email alerts. Starting the trial takes a
        card, because it becomes a paid subscription if you keep it. Here is
        exactly what that means.
      </p>

      {/* Billing period — nothing is pre-ticked beyond the site-wide default,
          and switching it rewrites the amount in the disclosure below. */}
      <div className="mt-5">
        <div id="trial-period-label" className="text-[11px] uppercase tracking-wider text-muted">
          Plan after the trial
        </div>
        <div
          role="group"
          aria-labelledby="trial-period-label"
          className="mt-2 inline-flex rounded-full border border-border bg-surface p-1"
        >
          {(["annual", "monthly"] as const).map((p) => (
            <button
              key={p}
              type="button"
              aria-pressed={billingPeriod === p}
              onClick={() => onBillingPeriod(p)}
              className={`rounded-full px-4 py-1.5 text-xs font-medium transition-all ${FOCUS} ${
                billingPeriod === p ? "bg-fg text-background" : "text-muted hover:text-fg"
              }`}
            >
              {p === "annual"
                ? `Annual · ${usdCompact(PRICING.premium.annual)}/yr`
                : `Monthly · ${usd(PRICING.premium.monthly)}/mo`}
            </button>
          ))}
        </div>
      </div>

      {/* THE DISCLOSURE. Plain text, always visible, never collapsed. */}
      <ul data-testid="trial-disclosure" className="mt-5 space-y-2 text-sm text-fg">
        <li className="flex gap-2">
          <span aria-hidden="true" className="text-muted">·</span>
          <span>
            <strong className="font-semibold">$0 today.</strong> Starting the
            trial charges you nothing now.
          </span>
        </li>
        <li className="flex gap-2">
          <span aria-hidden="true" className="text-muted">·</span>
          <span>
            <strong className="font-semibold">Your first charge is on {chargeDate}</strong>{" "}
            &mdash; {amount}, and then {billingPeriod === "annual" ? "every year" : "every month"}{" "}
            until you cancel.
          </span>
        </li>
        <li className="flex gap-2">
          <span aria-hidden="true" className="text-muted">·</span>
          <span>
            <strong className="font-semibold">Cancel in one click</strong> from this
            page any time before {chargeDate} and you are never charged.
          </span>
        </li>
        <li className="flex gap-2">
          <span aria-hidden="true" className="text-muted">·</span>
          <span>
            Card details are entered on Stripe&rsquo;s own checkout page. Your
            card number never reaches a Tapeline server.
          </span>
        </li>
      </ul>

      {/* THE FORK. Same height, same width behaviour, same font weight. */}
      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          onClick={onStartTrial}
          disabled={busy}
          className={`flex h-11 flex-1 items-center justify-center rounded-md border border-accent bg-accent/15 px-4 text-sm font-medium text-fg transition-colors hover:bg-accent/25 disabled:cursor-not-allowed disabled:opacity-60 ${FOCUS}`}
        >
          {busy ? "Opening Stripe…" : `Start the ${TRIAL_DAYS}-day trial`}
        </button>
        <Link
          href="/app/scanner"
          className={`flex h-11 flex-1 items-center justify-center rounded-md border border-border bg-surface px-4 text-sm font-medium text-fg transition-colors hover:bg-panel2 ${FOCUS}`}
        >
          Continue on the Free plan
        </Link>
      </div>

      <p className="mt-4 text-xs text-muted leading-relaxed">
        Declining costs you nothing: you stay on the Free plan &mdash; live scores,
        top-{FREE_LIMITS.scannerRows}{" "}scanner, {FREE_LIMITS.dailyLookups}{" "}look-ups a day
        {freeHasWatchlist() ? `, a ${FREE_LIMITS.watchlistTickers}-ticker watchlist` : ""}, and
        {" "}{FREE_LIMITS.savedScans}{" "}saved screen &mdash; and no further charge is made. The
        public record stays open too, with no account at all. You can start the trial later from
        this page &mdash; it is here whenever you want it.
      </p>
    </section>
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
    <div>
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
  name, price, items, note, cta, disclosure, highlight, intent, disabled, busy, onUpgrade, proPlus,
}: {
  name: string; price: string; items: string[]; note?: string;
  cta?: string;
  /**
   * Charge terms printed directly under the CTA, as body text. Used by the
   * trial CTA so the four disclosure facts ($0 today / first-charge date /
   * amount / one-click cancel) travel with the button even when the user
   * reached this card without passing the offer panel.
   */
  disclosure?: string;
  highlight?: boolean; intent?: boolean; disabled?: boolean; busy?: boolean;
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
      {cta && disclosure && !disabled && (
        <p className="mt-2 text-[11px] leading-relaxed text-muted">{disclosure}</p>
      )}
    </div>
  );
}
