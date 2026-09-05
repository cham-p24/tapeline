/**
 * The card gate — the wall a brand-new account meets at /app/start, and the
 * /app layout that routes people to it (or, far more often, doesn't).
 *
 * Four properties matter more than everything else on this surface, and each
 * one is a test below:
 *
 *   1. GRANDFATHERED ACCOUNTS NEVER SEE IT. Anyone who signed up before the
 *      cutover signed up under "free, no card". The server withholds
 *      `must_add_card` for them, and this layout must render the ordinary app
 *      — no wall, no redirect, nothing different at all. Same for admins,
 *      lifetime accounts, and anyone with a card on file.
 *   2. NOTHING FLASHES. While the session verdict is unknown the layout shows
 *      a neutral frame: not the wall (which would paywall a paying customer
 *      for a beat) and not the product (which would flash the app at a gated
 *      account and fire its authed fetches).
 *   3. THE TERMS ARE THERE, AS TEXT, BEFORE THE CARD. $0 today, the exact
 *      first-charge date, the amount, one-click cancellation, and the
 *      three-days-ahead email.
 *   4. THERE IS A REAL WAY OUT. The free public record, today's picks, and a
 *      sign-out — none of them punished, none of them hidden.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { PRICING, usd, usdCompact } from "@/lib/pricing";

// Imported, never restated. A local copy of the trial length keeps asserting
// the OLD promise after the real one moves: this file said 14 while the page
// it tests said 30, and the date assertion below passed against a first-charge
// date no customer would ever be shown.
import { TRIAL_DAYS } from "@/lib/trial";

const trackEventMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/gtag", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/gtag")>();
  return { ...actual, trackEvent: trackEventMock };
});

// Mutable session + route, shared by the layout and the page under test.
const session = vi.hoisted(() => ({
  user: null as Record<string, unknown> | null,
  loading: false,
  mustAddCard: false,
  refresh: vi.fn(async () => {}),
  signout: vi.fn(async () => {}),
}));
vi.mock("@/components/UserContext", () => ({
  useUser: () => session,
}));

const nav = vi.hoisted(() => ({ pathname: "/app/start" }));
const routerSpies = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
  back: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => routerSpies,
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => nav.pathname,
}));

// The layout mounts a lot of self-gating chrome that has nothing to do with
// the gate. Stub the network-touching pieces so these tests exercise routing
// and copy, not banners.
vi.mock("@/components/GlobalSearch", () => ({ GlobalSearch: () => null }));
// No TRIAL_DAYS here. The page now reads it from lib/trial directly, so a
// mock cannot quietly pin these assertions to a trial length the product
// no longer offers.
vi.mock("@/components/TrialBanner", () => ({
  TrialBanner: () => null,
}));
vi.mock("@/components/TrialEndedModal", () => ({ TrialEndedModal: () => null }));
vi.mock("@/components/TrialEarlyCapture", () => ({ TrialEarlyCapture: () => null }));
vi.mock("@/components/StaleDataBanner", () => ({ StaleDataBanner: () => null }));
vi.mock("@/components/DunningBanner", () => ({ DunningBanner: () => null }));
vi.mock("@/components/UpgradeNudge", () => ({ UpgradeNudge: () => null }));
vi.mock("@/components/OnboardingTip", () => ({ OnboardingTip: () => null }));
vi.mock("@/components/BreakingNewsBar", () => ({ BreakingNewsBar: () => null }));
vi.mock("@/components/EmailVerificationBanner", () => ({
  EmailVerificationBanner: () => null,
}));

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

/** A brand-new, post-cutover account with no card: the only kind that is gated. */
function gatedUser() {
  session.user = {
    id: "u_new",
    email: "new@example.com",
    name: null,
    tier: "free",
    created_at: new Date().toISOString(),
    must_add_card: true,
  };
  session.loading = false;
  session.mustAddCard = true;
}

/** An account created before the cutover. The server never gates it. */
function grandfatheredUser() {
  session.user = {
    id: "u_old",
    email: "old@example.com",
    name: null,
    tier: "free",
    created_at: "2026-03-01T00:00:00Z",
    // The server withholds the flag entirely for these accounts.
  };
  session.loading = false;
  session.mustAddCard = false;
}

async function renderLayout(pathname: string, children: React.ReactNode) {
  nav.pathname = pathname;
  const { default: AppLayout } = await import("@/app/app/layout");
  return render(<AppLayout>{children}</AppLayout>);
}

async function renderWall() {
  nav.pathname = "/app/start";
  const { default: CardGateStartPage } = await import("@/app/app/start/page");
  return render(<CardGateStartPage />);
}

beforeEach(() => {
  vi.resetModules();
  trackEventMock.mockClear();
  routerSpies.replace.mockClear();
  routerSpies.push.mockClear();
  session.refresh.mockClear();
  session.signout.mockClear();
  window.sessionStorage.clear();
  gatedUser();
  stubFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/* ─────────────────────────────────────────────────────────────────────────
 * 1. Grandfathering — the constraint that protects real people.
 * ───────────────────────────────────────────────────────────────────────── */
describe("card gate — a grandfathered account is untouched", () => {
  it("renders the ordinary app, with its nav, and redirects nowhere", async () => {
    grandfatheredUser();
    await renderLayout("/app/scanner", <div>scanner content</div>);

    expect(screen.getByText("scanner content")).toBeInTheDocument();
    // The real shell, not the bare gate shell.
    expect(screen.queryByTestId("card-gate-shell")).toBeNull();
    expect(screen.queryByTestId("app-frame")).toBeNull();
    expect(screen.getAllByRole("link", { name: /scanner/i }).length).toBeGreaterThan(0);
    expect(routerSpies.replace).not.toHaveBeenCalled();
  });

  it("never shows the wall's terms to them", async () => {
    grandfatheredUser();
    await renderLayout("/app/scanner", <div>scanner content</div>);
    expect(screen.queryByTestId("card-gate-terms")).toBeNull();
    expect(document.body.textContent).not.toMatch(/add a card to open tapeline/i);
  });

  it("bounces them straight back out if they land on the wall's URL", async () => {
    grandfatheredUser();
    const { container } = await renderWall();
    await waitFor(() => expect(routerSpies.replace).toHaveBeenCalledWith("/app/scanner"));
    // …and shows them nothing at all on the way.
    expect(container.textContent).toBe("");
  });
});

/* ─────────────────────────────────────────────────────────────────────────
 * 2. Nothing flashes.
 * ───────────────────────────────────────────────────────────────────────── */
describe("card gate — the loading state", () => {
  it("shows a neutral frame, not the wall, while the session is unknown", async () => {
    session.loading = true;
    // Worst case: the flag is already true but we have not finished loading.
    session.mustAddCard = true;
    await renderLayout("/app/scanner", <div>scanner content</div>);

    expect(screen.getByTestId("app-frame")).toBeInTheDocument();
    expect(screen.queryByTestId("card-gate-terms")).toBeNull();
    expect(document.body.textContent).not.toMatch(/add a card/i);
    // …and no product either, so a gated account's page never fires its fetches.
    expect(screen.queryByText("scanner content")).toBeNull();
    expect(routerSpies.replace).not.toHaveBeenCalled();
  });

  it("renders nothing from the wall page itself while loading", async () => {
    session.loading = true;
    session.mustAddCard = true;
    const { container } = await renderWall();
    expect(container.textContent).toBe("");
    expect(routerSpies.replace).not.toHaveBeenCalled();
  });

  it("shows the product once the session resolves, with no redirect", async () => {
    // Was "does not flash the product at a gated account mid-redirect". There
    // is no mid-redirect any more — nothing to flash past. The property that
    // still matters is the other half of the original: while the session
    // verdict is unknown the layout renders a neutral frame rather than
    // guessing, and once it resolves the account gets the product.
    await renderLayout("/app/scanner", <div>scanner content</div>);
    await waitFor(() =>
      expect(screen.getByText("scanner content")).toBeInTheDocument(),
    );
    expect(routerSpies.replace).not.toHaveBeenCalled();
  });
});

/* ─────────────────────────────────────────────────────────────────────────
 * 3. The routing itself.
 * ───────────────────────────────────────────────────────────────────────── */
describe("no route wall — an account without a card reaches the product", () => {
  // REPLACED 2026-08-30. These cases used to assert the opposite: that an
  // account without a card was redirected from every /app route to
  // /app/start. That wall was removed.
  //
  // Why, in one line: it was never a wall. `must_add_card` appears only in
  // session payloads and copy — no backend route reads it — so any caller
  // hitting the API directly, or the public MCP server, always had the whole
  // product without a card. It stopped ordinary visitors and nobody else.
  //
  // What it cost: of the three accounts created under it, none added a card,
  // none ran a single scan, and two never opened the payment page at all.
  // Someone who bounces off a wall is gone and you asked once. Someone inside
  // the product can be asked every visit, at the moment they reach for
  // something a card turns on.
  //
  // The card did not become optional. It moved. The limits that sell it live
  // in backend services/tier.py and are enforced server-side, which is the
  // part that was always real.
  it.each(["/app/scanner", "/app/watchlist", "/app/alerts", "/app/account"])(
    "renders %s for an account with no card, and does not redirect",
    async (path) => {
      await renderLayout(path, <div>product</div>);
      await waitFor(() => expect(screen.getByText("product")).toBeInTheDocument());
      expect(routerSpies.replace).not.toHaveBeenCalled();
    },
  );

  it("still renders /app/billing — Stripe returns there after checkout", async () => {
    await renderLayout("/app/billing", <div>billing</div>);
    await waitFor(() => expect(screen.getByText("billing")).toBeInTheDocument());
    expect(routerSpies.replace).not.toHaveBeenCalled();
  });

  it("gives an uncarded account the real app frame, not a bare shell", async () => {
    // The bare GateShell existed to deny a walled account any navigation into
    // pages it could not open. There are no such pages now — every /app route
    // renders, with the free-tier limits applied inside it — so withholding
    // the nav would only hide the product from someone we want using it.
    await renderLayout("/app/scanner", <div>product</div>);
    await waitFor(() => expect(screen.getByText("product")).toBeInTheDocument());
    expect(screen.queryByTestId("card-gate-shell")).toBeNull();
  });

  it("still renders /app/start when the user goes there deliberately", async () => {
    // The page is no longer a wall, but it is still where the trial is
    // started, and the post-signup hand-off and upgrade prompts point at it.
    await renderLayout("/app/start", <div>the trial offer</div>);
    expect(screen.getByText("the trial offer")).toBeInTheDocument();
    expect(routerSpies.replace).not.toHaveBeenCalled();
  });

  it("lets the one-time provisioning hop through", async () => {
    await renderLayout("/app/onboarding", <div>provisioning</div>);
    expect(screen.getByText("provisioning")).toBeInTheDocument();
    expect(routerSpies.replace).not.toHaveBeenCalled();
  });
});

/* ─────────────────────────────────────────────────────────────────────────
 * 4. The disclosure.
 * ───────────────────────────────────────────────────────────────────────── */
describe("card gate — the terms, as real text, before the card", () => {
  it("states $0 today, the exact first-charge date, the amount, one-click cancel and the reminder email", async () => {
    await renderWall();
    const terms = await screen.findByTestId("card-gate-terms");
    const text = (terms.textContent ?? "").replace(/\s+/g, " ");
    const due = new Date(Date.now() + TRIAL_DAYS * 86_400_000);

    expect(text).toMatch(/\$0 today/i);
    // Locale-agnostic: CI and dev machines format billing dates differently and
    // both are correct, so assert the PARTS rather than one rendering.
    expect(text).toMatch(/first charge/i);
    expect(text).toContain(due.toLocaleDateString("en-US", { month: "long" }));
    expect(text).toContain(String(due.getDate()));
    expect(text).toContain(String(due.getFullYear()));
    // MONTHLY, and only monthly. The trial no longer offers an annual
    // conversion: a 30-day free run ending in a $199 charge is the most
    // disputable shape a subscription can have.
    expect(text).toMatch(
      new RegExp(`\\$${PRICING.premium.monthly} for the month`, "i"),
    );
    expect(text).toMatch(/every month until you cancel/i);
    expect(text).toMatch(/cancel in one click/i);
    expect(text).toMatch(/never charged/i);
    expect(text).toMatch(/three days before/i);
  });

  it("carries the terms as readable content — not an image, tooltip or disclosure widget", async () => {
    await renderWall();
    const terms = await screen.findByTestId("card-gate-terms");
    expect(terms.querySelectorAll("img")).toHaveLength(0);
    expect(terms.querySelector("[title]")).toBeNull();
    expect(terms.closest("details")).toBeNull();
    expect((terms.textContent ?? "").length).toBeGreaterThan(200);
  });

  it("offers no annual option — the trial converts to monthly, full stop", async () => {
    await renderWall();
    // The period toggle is gone on purpose. Its absence IS the assertion:
    // re-adding an annual choice puts a $199 charge 30 days after a free
    // signup, which is the shape that produces disputes.
    expect(screen.queryByRole("button", { name: /annual/i })).toBeNull();
    const t = (await screen.findByTestId("card-gate-terms")).textContent ?? "";
    expect(t).not.toMatch(/for the year/i);
    expect(t).not.toMatch(/every year/i);
  });

  it("explains WHY a card is needed, right next to the ask", async () => {
    // The one uncontested finding in the free-trial literature: Conversion
    // Rate Experts found Crazy Egg's signups were blocked by people thinking
    // the card request "was unnecessary at least, and quite possibly a scam".
    // Explaining it in place — rather than dropping the requirement — took
    // the challenger page to 116% more signups.
    await renderWall();
    const t = (await screen.findByTestId("card-gate-terms")).textContent ?? "";
    expect(t).toMatch(/why a card/i);
    expect(t).toMatch(/one trial per person|endless supply/i);
  });

  it("puts the terms above the button that asks for the card", async () => {
    await renderWall();
    const terms = await screen.findByTestId("card-gate-terms");
    const cta = screen.getByTestId("card-gate-cta");
    // DOCUMENT_POSITION_FOLLOWING: the CTA comes after the terms in the DOM,
    // which is also the order a screen reader walks them.
    expect(terms.compareDocumentPosition(cta) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

/* ─────────────────────────────────────────────────────────────────────────
 * 5. The way out.
 * ───────────────────────────────────────────────────────────────────────── */
describe("card gate — a real, unpunished way out", () => {
  it("links the free public record and today's picks, neither needing an account", async () => {
    await renderWall();
    const exits = await screen.findByTestId("card-gate-exits");
    expect(within(exits).getByRole("link", { name: /public record/i })).toHaveAttribute(
      "href",
      "/scorecard",
    );
    expect(within(exits).getByRole("link", { name: /today.s picks/i })).toHaveAttribute(
      "href",
      "/daily-picks",
    );
    expect((exits.textContent ?? "").replace(/\s+/g, " ")).toMatch(
      /free, with no account and no card/i,
    );
  });

  it("offers a sign-out that actually signs out", async () => {
    await renderWall();
    const exits = await screen.findByTestId("card-gate-exits");
    fireEvent.click(within(exits).getByRole("button", { name: /sign out/i }));
    await waitFor(() => expect(session.signout).toHaveBeenCalled());
  });

  it("does not dim, shrink or hide the exits", async () => {
    await renderWall();
    const exits = await screen.findByTestId("card-gate-exits");
    for (const el of Array.from(exits.querySelectorAll("a, button"))) {
      expect(el.className).not.toMatch(/opacity-\d|hidden|sr-only|text-\[10px\]/);
    }
  });
});

/* ─────────────────────────────────────────────────────────────────────────
 * 6. No dark patterns, and one checkout path.
 * ───────────────────────────────────────────────────────────────────────── */
describe("card gate — no dark patterns", () => {
  it("never opens Stripe on its own — the user has to click", async () => {
    await renderWall();
    await screen.findByTestId("card-gate-cta");
    await new Promise((r) => setTimeout(r, 30));
    expect(checkoutBodies).toHaveLength(0);
    expect(trackEventMock.mock.calls.some((c) => c[0] === "begin_checkout")).toBe(false);
  });

  it("pre-ticks nothing", async () => {
    const { container } = await renderWall();
    expect(container.querySelectorAll("input[type=checkbox]")).toHaveLength(0);
    expect(container.querySelectorAll("input[type=radio]")).toHaveLength(0);
  });

  it("carries no urgency, scarcity or countdown language", async () => {
    const { container } = await renderWall();
    const text = (container.textContent ?? "").replace(/\s+/g, " ");
    for (const phrase of [
      /hurry/i,
      /last chance/i,
      /act (?:now|fast)/i,
      /only \d+ (?:left|spots?|seats?)/i,
      /spots? remaining/i,
      /limited[- ]time/i,
      /countdown/i,
      /don'?t miss out/i,
      /expires? in \d+ (?:hour|minute|second)/i,
      /price (?:goes up|increases)/i,
    ]) {
      expect(text).not.toMatch(phrase);
    }
  });

  it("uses real, keyboard-operable controls with a visible focus ring", async () => {
    const { container } = await renderWall();
    expect(container.querySelectorAll("div[role='button']")).toHaveLength(0);
    const cta = screen.getByTestId("card-gate-cta");
    expect(cta.tagName).toBe("BUTTON");
    expect(cta.className).toMatch(/focus-visible:ring-2/);
    for (const link of Array.from(
      screen.getByTestId("card-gate-exits").querySelectorAll("a, button"),
    )) {
      expect(link.className).toMatch(/focus-visible:ring-2/);
    }
  });
});

describe("card gate — the mechanism", () => {
  it("POSTs start_trial to the existing checkout endpoint, and only on click", async () => {
    await renderWall();
    fireEvent.click(screen.getByTestId("card-gate-cta"));

    await waitFor(() => expect(checkoutBodies).toHaveLength(1));
    expect(checkoutBodies[0]).toMatchObject({
      tier: "premium",
      // Monthly, not annual: the trial converts to $19.99/mo by design.
      billing_period: "monthly",
      start_trial: true,
    });
    // The return from a $0 checkout must never be booked as revenue, so the
    // page leaves the same trial-intent record the billing page reads back.
    await waitFor(() =>
      expect(window.sessionStorage.getItem("tapeline_trial_checkout_intent")).toContain(
        "premium",
      ),
    );
  });

  it("reports the checkout intent as a trial start from the gate surface", async () => {
    await renderWall();
    fireEvent.click(screen.getByTestId("card-gate-cta"));
    await waitFor(() => {
      const call = trackEventMock.mock.calls.find((c) => c[0] === "begin_checkout");
      expect(call).toBeDefined();
      expect(call![1]).toMatchObject({
        tier: "premium",
        start_trial: true,
        surface: "card_gate",
      });
    });
  });

  it("says nothing was charged when the checkout can't be opened", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 503,
          json: () => Promise.resolve({}),
        }),
      ),
    );
    await renderWall();
    fireEvent.click(screen.getByTestId("card-gate-cta"));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/nothing was charged/i);
  });
});

/* ─────────────────────────────────────────────────────────────────────────
 * 7. Coming back from Stripe ahead of the webhook.
 * ───────────────────────────────────────────────────────────────────────── */
describe("card gate — the return from Stripe", () => {
  it("says a confirmation may still be landing, without claiming the card went through", async () => {
    window.sessionStorage.setItem("tapeline_card_gate_handoff", String(Date.now()));
    await renderWall();
    const note = await screen.findByTestId("card-gate-confirming");
    const text = (note.textContent ?? "").replace(/\s+/g, " ");
    expect(text).toMatch(/nothing was charged today/i);
    // It must not assert something we cannot know — the user may have backed
    // out of the Stripe page.
    expect(text).not.toMatch(/you (?:have )?added a card|your card was accepted/i);
    // …and the wall stays usable underneath, so a backed-out user isn't stuck.
    expect(screen.getByTestId("card-gate-cta")).toBeEnabled();
  });

  it("re-checks the session in the background while that window is open", async () => {
    vi.useFakeTimers();
    try {
      window.sessionStorage.setItem("tapeline_card_gate_handoff", String(Date.now()));
      nav.pathname = "/app/start";
      const { default: CardGateStartPage } = await import("@/app/app/start/page");
      render(<CardGateStartPage />);
      expect(session.refresh).not.toHaveBeenCalled();
      vi.advanceTimersByTime(3_100);
      expect(session.refresh).toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("shows no such note on a plain first visit", async () => {
    await renderWall();
    await screen.findByTestId("card-gate-cta");
    expect(screen.queryByTestId("card-gate-confirming")).toBeNull();
  });

  it("ignores a stale hand-off record", async () => {
    window.sessionStorage.setItem(
      "tapeline_card_gate_handoff",
      String(Date.now() - 10 * 60_000),
    );
    await renderWall();
    await screen.findByTestId("card-gate-cta");
    expect(screen.queryByTestId("card-gate-confirming")).toBeNull();
  });
});
