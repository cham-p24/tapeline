"use client";

import Link from "next/link";
import { useEffect } from "react";
import { track } from "@vercel/analytics";
import { trackEvent } from "@/lib/gtag";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { PRICING } from "@/lib/pricing";

export function CheckoutSuccessClient() {
  // Conversion analytics — the same pair /app/billing fires for the authed
  // flow (trial_converted + the GA4/Ads "subscribe" revenue event), read from
  // window.location.search inside a browser-only effect rather than
  // useSearchParams (which would force a Suspense boundary). Without this,
  // email-originated conversions — the exact ones the one-click flow exists
  // to produce — would be invisible in analytics.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const qp = new URLSearchParams(window.location.search);
    const tier = qp.get("tier") === "pro" ? "pro" : "premium";
    const period = qp.get("billing_period") === "annual" ? "annual" : "monthly";
    track("trial_converted", { tier, billing_period: period, src: "email" });
    const p = PRICING[tier];
    const value = period === "annual" ? p.annual : p.monthly;
    trackEvent("subscribe", { tier, billing_period: period, value, currency: "USD" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="relative min-h-screen overflow-x-hidden">
      <MarketingNav />
      <section className="mx-auto max-w-xl px-6 py-20 text-center">
        <div className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-full bg-up/15 text-3xl">
          ✓
        </div>
        <h1 className="mt-6 text-4xl font-bold tracking-tight">
          Payment received — you&rsquo;re in.
        </h1>
        <p className="mt-5 text-muted leading-relaxed">
          Your subscription is active and your account upgrades automatically
          within a few seconds. Your watchlist and alert rules are exactly as
          you left them.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/signin?next=/app/scanner" className="btn-primary text-base">
            Sign in to open the app &rarr;
          </Link>
        </div>
        <p className="mt-4 text-xs text-muted">
          Forgot your password?{" "}
          <Link href="/forgot-password" className="link">
            Reset it in one click
          </Link>{" "}
          &mdash; your subscription is already attached to your account either way.
        </p>
        <p className="mt-8 text-xs text-subtle">
          30-day money back, no questions &middot; cancel any time in one click
          &middot; receipt arrives from Stripe by email
        </p>
      </section>
      <MarketingFooter />
    </main>
  );
}
