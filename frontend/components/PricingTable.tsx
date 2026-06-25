"use client";

import { useState } from "react";
import Link from "next/link";
import { PRICING } from "@/lib/pricing";

type Billing = "monthly" | "annual";

const PLANS = [
  {
    name: "Free",
    tagline: "Free forever — live scores",
    prices: { monthly: 0, annual: 0 },
    highlights: [
      "Live scores — no delay",
      "5 ticker look-ups per day",
      "Top-10 scanner rows",
      "Watchlist (3 tickers)",
      "Public scorecard, fully open",
    ],
    cta: "Start free",
    ctaHref: "/signup",
    highlight: false,
  },
  {
    name: "Pro",
    tagline: "Live scanner. Daily edge.",
    prices: { monthly: PRICING.pro.monthly, annual: PRICING.pro.annual },
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
    highlight: false,
  },
  {
    name: "Premium",
    tagline: "For the serious operator.",
    prices: { monthly: PRICING.premium.monthly, annual: PRICING.premium.annual },
    // Premium-only additions on top of everything in Pro. Rendered in a
    // visually distinct block under the price so the upgrade reason is
    // obvious — not buried in a 7-bullet list that looks like Pro's.
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
    highlight: true,
    badge: "Most popular",
  },
];

export function PricingTable() {
  const [billing, setBilling] = useState<Billing>("annual");

  return (
    <div>
      {/* Billing toggle */}
      <div className="flex justify-center">
        <div className="inline-flex rounded-full border border-border bg-panel p-1">
          {(["monthly", "annual"] as const).map((b) => (
            <button
              key={b}
              onClick={() => setBilling(b)}
              className={`relative rounded-full px-5 py-1.5 text-sm font-medium transition-all ${
                billing === b ? "bg-fg text-background" : "text-muted hover:text-fg"
              }`}
            >
              {b === "annual" ? "Annual" : "Monthly"}
              {b === "annual" && billing !== "annual" && (
                <span className="absolute -right-2 -top-2 rounded-full bg-up px-1.5 py-0.5 text-[10px] font-bold text-background">
                  −17%
                </span>
              )}
            </button>
          ))}
        </div>
      </div>
      <p className="mt-3 text-center text-xs text-muted">All prices in USD</p>
      {billing === "annual" && (
        <p className="mt-1 text-center text-xs text-up/90">Save 2 months · today's price, locked</p>
      )}

      {/* 3 main plans */}
      <div className="mx-auto mt-10 grid max-w-5xl gap-4 md:grid-cols-3 md:gap-6">
        {PLANS.map((p) => {
          const price = p.prices[billing];
          // Charm-price the annual per-month display: round up to nearest .99
          // ($299.99/yr → $24.99/mo; $479.99/yr → $39.99/mo). Monthly stays as-is.
          const rawPerMonth = billing === "annual" ? price / 12 : price;
          const perMonth = billing === "annual" && price > 0
            ? Math.floor(rawPerMonth) + 0.99
            : rawPerMonth;
          const ctaHref = p.ctaHref.includes("?")
            ? `${p.ctaHref}&billing=${billing}`
            : `${p.ctaHref}?billing=${billing}`;
          return (
            <div
              key={p.name}
              className={`relative rounded-2xl border p-6 sm:p-8 transition-all ${
                p.highlight
                  ? "border-accent/60 bg-gradient-to-b from-accent/10 via-panel to-panel shadow-lg shadow-accent/20"
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
                {billing === "annual" && price > 0 && (
                  <p className="mt-1.5 text-xs text-muted">Billed ${price.toFixed(2)}/yr · save ${Math.round((p.prices.monthly * 12) - p.prices.annual)}/yr</p>
                )}
              </div>
              {/* Premium card: price-anchor chip — Bloomberg Terminal as the
                  universally-known "expensive professional terminal" cost.
                  Makes $479.99/yr read as 98% off the same data spine. */}
              {(p as { proPlus?: boolean }).proPlus && billing === "annual" && price > 0 && (
                <div className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-up/20 bg-up/5 px-2.5 py-1 text-[11px] text-up">
                  <span aria-hidden="true">↘</span>
                  <span className="text-fg">98% cheaper</span>
                  <span className="text-muted">than Bloomberg Terminal</span>
                  <span className="text-subtle line-through nums">$31,980/yr</span>
                </div>
              )}

              {/* Premium card: "Everything in Pro" anchor strip above the
                  bullets so the upgrade reason is the additions, not "look
                  here's a duplicate of the Pro list". */}
              {(p as { proPlus?: boolean }).proPlus && (
                <div className="mt-6 flex items-center gap-2 rounded-md border border-border bg-panel2/40 px-3 py-2 text-xs text-muted">
                  <svg className="h-3.5 w-3.5 text-up flex-shrink-0" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                    <path d="M3 8l3 3 7-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span>Everything in Pro</span>
                  <span className="ml-auto text-accent font-medium">+ all of:</span>
                </div>
              )}
              <ul className={`${(p as { proPlus?: boolean }).proPlus ? "mt-3" : "mt-6"} space-y-2.5 text-sm`}>
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

      {/* Commitments — single tight strip, 4 chips */}
      <div className="mx-auto mt-10 flex max-w-3xl flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-muted">
        <span>14-day Premium trial · no card</span>
        <span className="text-subtle">·</span>
        <span>7-day money back</span>
        <span className="text-subtle">·</span>
        <span>Annual price locked forever</span>
        <span className="text-subtle">·</span>
        <span>Cancel in one click</span>
      </div>

      {/* Payment-security trust badge — sits under the plan CTAs at the
          decision point. Card details are never handled by Tapeline; checkout
          runs on Stripe. Descriptive only, no security claims of our own. */}
      <div className="mx-auto mt-5 flex items-center justify-center gap-1.5 text-[11px] text-subtle">
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

