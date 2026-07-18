"use client";

/**
 * Shared billing-period state + the pill toggle UI.
 *
 * FOUNDER DECISION (2026-07-18): pricing displays default to ANNUAL
 * everywhere, with the annual total always explicit ("$8.25/mo · billed
 * annually ($99/yr)"); monthly stays one click away.
 *
 * Why a context and not per-component state: every component on one screen
 * that shows a price must read the SAME toggle state. Before this existed the
 * /pricing plan cards defaulted to monthly ($9.99) while the always-annual
 * ComparisonTable header showed $8.25 — two prices for the same plan on one
 * screen (and the SERP title promised a third, unqualified). Pages wrap their
 * pricing surfaces in <BillingPeriodProvider>; PricingTable renders the
 * toggle; ComparisonTable follows the same context. A component rendered
 * without a provider falls back to its own state seeded with the sitewide
 * annual default, so it can never disagree with the default view.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { DEFAULT_BILLING_PERIOD, type BillingPeriod } from "@/lib/pricing";

type BillingPeriodCtx = {
  billing: BillingPeriod;
  setBilling: (b: BillingPeriod) => void;
};

const BillingPeriodContext = createContext<BillingPeriodCtx | null>(null);

export function BillingPeriodProvider({
  children,
  value,
  onChange,
}: {
  children: ReactNode;
  /**
   * Controlled mode: the parent owns the state (e.g. /app/billing, whose own
   * toggle also drives the checkout payload). Omit for uncontrolled usage —
   * the provider then holds the state itself, seeded with the annual default.
   */
  value?: BillingPeriod;
  onChange?: (b: BillingPeriod) => void;
}) {
  const [internal, setInternal] = useState<BillingPeriod>(DEFAULT_BILLING_PERIOD);
  const billing = value ?? internal;
  const setBilling = useCallback(
    (b: BillingPeriod) => {
      onChange?.(b);
      setInternal(b);
    },
    [onChange],
  );
  const ctx = useMemo(() => ({ billing, setBilling }), [billing, setBilling]);
  return (
    <BillingPeriodContext.Provider value={ctx}>{children}</BillingPeriodContext.Provider>
  );
}

/**
 * Read/write the shared billing period. Components rendered without a
 * provider (standalone tests, one-off embeds) get their own local state,
 * still seeded with the sitewide annual default.
 */
export function useBillingPeriod(): BillingPeriodCtx {
  const ctx = useContext(BillingPeriodContext);
  const [local, setLocal] = useState<BillingPeriod>(DEFAULT_BILLING_PERIOD);
  return ctx ?? { billing: local, setBilling: setLocal };
}

/**
 * The pill toggle — a pure controlled UI component; pass it the pair from
 * useBillingPeriod() at the call site (so a standalone render without a
 * provider still shares ONE local state with its host component). Annual
 * (the default) is listed first; monthly is one click away. The −17% chip on
 * the Annual pill is the factual annual-vs-monthly saving (e.g. $99/yr vs
 * $9.99×12), shown only while monthly is selected.
 */
export function BillingToggle({
  billing,
  setBilling,
}: {
  billing: BillingPeriod;
  setBilling: (b: BillingPeriod) => void;
}) {
  return (
    <div className="inline-flex rounded-full border border-border bg-panel p-1">
      {(["annual", "monthly"] as const).map((b) => (
        <button
          key={b}
          onClick={() => setBilling(b)}
          aria-pressed={billing === b}
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
  );
}
