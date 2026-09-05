/**
 * Signup page tests:
 *   - the offscreen honeypot field (bot-protection layer depends on it)
 *   - core fields, and the CARD RULE stated honestly. Since 2026-08 this form
 *     creates a FREE account and nothing else: no card, no trial. Since #683
 *     (2026-08-30) that account is also immediately usable — the live scanner's
 *     top ten rows, one saved screen, a five-symbol watchlist — where it
 *     previously met a card wall at first sign-in. The 14-day Premium trial is
 *     a separate opt-in on the next screen and it DOES take a card, so a
 *     card-free claim here must qualify the ACCOUNT, never the trial. The page
 *     must also contain NO card input of any kind.
 *   - source-aware (message-match) headlines driven by ?from=, the funnel
 *     fix that carries an ad/landing-page promise through to the signup H1
 *     instead of showing cold traffic a generic form.
 *   - the two email-consent checkboxes (weekly digest + Daily Top 10):
 *     UNCHECKED by default, and their state is forwarded on the signup POST.
 *   - price/limit prose derived from lib/pricing (no hardcoded drift).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SignUpPage from "@/app/signup/page";
import { PRICING, REFUND, usd, usdCompact } from "@/lib/pricing";

vi.mock("@/lib/auth", () => ({
  authApi: {
    signup: vi.fn().mockResolvedValue({ user: { id: "u1" } }),
    session: vi.fn().mockResolvedValue({ user: null }),
    signin: vi.fn(),
    signout: vi.fn(),
  },
  hasMinTier: vi.fn(() => false),
  canUse: vi.fn(() => false),
  FEATURE_TIERS: {},
}));

// The submit path lazily imports the device fingerprint (crypto.subtle) —
// stub it so jsdom submits resolve deterministically.
vi.mock("@/lib/fingerprint", () => ({
  deviceFingerprint: vi.fn().mockResolvedValue("aabbccddeeff0011"),
}));

// Analytics: only `trackEvent` is intercepted, so the funnel assertions below
// see real calls without the rest of lib/gtag being stubbed out.
const trackEventMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/gtag", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/gtag")>();
  return { ...actual, trackEvent: trackEventMock };
});

// Override the global next/navigation stub so each test can drive the
// ?from=/?plan= search params and assert on router.push. vi.hoisted keeps
// `nav`/`routerSpies` reachable inside the hoisted mock factory; tests
// mutate nav.search before rendering.
const nav = vi.hoisted(() => ({ search: new URLSearchParams() }));
const routerSpies = vi.hoisted(() => ({
  push: vi.fn(),
  refresh: vi.fn(),
  back: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => routerSpies,
  useSearchParams: () => nav.search,
  usePathname: () => "/",
}));

// URL-aware fetch mock. The signup page fetches two endpoints on mount:
//   - /api/auth/oauth/providers  (OAuthButtons feature-detection)
//   - /api/scorecard             (the proof block)
// `oauthProviders` lets a test flip which providers are "enabled" so we can
// assert the Google-first layout with providers present AND the graceful
// email-only fallback when providers come back empty.
let oauthProviders = { google: true, microsoft: false, apple: false };
beforeEach(() => {
  nav.search = new URLSearchParams();
  routerSpies.push.mockClear();
  trackEventMock.mockClear();
  oauthProviders = { google: true, microsoft: false, apple: false };
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/auth/oauth/providers")) {
        return Promise.resolve({ ok: true, json: async () => oauthProviders });
      }
      // scorecard + anything else: benign empty payload (proof block no-ops).
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }),
  );
});

/**
 * Fill the minimum valid form and submit it.
 *
 * The subscription-terms checkbox is REQUIRED (Meta's Subscription Services
 * standard: an unticked opt-in must exist where PII is entered, and submit must
 * not proceed without it). So "minimum valid" now includes ticking it — every
 * submit-path test would otherwise be asserting against a blocked form.
 * `signupTermsGate` below is the test that the gate actually gates.
 */
function fillAndSubmit(container: HTMLElement) {
  fireEvent.change(screen.getByLabelText(/^email$/i), {
    target: { value: "trader@example.com" },
  });
  fireEvent.change(screen.getByLabelText(/password/i), {
    target: { value: "longenough-pass" },
  });
  fireEvent.submit(container.querySelector("form")!);
}

describe("SignUpPage", () => {
  it("renders email + password + name fields", () => {
    render(<SignUpPage />);
    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
  });

  it("includes the offscreen honeypot field (name='company')", () => {
    const { container } = render(<SignUpPage />);
    const honeypot = container.querySelector('input[name="company"]');
    expect(honeypot).not.toBeNull();
    expect(honeypot?.getAttribute("aria-hidden")).toBe("true");
    expect(honeypot?.getAttribute("tabindex")).toBe("-1");
    expect(honeypot?.getAttribute("autocomplete")).toBe("off");
  });

  // ── Google-first layout (the friction-reduction flip) ────────────────────
  // The highest-leverage lever on this page: most visitors are already logged
  // into Google, so a one-click "Continue with Google" above the email form
  // converts far better than a forced email/password account creation.

  it("renders the Continue with Google button ABOVE the email form when providers include google", async () => {
    const { container } = render(<SignUpPage />);
    const google = await screen.findByRole("link", { name: /Continue with Google/i });
    const emailInput = screen.getByLabelText(/^email$/i);
    // DOCUMENT_POSITION_FOLLOWING === 4: emailInput follows the Google button
    // in document order, i.e. Google is above the email form.
    expect(
      google.compareDocumentPosition(emailInput) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // And it carries the intent (?next=) so /pricing context survives Google.
    expect(google.getAttribute("href")).toContain("/api/auth/oauth/google/start");
    expect(container.querySelector("form")).not.toBeNull();
  });

  it("carries plan intent into the Google start link (?next=)", async () => {
    nav.search = new URLSearchParams("plan=premium&billing=annual");
    render(<SignUpPage />);
    const google = await screen.findByRole("link", { name: /Continue with Google/i });
    expect(google.getAttribute("href")).toContain(
      `?next=${encodeURIComponent("/app/billing?intent=premium&billing=annual")}`,
    );
  });

  it("renders the coherent value strip, with the card rule attached to the right thing", () => {
    render(<SignUpPage />);
    // CHANGED THREE TIMES, and the shape of the sentence is the whole point.
    // #536 moved "no credit card" off the trial and onto the account. #548 put
    // a card wall at first sign-in, so the strip had to lead with the card.
    // #683 removed the wall: the account is card-free again, and the card is
    // what buys the trial. The strip must therefore say both things in that
    // order — free plan first, then what a card adds and what it costs.
    const strip = screen.getByText(
      /no card.*Premium trial.*\$0.*Cancel in one click.*money-back/i,
    );
    expect(strip).toBeInTheDocument();
    expect(strip.textContent).toMatch(/free plan/i);
  });

  // ── The card rule, stated before an account exists ────────────────────────

  it("contains NO card input of any kind", () => {
    const { container } = render(<SignUpPage />);
    const inputs = Array.from(container.querySelectorAll("input, select, textarea"));
    const cardish = /card|cc-|cvc|cvv|expiry|exp-|postal|billing/i;
    for (const el of inputs) {
      expect(el.getAttribute("name") ?? "").not.toMatch(cardish);
      expect(el.getAttribute("id") ?? "").not.toMatch(cardish);
      expect(el.getAttribute("autocomplete") ?? "").not.toMatch(cardish);
    }
  });

  it("never promises a card-free TRIAL (the free account is what takes no card)", () => {
    const { container } = render(<SignUpPage />);
    const text = (container.textContent ?? "").replace(/\s+/g, " ");
    // NARROWED by #683. These patterns used to treat "no card" anywhere near
    // "trial" as the tell, which was right while the account took a card too.
    // Now the page says both things a sentence apart — "Sign up with no card;
    // a card starts the 14-day Premium trial" — and the old windows read that
    // honest pairing as a violation. So the windows now stop at a sentence
    // break or a `·` separator: the two facts stated side by side pass, and a
    // card-free claim carried INTO the trial clause does not.
    expect(text).not.toMatch(/\btrial\b[^.;·]{0,30}(?:no|without a) (?:credit )?card/i);
    expect(text).not.toMatch(/(?:no|without a) (?:credit )?card[^.;·]{0,28}\btrial\b/i);
    expect(text).not.toMatch(/card[-\s]free trial/i);
    // Still banned outright: it is the marketing phrase, and it is false of
    // the only thing on this page that takes a card.
    expect(text).not.toMatch(/no credit card required/i);
  });

  it("states the trial's charge terms up front: what a card buys, $0 today, first charge at day 14, one-click exit", () => {
    const { container } = render(<SignUpPage />);
    const text = (container.textContent ?? "").replace(/\s+/g, " ");
    // CHANGED by #683. The page used to open this block with "At first sign-in
    // you add a card" — a wall that no longer exists, and the single sentence
    // most likely to make a reader think the scanner is unreachable without
    // paying. What replaces it has to say the same amount, not less: the form
    // takes no card, and adding one later is what starts the trial.
    expect(text).toMatch(/no card/i);
    expect(text).toMatch(/adding a card[^.]{0,30}starts/i);
    expect(text).not.toMatch(/at first sign-in,? you add a card/i);
    expect(text).not.toMatch(/card (?:added|comes|goes on) at first sign-in/i);
    expect(text).toMatch(/\$0 on the day the card goes on/i);
    // A DATE, not a duration. The paid ad's headline is "$0 today. The charge
    // date is on the page", and Meta reviews the landing page against the ad —
    // "14 days later" left that literal promise unmet. Matched loosely on the
    // month name so the assertion does not break every day as the date rolls.
    expect(text).toMatch(
      /first charge[^.]{0,90}\d{1,2} (January|February|March|April|May|June|July|August|September|October|November|December) \d{4}/i,
    );
    expect(text).not.toMatch(/first charge is 14 days later/i);
    // The date is now stated CONDITIONALLY. Signing up schedules no charge, so
    // an unqualified "your first charge is on <date>" was false for everyone
    // who was not adding a card — which is everyone at this step.
    expect(text).not.toMatch(/your first charge is on/i);
    expect(text).toMatch(/if (you started the trial today|that were today)/i);
    expect(text).toMatch(/one click ends it before then/i);
    // The advance warning is a promise the backend actually keeps (the
    // trial_will_end handler), so the page is allowed to make it.
    expect(text).toMatch(/three days before/i);
  });

  it("keeps the strongest card-free claim: the record needs no account at all", () => {
    const { container } = render(<SignUpPage />);
    const text = (container.textContent ?? "").replace(/\s+/g, " ");
    // Under the card gate this was the ONLY card-free path left, and the test
    // was named for that scarcity. #683 gave the page a second one — signing
    // up takes no card — but this line is still the stronger claim, because it
    // needs no account either, and it is the one a sceptical reader can check
    // before typing anything. If it goes, the page loses its only offer that
    // costs the reader nothing at all.
    expect(text).toMatch(/do not need an account — or a card — to read the record/i);
    // Still banned: the permanence promise. "Free" is a product decision, and
    // the app does ask for a card when a cap is reached.
    expect(text).not.toMatch(/free forever and never needing a card/i);
    // DELIBERATELY NOT ASSERTED ANY MORE:
    //   - "no card to sign up" was banned here as a false claim. #683 made it
    //     the literal truth, and it is now on the page on purpose.
    //   - the grandfather clause ("accounts created before 22 August 2026 keep
    //     the free access they signed up for") was a promise to one cohort
    //     while the wall split the userbase in two. Every account now has that
    //     access, so pinning the sentence would keep a distinction alive in
    //     copy that no longer exists in the product.
  });

  it("labels the submit button as account creation, not a trial start", () => {
    render(<SignUpPage />);
    const submit = screen.getByRole("button", { name: /^create my account$/i });
    expect(submit).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start my free trial/i })).toBeNull();
  });

  it("falls back to an email-first, unbroken page when no providers are enabled", async () => {
    oauthProviders = { google: false, microsoft: false, apple: false };
    const { container } = render(<SignUpPage />);
    // Give the providers fetch a tick to resolve; the OAuth block should stay empty.
    await waitFor(() => expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument());
    expect(screen.queryByRole("link", { name: /Continue with Google/i })).toBeNull();
    // The email form is still fully present and usable.
    expect(container.querySelector("form")).not.toBeNull();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("keeps the email path working: submit still creates an account and routes on", async () => {
    const { authApi } = await import("@/lib/auth");
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() => expect(authApi.signup).toHaveBeenCalled());
    await waitFor(() => expect(routerSpies.push).toHaveBeenCalled());
    // CHANGED: the default destination is now the trial OFFER rather than the
    // scanner. Signup no longer starts a trial, so if nothing presented the
    // choice the trial would never be offered to anyone. The offer is a
    // two-button fork, and since #683 the decline is unconditional again:
    // every account continues on the Free plan into /app/scanner, because
    // /app/scanner no longer bounces anyone to a card wall. (#684 had split
    // that button on must_add_card — a gated account was sent to /scorecard
    // instead — which was the honest branch while the wall stood.)
    expect(routerSpies.push).toHaveBeenCalledWith(
      `/app/onboarding?next=${encodeURIComponent("/app/billing?trial=start")}`,
    );
  });

  it("makes the Name field optional (email + password are the only required inputs)", () => {
    render(<SignUpPage />);
    const name = screen.getByLabelText(/name/i) as HTMLInputElement;
    expect(name.required).toBe(false);
    expect((screen.getByLabelText(/^email$/i) as HTMLInputElement).required).toBe(true);
    expect((screen.getByLabelText(/password/i) as HTMLInputElement).required).toBe(true);
  });

  it("shows the card-transparency block", () => {
    render(<SignUpPage />);
    // CHANGED TWICE: it headlined "After your 14 days" (assumed a trial had
    // started), then "Free account, and where a card does come in" — dropped
    // under #548 because the account was not free. #683 made it free again,
    // but the heading stays as it is: "Where the card comes in" is the more
    // useful question now that the answer is "not here, and not to scan".
    expect(
      screen.getByText(/^Where the card comes in$/i),
    ).toBeInTheDocument();
  });

  it("uses the default headline when no ?from= source is set", () => {
    render(<SignUpPage />);
    // CHANGED: "Try Premium free for 14 days" over an email+password form was
    // a mis-promise, and so was "free account" once #548 put a card wall at
    // first sign-in. The H1 claims neither. #683 makes "free account" true
    // again, so the H1 could say it — but "Create your Tapeline account" is
    // what the button below actually does, and the subhead carries the terms.
    expect(
      screen.getByRole("heading", { name: /^Create your Tapeline account$/i }),
    ).toBeInTheDocument();
  });

  it("restates the Finviz promise in the H1 when from=finviz (message-match)", () => {
    nav.search = new URLSearchParams("from=finviz");
    render(<SignUpPage />);
    expect(
      screen.getByRole("heading", { name: /Finviz alternative/i }),
    ).toBeInTheDocument();
  });

  it("restates the scanner promise when from=screener", () => {
    nav.search = new URLSearchParams("from=screener");
    render(<SignUpPage />);
    expect(
      screen.getByRole("heading", { name: /shows its receipts/i }),
    ).toBeInTheDocument();
  });

  it("falls back to the default headline for an unknown ?from= value", () => {
    nav.search = new URLSearchParams("from=bogus");
    render(<SignUpPage />);
    expect(
      screen.getByRole("heading", { name: /^Create your Tapeline account$/i }),
    ).toBeInTheDocument();
  });

  it("keeps every source headline honest about the card (no source promises a card-free trial)", () => {
    for (const from of ["", "finviz", "screener", "scorecard", "compare", "trial", "bogus"]) {
      nav.search = new URLSearchParams(from ? `from=${from}` : "");
      const { container, unmount } = render(<SignUpPage />);
      const head = (container.querySelector("h1")?.textContent ?? "") +
        " " + (container.querySelector("h1")?.nextElementSibling?.textContent ?? "");
      expect(head).not.toMatch(/Premium free/i);
      expect(head).not.toMatch(/no credit card required/i);
      // "14 days free — no credit card" is the trial sold as a free period
      // without naming it a trial; it survives the rewrite below because it
      // never says the word. A free PLAN needing no card is a different
      // sentence and is now true, so the pattern is pinned to "N days free".
      expect(head).not.toMatch(
        /\b\d+[- ]days? free\b[^.;·]{0,25}(?:no|without a) (?:credit )?card/i,
      );
      // #548 added blanket bans on "free account" and "no card" here, because
      // the wall made both false whatever the source. #683 removed the wall,
      // so a subhead may now say a source-matched visitor gets a free account
      // with no card — every one of them does. The line that stays banned is
      // the one that carries card-freeness into the TRIAL clause, which is the
      // easiest mistake to make in exactly these one-sentence variants.
      expect(head).not.toMatch(/\btrial\b[^.;·]{0,30}(?:no|without a) (?:credit )?card/i);
      expect(head).not.toMatch(/(?:no|without a) (?:credit )?card[^.;·]{0,28}\btrial\b/i);
      unmount();
    }
  });

  // ── from=trial: the card-objection ad's landing key ──────────────────────
  // Ad variant 9 ("$0 today. The charge date is on the page.") sells the
  // SAFETY of the card trial instead of talking around it. Without this key
  // it lands on the generic hero and the test measures the page's
  // translation of the message rather than the message.

  it("restates the trial-transparency promise in the H1 when from=trial", () => {
    nav.search = new URLSearchParams("from=trial");
    render(<SignUpPage />);
    expect(
      screen.getByRole("heading", { name: /\$0 today\. The charge date is on the page\./i }),
    ).toBeInTheDocument();
  });

  it("states the whole card-trial rule in the from=trial subhead", () => {
    nav.search = new URLSearchParams("from=trial");
    const { container } = render(<SignUpPage />);
    const sub = (container.querySelector("h1")?.nextElementSibling?.textContent ?? "")
      .replace(/\s+/g, " ");
    // Every clause is something the codebase can actually produce: Stripe
    // Checkout ($0 today + the exact date), the cancel flow, and the T-3
    // render_trial_precharge_reminder_email fired from trial_will_end.
    expect(sub).toMatch(/takes a card/i);
    expect(sub).toMatch(/\$0 today/i);
    expect(sub).toMatch(/exact date of the first charge/i);
    expect(sub).toMatch(/three days ahead/i);
    expect(sub).toMatch(/one click ends the trial/i);
    // The escape hatch that keeps "read the record first" true.
    expect(sub).toMatch(/public record needs no account/i);
    // NARROWED by #683. This used to ban "no card" outright in this subhead —
    // correct while the account took one too. Now that signing up genuinely
    // takes none, this variant may say so; what it may never say is that the
    // TRIAL takes none, which is the exact thing the ad it answers is about.
    expect(sub).not.toMatch(/\btrial\b[^.;·]{0,30}(?:no|without a) (?:credit )?card/i);
    expect(sub).not.toMatch(/(?:no|without a) (?:credit )?card[^.;·]{0,28}\btrial\b/i);
  });

  // ── HDYHAU: optional free-text self-reported attribution (gap G2) ─────────
  // The only instrument that can ever credit AI-assistant and dark-social
  // referrals — both arrive with no referrer and no UTM, so every automatic
  // capture in lib/utm.ts is blind to them.

  it("renders an optional free-text 'How did you hear about us?' field", () => {
    render(<SignUpPage />);
    const field = screen.getByLabelText(/how did you hear about us/i) as HTMLInputElement;
    // FREE TEXT, not a dropdown. A fixed option list can only count the
    // channels we already thought of, and the ones worth finding are the
    // ones we can't see.
    expect(field.tagName).toBe("INPUT");
    expect(field.type).toBe("text");
    expect(field.required).toBe(false);
  });

  it("submits fine with the attribution field left blank, sending nothing", async () => {
    const { authApi } = await import("@/lib/auth");
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() => expect(authApi.signup).toHaveBeenCalled());
    const extras = (authApi.signup as ReturnType<typeof vi.fn>).mock.calls.at(-1)![3];
    // undefined, not "" — an empty string would become its own row in the
    // GROUP BY this field exists to feed.
    expect(extras.referral_source).toBeUndefined();
  });

  it("forwards the typed answer verbatim on the signup POST", async () => {
    const { authApi } = await import("@/lib/auth");
    const { container } = render(<SignUpPage />);
    fireEvent.change(screen.getByLabelText(/how did you hear about us/i), {
      target: { value: "  Claude suggested it  " },
    });
    fillAndSubmit(container);
    await waitFor(() => expect(authApi.signup).toHaveBeenCalled());
    const extras = (authApi.signup as ReturnType<typeof vi.fn>).mock.calls.at(-1)![3];
    expect(extras.referral_source).toBe("Claude suggested it");
  });

  // ── Meta click identifiers on the signup POST (gap G4) ───────────────────

  it("forwards the stored fbclid and the _fbp cookie", async () => {
    const { authApi } = await import("@/lib/auth");
    window.localStorage.setItem(
      "tapeline_fbclid_v1",
      JSON.stringify({ fbclid: "IwAR0-TeSt", captured_at: Date.now() }),
    );
    Object.defineProperty(document, "cookie", {
      value: "_fbp=fb.1.1755900000000.987654321",
      configurable: true,
      writable: true,
    });
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() => expect(authApi.signup).toHaveBeenCalled());
    const extras = (authApi.signup as ReturnType<typeof vi.fn>).mock.calls.at(-1)![3];
    expect(extras.fbclid).toBe("IwAR0-TeSt");
    expect(extras.fbp).toBe("fb.1.1755900000000.987654321");
    window.localStorage.clear();
  });

  it("omits both Meta keys for organic traffic", async () => {
    const { authApi } = await import("@/lib/auth");
    window.localStorage.clear();
    Object.defineProperty(document, "cookie", {
      value: "",
      configurable: true,
      writable: true,
    });
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() => expect(authApi.signup).toHaveBeenCalled());
    const extras = (authApi.signup as ReturnType<typeof vi.fn>).mock.calls.at(-1)![3];
    expect(extras.fbclid).toBeUndefined();
    expect(extras.fbp).toBeUndefined();
  });

  // ── Plan-intent carry-through (?plan= / ?billing= from /pricing) ──────────
  // /pricing CTAs link to /signup?plan=pro|premium&billing=monthly|annual.
  // These params used to be silently dropped — the buyer's plan choice never
  // survived signup. They must now be restated to /app/billing via the
  // onboarding `next` param.

  it("routes plan intent from /pricing into the billing page after signup", async () => {
    nav.search = new URLSearchParams("plan=premium&billing=annual");
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() => expect(routerSpies.push).toHaveBeenCalled());
    expect(routerSpies.push).toHaveBeenCalledWith(
      `/app/onboarding?next=${encodeURIComponent("/app/billing?intent=premium&billing=annual")}`,
    );
  });

  it("preserves the billing period (monthly) in the carried intent", async () => {
    nav.search = new URLSearchParams("plan=pro&billing=monthly");
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() => expect(routerSpies.push).toHaveBeenCalled());
    expect(routerSpies.push).toHaveBeenCalledWith(
      `/app/onboarding?next=${encodeURIComponent("/app/billing?intent=pro&billing=monthly")}`,
    );
  });

  it("falls back to the trial offer when no plan intent is present", async () => {
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() => expect(routerSpies.push).toHaveBeenCalled());
    expect(routerSpies.push).toHaveBeenCalledWith(
      `/app/onboarding?next=${encodeURIComponent("/app/billing?trial=start")}`,
    );
  });

  it("ignores a bogus ?plan= value (falls back to the default destination)", async () => {
    nav.search = new URLSearchParams("plan=enterprise&billing=weekly");
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() => expect(routerSpies.push).toHaveBeenCalled());
    expect(routerSpies.push).toHaveBeenCalledWith(
      `/app/onboarding?next=${encodeURIComponent("/app/billing?trial=start")}`,
    );
  });

  it("still honours an explicit ?next= deep link over the trial offer", async () => {
    nav.search = new URLSearchParams("next=/app/watchlist");
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() => expect(routerSpies.push).toHaveBeenCalled());
    expect(routerSpies.push).toHaveBeenCalledWith(
      `/app/onboarding?next=${encodeURIComponent("/app/watchlist")}`,
    );
  });

  it("does NOT fire start_trial — this form no longer starts a trial", async () => {
    // CHANGED with the card-required trial. `start_trial` used to fire on the
    // same beat as `sign_up` because signup auto-granted a trial. Leaving it
    // here would report a trial that hasn't started, and would hand Google Ads
    // a trial conversion for every account created. It now fires from
    // /app/billing on the confirmed return from a trial checkout.
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() =>
      expect(trackEventMock.mock.calls.some((c) => c[0] === "sign_up")).toBe(true),
    );
    expect(trackEventMock.mock.calls.some((c) => c[0] === "start_trial")).toBe(false);
  });

  it("carries the plan intent through the Sign in link for existing users", () => {
    nav.search = new URLSearchParams("plan=premium&billing=monthly");
    render(<SignUpPage />);
    const signin = screen.getByRole("link", { name: /sign in/i });
    expect(signin.getAttribute("href")).toBe(
      `/signin?next=${encodeURIComponent("/app/billing?intent=premium&billing=monthly")}`,
    );
  });

  // ── Email consent checkboxes (weekly digest + Daily Top 10) ──────────────
  // Both must be UNCHECKED by default — this is an explicit-opt-in placement
  // fix, not pre-ticking. Their state travels as `marketing_opt_in` /
  // `daily_top10_opt_in` on the signup POST.

  it("renders both consent checkboxes UNCHECKED by default", () => {
    render(<SignUpPage />);
    const weekly = screen.getByLabelText(/weekly market digest/i) as HTMLInputElement;
    const daily = screen.getByLabelText(/Daily Top 10/i) as HTMLInputElement;
    expect(weekly.type).toBe("checkbox");
    expect(daily.type).toBe("checkbox");
    expect(weekly.checked).toBe(false);
    expect(daily.checked).toBe(false);
  });

  it("forwards both consents on the signup POST when ticked", async () => {
    const { authApi } = await import("@/lib/auth");
    const { container } = render(<SignUpPage />);
    fireEvent.click(screen.getByLabelText(/weekly market digest/i));
    fireEvent.click(screen.getByLabelText(/Daily Top 10/i));
    fillAndSubmit(container);
    await waitFor(() => expect(authApi.signup).toHaveBeenCalled());
    const extras = (authApi.signup as ReturnType<typeof vi.fn>).mock.calls.at(-1)![3];
    expect(extras.marketing_opt_in).toBe(true);
    expect(extras.daily_top10_opt_in).toBe(true);
  });

  it("forwards NO consent when both boxes are left untouched", async () => {
    const { authApi } = await import("@/lib/auth");
    const { container } = render(<SignUpPage />);
    fillAndSubmit(container);
    await waitFor(() => expect(authApi.signup).toHaveBeenCalled());
    const extras = (authApi.signup as ReturnType<typeof vi.fn>).mock.calls.at(-1)![3];
    expect(extras.marketing_opt_in).toBe(false);
    expect(extras.daily_top10_opt_in).toBe(false);
  });

  it("does not require either consent to submit (signup never gated on marketing)", async () => {
    render(<SignUpPage />);
    const weekly = screen.getByLabelText(/weekly market digest/i) as HTMLInputElement;
    const daily = screen.getByLabelText(/Daily Top 10/i) as HTMLInputElement;
    expect(weekly.required).toBe(false);
    expect(daily.required).toBe(false);
  });

  // ── Price prose derived from lib/pricing ─────────────────────────────────
  // The after-trial footer used to hardcode "Pro from $8.25/mo" (and the
  // Free-tier caps + refund window); all four now derive from the same
  // constants checkout and every other surface use.

  // Meta's Subscription Services standard requires the PRICE and BILLING
  // INTERVAL of the subscription being advertised, shown clearly — not in fine
  // print, not behind a link. The paid trial ad lands here, so this page is the
  // enforcement surface.
  //
  // This previously asserted `Pro from $8.25/mo`, which pinned a real defect:
  // the trial converts to PREMIUM (annual by default, so a $199 first charge),
  // and the page advertised PRO's annually-billed monthly rate instead. Wrong
  // plan, wrong interval. A misleading interval is a heavier failure than a
  // missing one, so the assertion is inverted: Pro's per-month-of-annual rate
  // must NOT be the headline price here.
  // ── The removed subscription acknowledgement ──────────────────────────────
  // Until 2026-09-05 a REQUIRED checkbox hard-gated account creation on "I
  // understand my Premium trial charges $0 today, then $19.99/month from
  // <date>". Signing up takes no card and schedules no charge, so that was
  // false for every visitor, and they could not create a free account without
  // affirming it. The founder removed it.
  //
  // It was added for Meta's Subscription Services standard, which prohibits on
  // a page where personal info is entered "not including an unticked opt-in
  // checkbox". That standard governs pages where a SUBSCRIPTION is entered
  // into; this form enters into none. Whether Meta reads it that way is open
  // and is with the lawyer. What must NOT regress meanwhile is the disclosure
  // itself: price, interval, recurrence, the exit and a dated example all stay
  // on the page, at readable size, without a false acknowledgement.

  it("has no acknowledgement checkbox gating account creation", () => {
    render(<SignUpPage />);
    expect(document.getElementById("signup-subscription-terms")).toBeNull();
    const required = Array.from(
      document.querySelectorAll('input[type="checkbox"][aria-required="true"]'),
    );
    expect(required).toEqual([]);
  });

  it("creates the account without any acknowledgement step", async () => {
    const { authApi } = await import("@/lib/auth");
    vi.mocked(authApi.signup).mockClear();
    const { container } = render(<SignUpPage />);

    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: "trader@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "longenough-pass" },
    });
    fireEvent.submit(container.querySelector("form")!);

    await waitFor(() => expect(authApi.signup).toHaveBeenCalled());
    // The old gate's error must never reappear.
    expect(
      screen.queryByText(/confirm you understand the trial's price and billing/i),
    ).toBeNull();
  });

  it("keeps the full subscription disclosure on the page, not in fine print", () => {
    const { container } = render(<SignUpPage />);
    const text = (container.textContent ?? "").replace(/\s+/g, " ");
    // Everything the acknowledgement used to carry must still be stated.
    expect(text).toContain(`${usd(PRICING.premium.monthly)}/month`);
    expect(text).toContain(`${usdCompact(PRICING.premium.annual)}/year`);
    expect(text).toMatch(/recurring until you cancel/i);
    expect(text).toMatch(/cancel in one click|one click ends it/i);
  });

  it("shows Premium's real price and interval, derived from PRICING", () => {
    render(<SignUpPage />);
    const text = (document.body.textContent ?? "").replace(/\s+/g, " ");

    expect(text).toContain(`${usd(PRICING.premium.monthly)}/month`);
    expect(text).toContain(`${usdCompact(PRICING.premium.annual)}/year`);
    // "recurring until you cancel" is the recurrent-billing disclosure.
    expect(text).toMatch(/recurring until you cancel/i);

    // The old, wrong headline price must not come back.
    expect(text).not.toContain(`Pro from ${usd(PRICING.pro.annualPerMonth)}/mo`);
  });

  it("names the account-free escape hatch in the transparency footer", () => {
    // This replaced a FREE_LIMITS-derivation check: the footer used to sell a
    // card-free Free tier with its caps, and #548 made that false. #683 makes
    // the caps real again (ten scanner rows, one saved screen, five watchlist
    // symbols, twelve ticker pages a day), so a FREE_LIMITS-derived line would
    // be honest here once more — this test does not ask for one. What it does
    // require is the claim that needs no account at all: the published record.
    render(<SignUpPage />);
    const text = (document.body.textContent ?? "").replace(/\s+/g, " ");
    expect(text).toMatch(/the daily Top 10, the whole back-checked scorecard/i);
    expect(text).toMatch(/raw CSV\/JSON export are open to everyone/i);
  });

  it("derives the refund copy from REFUND", () => {
    render(<SignUpPage />);
    expect(screen.getByText(REFUND.short)).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`${REFUND.windowDays}-day money-back on paid plans`)),
    ).toBeInTheDocument();
  });

  // ── Inline validation, blur timing, and the aria wiring ──────────────────
  // Errors must appear when the user LEAVES a field (not on every keystroke,
  // and not only after a wasted submit round-trip), render next to the field
  // that caused them, and be wired to assistive tech.

  it("does NOT show an error while the user is still typing the email", () => {
    render(<SignUpPage />);
    const email = screen.getByLabelText(/^email$/i);
    fireEvent.change(email, { target: { value: "trader@" } });
    expect(email).not.toHaveAttribute("aria-invalid");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows an adjacent, actionable email error ON BLUR", () => {
    render(<SignUpPage />);
    const email = screen.getByLabelText(/^email$/i);
    fireEvent.change(email, { target: { value: "trader-at-example.com" } });
    fireEvent.blur(email);

    const error = screen.getByRole("alert");
    // Says what went wrong AND how to fix it — never a bare "Invalid input".
    expect(error.textContent).toMatch(/missing an @/i);
    expect(error.textContent).toMatch(/you@example\.com/i);
    expect(error.textContent).not.toMatch(/^invalid/i);
    // Adjacent to the offending field, not parked at the foot of the form.
    expect(email.parentElement).toContainElement(error);
  });

  it("wires aria-invalid + aria-describedby from the input to its error", () => {
    render(<SignUpPage />);
    const email = screen.getByLabelText(/^email$/i);
    fireEvent.change(email, { target: { value: "nope" } });
    fireEvent.blur(email);

    expect(email).toHaveAttribute("aria-invalid", "true");
    const describedBy = email.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    // Every id referenced must actually exist — a dangling describedby
    // target silently announces nothing.
    for (const id of describedBy!.split(" ")) {
      expect(document.getElementById(id)).not.toBeNull();
    }
    expect(document.getElementById("signup-email-error")!.textContent).toMatch(
      /email address/i,
    );
  });

  it("keeps the password hint described alongside the error, not replaced by it", () => {
    render(<SignUpPage />);
    const password = screen.getByLabelText(/password/i);
    fireEvent.change(password, { target: { value: "short" } });
    fireEvent.blur(password);

    const describedBy = password.getAttribute("aria-describedby")!.split(" ");
    expect(describedBy).toContain("signup-password-error");
    expect(describedBy).toContain("signup-password-hint");
    // The message counts the shortfall rather than restating the rule.
    expect(document.getElementById("signup-password-error")!.textContent).toMatch(
      /5 characters.*add 3 more/i,
    );
  });

  it("clears a shown error as the user starts fixing the field", () => {
    render(<SignUpPage />);
    const email = screen.getByLabelText(/^email$/i);
    fireEvent.change(email, { target: { value: "nope" } });
    fireEvent.blur(email);
    expect(email).toHaveAttribute("aria-invalid", "true");

    fireEvent.change(email, { target: { value: "nope@example.com" } });
    expect(email).not.toHaveAttribute("aria-invalid");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("blocks submit on an invalid email and never calls the API", async () => {
    const { authApi } = await import("@/lib/auth");
    // The module-level mock accumulates across tests in this file; only the
    // calls made by THIS test are meaningful here.
    (authApi.signup as ReturnType<typeof vi.fn>).mockClear();
    const { container } = render(<SignUpPage />);
    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: "not-an-email" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "longenough-pass" },
    });
    fireEvent.submit(container.querySelector("form")!);

    await waitFor(() =>
      expect(screen.getByLabelText(/^email$/i)).toHaveAttribute("aria-invalid", "true"),
    );
    expect(authApi.signup).not.toHaveBeenCalled();
  });

  it("PRESERVES everything the user typed when submit fails validation", async () => {
    const { container } = render(<SignUpPage />);
    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: "trader@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: "tiny" } , // too short → submit fails
    });
    fireEvent.change(screen.getByLabelText(/name/i), {
      target: { value: "Ada Lovelace" },
    });
    fireEvent.click(screen.getByLabelText(/Daily Top 10/i));
    fireEvent.submit(container.querySelector("form")!);

    await waitFor(() =>
      expect(screen.getByLabelText(/password/i)).toHaveAttribute("aria-invalid", "true"),
    );
    // Nothing was wiped — including the consent checkbox.
    expect((screen.getByLabelText(/^email$/i) as HTMLInputElement).value).toBe(
      "trader@example.com",
    );
    expect((screen.getByLabelText(/password/i) as HTMLInputElement).value).toBe("tiny");
    expect((screen.getByLabelText(/name/i) as HTMLInputElement).value).toBe(
      "Ada Lovelace",
    );
    expect(
      (screen.getByLabelText(/Daily Top 10/i) as HTMLInputElement).checked,
    ).toBe(true);
  });

  it("announces the form-level error from an always-mounted live region", async () => {
    const { container } = render(<SignUpPage />);
    // The live region must exist BEFORE the error arrives, or assistive tech
    // has nothing to observe when the message is inserted.
    const region = container.querySelector('[aria-live="assertive"]');
    expect(region).not.toBeNull();
    expect(region!.textContent).toBe("");

    fireEvent.change(screen.getByLabelText(/^email$/i), {
      target: { value: "bad" },
    });
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => expect(region!.textContent).toMatch(/needs? fixing/i));
  });

  it("submits normally once the fields are valid (validation is not a wall)", async () => {
    const { authApi } = await import("@/lib/auth");
    const { container } = render(<SignUpPage />);
    const email = screen.getByLabelText(/^email$/i);
    fireEvent.change(email, { target: { value: "trader@example.com" } });
    fireEvent.blur(email);
    const password = screen.getByLabelText(/password/i);
    fireEvent.change(password, { target: { value: "longenough-pass" } });
    fireEvent.blur(password);
    expect(screen.queryByRole("alert")).toBeNull();

    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => expect(authApi.signup).toHaveBeenCalled());
  });

  // ── Compliance Rule 8: no suitability data at the account-creation step ───
  it("collects NO suitability data (experience, capital, risk tolerance, goals)", () => {
    const { container } = render(<SignUpPage />);
    const inputs = Array.from(
      container.querySelectorAll("input, select, textarea"),
    );
    const banned =
      /experience|portfolio|capital|net worth|risk toleran|investment goal|holdings|how much/i;
    for (const el of inputs) {
      expect(el.getAttribute("name") ?? "").not.toMatch(banned);
      expect(el.getAttribute("id") ?? "").not.toMatch(banned);
    }
    // And nothing on the page asks for it in prose either.
    expect(container.textContent ?? "").not.toMatch(
      /how much (do you|capital)|portfolio size|risk tolerance|investing experience/i,
    );
  });
});
