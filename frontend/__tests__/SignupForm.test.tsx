/**
 * Signup page tests:
 *   - the offscreen honeypot field (bot-protection layer depends on it)
 *   - core fields, and the CARD RULE stated honestly. Since 2026-08 this form
 *     creates a FREE account and nothing else: no card, no trial. The 14-day
 *     Premium trial is a separate opt-in on the next screen and it DOES take a
 *     card, so every "no credit card" line here must qualify the account, not
 *     the trial. The page must also contain NO card input of any kind.
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
import { FREE_LIMITS, PRICING, REFUND, usd } from "@/lib/pricing";

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

/** Fill the minimum valid form and submit it. */
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
    // CHANGED with the card-required trial: the strip used to read
    // "Free forever · No credit card · 14-day Premium trial", which now reads
    // as a promise that the TRIAL takes no card. It does. So "no credit card"
    // has to qualify signup, and the trial has to carry its own qualifier.
    expect(
      screen.getByText(
        /Free forever.*No credit card to sign up.*14-day Premium trial \(card required, \$0 today\).*30-day money-back/i,
      ),
    ).toBeInTheDocument();
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
    // The exact claim that stopped being true.
    expect(text).not.toMatch(/(?:14[- ]day|Premium) trial[^.]{0,40}no (?:credit )?card/i);
    expect(text).not.toMatch(/no (?:credit )?card[^.]{0,25}(?:14[- ]day|Premium) trial/i);
  });

  it("states the trial's charge terms up front: card required, $0 today, first charge at day 14, one-click exit", () => {
    const { container } = render(<SignUpPage />);
    const text = (container.textContent ?? "").replace(/\s+/g, " ");
    expect(text).toMatch(/card required/i);
    expect(text).toMatch(/\$0 is charged today/i);
    expect(text).toMatch(/first charge is 14 days later/i);
    expect(text).toMatch(/one click ends it before then/i);
    // And the free fallback is named as a real, unpunished outcome.
    expect(text).toMatch(/stay on Free/i);
  });

  it("keeps the Free-tier no-card promise literally true", () => {
    const { container } = render(<SignUpPage />);
    const text = (container.textContent ?? "").replace(/\s+/g, " ");
    expect(text).toMatch(/free forever and never needing a card/i);
  });

  it("labels the submit button as account creation, not a trial start", () => {
    render(<SignUpPage />);
    const submit = screen.getByRole("button", { name: /create my free account/i });
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
    // two-button fork, one of which is "Continue on the Free plan" → scanner.
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
    // CHANGED: the footer used to headline "After your 14 days", which assumed
    // a trial had already started. It now explains what this form creates
    // (a free account) and where a card does come in.
    expect(
      screen.getByText(/Free account, and where a card does come in/i),
    ).toBeInTheDocument();
  });

  it("uses the default headline when no ?from= source is set", () => {
    render(<SignUpPage />);
    // CHANGED: "Try Premium free for 14 days" over an email+password form is
    // now a mis-promise — the form creates a free account, not a trial.
    expect(
      screen.getByRole("heading", { name: /Create your free Tapeline account/i }),
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
      screen.getByRole("heading", { name: /Create your free Tapeline account/i }),
    ).toBeInTheDocument();
  });

  it("keeps every source headline honest about the card (no source promises a card-free trial)", () => {
    for (const from of ["", "finviz", "screener", "scorecard", "compare", "bogus"]) {
      nav.search = new URLSearchParams(from ? `from=${from}` : "");
      const { container, unmount } = render(<SignUpPage />);
      const head = (container.querySelector("h1")?.textContent ?? "") +
        " " + (container.querySelector("h1")?.nextElementSibling?.textContent ?? "");
      expect(head).not.toMatch(/(?:14[- ]days? )?free[^.]{0,20}no credit card/i);
      expect(head).not.toMatch(/Premium free/i);
      unmount();
    }
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

  it("derives the after-trial Pro price from PRICING (no hardcoded prose)", () => {
    render(<SignUpPage />);
    expect(
      screen.getByText(`Pro from ${usd(PRICING.pro.annualPerMonth)}/mo`),
    ).toBeInTheDocument();
  });

  it("derives the Free-tier caps in the after-trial footer from FREE_LIMITS", () => {
    render(<SignUpPage />);
    expect(
      screen.getByText(
        new RegExp(
          `top-${FREE_LIMITS.scannerRows} scanner, ${FREE_LIMITS.dailyLookups} look-ups/day`,
        ),
      ),
    ).toBeInTheDocument();
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
