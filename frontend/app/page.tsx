import Link from "next/link";
import { ScannerPreview } from "@/components/ScannerPreview";

export default function LandingPage() {
  return (
    <main className="min-h-screen">
      {/* Nav */}
      <nav className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <div className="h-2 w-6 rounded-full bg-accent" />
            <span className="text-lg font-semibold tracking-tight">Tapeline</span>
          </div>
          <div className="flex items-center gap-5">
            <Link href="/how-it-works" className="hidden text-sm text-muted hover:text-fg sm:inline">How it works</Link>
            <Link href="/scorecard" className="hidden text-sm text-muted hover:text-fg sm:inline">Scorecard</Link>
            <Link href="/pricing" className="hidden text-sm text-muted hover:text-fg sm:inline">Pricing</Link>
            <Link href="/signin" className="hidden text-sm text-muted hover:text-fg sm:inline">Sign in</Link>
            <Link href="/signup" className="btn-primary">Start free</Link>
          </div>
        </div>
      </nav>

      {/* Hero + product preview in one fold */}
      <section className="mx-auto max-w-6xl px-6 pt-16 pb-12">
        <div className="grid gap-10 lg:grid-cols-5 lg:gap-8">
          {/* Left: copy */}
          <div className="lg:col-span-2">
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-panel px-3 py-1 text-xs text-muted">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-up" />
              Live market scanning
            </div>
            <h1 className="mt-6 text-5xl font-bold tracking-tight sm:text-6xl">
              A scanner that
              <br />
              <span className="text-accent">shows its work.</span>
            </h1>
            <p className="mt-6 text-lg text-muted">
              Six factors with the exact weights published. One plain-English sentence on every ticker, every row.
              Every call we make goes on a permanent public record — same day.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/signup" className="btn-primary text-base">Start 14-day trial &rarr;</Link>
              <Link href="/scorecard" className="btn-ghost text-base">See the record</Link>
            </div>
            <p className="mt-3 text-xs text-muted">14-day Premium trial · no credit card · cancel in one click</p>
          </div>

          {/* Right: product preview */}
          <div className="lg:col-span-3">
            <ScannerPreview />
            <p className="mt-3 text-center text-xs text-muted">
              Every ticker scored on 6 factors · hover any score in the app for the full breakdown
            </p>
          </div>
        </div>
      </section>

      {/* Trust bar — 3 points, tight */}
      <section className="border-y border-border bg-panel/50">
        <div className="mx-auto grid max-w-6xl gap-3 px-6 py-5 text-center text-xs text-muted sm:grid-cols-3">
          <div>🔬 Powered by Polygon.io licensed data</div>
          <div>📈 Every pick on the <Link href="/scorecard" className="text-accent hover:underline">public scorecard</Link></div>
          <div>⚠️ Informational only — <Link href="/legal/risk" className="text-accent hover:underline">not investment advice</Link></div>
        </div>
      </section>

      {/* How it works — 3 steps */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="text-3xl font-bold tracking-tight">How it works</h2>
        <p className="mt-2 text-muted">From data to decision in one glance.</p>

        <div className="mt-10 grid gap-6 md:grid-cols-3">
          <Step n="1" title="Six factors, exact weights">
            Trend 25% · relative strength 20% · fundamentals 15% · smart money 15% · macro 15% · momentum 10%.
            Weights are public. Every change is announced before it ships.
          </Step>
          <Step n="2" title="One sentence per ticker">
            Default plain-English Why on every row — no chat session required, no premium gate.
            Hover the score for the factor breakdown.
          </Step>
          <Step n="3" title="Every call on the public record">
            Top-10 picks logged daily to the <Link href="/scorecard" className="text-accent">public scorecard</Link>{" "}
            with the original reasoning preserved. Performance vs SPY recorded next session. No cherry-picking, no hindsight edits.
          </Step>
        </div>

        <div className="mt-8 text-center">
          <Link href="/how-it-works" className="text-sm text-accent hover:underline">
            See the exact weights and methodology →
          </Link>
        </div>
      </section>

      {/* Final CTA */}
      <section className="mx-auto max-w-4xl px-6 pt-10 pb-20 text-center">
        <h2 className="text-4xl font-bold tracking-tight">Stop scrolling. Start scanning.</h2>
        <p className="mt-4 text-muted">14 days free · No credit card · Cancel in one click</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/signup" className="btn-primary text-base">
            Open the live scanner &rarr;
          </Link>
          <Link href="/pricing" className="btn-ghost text-base">
            See pricing
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <div className="flex flex-wrap items-center justify-between gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="h-2 w-6 rounded-full bg-accent" />
              <span className="font-semibold">Tapeline</span>
            </div>
            <div className="flex flex-wrap gap-5 text-xs text-muted">
              <Link href="/how-it-works" className="hover:text-fg">How it works</Link>
              <Link href="/pricing" className="hover:text-fg">Pricing</Link>
              <Link href="/scorecard" className="hover:text-fg">Scorecard</Link>
              <Link href="/changelog" className="hover:text-fg">Changelog</Link>
              <Link href="/roadmap" className="hover:text-fg">Roadmap</Link>
              <Link href="/legal/terms" className="hover:text-fg">Terms</Link>
              <Link href="/legal/privacy" className="hover:text-fg">Privacy</Link>
              <Link href="/legal/risk" className="hover:text-fg">Risk</Link>
            </div>
          </div>

          <p className="mt-6 text-xs leading-relaxed text-muted">
            <strong className="text-fg">⚠ Not investment advice.</strong>{" "}
            Tapeline is a quantitative data analysis tool. Scores and signals are informational
            only and do not constitute buy or sell recommendations. Past performance does not
            indicate future results. Trading securities involves substantial risk of loss.
            Consult a licensed financial advisor before making investment decisions.
          </p>
          <p className="mt-3 text-xs text-muted">&copy; {new Date().getFullYear()} Tapeline. All rights reserved.</p>
        </div>
      </footer>
    </main>
  );
}

function Step({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <div className="card p-6">
      <div className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-accent/10 font-mono text-sm font-bold text-accent">
        {n}
      </div>
      <h3 className="mt-4 text-lg font-semibold">{title}</h3>
      <p className="mt-2 text-sm text-muted leading-relaxed">{children}</p>
    </div>
  );
}

