/**
 * PricingTable should render the plan columns at the canonical price points.
 * If this test fails, pricing copy has drifted from
 * `backend/app/services/tier.py` — sync them before shipping.
 *
 * Annual-default suite (founder decision 2026-07-18): the default render is
 * ANNUAL with the explicit "billed annually ($99/yr)" qualifier on every
 * annual per-month figure; monthly is one toggle click away; and the plan
 * cards + ComparisonTable header share one toggle state so they can never
 * show different billing periods on the same screen.
 *
 * THE $0 COLUMN, AND WHY IT SAYS WHAT IT SAYS. It began as a "Free" plan card
 * with a "Start free" button into /signup. The 2026-08-22 card gate made that
 * false — a new account met a card wall at first sign-in — so the column was
 * rewritten as the PUBLIC RECORD: the daily Top 10, the whole scorecard, a
 * page per scored ticker and the raw CSV/JSON, open with no account, no card
 * and no email.
 *
 * #683 (2026-08-30) removed the wall. Signing up is an email and a password,
 * and the free account it creates reaches the live scanner immediately — the
 * top ten scored rows of any scan, one saved screen, a five-symbol watchlist,
 * twelve ticker pages a day. So a card-free ACCOUNT is now an honest thing to
 * advertise, and this suite no longer forbids it. Two claims are still
 * policed, because both are still false: that the Premium trial is
 * card-free (it is not — a card is exactly what starts it), and any promise
 * of permanence the product cannot keep.
 *
 * What the public-record assertions below pin is unchanged and independent of
 * all that: every line in the $0 column has to be reachable with no account
 * at all. A free PLAN column would be an honest addition beside it — it just
 * would not belong in the account-free list.
 */
import { describe, it, expect } from "vitest";
// Trial length from lib/trial.ts, never a literal.
import { TRIAL_DAYS } from "@/lib/trial";
import { render, screen, fireEvent } from "@testing-library/react";
import { PricingTable } from "@/components/PricingTable";
import { ComparisonTable } from "@/components/ComparisonTable";
import { BillingPeriodProvider } from "@/components/BillingToggle";
import { PRICING, REFUND, FREE_LIMITS, usd, billedAnnuallyNote } from "@/lib/pricing";

/** Escape a literal string for use inside a RegExp ("$8.25 (…)" etc.). */
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

describe("PricingTable", () => {
  it("renders the Free, Pro, and Premium columns", () => {
    render(<PricingTable />);
    // FOLLOWS THE COMPONENT, #683 (2026-08-30). The $0 column was narrowed to
    // "Public record" while the card gate stood, because there was no free
    // logged-in tier to sell and a /signup CTA would have been a lie. The wall
    // is gone: signing up takes an email and a password and lands on a Free
    // PLAN, so the column is a plan again and its CTA is a signup door.
    expect(screen.getByRole("heading", { name: "Free" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pro" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Premium" })).toBeInTheDocument();
    const free = screen.getByRole("link", { name: /create an account/i });
    expect(free).toHaveAttribute("href", "/signup");
  });

  it("defaults to ANNUAL with the billed-annually qualifier and real totals", () => {
    render(<PricingTable />);
    // Annual effective-monthly headline rates by default…
    expect(screen.getByText(usd(PRICING.pro.annualPerMonth))).toBeInTheDocument();
    expect(screen.getByText(usd(PRICING.premium.annualPerMonth))).toBeInTheDocument();
    // …never bare: each carries "billed annually ($99/yr)" from the shared helper.
    expect(screen.getByText(new RegExp(esc(billedAnnuallyNote(PRICING.pro))))).toBeInTheDocument();
    expect(screen.getByText(new RegExp(esc(billedAnnuallyNote(PRICING.premium))))).toBeInTheDocument();
    // No monthly sticker anywhere in the default view.
    expect(screen.queryByText(usd(PRICING.pro.monthly))).not.toBeInTheDocument();
    expect(screen.queryByText(usd(PRICING.premium.monthly))).not.toBeInTheDocument();
  });

  it("keeps monthly one click away and shows it consistently", () => {
    render(<PricingTable />);
    fireEvent.click(screen.getByRole("button", { name: /monthly/i }));
    expect(screen.getByText(usd(PRICING.pro.monthly))).toBeInTheDocument();
    expect(screen.getByText(usd(PRICING.premium.monthly))).toBeInTheDocument();
    // The annual effective rate never lingers on the monthly view.
    expect(screen.queryByText(usd(PRICING.pro.annualPerMonth))).not.toBeInTheDocument();
  });

  it("keeps the plan cards and the comparison header on ONE toggle state", () => {
    // The /pricing page wraps both in BillingPeriodProvider — this is the
    // regression test for the pre-decision screen where cards said $9.99
    // while the always-annual comparison header said $8.25.
    render(
      <BillingPeriodProvider>
        <PricingTable />
        <ComparisonTable />
      </BillingPeriodProvider>,
    );
    // Default: annual everywhere — card + header both show $8.25, no $9.99.
    expect(screen.getAllByText(usd(PRICING.pro.annualPerMonth)).length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(usd(PRICING.pro.monthly))).not.toBeInTheDocument();
    // Flip to monthly: both surfaces flip together.
    fireEvent.click(screen.getByRole("button", { name: /monthly/i }));
    expect(screen.getAllByText(usd(PRICING.pro.monthly)).length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(usd(PRICING.premium.monthly)).length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(usd(PRICING.pro.annualPerMonth))).not.toBeInTheDocument();
    expect(screen.queryByText(usd(PRICING.premium.annualPerMonth))).not.toBeInTheDocument();
  });

  it("shows a sales contact line for B2B / lifetime instead of a third row of cards", () => {
    // Anchor cards (Team / Enterprise / Lifetime) were retired 2026-05-04
    // for visual cleanup — sales-curious buyers email instead.
    render(<PricingTable />);
    expect(screen.getByText(/sales@tapeline\.io/i)).toBeInTheDocument();
  });

  it("states the card-required trial as a mechanism, not just a label", () => {
    // The trial takes a card, so the disclosure has to say WHAT is charged
    // and WHEN — $0 today, first charge when the trial ends — plus a real, unpunished
    // way out. A vague "free trial" label here would be the exact failure
    // this test exists to catch.
    const { container } = render(<PricingTable />);
    const text = (container.textContent ?? "").replace(/\s+/g, " ");
    expect(
      screen.getByText(
        new RegExp(`${TRIAL_DAYS}-day Premium trial — \\$0 today`, "i"),
      ),
    ).toBeInTheDocument();
    // CHANGED by #683. This block used to open "A new account adds a card at
    // first sign-in, and that starts the trial" — the first half described a
    // wall that no longer exists, and stating it here would tell a reader the
    // scanner is unreachable without paying. The second half is the part that
    // was always the point: a card is what starts the trial.
    expect(text).toMatch(/card[^.]{0,30}starts the trial/i);
    expect(text).not.toMatch(/(?:adds|adding) a card at first sign-in/i);
    expect(text).toMatch(
      new RegExp(`day ${TRIAL_DAYS}, at the plan and billing period you picked`, "i"),
    );
    // The way out is a link to the free public record, not a dead sentence.
    expect(screen.getByRole("link", { name: /public record/i })).toHaveAttribute(
      "href",
      "/scorecard",
    );
  });

  it("advertises one-click cancel with no survey gate", () => {
    render(<PricingTable />);
    expect(screen.getByText(/Cancel in one click/i)).toBeInTheDocument();
    expect(screen.getByText(/No survey to complete/i)).toBeInTheDocument();
  });

  it("sells the Free PLAN at $0, and keeps the account-free record visible beside it", () => {
    // REWRITTEN for #683. The old invariant was "every line in the $0 column
    // must be reachable with NO ACCOUNT", which was right while the column
    // described only the published record. The column is now a plan, so the
    // invariant moves with it: every line must be reachable on a FREE ACCOUNT,
    // which costs an email and a password and no card. The account-free record
    // did not stop existing — it moved to the footnote, and this test pins it
    // there so it can never be quietly dropped in favour of the plan.
    const { container } = render(<PricingTable />);
    const text = (container.textContent ?? "").replace(/\s+/g, " ");

    // The plan: what the account actually gets.
    expect(screen.getByText(/an email and a password\. no card\./i)).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`the top ${FREE_LIMITS.scannerRows} scored rows`, "i")),
    ).toBeInTheDocument();
    expect(screen.getByText(/one saved screen/i)).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`${FREE_LIMITS.watchlistTickers}-ticker watchlist`, "i")),
    ).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(`${FREE_LIMITS.dailyLookups} ticker look-ups a day`, "i")),
    ).toBeInTheDocument();

    // The record, still stated as needing no account at all.
    expect(text).toMatch(/signing up takes an email and a password, no card/i);
    expect(text).toMatch(/stays open with no account at all/i);
    expect(text).toMatch(/the daily top 10/i);
    expect(text).toMatch(/raw csv\/json/i);
  });

  it("never advertises a card-free TRIAL, and never promises permanence", () => {
    // REWRITTEN by #683. This list used to ban every card-free claim about an
    // ACCOUNT, because a new account met a card wall — "start free" and
    // "signing up asks for an email and a password" were on it, and both are
    // now literally what happens. Banning them would be policing the truth.
    //
    // What is still worth catching is a growth edit that moves card-free
    // wording ONE noun across, from the account to the trial. The trial takes
    // a card; that is the whole reason the disclosure block above exists.
    const { container } = render(<PricingTable />);
    const text = (container.textContent || "").replace(/\s+/g, " ");
    // Windows stop at a sentence break or a `·` separator, so honest copy that
    // states both facts in one breath ("no card to sign up; a card starts the
    // trial") reads clean, while "no card needed to start your trial" does not.
    expect(text).not.toMatch(/\btrial\b[^.;·]{0,30}(?:no|without a) (?:credit )?card/i);
    expect(text).not.toMatch(/(?:no|without a) (?:credit )?card[^.;·]{0,28}\btrial\b/i);
    expect(text).not.toMatch(/card[-\s]free trial/i);
    expect(text).not.toMatch(/no credit card required/i);
    // And no promise the product cannot keep. A free tier is a decision that
    // can be revisited, and the app does ask for a card at a cap — so neither
    // "forever" nor "never" belongs on a plan card.
    expect(text.toLowerCase()).not.toContain("free forever");
    expect(text.toLowerCase()).not.toContain("never asks for a card");
    // The grandfather clause ("accounts created before 22 August 2026 keep the
    // free access they signed up for") is deliberately NOT asserted any more.
    // It was a promise to one cohort while the wall split the userbase in two;
    // with the wall gone every account has that access, and requiring the
    // sentence here would keep implying a distinction that no longer exists.
  });

  // ── Open-access month note (backend tier.py free_open_access, #523) ──────
  // One factual line on the $0 column while the promo window runs. It
  // describes a SIGNED-IN entitlement, so it lives in the footnote area —
  // never in the highlights list, whose lines must all be account-free.
  describe("open-access month note", () => {
    const DURING = new Date("2026-08-23T12:00:00Z");
    const CUTOFF = new Date("2026-09-08T00:00:00Z");

    it("carries the factual promo line while the window runs", () => {
      render(<PricingTable now={DURING} />);
      const note = screen.getByText(/open-access month/i);
      const text = note.textContent || "";
      expect(text).toMatch(/until 8 September/i);
      // The honest mechanism: sign in, rows-only lift, real numbers.
      expect(text).toMatch(/signing in to a free account/i);
      expect(text).toMatch(/top\s+10/i);
      expect(text).toMatch(/1,000 rows/);
      expect(text).toMatch(/the same as\s+Pro/i);
    });

    it("drops the line at the backend cutoff instant (d < UNTIL mirror)", () => {
      render(<PricingTable now={CUTOFF} />);
      expect(screen.queryByText(/open-access month/i)).toBeNull();
    });

    it("keeps the promo line free of urgency and of promises it can't keep", () => {
      render(<PricingTable now={DURING} />);
      const text = (screen.getByText(/open-access month/i).textContent || "").toLowerCase();
      expect(text).not.toMatch(
        /hurry|act now|last chance|limited time|countdown|only \d+ (left|remaining)/i,
      );
      // "no card" and "start free" left this list with #683 — a free account
      // really is an email and a password now, so the promo line is allowed to
      // say so. The permanence promise and the banned marketing phrase stay
      // out, and a temporary row-cap lift must never be sold as a free tier
      // that outlives it.
      for (const banned of ["free forever", "no credit card required"]) {
        expect(text).not.toContain(banned);
      }
    });
  });

  it("states the refund guarantee from the REFUND single source of truth", () => {
    render(<PricingTable />);
    expect(screen.getByText(REFUND.short)).toBeInTheDocument();
  });

  it("states payment security as a plain fact, not a badge", () => {
    // Deliberately NOT a shield/seal: the claim has to be something the
    // reader can verify (the card form is on Stripe's domain) rather than a
    // security assertion Tapeline makes about itself.
    render(<PricingTable />);
    expect(
      screen.getByText(/Card details are entered on Stripe’s own checkout page/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/never reaches a Tapeline server/i),
    ).toBeInTheDocument();
  });

  it("discloses the charge currency before the redirect", () => {
    // Currency is stated on OUR page so checkout.stripe.com can't surprise.
    // With no API reachable in jsdom the hook keeps its currency-only default
    // sourced from PRICING.currency — and says nothing at all about tax,
    // which is the safe direction when the tax posture is unconfirmed.
    render(<PricingTable />);
    expect(
      screen.getByText(new RegExp(`Charged in ${PRICING.currency}`, "i")),
    ).toBeInTheDocument();
    expect(screen.queryByText(/No tax is added/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Tax may be added/i)).not.toBeInTheDocument();
  });

  it("explains the money-back mechanism at the annual decision point", () => {
    // Annual buyers commit 12 months up front — the useful reassurance is the
    // procedure and the timing, not a seal. Window derives from REFUND.
    render(<PricingTable />);
    expect(
      screen.getByText(new RegExp(`within ${REFUND.windowDays} days of your first charge`, "i")),
    ).toBeInTheDocument();
    expect(screen.getByText(/no form and\s+no reason required/i)).toBeInTheDocument();
    // Monthly view drops it — the annual commitment is what warrants it.
    fireEvent.click(screen.getByRole("button", { name: /monthly/i }));
    expect(
      screen.queryByText(new RegExp(`within ${REFUND.windowDays} days of your first charge`, "i")),
    ).not.toBeInTheDocument();
  });
});
