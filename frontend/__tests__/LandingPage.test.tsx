/**
 * Landing page fold — the hero must pair the real-data scanner preview with
 * a zero-signup path into the product: the "See today's full Top 10 — no
 * signup →" link to /daily-picks, and no leftover "Live mock" framing from
 * the retired fabricated demo.
 *
 * It must also offer TWO first-class entry points, not one button plus a
 * ghost link. The fold previously demoted everything except /signup to
 * `btn-ghost` (borderless, muted text), so the trial's terms and the
 * no-account browse path both read as footnotes. Both doors now carry equal
 * visual weight, and the terms are described plainly: signing up takes an
 * email and a password and no card, a card is what starts the trial, nothing
 * is charged the day it does, and there is no deadline framing anywhere
 * (compliance Rule 6).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

// ScannerPreview is an async server component (server-fetches the real
// anonymous top-10) — RTL/jsdom can't render async components, so stub it.
// Its own contract is covered in ScannerPreview.test.tsx.
vi.mock("@/components/ScannerPreview", () => ({
  ScannerPreview: () =>
    require("react").createElement("div", { "data-testid": "scanner-preview" }),
}));
// Client widgets with their own timers/fetch loops — out of scope here.
vi.mock("@/components/LiveCounters", () => ({ LiveCounters: () => null }));
vi.mock("@/components/ExitIntentModal", () => ({ ExitIntentModal: () => null }));
// FadeIn mounts an IntersectionObserver, which jsdom doesn't implement —
// pass children straight through.
vi.mock("@/components/FadeIn", () => ({
  FadeIn: ({ children }: { children: unknown }) => children,
}));

import LandingPage from "@/app/page";

// LandingPage is now an async server component (it server-fetches the scorecard
// summary for the usage-as-proof line, GAP #20). RTL/jsdom can't render an
// async component as JSX, so each test awaits the component call. A default
// fetch mock returns a representative summary; the summary carries vs-SPY
// figures precisely so we can prove they DON'T leak onto the hero (Rule 3).
const SUMMARY = {
  days_tracked: 62,
  // Larger than entries_scored on purpose — see scorecardCitation.test.tsx.
  entries_logged: 620,
  entries_scored: 610,
  entries_excluded_outliers: 0,
  median_alpha_vs_spy: 0.42,
  hit_rate_beat_spy: 51.3,
  first_tracked_date: "2026-05-12",
};

function mockSummaryFetch(summary: unknown) {
  global.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ summary }),
    }),
  ) as any;
}

beforeEach(() => {
  mockSummaryFetch(SUMMARY);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("LandingPage hero fold", () => {
  it("links the fold to the zero-signup /daily-picks Top 10", async () => {
    render(await LandingPage());
    const link = screen.getByRole("link", {
      name: /see today.s full top 10 — no signup/i,
    });
    expect(link).toHaveAttribute("href", "/daily-picks");
  });

  it("retires the 'Live mock' framing from the fold", async () => {
    render(await LandingPage());
    expect(screen.queryByText(/live mock/i)).toBeNull();
  });

  // ── Paired entry points ──────────────────────────────────────────────────

  it("offers BOTH hero CTAs: see the record, and browse with no account", async () => {
    // Proof-first repositioning (2026-08): the primary door is the public
    // track record (/scorecard) for the newsletter-burned audience, with the
    // no-account browse path alongside it. The trial stays reachable via the
    // nav + the terms line below the fold.
    render(await LandingPage());
    expect(
      screen.getByRole("link", { name: /see the track record/i }),
    ).toHaveAttribute("href", "/scorecard");
    expect(
      screen.getByRole("link", { name: /browse without an account/i }),
    ).toHaveAttribute("href", "/daily-picks");
  });

  it("gives both hero CTAs equal visual weight (neither is a muted btn-ghost)", async () => {
    render(await LandingPage());
    const record = screen.getByRole("link", { name: /see the track record/i });
    const browse = screen.getByRole("link", { name: /browse without an account/i });
    // Both are full pill buttons...
    expect(record.className).toMatch(/\bbtn(-primary)?\b/);
    expect(browse.className).toMatch(/\bbtn\b/);
    // ...and neither is the borderless, muted treatment that buried the
    // secondary path before. `btn-ghost` here is the regression to catch.
    expect(record.className).not.toMatch(/btn-ghost/);
    expect(browse.className).not.toMatch(/btn-ghost/);
    // The browse CTA carries a real border so it reads as a button, not text.
    expect(browse.className).toMatch(/border/);
  });

  it("adds a subtle tertiary /signup link without demoting the two pills (GAP #6)", async () => {
    render(await LandingPage());
    // The tertiary link is present and points at /signup. Matched on the HREF,
    // not on the label: this used to assert the words "Start the 14-day
    // trial", and since #683 signing up does not start a trial — it creates a
    // free account that can scan straight away. What GAP #6 is actually about
    // is the DOOR being there, so that is what is pinned; the wording of the
    // link belongs to app/page.tsx.
    const signup = screen
      .getAllByRole("link")
      .filter((a) => a.getAttribute("href") === "/signup");
    expect(signup.length).toBeGreaterThan(0);
    // ...and the two proof-first pills are still first-class (unchanged).
    expect(
      screen.getByRole("link", { name: /see the track record/i }),
    ).toHaveAttribute("href", "/scorecard");
    expect(
      screen.getByRole("link", { name: /browse without an account/i }),
    ).toHaveAttribute("href", "/daily-picks");
  });

  it("states the terms plainly: what a card buys, \$0 that day, day-14 charge, one-click exit", async () => {
    const { container } = render(await LandingPage());
    const text = (container.textContent ?? "").replace(/\s+/g, " ");
    // CHANGED TWICE. #548 replaced "no credit card, no payment details" with
    // "your card goes on at first sign-in"; #683 (2026-08-30) took the wall
    // that sentence described back out. Signing up is an email and a password
    // and the new account can scan immediately — the card is what buys the
    // trial, and the TRIAL's terms below are exactly as they were.
    expect(text).toMatch(/no card/i);
    expect(text).toMatch(/14 days of Premium/i);
    expect(text).toMatch(/nothing is charged/i);
    expect(text).toMatch(/first charge is on day 14/i);
    expect(text).toMatch(/one click cancels/i);
    // The path that needs no account at all is still offered alongside it.
    expect(text).toMatch(/free to read with no account/i);
    // The retired wall must not survive anywhere in the fold copy. Asserted on
    // the whole render because the sentence could reappear in any block.
    expect(text).not.toMatch(/card (?:goes on|is added|comes) at first sign-in/i);
    expect(text).not.toMatch(/at first sign-in,? you add a card/i);
  });

  it("keeps the trial CTA free of urgency and scarcity framing (Rule 6)", async () => {
    const { container } = render(await LandingPage());
    const text = container.textContent ?? "";
    // No deadline pricing, no countdown, no "N spots/seats left", no
    // "expires"/"ends soon" pressure anywhere in the fold copy.
    expect(text).not.toMatch(/only \d+ (left|remaining|spots?|seats?)/i);
    expect(text).not.toMatch(/countdown|hurry|act now|limited time|ends soon/i);
    expect(text).not.toMatch(/offer expires|last chance to/i);
  });
});

// ── Open-access month strip (backend tier.py free_open_access, #523) ───────
describe("LandingPage open-access strip", () => {
  // The page reads the real clock (no `now` prop threads through an async
  // server component), so pin Date only — timers/promises stay real, which
  // keeps the awaited fetch mocks working.
  function pinDate(iso: string) {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(iso));
  }

  it("shows the strip ABOVE the hero while the window runs — hero intact", async () => {
    pinDate("2026-08-23T12:00:00Z");
    try {
      render(await LandingPage());
      const strip = screen.getByTestId("open-access-banner");
      expect(strip.textContent).toMatch(/until 8 September/i);
      expect(strip.textContent).toMatch(/signed-in account/i);
      // The strip supplements the hero, never replaces it: h1 + both CTAs stay.
      expect(
        screen.getByRole("heading", { level: 1 }).textContent,
      ).toMatch(/every pick on the public record/i);
      expect(
        screen.getByRole("link", { name: /see the track record/i }),
      ).toHaveAttribute("href", "/scorecard");
    } finally {
      vi.useRealTimers();
    }
  });

  it("renders no strip once the window has closed", async () => {
    pinDate("2026-09-09T00:00:00Z");
    try {
      render(await LandingPage());
      expect(screen.queryByTestId("open-access-banner")).toBeNull();
      // The page itself is unaffected by the promo ending.
      expect(
        screen.getByRole("heading", { level: 1 }).textContent,
      ).toMatch(/every pick on the public record/i);
    } finally {
      vi.useRealTimers();
    }
  });
});

// ── Usage-as-proof (GAP #20) ───────────────────────────────────────────────
describe("LandingPage usage-as-proof line", () => {
  it("renders the live raw counts and tracked-since date", async () => {
    render(await LandingPage());
    // Sourced from the mocked scorecard summary: entries_scored across
    // days_tracked, with the tracked-since clause from first_tracked_date.
    const proof = screen.getByText(
      /620 picks logged across 62 market days/i,
    );
    expect(proof).toBeInTheDocument();
    expect(proof.textContent).toMatch(/tracked since 12 May 2026/i);
    // The hero used to print entries_scored (610) here under "logged".
    expect(proof.textContent).not.toMatch(/610 picks logged/i);
    // The summary fetch actually fired at /api/scorecard.
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/scorecard"),
      expect.anything(),
    );
  });

  it("says 'back-checked', not 'logged', when the API omits entries_logged", async () => {
    // A response cached from before entries_logged shipped carries only the
    // back-checked count. The hero must change the NOUN rather than print
    // that smaller number after the word "logged" — which is precisely the
    // understatement this field was added to remove. Without this case the
    // whole guard is vacuous: a hero hardcoded to "logged" passes every other
    // test in this file.
    const legacy = { ...SUMMARY } as Record<string, unknown>;
    delete legacy.entries_logged;
    mockSummaryFetch(legacy);
    render(await LandingPage());
    const proof = screen.getByText(/610 picks back-checked across 62 market days/i);
    expect(proof).toBeInTheDocument();
    expect(proof.textContent).not.toMatch(/logged/i);
  });

  it("surfaces NO vs-SPY figure on the landing surface (Rule 3)", async () => {
    const { container } = render(await LandingPage());
    const text = container.textContent ?? "";
    // The summary carries a 51.3% hit rate and a +0.42% median alpha. The
    // proof line must expose ONLY raw counts + the date, so neither numeric
    // FIGURE may render. (The words "vs SPY"/"alpha" describing the mechanism
    // are pre-existing, allowed copy — this guards the numbers, not the words.)
    expect(text).not.toMatch(/51\.3/);
    expect(text).not.toMatch(/0\.42/);
    // And no percentage is tied to a beat/vs-SPY claim anywhere on the page.
    expect(text).not.toMatch(/\d+(\.\d+)?%[^.]{0,20}(beat|vs\.?)\s*spy/i);
    expect(text).not.toMatch(/(beat|vs\.?)\s*spy[^.]{0,20}\d+(\.\d+)?%/i);
  });

  it("renders nothing extra when the summary fetch fails", async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error("down"))) as any;
    render(await LandingPage());
    // No proof line, and the page still renders the rest of the fold.
    expect(screen.queryByText(/picks logged across/i)).toBeNull();
    expect(
      screen.getByRole("link", { name: /see the track record/i }),
    ).toBeInTheDocument();
  });
});
