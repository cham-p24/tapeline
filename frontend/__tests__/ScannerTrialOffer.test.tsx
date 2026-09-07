/**
 * The Premium trial offer, on the scanner (components/ScannerTrialOffer.tsx).
 *
 * WHAT THIS FILE IS ACTUALLY GUARDING
 * -----------------------------------
 * A new account used to land on `/app/billing?trial=start` — a payment decision
 * standing between signup and the first scored row. That default is now
 * `/app/scanner`, and the offer travels with the user instead of standing in
 * front of them.
 *
 * The risk in a change like that is not that the offer breaks; it is that the
 * offer quietly SOFTENS on the way. So the first assertion here is that the
 * scanner panel carries the exact same four disclosure facts /app/billing has
 * always carried — $0 today, the exact first-charge date, the amount, and the
 * one-click exit — because both surfaces render one component. If someone ever
 * writes a second, friendlier trial pitch for the scanner, this fails.
 *
 * The rest pins the properties that make it a banner rather than a wall: it
 * yields to the first-run welcome through the SHARED FirstRunTip context (not a
 * second coordination system), it is dismissible and stays dismissed, it never
 * navigates on its own, and it is not shown to an account that cannot accept it.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { useEffect } from "react";
import { PRICING, usdCompact, usd } from "@/lib/pricing";
// Read the length from the single source of truth — never a literal. This repo
// has shipped a trial test that hardcoded 14 and passed for weeks against a
// page that also hardcoded 14 while the backend charged at day 30.
import { TRIAL_DAYS } from "@/lib/trial";
import { FirstRunTipProvider, useFirstRunTip } from "@/components/FirstRunTip";
// Imported STATICALLY, and vi.resetModules() is deliberately not used in this
// file. Loading the component through a dynamic import after a module reset
// gives it a second copy of FirstRunTip.tsx — and therefore a second React
// context object — so the provider rendered here would not be the provider it
// reads. The yield test then passes the panel a permanently-false tipVisible
// and asserts nothing. (Observed: it failed with the panel on screen.)
import { ScannerTrialOffer } from "@/components/ScannerTrialOffer";

const trackEventMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/gtag", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/gtag")>();
  return { ...actual, trackEvent: trackEventMock };
});

const session = vi.hoisted(() => ({
  user: {} as Record<string, unknown> | null,
  loading: false,
  refresh: vi.fn(),
  mustAddCard: true as boolean,
}));
vi.mock("@/components/UserContext", () => ({ useUser: () => session }));

/** Records every POST body sent to the checkout endpoint. */
let checkoutBodies: Array<Record<string, unknown>>;

function stubFetch() {
  checkoutBodies = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/billing/checkout")) {
        checkoutBodies.push(JSON.parse(String(init?.body ?? "{}")));
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ url: "https://checkout.stripe.com/c/x" }),
        });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) });
    }),
  );
}

/** A brand-new account: free tier, never trialled, no card. */
function freshFreeUser() {
  session.user = {
    id: "u_new",
    email: "new@example.com",
    name: null,
    tier: "free",
    trial_ends_at: null,
    created_at: new Date().toISOString(),
  };
  session.loading = false;
  session.mustAddCard = true;
}

/** Raises tipVisible, i.e. the first-run OnboardingTip is on screen. */
function WelcomeIsUp() {
  const { setTipVisible } = useFirstRunTip();
  useEffect(() => setTipVisible(true), [setTipVisible]);
  return null;
}

function renderOffer({ welcomeUp = false }: { welcomeUp?: boolean } = {}) {
  return render(
    <FirstRunTipProvider>
      {welcomeUp && <WelcomeIsUp />}
      <ScannerTrialOffer />
    </FirstRunTipProvider>,
  );
}

/** Asserts the first-charge date is present as real text, in ANY locale. */
const expectFirstChargeDate = (text: string) => {
  const d = new Date(Date.now() + TRIAL_DAYS * 86_400_000);
  expect(text).toMatch(/first charge/i);
  expect(text).toContain(d.toLocaleDateString("en-US", { month: "long" }));
  expect(text).toContain(String(d.getDate()));
  expect(text).toContain(String(d.getFullYear()));
};

beforeEach(() => {

  trackEventMock.mockClear();
  window.localStorage.clear();
  window.sessionStorage.clear();
  freshFreeUser();
  stubFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("scanner trial offer — the disclosure moved, it did not soften", () => {
  it("carries the same four facts /app/billing carries, as real text", async () => {
    renderOffer();
    const disclosure = await screen.findByTestId("trial-disclosure");
    const text = (disclosure.textContent ?? "").replace(/\s+/g, " ");

    expect(text).toMatch(/\$0 today/i);
    expectFirstChargeDate(text);
    // Annual is the site-wide default period.
    expect(text).toMatch(
      new RegExp(`${usdCompact(PRICING.premium.annual).replace("$", "\\$")} for the year`, "i"),
    );
    expect(text).toMatch(/cancel in one click/i);
    expect(text).toMatch(/never charged/i);
    // Real text, not an image, a tooltip or a collapsed <details>.
    expect(disclosure.querySelectorAll("img")).toHaveLength(0);
    expect(disclosure.querySelector("[title]")).toBeNull();
    expect(disclosure.closest("details")).toBeNull();
  });

  it("rewrites the amount when the reader picks monthly", async () => {
    renderOffer();
    const panel = await screen.findByTestId("trial-offer");
    fireEvent.click(within(panel).getByRole("button", { name: /monthly/i }));
    await waitFor(() =>
      expect(screen.getByTestId("trial-disclosure").textContent).toMatch(
        new RegExp(`${usd(PRICING.premium.monthly).replace("$", "\\$")} for the month`, "i"),
      ),
    );
  });

  it("says a card is what starts it, and that the card is entered on Stripe", async () => {
    renderOffer();
    const panel = await screen.findByTestId("trial-offer");
    const text = (panel.textContent ?? "").replace(/\s+/g, " ");
    expect(text).toMatch(/takes a card/i);
    expect(text).toMatch(/never reaches a Tapeline server/i);
  });

  it("carries no urgency, scarcity or countdown language", async () => {
    renderOffer();
    const panel = await screen.findByTestId("trial-offer");
    const text = (panel.textContent ?? "").replace(/\s+/g, " ");
    for (const phrase of [
      /hurry/i,
      /last chance/i,
      /act (?:now|fast)/i,
      /only \d+ (?:left|spots?|seats?)/i,
      /limited[- ]time/i,
      /countdown/i,
      /don'?t miss out/i,
      /expires? in \d+ (?:hour|minute|second)/i,
    ]) {
      expect(text).not.toMatch(phrase);
    }
  });
});

describe("scanner trial offer — a banner, not a wall", () => {
  it("does NOT open a checkout on its own — the user has to click", async () => {
    renderOffer();
    await screen.findByTestId("trial-offer");
    await new Promise((r) => setTimeout(r, 30));
    expect(checkoutBodies).toHaveLength(0);
  });

  it("closes on the decline and stays closed on the next visit", async () => {
    const first = renderOffer();
    const panel = await screen.findByTestId("trial-offer");
    // The decline is a real, keyboard-operable control of the same weight as
    // the trial button — and on THIS surface it closes the panel rather than
    // linking to the page the reader is already on.
    const decline = within(panel).getByRole("button", { name: /continue on the free plan/i });
    expect(decline.tagName).toBe("BUTTON");
    fireEvent.click(decline);
    await waitFor(() => expect(screen.queryByTestId("trial-offer")).toBeNull());
    first.unmount();

    renderOffer();
    await new Promise((r) => setTimeout(r, 30));
    expect(screen.queryByTestId("trial-offer")).toBeNull();
  });

  it("yields to the first-run welcome through the SHARED FirstRunTip context", async () => {
    // The welcome and a card ask must not stack on a brand-new account. This
    // is the same mechanism TrialBanner / UpgradeNudge / BreakingNewsBar use —
    // if someone builds a second banner-coordination system, this goes red.
    renderOffer({ welcomeUp: true });
    await new Promise((r) => setTimeout(r, 30));
    expect(screen.queryByTestId("trial-offer")).toBeNull();
  });
});

describe("scanner trial offer — eligibility", () => {
  it("is not shown to an account that already had a trial", async () => {
    session.user = {
      ...(session.user as Record<string, unknown>),
      trial_ends_at: new Date(Date.now() - 5 * 86_400_000).toISOString(),
    };
    renderOffer();
    await new Promise((r) => setTimeout(r, 30));
    expect(screen.queryByTestId("trial-offer")).toBeNull();
  });

  it("is not shown to a paying subscriber", async () => {
    session.user = { ...(session.user as Record<string, unknown>), tier: "premium" };
    renderOffer();
    await new Promise((r) => setTimeout(r, 30));
    expect(screen.queryByTestId("trial-offer")).toBeNull();
  });

  it("is not shown to a signed-out visitor", async () => {
    session.user = null;
    renderOffer();
    await new Promise((r) => setTimeout(r, 30));
    expect(screen.queryByTestId("trial-offer")).toBeNull();
  });
});

describe("scanner trial offer — the mechanism", () => {
  it("POSTs start_trial to the existing checkout endpoint, on click only", async () => {
    renderOffer();
    const panel = await screen.findByTestId("trial-offer");
    fireEvent.click(
      within(panel).getByRole("button", { name: new RegExp(`start the ${TRIAL_DAYS}-day trial`, "i") }),
    );
    await waitFor(() => expect(checkoutBodies).toHaveLength(1));
    expect(checkoutBodies[0]).toMatchObject({
      tier: "premium",
      billing_period: "annual",
      start_trial: true,
    });
  });

  it("records that this checkout is a TRIAL, so the return can't be booked as revenue", async () => {
    // The return from Stripe always lands on /app/billing, which reads this
    // record. Without it, a trial started HERE would look like a purchase the
    // moment `trial=1` were ever dropped from the success_url — booking $199
    // of revenue for a checkout where $0 moved.
    renderOffer();
    const panel = await screen.findByTestId("trial-offer");
    fireEvent.click(
      within(panel).getByRole("button", { name: new RegExp(`start the ${TRIAL_DAYS}-day trial`, "i") }),
    );
    await waitFor(() =>
      expect(window.sessionStorage.getItem("tapeline_trial_checkout_intent")).toContain("premium"),
    );
  });
});

/**
 * Everything above renders the component in isolation, which proves the panel
 * behaves — and proves nothing about whether anybody can SEE it. Two wiring
 * facts carry the whole change and both are invisible to a component test, so
 * they are asserted against the source with comments stripped first. (Comments
 * in this repo describe exactly these mechanisms; a naive substring match would
 * pass against the explanation of the thing rather than the thing.)
 */
describe("scanner trial offer — the wiring that makes it visible", () => {
  /** Strip // line comments and block comments before matching. */
  const stripComments = (src: string) =>
    src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");

  it("is rendered on the scanner page, ABOVE the results table", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const src = stripComments(
      fs.readFileSync(
        path.join(process.cwd(), "app", "app", "scanner", "page.tsx"),
        "utf8",
      ),
    );
    const offer = src.indexOf("<ScannerTrialOffer");
    const table = src.indexOf("<table");
    expect(offer).toBeGreaterThan(-1);
    expect(table).toBeGreaterThan(-1);
    expect(offer).toBeLessThan(table);
  });

  it("has the app shell render page content INSIDE FirstRunTipProvider", async () => {
    // The yield test above only means something if the provider is actually an
    // ancestor of the page in production. It was not: the provider used to wrap
    // the four banners and stop, with {children} outside it — so the panel would
    // have read the context's no-op default (tipVisible permanently false) and
    // stacked a card ask on top of a brand-new user's welcome.
    const fs = await import("node:fs");
    const path = await import("node:path");
    const src = stripComments(
      fs.readFileSync(path.join(process.cwd(), "app", "app", "layout.tsx"), "utf8"),
    );
    const open = src.indexOf("<FirstRunTipProvider>");
    const close = src.indexOf("</FirstRunTipProvider>");
    expect(open).toBeGreaterThan(-1);
    expect(close).toBeGreaterThan(open);
    // The provider's own subtree — not the whole file, which renders
    // {children} in several other shells (the gate shell, the marketing frame).
    const inner = src.slice(open, close);
    expect(inner).toContain("{children}");
    // …and the one component that WRITES tipVisible is in there with it.
    expect(inner).toContain("<OnboardingTip");
  });
});
