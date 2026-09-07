/**
 * /survey — the September 2026 customer survey.
 *
 * PUBLIC AND UNAUTHENTICATED, deliberately. Of 32 external accounts, 22 never
 * returned after their signup day and only 8 ever performed a real product
 * action. A sign-in wall in front of the one thing you are asking a dormant
 * person to do is asking them to do two things. It also keeps the promise the
 * recruiting email makes — the link is the same for everyone and does not
 * identify them (see backend/app/models/survey.py).
 *
 * `?a=` pre-selects the one-tap first question so the four options can be
 * clickable links in the email body. That is the single best-evidenced tactic
 * in the research behind this: a randomised trial (n = 4,333 vs 4,347) putting
 * the first question in the invitation raised completed surveys from 24.4% to
 * 29.1% — +19% relative, p<0.001 — without distorting the answer distribution.
 *
 * The value arrives as a SERVER prop, not via useSearchParams. `force-dynamic`
 * plus a thin server page plus a client form sibling is the pattern from the
 * 2026-09-06 incident (#759) where useSearchParams in a statically prerendered
 * page shipped only the Suspense fallback, so the signin and signup pages
 * served no form at all while ads were pointing at them.
 */
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";
import { SurveyForm } from "./SurveyForm";

export const dynamic = "force-dynamic";

// `pageMeta` has no noindex option, so robots is set alongside it. This page
// is for people who were emailed the link; it has no business in search
// results, and an indexed survey would collect responses from strangers whose
// answers are indistinguishable from customers' in a table with no user_id.
export const metadata = {
  ...pageMeta({
    title: "Tapeline — four questions",
    description:
      "A short survey for people with a Tapeline account. Four questions, about ninety seconds.",
    path: "/survey",
  }),
  robots: { index: false, follow: false },
};

export default async function SurveyPage({
  searchParams,
}: {
  // Next 16 made searchParams async — see app/search/page.tsx.
  searchParams: Promise<{ a?: string | string[] }>;
}) {
  const { a } = await searchParams;
  const initial = Array.isArray(a) ? a[0] : a;

  return (
    <>
      <MarketingNav />
      <main className="mx-auto max-w-2xl px-5 py-16">
        <h1 className="text-3xl font-semibold tracking-tight">Four questions</h1>
        <p className="mt-3 text-muted">
          About ninety seconds. Nothing here is required, and you can skip
          anything you'd rather not answer.
        </p>

        {/*
          This paragraph is load-bearing, not boilerplate. It sets the
          expectation that no money question is coming — which is both the
          honest position and the thing that stops someone volunteering their
          account size into a free-text box, where it would become a record the
          publisher exemption depends on not existing.
        */}
        <div className="mt-8 rounded-lg border border-border bg-surface/50 p-5 text-sm leading-relaxed text-muted">
          <p>
            I'm deliberately not asking anything about your money: not your
            account size, not what you hold, not how long you've been at this.
            Tapeline publishes general information and doesn't take anyone's
            circumstances into account, and that's not something I want to
            change by accident with a survey. If you type something like that
            into a box anyway, I'll leave it out of my notes.
          </p>
          <p className="mt-3">
            The link is the same for everyone, so it doesn't identify you. With
            a list this small I can sometimes guess who wrote what. I won't act
            on a guess, and I won't quote anyone anywhere without asking them
            first. Nothing you say here changes your account, your price, or
            what you get shown.
          </p>
        </div>

        <SurveyForm initialStatus={initial} />
      </main>
      <MarketingFooter />
    </>
  );
}
