"use client";

import { useState } from "react";
import Link from "next/link";

type Billing = "monthly" | "annual";

const PLANS = [
  {
    name: "Free",
    tagline: "See what's possible",
    prices: { monthly: 0, annual: 0 },
    highlights: [
      "Top 20 tickers, 24-hour delayed",
      "Public scorecard + basic regime",
      "Watchlist (5 tickers, no alerts)",
    ],
    cta: "Start free",
    ctaHref: "/signup",
    highlight: false,
  },
  {
    name: "Pro",
    tagline: "Live scanner. Daily edge.",
    prices: { monthly: 29, annual: 299 },
    highlights: [
      "Full ~870 ticker universe, live",
      "Score + plain-English Why on every row",
      "Squeeze Watch · Regime · Heatmap",
      "IPOs · Earnings · News calendars",
      "Watchlist (50) with smart alerts",
      "Email alerts (10/day) · daily briefing",
      "TradingView charts · CSV export",
    ],
    cta: "Start 14-day trial",
    ctaHref: "/signup?plan=pro",
    highlight: false,
  },
  {
    name: "Premium",
    tagline: "Everything, no limits.",
    prices: { monthly: 49, annual: 491 },
    highlights: [
      "Everything in Pro, plus:",
      "Congressional trades feed",
      "Telegram alerts (unlimited)",
      "Email alerts (unlimited)",
      "Public API (1,000 req/day)",
      "Watchlist (200) · saved scans (100)",
      "Priority support",
    ],
    cta: "Start 14-day trial",
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
      {billing === "annual" && (
        <p className="mt-3 text-center text-xs text-up/90">Save 2 months · price locked forever</p>
      )}

      {/* 3 main plans */}
      <div className="mx-auto mt-10 grid max-w-5xl gap-4 md:grid-cols-3 md:gap-6">
        {PLANS.map((p) => {
          const price = p.prices[billing];
          // Charm-price the annual per-month display: round up to nearest .99
          // ($299/yr → $24.99/mo; $491/yr → $40.99/mo). Monthly stays as-is.
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
              className={`relative rounded-2xl border p-8 transition-all ${
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
                  <p className="mt-1.5 text-xs text-muted">Billed ${price}/yr · save ${(p.prices.monthly * 12) - p.prices.annual}/yr</p>
                )}
              </div>
              <ul className="mt-6 space-y-2.5 text-sm">
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

      {/* Anchor row — Team / Enterprise / Lifetime */}
      <div className="mx-auto mt-16 max-w-5xl">
        <p className="mb-6 text-center text-xs uppercase tracking-[0.12em] text-subtle">For teams, enterprises &amp; founders</p>
        <div className="grid gap-4 md:grid-cols-3">
          <AnchorCard
            name="Team"
            tag="B2B"
            tagline="RIAs, funds, trading desks"
            price="$149"
            priceSuffix="/mo · 5 seats"
            detail="$29/extra · admin panel · shared watchlists"
            cta="Contact sales"
            href="mailto:sales@tapeline.io?subject=Team tier"
          />
          <AnchorCard
            name="Enterprise"
            tag="Custom"
            tagline="Hedge funds, family offices"
            price="Custom"
            priceSuffix=" · from $2k/mo"
            detail="SSO · SCIM · 10k+ API · SLA · dedicated CSM"
            cta="Talk to us"
            href="mailto:enterprise@tapeline.io?subject=Enterprise"
          />
          <AnchorCard
            name="Founder's Lifetime"
            tag="47 of 100 left"
            tagline="Pro tier, forever"
            price="$399"
            priceSuffix=" once"
            detail="Never billed · founders wall · early access"
            cta="Grab a spot"
            href="/signup?plan=lifetime"
            highlight
          />
        </div>
      </div>

      {/* Commitments */}
      <div className="mx-auto mt-12 flex max-w-2xl flex-wrap items-center justify-center gap-x-8 gap-y-2 text-xs text-muted">
        <span>14-day Pro trial, no card</span>
        <span className="text-subtle">•</span>
        <span>7-day money back</span>
        <span className="text-subtle">•</span>
        <span>Price locked on annual</span>
        <span className="text-subtle">•</span>
        <span>Cancel anytime, one click</span>
      </div>
    </div>
  );
}

function AnchorCard({
  name, tag, tagline, price, priceSuffix, detail, cta, href, highlight,
}: {
  name: string; tag: string; tagline: string; price: string; priceSuffix: string;
  detail: string; cta: string; href: string; highlight?: boolean;
}) {
  return (
    <div className={`rounded-xl border p-6 transition-all ${
      highlight ? "border-accent/50 bg-gradient-to-b from-accent/5 to-transparent" : "border-border bg-panel"
    }`}>
      <div className="flex items-baseline justify-between">
        <h3 className="font-semibold">{name}</h3>
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${
          highlight ? "bg-accent text-white" : "bg-panel2 text-subtle"
        }`}>{tag}</span>
      </div>
      <p className="mt-1 text-xs text-muted">{tagline}</p>
      <div className="mt-4 text-2xl font-semibold nums">
        {price}<span className="text-sm font-normal text-muted">{priceSuffix}</span>
      </div>
      <p className="mt-2 text-xs text-muted leading-relaxed">{detail}</p>
      <Link
        href={href}
        className={`mt-5 inline-flex h-9 items-center gap-1 text-sm ${
          highlight ? "text-accent hover:text-accent/80" : "text-muted hover:text-fg"
        } transition-colors`}
      >
        {cta} &rarr;
      </Link>
    </div>
  );
}
