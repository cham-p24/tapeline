/**
 * Two things /app/billing offered that it could not deliver.
 *
 * 1. "SWITCH TO PRO" / "SWITCH TO PREMIUM" called startCheckout(). Checkout
 *    always mints a NEW Stripe customer and subscription, so the backend
 *    refuses it: routers/billing.py's double-billing guard 409s on exactly
 *    this shape and says "Manage or switch your plan from the billing portal".
 *    That guard is why nobody was double-billed — but the button still
 *    advertised an action it could only fail at, then showed the refusal as
 *    though the user had done something wrong.
 *
 * 2. THE BROWSER-PUSH CARD rendered for free accounts. `alerts.web_push` is
 *    flag-FREE (an activation bet from 2026-07-04) while FREE_WEB_PUSH_ALERTS
 *    went to 0 in #683 — and Paywall gates on the FLAG, not the cap. So a free
 *    user was invited to enable browser notifications for a channel they could
 *    not attach a single rule to.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { FREE_LIMITS } from "@/lib/pricing";

// Hoisted + mutable, the pattern the other suites here use. vi.doMock inside a
// test body races the module graph — the first draft of the Paywall test did
// that and rendered children regardless of `exhausted`, which looked like the
// component ignoring the prop.
const session = vi.hoisted(() => ({
  user: null as Record<string, unknown> | null,
  loading: false,
}));
vi.mock("@/components/UserContext", () => ({ useUser: () => session }));

import { Paywall } from "@/components/Paywall";

const BILLING = join(__dirname, "..", "app", "app", "billing", "page.tsx");

/** Executable source only — the explanations above and in the page quote the
 *  very identifiers these assertions look for. */
function code(path: string): string {
  return readFileSync(path, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

describe("plan change routes somewhere that can actually change the plan", () => {
  const src = () => code(BILLING);

  it("both plan CTAs go through changePlan, not straight to checkout", () => {
    expect(src()).toMatch(/onUpgrade=\{\(\) => changePlan\("pro"\)\}/);
    expect(src()).toMatch(/onUpgrade=\{\(\) => changePlan\("premium"\)\}/);
    // The old shape, which produced a 409 for every subscriber.
    expect(src()).not.toMatch(/onUpgrade=\{\(\) => startCheckout\("pro"\)\}/);
  });

  it("an existing subscriber is sent to the Stripe portal", () => {
    const fn = src().slice(src().indexOf("function changePlan"));
    const body = fn.slice(0, fn.indexOf("\n  }"));
    expect(body).toMatch(/openPortal\(\)/);
  });

  it("the condition mirrors the backend guard, not merely 'is a paid tier'", () => {
    // routers/billing.py 409s on `stripe_customer_id AND tier in (pro, premium)`.
    // A legacy card-free trial holds a paid tier with NO customer record, passes
    // that guard, and genuinely needs Checkout — sending it to the portal would
    // 400 with "No billing account yet", the same mistake reversed.
    const fn = src().slice(src().indexOf("function changePlan"));
    const body = fn.slice(0, fn.indexOf("\n  }"));
    expect(body).toMatch(/hasBilling === true/);
    expect(body).toMatch(/tier === "pro" \|\| tier === "premium"/);
  });

  it("falls through to checkout while the billing-account fetch is unknown", () => {
    // hasBilling starts null. `=== true` keeps null out of the portal branch,
    // and the server-side 409 still covers anyone who beats the fetch.
    const fn = src().slice(src().indexOf("function changePlan"));
    const body = fn.slice(0, fn.indexOf("\n  }"));
    expect(body).toMatch(/startCheckout\(/);
  });
});

describe("the browser-push card is not offered to accounts with no allowance", () => {
  it("the Paywall is told the free allowance is exhausted", () => {
    expect(code(BILLING)).toMatch(
      /exhausted=\{tier === "free" && FREE_LIMITS\.webPushAlerts === 0\}/,
    );
  });

  it("the section blurb does not promise channels to an account with none", () => {
    const src = code(BILLING);
    expect(src).toMatch(/Alert delivery is a paid feature/);
    // The unconditional promise it replaced.
    expect(src).not.toMatch(/^\s*Email is the default\. Add any channel below/m);
  });

  it("the fixture this depends on is real: free really does get zero", () => {
    // If the allowance is ever restored, these gates open again on their own
    // and this test tells the next reader why it changed.
    expect(FREE_LIMITS.webPushAlerts).toBe(0);
  });
});

describe("Paywall.exhausted", () => {
  // alerts.web_push is Tier.FREE, so a free user PASSES the feature gate.
  // That is the whole point: only `exhausted` can close this one.
  const asFree = () => { session.user = { id: "u", tier: "free" }; session.loading = false; };

  // NOTE ON WHAT "LOCKED" LOOKS LIKE. Paywall does not remove the children —
  // it renders them behind the upgrade card, blurred and pointer-events-none.
  // My first draft asserted the children were absent, which failed against a
  // component that was working correctly. The real contract is: the upgrade
  // prompt appears, and the children become non-interactive decoration.
  const lockedShell = (c: HTMLElement) =>
    c.querySelector(".pointer-events-none.select-none");

  it("locks a feature the tier flag allows but the allowance does not", () => {
    asFree();
    const { container } = render(
      <Paywall feature="alerts.web_push" title="Browser push" exhausted>
        <div data-testid="card">card</div>
      </Paywall>,
    );
    expect(screen.getByRole("heading", { name: /browser push/i })).toBeInTheDocument();
    expect(lockedShell(container)).not.toBeNull();
    // The card is decoration now, not something the user can act on.
    expect(lockedShell(container)!.contains(screen.getByTestId("card"))).toBe(true);
  });

  it("still renders children live when the allowance is intact", () => {
    asFree();
    const { container } = render(
      <Paywall feature="alerts.web_push" title="Browser push" exhausted={false}>
        <div data-testid="card">card</div>
      </Paywall>,
    );
    // Proves `exhausted` closed it above rather than the tier flag: the same
    // free user, the same feature, and no paywall at all.
    expect(lockedShell(container)).toBeNull();
    expect(screen.queryByRole("heading", { name: /browser push/i })).not.toBeInTheDocument();
    expect(screen.getByTestId("card")).toBeInTheDocument();
  });

  it("leaves a genuinely tier-gated feature locked regardless", () => {
    asFree();
    const { container } = render(
      <Paywall feature="alerts.email" title="Email alerts" exhausted={false}>
        <div data-testid="email">email</div>
      </Paywall>,
    );
    expect(lockedShell(container)).not.toBeNull();
  });
});
