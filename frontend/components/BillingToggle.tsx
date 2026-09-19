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
  useRef,
  useState,
  type ReactNode,
} from "react";
import { DEFAULT_BILLING_PERIOD, PRICING, type BillingPeriod } from "@/lib/pricing";

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
 * The yearly saving as a whole percent, floored so it is never overstated,
 * and taken as the SMALLEST across the paid plans so the one chip is true of
 * every card it sits above: Pro $99 vs $9.99×12 = 17.4%, Premium $199 vs
 * $19.99×12 = 17.0% → "Save 17%".
 */
export const YEARLY_SAVING_PCT = Math.floor(
  Math.min(
    ...[PRICING.pro, PRICING.premium].map((p) => (1 - p.annual / (p.monthly * 12)) * 100),
  ),
);

/**
 * The billing switch — two equal segments and one sliding thumb, the
 * Monthly | Yearly pattern people know from LinkedIn and most subscription
 * pages. A pure controlled component: pass it the pair from
 * useBillingPeriod() at the call site (so a standalone render without a
 * provider still shares ONE local state with its host component).
 *
 * Built this way because the founder asked for switching to be "a lot more
 * smoother" (2026-09-19). The old pill swapped its background instantly and a
 * "−17%" chip popped in and out above it. Now both segments are always the
 * same width (a 2-column grid), a single thumb slides between them, and the
 * saving chip is always on Yearly, so nothing appears, disappears or resizes
 * when you switch. Yearly stays the default (founder decision 2026-07-18).
 */
export function BillingToggle({
  billing,
  setBilling,
}: {
  billing: BillingPeriod;
  setBilling: (b: BillingPeriod) => void;
}) {
  return (
    <div
      role="group"
      aria-label="Billing period"
      className="relative inline-grid grid-cols-2 rounded-full border border-border bg-panel p-1 shadow-sm"
    >
      <span
        aria-hidden="true"
        data-testid="billing-toggle-thumb"
        className="absolute inset-y-1 left-1 w-[calc(50%-0.25rem)] rounded-full bg-fg shadow transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none"
        style={{ transform: billing === "annual" ? "translateX(100%)" : "translateX(0)" }}
      />
      {(["monthly", "annual"] as const).map((b) => (
        <button
          key={b}
          type="button"
          onClick={() => setBilling(b)}
          aria-pressed={billing === b}
          className={`relative z-10 inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full px-5 py-2 text-sm font-medium transition-colors duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 ${
            billing === b ? "text-background" : "text-muted hover:text-fg"
          }`}
        >
          {b === "annual" ? "Yearly" : "Monthly"}
          {b === "annual" && (
            <span className="rounded-full bg-up px-1.5 py-0.5 text-[10px] font-bold leading-none text-background">
              Save {YEARLY_SAVING_PCT}%
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

/**
 * True once the billing period has changed at least once since mount. Prices
 * use it to ease in only on a real switch, never on first paint, where a
 * fade-in would just delay the numbers.
 */
export function useBillingChanged(billing: BillingPeriod): boolean {
  const first = useRef(billing);
  const changed = useRef(false);
  if (billing !== first.current) changed.current = true;
  return changed.current;
}
