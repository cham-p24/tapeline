/**
 * /why — the signed, first-person page.
 *
 * This is the one page on the site written in a voice rather than in product
 * copy. It is signed under the founder's real name, which is already public on
 * /press (fact sheet + founder bio), so this discloses nothing new.
 *
 * ── WHAT MAY GO IN HERE ──────────────────────────────────────────────────
 * Only claims that are defensible from the public record:
 *   - solo founder, Melbourne — /press fact sheet
 *   - engine built 2025 as a personal system, public SaaS 2026 — /press bio
 *   - the scorecard publishes losing days — /scorecard
 *   - the record to date is around a coin flip on a small sample — /scorecard
 *   - factor set and weight ordering are published, exact weights are not
 *     — /how-it-works, PR #342
 *
 * NO origin-story embellishment. No "I lost money on a bad tip and swore
 * never again" narrative — that is unverifiable, and inventing biography on
 * the page whose entire premise is honesty is self-defeating. If a sentence
 * cannot be pointed at a public artefact, it does not belong here.
 *
 * NO performance claims, no implication that publishing the record makes the
 * record good. The pitch is the disclosure, never the outcome.
 */
import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { MethodologyCaveat } from "@/components/MethodologyCaveat";
import { pageMeta } from "@/lib/seo";
import { breadcrumbJsonLd, jsonLdScript } from "@/lib/jsonld";

export const metadata = pageMeta({
  title: "Why I Built a Scanner That Publishes Its Losing Days",
  description:
    "Christian Piyatilaka, solo founder of Tapeline, on why the methodology and the daily record are public — including the days the picks went nowhere. Written plainly, no hype.",
  path: "/why",
});

export default function WhyPage() {
  const breadcrumbs = breadcrumbJsonLd([
    { name: "Tapeline", url: "https://tapeline.io/" },
    { name: "Why", url: "https://tapeline.io/why" },
  ]);

  return (
    <main id="main" className="min-h-screen">
      <script {...jsonLdScript(breadcrumbs)} />
      <MarketingNav />

      <section className="section py-8 sm:py-10">
        <div className="mx-auto max-w-2xl">
          <p className="eyebrow">A note from the founder</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">
            Why I built a scanner that publishes its losing days
          </h1>
          <p className="mt-6 text-lg text-muted leading-relaxed">
            Most tools in this category will not tell you two things: what the
            formula is, and how it has actually done. I got tired of that, so I
            built the version that tells you both.
          </p>
        </div>
      </section>

      <section className="section pb-8">
        <div className="mx-auto max-w-2xl space-y-6 text-[0.95rem] leading-relaxed text-muted">
          <p>
            I&rsquo;m Christian Piyatilaka. I build Tapeline on my own, from
            Melbourne, Australia. There is no team behind this and no outside
            investment &mdash; if something on this site is wrong, I am the
            person who got it wrong.
          </p>

          <p>
            The scoring engine started in 2025 as a personal system, for me, and
            it still runs that way. Tapeline is that work opened up to other
            people in 2026. That order matters to how the product is built: it
            was a tool before it was a business, so the parts that are useful to
            somebody actually reading the output got attention long before the
            marketing did.
          </p>

          <h2 className="pt-4 text-xl font-semibold text-fg">
            The two things that are usually hidden
          </h2>

          <p>
            When I was shopping for tools, the pattern was consistent enough to
            be funny. A scanner would tell me a stock scored 94 out of 100, and
            when I went looking for what produced the 94, I would find either
            nothing at all or a page describing a proprietary process in language
            carefully arranged to say very little. Then I would go looking for a
            record &mdash; any record &mdash; of how the tool&rsquo;s output had
            done over time, and find a testimonial page.
          </p>

          <p>
            Those two absences are related. If nobody can see the method and
            nobody can see the record, then the number is unfalsifiable, and an
            unfalsifiable number is a marketing asset rather than an analytical
            one. I did not want to buy that, and I am not going to sell it.
          </p>

          <h2 className="pt-4 text-xl font-semibold text-fg">
            So: the method is named, and the record is published
          </h2>

          <p>
            All six factors are named, and each one has its own page explaining
            what it measures, how the reading is derived, what data feeds it,
            and where it falls down &mdash;{" "}
            <Link href="/how-it-works/trend" className="link">
              Trend
            </Link>
            ,{" "}
            <Link href="/how-it-works/relative-strength" className="link">
              Relative Strength
            </Link>
            ,{" "}
            <Link href="/how-it-works/fundamentals" className="link">
              Fundamentals
            </Link>
            ,{" "}
            <Link href="/how-it-works/smart-money" className="link">
              Smart Money
            </Link>
            ,{" "}
            <Link href="/how-it-works/macro" className="link">
              Macro
            </Link>{" "}
            and{" "}
            <Link href="/how-it-works/momentum" className="link">
              Momentum
            </Link>
            . I publish which factors count for more than others. I do not
            publish the exact numeric weights or the equation, and I want to be
            straight about why rather than dress it up: that specific piece is
            the part a competitor could copy in an afternoon. You get the
            mechanism, the ordering, each factor&rsquo;s contribution on every
            ticker, and the full record. You do not get the constants.
          </p>

          <p>
            The record is the{" "}
            <Link href="/scorecard" className="link">
              public scorecard
            </Link>
            . Every daily top-10 is written down and checked against what
            happened next, and the days that went nowhere are on the page in the
            same styling as the days that went well. Nothing is removed after the
            fact. When the method changes, the change is dated in the{" "}
            <Link href="/changelog" className="link">
              changelog
            </Link>{" "}
            and past entries stay as they were recorded.
          </p>

          <MethodologyCaveat label="What the record currently shows">
            The honest summary is that the sample is small and the result so far
            is close to a coin flip. It sat below an even split for weeks. I am
            not going to describe that as anything better than it is, and if it
            improves later I still will not put the number in a headline &mdash;
            the presentation was designed while the figure was unflattering,
            deliberately, so that it stays the same when it is not. The numbers
            are on the scorecard with the sample size next to them.
          </MethodologyCaveat>

          <h2 className="pt-4 text-xl font-semibold text-fg">
            What this is, and what it is not
          </h2>

          <p>
            Tapeline is descriptive analytics. It reads published data, applies
            the same six measurements to every US-listed ticker it covers, and
            shows you what those measurements came out as. It is a way to narrow
            a very long list down to something a person can actually look at.
          </p>

          <p>
            It is not advice, and I am not a licensed adviser. It does not know
            anything about you &mdash; and by design it never will, because
            Tapeline does not ask for your portfolio, your capital, your
            experience or your goals in any form on this site. A score is not a
            recommendation, a six-factor screen is a blunt instrument compared
            with reading a company properly, and the honest list of what this
            product is bad at is on{" "}
            <Link href="/limitations" className="link">
              limitations
            </Link>
            . I would rather you read that page before you pay for anything.
          </p>

          <p>
            If you find something wrong &mdash; a number that does not
            reconcile, a factor page that has drifted from what the product
            actually does, a scorecard entry that looks off &mdash; email{" "}
            <a href="mailto:support@tapeline.io" className="link">
              support@tapeline.io
            </a>
            . Corrections get logged in the changelog with a date, including the
            ones that are embarrassing.
          </p>

          <div className="mt-10 border-t border-border pt-6">
            <p className="text-sm font-semibold text-fg">Christian Piyatilaka</p>
            <p className="mt-1 text-xs text-subtle">
              Founder, Tapeline &middot; Melbourne, Australia
            </p>
            <p className="mt-3 text-xs text-subtle">
              More background on the{" "}
              <Link href="/about" className="link">
                about page
              </Link>{" "}
              and the{" "}
              <Link href="/press" className="link">
                press kit
              </Link>
              .
            </p>
          </div>
        </div>
      </section>

      <TransparencyStrip />
      <MarketingFooter />
    </main>
  );
}
