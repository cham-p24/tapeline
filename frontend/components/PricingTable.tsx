"use client";

import Link from "next/link";
import { PRICING, FREE_LIMITS, REFUND, annualSaving, billedAnnuallyNote } from "@/lib/pricing";
import { BillingToggle, useBillingPeriod } from "@/components/BillingToggle";
import { useChargeDisclosure, chargeDisclosureLine } from "@/lib/chargeDisclosure";

const PLANS = [
  {
    name: "Free",
    tagline: "Free forever — live scores",
    prices: { monthly: 0, annual: 0, annualPerMonth: 0 },
    // Free-tier numbers derive from FREE_LIMITS (mirrors backend tier.py) so
    // this card always sells the tier the backend actually enforces.
    highlights: [
      "Live scores — no delay",
      `${FREE_LIMITS.dailyLookups} ticker look-ups per day — unmetered your first ${FREE_LIMITS.firstSessionGraceHours}h`,
      `Top-${FREE_LIMITS.scannerRows} scanner rows`,
      `Watchlist (${FREE_LIMITS.watchlistTickers} tickers)`,
      `Squeeze Watch top-${FREE_LIMITS.squeezePreviewRows} preview`,
      `${FREE_LIMITS.webPushAlerts} browser push alerts`,
      "Public scorecard, fully open",
    ],
    cta: "Start free",
    ctaHref: "/signup",
    highlight: false,
  },
  {
    name: "Pro",
    tagline: "Live scanner. Daily edge.",
    prices: {
      monthly: PRICING.pro.monthly,
      annual: PRICING.pro.annual,
      annualPerMonth: PRICING.pro.annualPerMonth,
    },
    highlights: [
      "Unlimited ticker look-ups",
      "Real-time, full ~2,500-ticker scanner",
      "Score + plain-English Why on every row",
      "Squeeze Watch · Regime · Heatmap",
      "IPOs · Earnings · News calendars",
      "Watchlist (50) with smart alerts",
      "Email alerts (10/day) · daily briefing",
      "TradingView charts · CSV export",
    ],
    cta: "Start free trial",
    ctaHref: "/signup?plan=pro",
    // Pro is the highlighted protagonist — the realistic first purchase.
    // "Best value" is a factual framing (cheapest paid tier per feature),
    // not manufactured social proof; with zero customers a "Most popular"
    // badge would be fabricated. Matches the Pro badge on ComparisonTable.
    highlight: true,
    badge: "Best value",
  },
  {
    name: "Premium",
    tagline: "The full surface — for the serious operator.",
    prices: {
      monthly: PRICING.premium.monthly,
      annual: PRICING.premium.annual,
      annualPerMonth: PRICING.premium.annualPerMonth,
    },
    // Premium-only additions on top of everything in Pro. Rendered in a
    // visually distinct block under the price so the upgrade reason is
    // obvious — not buried in a 7-bullet list that looks like Pro's.
    // Styled as the power tier (darker, quieter) — no popularity badge.
    proPlus: true,
    highlights: [
      "Congressional trades feed (House + Senate)",
      "Recent insider buys — live SEC Form 4 across ~2,500 tickers",
      "Telegram alerts · unlimited (Pro: none)",
      "Email alerts · unlimited (Pro: 10/day)",
      "Public API access · 1,000 requests/day",
      "Watchlist 200 · saved scans 100 (Pro: 50 · 10)",
      "Priority support · same-day reply",
    ],
    cta: "Try Premium free",
    ctaHref: "/signup?plan=premium",
    highlight: false,
  },
];

export function PricingTable() {
  // ANNUAL is the default (founder decision 2026-07-18) — monthly stays one
  // click away. State lives in the shared BillingPeriod context so the
  // ComparisonTable header on the same page can never disagree with these
  // cards; standalone renders fall back to the same annual default.
  const { billing, setBilling } = useBillingPeriod();
  // What Stripe will actually take, derived from the live Price object plus
  // the session kwargs the backend sends — never a hardcoded guess. Falls
  // back to the PRICING.currency constant and stays silent about tax until
  // the server confirms it.
  const disclosure = useChargeDisclosure();

  return (
    <div>
      {/* Billing toggle — drives the page-wide shared billing period */}
      <div className="flex justify-center">
        <BillingToggle billing={billing} setBilling={setBilling} />
      </div>
      {/* Currency + tax, stated here rather than discovered on
          checkout.stripe.com. "Unexpected cost at the payment step" is the
          top documented abandonment cause; this is the answer to it. */}
      <p className="mt-3 text-center text-xs text-muted">
        {chargeDisclosureLine(disclosure)}
      </p>
      {billing === "annual" && (
        <p className="mt-1 text-center text-xs text-up/90">Save 2 months · your rate, locked in</p>
      )}

      {/* 3 main plans */}
      <div className="mx-auto mt-10 grid max-w-5xl gap-4 md:grid-cols-3 md:gap-6">
        {PLANS.map((p) => {
          const price = p.prices[billing];
          // Annual advertises the exact per-month equivalent from
          // lib/pricing.ts ($99/yr → $8.25/mo; $199/yr → $16.58/mo).
          // Monthly stays as-is.
          const perMonth = billing === "annual" ? p.prices.annualPerMonth : price;
          const isPower = (p as { proPlus?: boolean }).proPlus === true;
          const ctaHref = p.ctaHref.includes("?")
            ? `${p.ctaHref}&billing=${billing}`
            : `${p.ctaHref}?billing=${billing}`;
          return (
            <div
              key={p.name}
              className={`relative rounded-2xl border p-6 sm:p-8 transition-all ${
                p.highlight
                  ? "border-accent/60 bg-gradient-to-b from-accent/10 via-panel to-panel shadow-lg shadow-accent/20"
                  : isPower
                  ? "border-border2 bg-gradient-to-b from-panel2/60 via-panel to-panel"
                  : "border-border bg-panel"
              }`}
            >
              {p.highlight && p.badge && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-gradient-to-r from-accent to-accent2 px-3 py-1 text-[11px] font-medium text-white shadow-md">
                  {p.badge}
                </span>
              )}
              <h3 className="text-xl font-semibold">{p.name}</h3>
              <p className="mt-1 text-sm text-muted">{p.tagline}</p>
              <div className="mt-6">
                <div className="flex items-baseline gap-1.5">
                  <span className="text-5xl font-bold nums tracking-tight">
                    {price === 0 ? "$0" : `$${perMonth.toFixed(2)}`}
                  </span>
                  <span className="text-muted">/ month</span>
                </div>
                {/* An annual per-month figure never renders without the
                    explicit billed-annually qualifier + the real total. */}
                {billing === "annual" && price > 0 && (
                  <p className="mt-1.5 text-xs text-muted">
                    {billedAnnuallyNote(p.prices)} · save ${annualSaving(p.prices)}/yr
                  </p>
                )}
                {billing === "monthly" && price > 0 && (
                  <p className="mt-1.5 text-xs text-muted">billed monthly</p>
                )}
              </div>

              {/* Premium card: "Everything in Pro" anchor strip above the
                  bullets so the upgrade reason is the additions, not "look
                  here's a duplicate of the Pro list". */}
              {isPower && (
                <div className="mt-6 flex items-center gap-2 rounded-md border border-border bg-panel2/40 px-3 py-2 text-xs text-muted">
                  <svg className="h-3.5 w-3.5 text-up flex-shrink-0" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                    <path d="M3 8l3 3 7-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span>Everything in Pro</span>
                  <span className="ml-auto text-accent font-medium">+ all of:</span>
                </div>
              )}
              <ul className={`${isPower ? "mt-3" : "mt-6"} space-y-2.5 text-sm`}>
                {p.highlights.map((f) => (
                  <li key={f} className="flex gap-3">
                    <svg className="mt-0.5 h-4 w-4 flex-shrink-0 text-accent" viewBox="0 0 16 16" fill="none">
                      <path d="M3 8l3 3 7-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <Link
                href={ctaHref}
                className={`mt-8 flex h-11 w-full items-center justify-center rounded-md text-sm font-medium transition-all ${
                  p.highlight
                    ? "bg-gradient-to-r from-accent to-accent2 text-white hover:opacity-90 active:scale-[0.98]"
                    : "border border-border2 text-fg hover:bg-panel2"
                }`}
              >
                {p.cta}
              </Link>
            </div>
          );
        })}
      </div>

      {/* ── Risk reversals ────────────────────────────────────────────────
          Only the two that are unconditionally true and cost the user nothing
          to verify: the trial genuinely takes no card, and cancellation is
          genuinely one button (POST /api/billing/cancel, no survey gate). Both
          are stated as mechanisms — what happens, and what does NOT happen —
          because "no card required" only reassures if the reader can tell it
          means "we cannot charge you". No urgency, no deadline, no scarcity. */}
      <div className="mx-auto mt-10 grid max-w-3xl gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-border bg-panel/60 px-4 py-3">
          <div className="text-xs font-medium text-fg">14 days of Premium, no card</div>
          <p className="mt-1 text-xs text-muted leading-relaxed">
            Signup asks for an email and a password — no card fields. Nothing to
            charge means nothing can auto-renew: at day 14 the account moves to
            Free on its own unless you choose to add a card.
          </p>
        </div>
        <div className="rounded-lg border border-border bg-panel/60 px-4 py-3">
          <div className="text-xs font-medium text-fg">Cancel in one click</div>
          <p className="mt-1 text-xs text-muted leading-relaxed">
            One button on your billing page. No survey to complete, no email to
            send, no retention call. You keep access until the end of the period
            you already paid for.
          </p>
        </div>
      </div>

      {/* Remaining commitments — the two that aren't risk reversals. */}
      <div className="mx-auto mt-4 flex max-w-3xl flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-muted">
        <span>{REFUND.short}</span>
        <span className="text-subtle">·</span>
        <span>Founding pricing — locked in for early subscribers</span>
      </div>

      {/* ── Money-back as a MECHANISM, at the annual decision point ────────
          An annual buyer is committing 12 months up front, so the useful thing
          is not a seal — it's knowing exactly what to do, and how long it
          takes. Every number derives from the REFUND constant in lib/pricing
          (itself single-sourced from /legal/refund) so the window can never
          drift from the policy it summarises. */}
      {billing === "annual" && (
        <div className="mx-auto mt-6 max-w-2xl rounded-lg border border-border bg-panel/60 px-5 py-4">
          <div className="text-xs font-medium text-fg">
            How the {REFUND.short.toLowerCase()} actually works
          </div>
          <p className="mt-1.5 text-xs text-muted leading-relaxed">
            Email support@tapeline.io from your account address within{" "}
            {REFUND.windowDays} days of your first charge — there is no form and
            no reason required. We process it within 3 business days, and Stripe
            returns the money to the card or wallet you paid with, which usually
            lands in 3&ndash;10 business days depending on your bank. Annual
            plans get a {REFUND.annual}; monthly plans get a {REFUND.monthly}.{" "}
            <Link href={REFUND.policyPath} className="text-accent hover:underline">
              Full policy
            </Link>
            .
          </p>
        </div>
      )}

      {/* Payment security, in plain language, at the point of card entry.
          Factual and verifiable: the card form is Stripe's, on Stripe's
          domain. No badges, no certification claims, no security promises of
          our own — we make none because we handle none of it. */}
      <p className="mx-auto mt-5 max-w-2xl text-center text-[11px] leading-relaxed text-subtle">
        Card details are entered on Stripe&rsquo;s own checkout page, not on
        Tapeline. Your card number never reaches a Tapeline server &mdash; we
        receive only the subscription status Stripe reports back.
      </p>

      {/* B2B / lifetime nudge — one line, no third row of cards.
          Curious enterprise buyers can email; everyone else stays focused
          on the three main tiers above. */}
      <p className="mx-auto mt-8 max-w-3xl text-center text-xs text-subtle">
        Need 5+ seats, custom SLA, or a one-time founder's lifetime? Email{" "}
        <a href="mailto:sales@tapeline.io" className="text-accent hover:underline">sales@tapeline.io</a>.
      </p>
    </div>
  );
}
