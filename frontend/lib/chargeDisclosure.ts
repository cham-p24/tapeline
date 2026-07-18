/**
 * Charge disclosure — what Stripe actually takes, stated before the redirect.
 *
 * Checkout research (Baymard) puts "unexpected cost at the payment step" at the
 * top of the abandonment list. The plan cards therefore have to answer two
 * questions on our own page rather than on checkout.stripe.com: what currency
 * is this charged in, and is anything added on top?
 *
 * Both answers come from GET /api/billing/charge-disclosure, which derives them
 * from the live Stripe Price object plus the Checkout kwargs the backend
 * actually sends (see backend/app/services/billing.py::get_charge_disclosure).
 * Nothing here is a guess:
 *
 *   - `currency` falls back to PRICING.currency (the same constant that drives
 *     the visible prices and the JSON-LD priceCurrency), so the currency
 *     sentence renders on first paint and only ever gets *corrected* by the
 *     server, never invented by it.
 *   - `taxAdded` starts as null — "we don't know yet" — and the tax sentence
 *     stays hidden until the server confirms. A page that can't reach the API
 *     says nothing about tax rather than asserting a tax claim it can't back.
 *     The server itself also returns null when it declines to make the call
 *     (e.g. a tax_behavior="exclusive" Price, where "nothing is added" would
 *     be unsafe to assert), so null is a real answer here, not just a
 *     loading state — and it renders identically either way.
 */
"use client";

import { useEffect, useState } from "react";
import { PRICING } from "@/lib/pricing";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export type ChargeDisclosure = {
  /** ISO currency code the card is actually charged in, e.g. "USD". */
  currency: string;
  /**
   * Whether Stripe adds tax/GST on top of the sticker price at checkout.
   * `null` until the server answers — render nothing about tax while null.
   */
  taxAdded: boolean | null;
};

/** The pre-network state: real currency, no tax claim. */
export const DEFAULT_CHARGE_DISCLOSURE: ChargeDisclosure = {
  currency: PRICING.currency,
  taxAdded: null,
};

/**
 * Fetch the charge disclosure once on mount. Never throws, never blocks paint,
 * and degrades to currency-only when the API is unreachable.
 */
export function useChargeDisclosure(): ChargeDisclosure {
  const [disclosure, setDisclosure] = useState<ChargeDisclosure>(
    DEFAULT_CHARGE_DISCLOSURE,
  );

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/billing/charge-disclosure`, {
          cache: "no-store",
        });
        if (!res.ok || !alive) return;
        const body = await res.json();
        if (!alive) return;
        setDisclosure({
          // Only override the constant when the server actually resolved a
          // currency from a real Price object (it sends null otherwise).
          currency:
            typeof body?.currency === "string" && body.currency
              ? body.currency
              : PRICING.currency,
          taxAdded: typeof body?.tax_added === "boolean" ? body.tax_added : null,
        });
      } catch {
        // Offline / API down — keep the currency-only default. The tax
        // sentence stays hidden, which is the safe direction.
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return disclosure;
}

/**
 * The one-line disclosure shown on the plan card. Returns the currency
 * sentence alone until the tax behaviour is known, so the string can never
 * claim "no tax" on a page that failed to reach the API.
 */
export function chargeDisclosureLine(d: ChargeDisclosure): string {
  const base = `Charged in ${d.currency}`;
  if (d.taxAdded === null) return `${base}.`;
  return d.taxAdded
    ? `${base}. Tax may be added at checkout based on your billing address.`
    : `${base}. No tax is added — the amount shown is the amount charged.`;
}
