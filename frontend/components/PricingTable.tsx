"use client";

import Link from "next/link";
import { Button } from "@/components/Button";
// FREE_LIMITS is read again (#683): the $0 column describes a real logged-in
// Free plan once more, so its numbers must come from the shared constants
// rather than be retyped here — that retyping is exactly how the Free column
// drifted from the backend last time.
import {
  PRICING,
  REFUND,
  annualSaving,
  billedAnnuallyNote,
  freeOpenAccess,
  PRO_SCANNER_ROWS,
  FREE_LIMITS,
} from "@/lib/pricing";
import { BillingToggle, useBillingPeriod } from "@/components/BillingToggle";
import { BestValueBadge } from "@/components/BestValueBadge";
import { useChargeDisclosure, chargeDisclosureLine } from "@/lib/chargeDisclosure";

const PLANS = [
  {
    // ── The $0 column, restated again (#683, 2026-08-30) ───────────────────
    // History, because this column has now been rewritten twice and the next
    // person deserves to know why. Before 22 August it was "Free — free
    // forever" with a "Start free" button. The card gate then made a self-serve
    // free tier untrue, so the column was narrowed to the PUBLIC RECORD: the
    // one $0 thing that survived, and an honest column rather than a false one.
    //
    // #683 moved the card ask off the front door, and the honest column is now
    // wider than it was in either previous state. A visitor signs up with an
    // email and a password, lands on Free, and runs live scans. So the column
    // goes back to being a PLAN — but it keeps the public-record bullets,
    // because those remain reachable with no account at all and are the only
    // lines here a reader can verify before trusting us with an address.
    //
    // The bullets are ordered logged-in-first, then the no-account record, and
    // the footnote draws the line between them. Every number comes from
    // FREE_LIMITS so this column cannot drift from tier.py by hand again.
    name: "Free",
    tagline: "An email and a password. No card.",
    prices: { monthly: 0, annual: 0, annualPerMonth: 0 },
    highlights: [
      `The live scanner — the top ${FREE_LIMITS.scannerRows} scored rows of any scan`,
      "One saved screen, re-run whenever you open it",
      `A ${FREE_LIMITS.watchlistTickers}-ticker watchlist`,
      `${FREE_LIMITS.dailyLookups} ticker look-ups a day`,
      "The full scorecard — every pick, back-checked vs SPY",
      // Not "the scoring formula, named and weighted" — PR #342 deliberately
      // stripped the numbers. What /how-it-works publishes is the factor set
      // plus the weight ORDERING, and this bullet may promise no more.
      "The six scoring factors, named and ranked by weight",
    ],
    cta: "Create an account",
    ctaHref: "/signup",
    skipBillingParam: true,
    highlight: false,
    // Two facts a reader wants in this order: what the sign-up costs them
    // (nothing, and no card), and what is readable before they sign up at all.
    // The second is the more persuasive one, so it is not buried.
    footnote:
      "Signing up takes an email and a password, no card. The public record — the daily Top 10, the whole scorecard, a page per scored ticker and the raw CSV/JSON — stays open with no account at all.",
    // Marks the card that carries the date-gated open-access note below. The
    // note describes a SIGNED-IN entitlement, so it stays out of the highlights
    // list, which mixes signed-in lines with no-account ones and would blur the
    // two if the promo were folded in.
    openAccessNote: true,
  },
  {
    name: "Pro",
    tagline: "Live scanner. Daily edge.",
    prices: {
      monthly: PRICING.pro.monthly,
      annual: PRICING.pro.annual,
      annualPerMonth: PRICING.pro.annualPerMonth,
    },
    highlights: [
      "Unlimited ticker look-ups",
      "Real-time, full ~2,000-ticker scanner",
      "Score + plain-English Why on every row",
      "Squeeze Watch · Regime · Heatmap",
      "IPOs · Earnings · News calendars",
      "Watchlist (50) with smart alerts",
      "Email alerts (10/day) · daily briefing",
      "TradingView charts · CSV export",
    ],
    cta: "Start 30-day Premium trial",
    ctaHref: "/signup?plan=pro",
    // Pro is the highlighted protagonist — the realistic first purchase.
    // "Best value" is a factual framing (cheapest paid tier per feature),
    // not manufactured social proof; with zero customers a "Most popular"
    // badge would be fabricated. Matches the Pro badge on ComparisonTable.
    highlight: true,
    badge: "Best value",
  },
  {
    name: "Premium",
    tagline: "The full surface — for the serious operator.",
    prices: {
      monthly: PRICING.premium.monthly,
      annual: PRICING.premium.annual,
      annualPerMonth: PRICING.premium.annualPerMonth,
    },
    // Premium-only additions on top of everything in Pro. Rendered in a
    // visually distinct block under the price so the upgrade reason is
    // obvious — not buried in a 7-bullet list that looks like Pro's.
    // Styled as the power tier (darker, quieter) — no popularity badge.
    proPlus: true,
    highlights: [
      "Congressional trades feed (House + Senate)",
      "Recent insider buys — live SEC Form 4 across ~2,000 tickers",
      "Email alerts · unlimited (Pro: 10/day)",
      "Public API access · 1,000 requests/day",
      "Watchlist 200 · saved scans 100 (Pro: 50 · 10)",
      "Priority support · same-day reply",
    ],
    cta: "Start 30-day Premium trial",
    ctaHref: "/signup?plan=premium",
    highlight: false,
  },
  {
    name: "Trader",
    tagline: "Early access — for desks & power users.",
    prices: {
      monthly: PRICING.trader.monthly,
      annual: PRICING.trader.annual,
      annualPerMonth: PRICING.trader.annualPerMonth,
    },
    // Concierge / early-access tier — NOT self-serve. The differentiators are
    // built with early customers, so the CTA is "Talk to us" (→ /contact), not
    // a Stripe checkout. Its price is the high anchor that reframes Premium as
    // the sensible choice. No proPlus strip (that hardcodes "Everything in
    // Pro"); the first highlight states "Everything in Premium" instead.
    highlights: [
      "Everything in Premium",
      // "Your full track record + per-factor attribution" removed 2026-09-02:
      // that is the PER-USER watchlist record, held dark pending item 3 of
      // docs/launch/LAWYER_CONSULT_EMAIL.md. Selling a feature that is switched
      // off at every tier is the kind of claim the copy linter exists to stop.
      "Per-factor attribution on every score",
      "Get your data out — API, bulk export & webhooks",
      "Desk-grade watchlists, scans & alerts",
      "A hand in what we build next",
    ],
    cta: "Talk to us",
    ctaHref: "/contact",
    highlight: false,
  },
];

export function PricingTable({ now }: { now?: Date } = {}) {
  // ANNUAL is the default (founder decision 2026-07-18) — monthly stays one
  // click away. State lives in the shared BillingPeriod context so the
  // ComparisonTable header on the same page can never disagree with these
  // cards; standalone renders fall back to the same annual default.
  const { billing, setBilling } = useBillingPeriod();
  // Open-access month (backend tier.py free_open_access, mirrored in
  // lib/pricing.ts): while the window runs, a SIGNED-IN Free account's
  // scanner row cap lifts from the top 10 to the Pro cap. Date-gated so the
  // note vanishes from 8 September with no code change; `now` is injectable
  // for tests, mirroring the backend's `today` argument.
  const openAccess = freeOpenAccess(now ?? new Date());
  // What Stripe will actually take, derived from the live Price object plus
  // the session kwargs the backend sends — never a hardcoded guess. Falls
  // back to the PRICING.currency constant and stays silent about tax until
  // the server confirms it.
  const disclosure = useChargeDisclosure();

  return (
    <div>
      {/* Billing toggle — drives the page-wide shared billing period */}
      <div className="flex justify-center">
        <BillingToggle billing={billing} setBilling={setBilling} />
      </div>
      {/* Currency + tax, stated here rather than discovered on
          checkout.stripe.com. "Unexpected cost at the payment step" is the
          top documented abandonment cause; this is the answer to it. */}
      <p className="mt-3 text-center text-xs text-muted">
        {chargeDisclosureLine(disclosure)}
      </p>
      {billing === "annual" && (
        <p className="mt-1 text-center text-xs text-up/90">Save 2 months · your rate, locked in</p>
      )}

      {/* Plans — Free / Pro / Premium self-serve, plus the Trader early-access
          anchor. 2-up on tablet, 4-up on desktop. */}
      <div className="mx-auto mt-10 grid max-w-6xl gap-4 sm:grid-cols-2 lg:grid-cols-4 md:gap-6">
        {PLANS.map((p) => {
          const price = p.prices[billing];
          // Annual advertises the exact per-month equivalent from
          // lib/pricing.ts ($99/yr → $8.25/mo; $199/yr → $16.58/mo).
          // Monthly stays as-is.
          const perMonth = billing === "annual" ? p.prices.annualPerMonth : price;
          const isPower = (p as { proPlus?: boolean }).proPlus === true;
          // The Free column has no billing period to carry — there is nothing
          // to bill — so its CTA goes to a bare /signup rather than picking up
          // a ?billing= param that would be meaningless on arrival.
          const ctaHref = (p as { skipBillingParam?: boolean }).skipBillingParam
            ? p.ctaHref
            : p.ctaHref.includes("?")
            ? `${p.ctaHref}&billing=${billing}`
            : `${p.ctaHref}?billing=${billing}`;
          return (
            <div
              key={p.name}
              className={`relative rounded-2xl p-6 sm:p-8 transition-all ${
                p.highlight
                  ? "border border-accent/60 bg-gradient-to-b from-accent/10 via-panel to-panel shadow-lg shadow-accent/20"
                  : isPower
                  ? "bg-gradient-to-b from-panel2/60 via-panel to-panel shadow-md"
                  : "bg-panel shadow-sm"
              }`}
            >
              {p.highlight && p.badge && (
                <BestValueBadge className="absolute -top-3 left-1/2 -translate-x-1/2" />
              )}
              <h3 className="text-xl font-semibold">{p.name}</h3>
              <p className="mt-1 text-sm text-muted">{p.tagline}</p>
              <div className="mt-6">
                <div className="flex items-baseline gap-1.5">
                  <span className="text-5xl font-bold nums tracking-tight">
                    {price === 0 ? "$0" : `$${perMonth.toFixed(2)}`}
                  </span>
                  <span className="text-muted">/ month</span>
                </div>
                {/* An annual per-month figure never renders without the
                    explicit billed-annually qualifier + the real total. */}
                {billing === "annual" && price > 0 && (
                  <p className="mt-1.5 text-xs text-muted">
                    {billedAnnuallyNote(p.prices)} · save ${annualSaving(p.prices)}/yr
                  </p>
                )}
                {billing === "monthly" && price > 0 && (
                  <p className="mt-1.5 text-xs text-muted">billed monthly</p>
                )}
              </div>

              {/* Premium card: "Everything in Pro" anchor strip above the
                  bullets so the upgrade reason is the additions, not "look
                  here's a duplicate of the Pro list". */}
              {isPower && (
                <div className="mt-6 flex items-center gap-2 rounded-md bg-panel2/40 px-3 py-2 text-xs text-muted">
                  <svg className="h-3.5 w-3.5 text-up flex-shrink-0" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                    <path d="M3 8l3 3 7-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span>Everything in Pro</span>
                  <span className="ml-auto text-accent font-medium">+ all of:</span>
                </div>
              )}
              <ul className={`${isPower ? "mt-3" : "mt-6"} space-y-2.5 text-sm`}>
                {p.highlights.map((f) => (
                  <li key={f} className="flex gap-3">
                    <svg className="mt-0.5 h-4 w-4 flex-shrink-0 text-up" viewBox="0 0 16 16" fill="none">
                      <path d="M3 8l3 3 7-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              {(p as { footnote?: string }).footnote && (
                <p className="mt-4 text-xs text-muted leading-relaxed">
                  {(p as { footnote?: string }).footnote}
                </p>
              )}
              {/* Open-access month — one factual line under the Free column,
                  qualifying the row cap the bullet above states. The lift is
                  rows-only and signed-in-only (tier.py limit()): no lifted
                  look-ups, no Pro features, nothing for anonymous callers — so
                  the copy says exactly that and nothing more. It is deliberately
                  NOT folded into the bullet: the bullet describes the plan,
                  which outlives the promo. Factual end date only; no urgency
                  (Rule 6). */}
              {(p as { openAccessNote?: boolean }).openAccessNote && openAccess && (
                <p className="mt-3 text-xs leading-relaxed text-accent/90">
                  Open-access month: until 8 September, signing in to a free
                  account lifts the scanner cap from the top{" "}
                  {FREE_LIMITS.scannerRows} to the full list &mdash; up to{" "}
                  {PRO_SCANNER_ROWS.toLocaleString("en-US")} rows, the same as
                  Pro.
                </p>
              )}
              <Button
                href={ctaHref}
                variant={p.highlight ? "gradient" : "secondary"}
                shape="rounded"
                className="mt-8 w-full"
              >
                {p.cta}
              </Button>
            </div>
          );
        })}
      </div>

      {/* ── The trial, stated plainly ─────────────────────────────────────
          The Premium trial takes a card (Stripe Checkout, subscription mode
          with trial_end), so the honest thing is not a risk-reversal badge —
          it is the mechanism: what Stripe takes today, what it takes on day
          14, and the one button that stops it. Cancellation is genuinely one
          click (POST /api/billing/cancel, no survey gate).

          2026-08-30 (#683): the skip exists again. This paragraph's last
          sentence once read "Skip the trial and you stay on Free, which never
          asks for a card", was cut when the card moved to first sign-in, and is
          true once more — so it is restored, but as a mechanism rather than a
          reassurance, and naming BOTH ways of not paying: the free plan (an
          account, no card) and the public record (no account either). They suit
          different readers and neither substitutes for the other.
          What must never soften is the first sentence: the trial itself takes a
          card. Sign-up being card-free does not make the trial card-free, and
          the two sit one line apart here.
          No urgency, no deadline, no scarcity. */}
      <div className="mx-auto mt-10 grid max-w-3xl gap-3 sm:grid-cols-2">
        <div className="rounded-lg bg-panel/60 px-4 py-3">
          <div className="text-xs font-medium text-fg">30-day Premium trial — $0 today</div>
          <p className="mt-1 text-xs text-muted leading-relaxed">
            Adding a card is what starts the trial &mdash; nothing before it does.
            Stripe charges $0 that day and shows you the exact first-charge date
            before you confirm: day 14, at the plan and billing period you picked.
            One click stops it before that date and you are charged nothing. If you
            would rather not put a card down, you don&rsquo;t have to: the free plan
            runs without one, and the{" "}
            <Link href="/scorecard" className="text-accent hover:underline">
              public record
            </Link>{" "}
            is open with no account at all.
          </p>
        </div>
        <div className="rounded-lg bg-panel/60 px-4 py-3">
          <div className="text-xs font-medium text-fg">Cancel in one click</div>
          <p className="mt-1 text-xs text-muted leading-relaxed">
            One button on your billing page. No survey to complete, no email to
            send, no retention call. You keep access until the end of the period
            you already paid for.
          </p>
        </div>
      </div>

      {/* Remaining commitments — the two that aren't risk reversals. */}
      <div className="mx-auto mt-4 flex max-w-3xl flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-muted">
        <span>{REFUND.short}</span>
        <span className="text-subtle">·</span>
        <span>Founding pricing — locked in for early subscribers</span>
      </div>

      {/* ── Money-back as a MECHANISM, at the annual decision point ────────
          An annual buyer is committing 12 months up front, so the useful thing
          is not a seal — it's knowing exactly what to do, and how long it
          takes. Every number derives from the REFUND constant in lib/pricing
          (itself single-sourced from /legal/refund) so the window can never
          drift from the policy it summarises. */}
      {billing === "annual" && (
        <div className="mx-auto mt-6 max-w-2xl rounded-lg bg-panel/60 px-5 py-4">
          <div className="text-xs font-medium text-fg">
            How the {REFUND.short.toLowerCase()} actually works
          </div>
          <p className="mt-1.5 text-xs text-muted leading-relaxed">
            Email support@tapeline.io from your account address within{" "}
            {REFUND.windowDays}{" "}days of your first charge — there is no form and
            no reason required. We process it within 3 business days, and Stripe
            returns the money to the card or wallet you paid with, which usually
            lands in 3&ndash;10 business days depending on your bank. Annual
            plans get a {REFUND.annual}; monthly plans get a {REFUND.monthly}.{" "}
            <Link href={REFUND.policyPath} className="text-accent hover:underline">
              Full policy
            </Link>
            .
          </p>
        </div>
      )}

      {/* Payment security, in plain language, at the point of card entry.
          Factual and verifiable: the card form is Stripe's, on Stripe's
          domain. No badges, no certification claims, no security promises of
          our own — we make none because we handle none of it. */}
      <p className="mx-auto mt-5 max-w-2xl text-center text-[11px] leading-relaxed text-subtle">
        Card details are entered on Stripe&rsquo;s own checkout page, not on
        Tapeline. Your card number never reaches a Tapeline server &mdash; we
        receive only the subscription status Stripe reports back.
      </p>

      {/* B2B / lifetime nudge — one line, no third row of cards.
          Curious enterprise buyers can email; everyone else stays focused
          on the three main tiers above. */}
      <p className="mx-auto mt-8 max-w-3xl text-center text-xs text-subtle">
        Need 5+ seats, custom SLA, or a one-time founder's lifetime? Email{" "}
        <a href="mailto:sales@tapeline.io" className="text-accent hover:underline">sales@tapeline.io</a>.
      </p>
    </div>
  );
}
