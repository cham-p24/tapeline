import { Button } from "@/components/Button";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { ScoreRadial } from "@/components/ScoreRadial";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "What's new in Tapeline — MCP server, open access, more",
  description:
    "The latest Tapeline upgrades: a public MCP server for AI assistants, embeddable score badges, ticker pages rebuilt as a decision aid, a card-backed Premium trial, and the ranked scanner open on Free until 8 September.",
  path: "/whats-new",
});

/* ── Feature scaffold ─────────────────────────────────────────────────────── */

function FeatureRow({
  where,
  title,
  body,
  mock,
  flip,
}: {
  where: string;
  title: string;
  body: React.ReactNode;
  mock: React.ReactNode;
  flip?: boolean;
}) {
  return (
    <section className="mt-14 grid items-center gap-8 md:mt-20 md:grid-cols-2">
      <div className={flip ? "md:order-2" : undefined}>
        <div className="font-mono text-xs font-medium uppercase tracking-wider text-accent">
          Where · {where}
        </div>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-balance sm:text-[26px]">
          {title}
        </h2>
        <p className="mt-3 leading-relaxed text-muted">{body}</p>
      </div>
      <div className={flip ? "md:order-1" : undefined}>
        <Frame>{mock}</Frame>
      </div>
    </section>
  );
}

/** A soft window frame so each mock reads as a piece of the product. */
function Frame({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-background shadow-[0_18px_50px_-30px_rgba(0,0,0,0.6)]">
      <div className="flex items-center gap-1.5 border-b border-border/70 px-3 py-2">
        <span className="h-2.5 w-2.5 rounded-full bg-border2" />
        <span className="h-2.5 w-2.5 rounded-full bg-border2" />
        <span className="h-2.5 w-2.5 rounded-full bg-border2" />
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

/* ── Mocks ────────────────────────────────────────────────────────────────── */

function McpMock() {
  const tools = [
    "get_ticker_score",
    "get_daily_picks",
    "get_track_record",
    "get_ticker_record",
    "search_tickers",
  ];
  return (
    <div>
      <pre className="overflow-x-auto rounded-lg border border-border bg-panel px-3 py-2.5 font-mono text-[11px] leading-relaxed text-muted">
        {`{ "mcpServers": { "tapeline": {
    "url": "https://api.tapeline.io/mcp"
} } }`}
      </pre>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {tools.map((t) => (
          <span
            key={t}
            className="rounded-full border border-border bg-panel/40 px-2 py-0.5 font-mono text-[10px] text-muted"
          >
            {t}
          </span>
        ))}
      </div>
      <div className="mt-2 font-mono text-[10px] text-subtle">
        free · no account · no API key
      </div>
    </div>
  );
}

function EmbedMock() {
  return (
    <div className="mx-auto max-w-[280px]">
      <div className="rounded-lg border border-border bg-panel/40 p-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-sm font-semibold">NVDA</span>
          <span className="font-mono text-2xl font-bold text-up">91</span>
        </div>
        <div className="mt-1 text-[10px] uppercase tracking-wider text-subtle">
          Tapeline Score · live
        </div>
        <div className="mt-2 border-t border-border/60 pt-1.5 text-[9px] text-subtle">
          Powered by tapeline.io
        </div>
      </div>
      <pre className="mt-2 overflow-x-auto rounded border border-border bg-panel px-2 py-1.5 font-mono text-[10px] text-muted">
        {`![Score](tapeline.io/badge/NVDA)`}
      </pre>
    </div>
  );
}

function TickerDecisionMock() {
  const stats: [string, string, string][] = [
    ["Score", "91", "97th pctile · Info Tech (n=148)"],
    ["Trend", "88", "90th pctile · Info Tech (n=148)"],
    ["Momentum", "85", "86th pctile · Info Tech (n=143)"],
  ];
  return (
    <div className="flex items-center gap-4">
      <div className="shrink-0">
        <ScoreRadial
          trend={88}
          rs={92}
          fundamentals={74}
          smart_money={61}
          macro={70}
          momentum={85}
          score={91}
          size={120}
          showLabels={false}
        />
      </div>
      <div className="min-w-0 flex-1 space-y-1.5">
        {stats.map(([k, v, ctx]) => (
          <div key={k} className="rounded border border-border/70 bg-panel/40 px-2.5 py-1.5">
            <div className="flex items-baseline justify-between gap-2 text-xs">
              <span className="text-muted">{k}</span>
              <span className="font-mono font-semibold">{v}</span>
            </div>
            <div className="font-mono text-[9px] text-subtle">{ctx}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TrialMock() {
  const rows: [string, string][] = [
    ["Due today", "$0.00"],
    ["First charge", "day 14 · the plan you pick"],
    ["Reminder email", "three days before"],
  ];
  return (
    <div className="mx-auto max-w-[300px] space-y-1.5">
      {rows.map(([k, v]) => (
        <div
          key={k}
          className="flex items-center justify-between rounded border border-border/70 bg-panel/40 px-3 py-2 text-xs"
        >
          <span className="text-muted">{k}</span>
          <span className="font-mono font-medium">{v}</span>
        </div>
      ))}
      <div className="rounded border border-border/70 bg-panel/40 px-3 py-2 text-center text-xs text-muted">
        Cancel in one click — first screen, no hoops
      </div>
    </div>
  );
}

function OpenAccessMock() {
  const rows: [string, string, string][] = [
    ["11", "PLTR", "78"],
    ["247", "ONTO", "64"],
    ["893", "CRVL", "52"],
  ];
  return (
    <div>
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] text-subtle">Scanner · Free plan</span>
        <span className="rounded-full border border-accent/40 bg-accent/10 px-2 py-0.5 text-[10px] font-medium text-accent">
          until 8 September
        </span>
      </div>
      <div className="mt-2 space-y-1.5">
        {rows.map(([n, s, v]) => (
          <div
            key={s}
            className="flex items-center gap-3 rounded border border-border/70 bg-panel/40 px-2.5 py-1.5 text-xs"
          >
            <span className="w-8 text-right font-mono text-subtle">#{n}</span>
            <span className="font-mono font-semibold">{s}</span>
            <span className="ml-auto font-mono text-up">{v}</span>
          </div>
        ))}
      </div>
      <div className="mt-2 text-center font-mono text-[10px] text-subtle">
        1,000 ranked rows · was top 10
      </div>
    </div>
  );
}

function SearchMock() {
  const rows = [
    { sym: "NVDA", name: "NVIDIA Corp", tag: "91", tone: "text-up" },
    { sym: "AAPL vs MSFT", name: "head-to-head", tag: "Compare", tone: "text-muted" },
    { sym: "Watchlist", name: "your saved tickers", tag: "Go to", tone: "text-muted" },
  ];
  return (
    <div>
      <div className="flex items-center gap-2 rounded-lg border border-border bg-panel px-3 py-2.5 text-sm text-muted">
        <svg width="15" height="15" viewBox="0 0 18 18" fill="none" aria-hidden="true">
          <circle cx="8" cy="8" r="5.25" stroke="currentColor" strokeWidth="1.6" />
          <path d="M12 12l3.5 3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        Search any ticker, or “AAPL vs MSFT”…
        <span className="ml-auto rounded bg-panel2 px-1.5 py-0.5 font-mono text-[10px]">⌘K</span>
      </div>
      <ul className="mt-2 divide-y divide-border/60">
        {rows.map((r, i) => (
          <li
            key={r.sym}
            className={`flex items-center justify-between gap-3 px-1 py-2.5 text-sm ${i === 0 ? "rounded-md bg-panel" : ""}`}
          >
            <span>
              <span className="font-mono font-semibold">{r.sym}</span>
              <span className="ml-2 text-muted">{r.name}</span>
            </span>
            <span className={`font-mono text-xs ${r.tone}`}>{r.tag}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SidebarMock() {
  const groups: { label: string; items: { name: string; active?: boolean }[] }[] = [
    { label: "Trade", items: [{ name: "Scanner", active: true }, { name: "Watchlist" }, { name: "Alerts" }] },
    { label: "Signals", items: [{ name: "Heatmap" }, { name: "Squeeze" }, { name: "Regime" }] },
  ];
  return (
    <div className="flex min-h-[220px] gap-0 overflow-hidden rounded-lg border border-border">
      <aside className="w-36 shrink-0 space-y-3 border-r border-border bg-panel/40 p-2.5">
        <div className="flex items-center gap-1.5 px-1">
          <span className="h-1.5 w-4 rounded-full bg-accent" />
          <span className="text-xs font-semibold">Tapeline</span>
        </div>
        {groups.map((g) => (
          <div key={g.label}>
            <div className="px-1.5 pb-1 font-mono text-[9px] uppercase tracking-wider text-subtle">{g.label}</div>
            <div className="space-y-0.5">
              {g.items.map((it) => (
                <div
                  key={it.name}
                  className={`rounded px-1.5 py-1 text-xs ${it.active ? "bg-accent/10 font-medium text-fg" : "text-muted"}`}
                >
                  {it.name}
                </div>
              ))}
            </div>
          </div>
        ))}
      </aside>
      <div className="flex-1">
        <div className="flex items-center gap-2 border-b border-border px-3 py-2 text-xs text-muted">
          <span className="rounded border border-border bg-panel px-2 py-1">🔍 Search any ticker</span>
        </div>
        <div className="space-y-1.5 p-3">
          {[["NVDA", "91"], ["AMD", "84"], ["AVGO", "82"]].map(([s, v]) => (
            <div key={s} className="flex items-center justify-between rounded border border-border/70 bg-panel/40 px-2.5 py-1.5 text-xs">
              <span className="font-mono font-semibold">{s}</span>
              <span className="font-mono text-up">{v}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CompareMock() {
  const cards = [
    { sym: "NVDA", score: 91, tone: "text-up" },
    { sym: "AMD", score: 84, tone: "text-up" },
  ];
  return (
    <div>
      <div className="font-mono text-[11px] text-subtle">Compare › NVDA vs AMD</div>
      <div className="mt-2 grid grid-cols-2 gap-3">
        {cards.map((c) => (
          <div key={c.sym} className="rounded-lg border border-border bg-panel/40 p-3 text-center">
            <div className="font-mono text-xs text-muted">{c.sym}</div>
            <div className={`mt-1 font-mono text-3xl font-bold ${c.tone}`}>{c.score}</div>
            <div className="text-[10px] uppercase tracking-wider text-subtle">/ 100</div>
          </div>
        ))}
      </div>
      <div className="mt-3 space-y-1.5">
        {[["Trend", 88, 72], ["Relative strength", 92, 80], ["Momentum", 85, 78]].map(([f, a, b]) => (
          <div key={f as string} className="flex items-center justify-between gap-3 text-[11px]">
            <span className="w-28 text-muted">{f}</span>
            <span className="font-mono text-up">{a}</span>
            <span className="flex-1" />
            <span className="font-mono text-up">{b}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SavedScreensMock() {
  return (
    <div className="mx-auto max-w-[240px]">
      <div className="rounded-lg border border-border bg-panel/40 p-3">
        <div className="px-1 pb-1 font-mono text-[9px] uppercase tracking-wider text-subtle">Saved screens</div>
        {["High-momentum small caps", "Value + rising estimates", "Insider buying, top scores"].map((s, i) => (
          <div key={s} className={`rounded px-2 py-1.5 text-xs ${i === 0 ? "bg-accent/10 text-fg" : "text-muted"}`}>
            {s}
          </div>
        ))}
      </div>
      <div className="mt-2 text-center font-mono text-[10px] text-subtle">shareable link · one click to load</div>
    </div>
  );
}

function AlertsMock() {
  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <span className="rounded-full border border-up/40 bg-up/10 px-3 py-1 text-xs font-medium text-up">Email alerts</span>
        <span className="rounded-full border border-accent/40 bg-accent/10 px-3 py-1 text-xs font-medium text-accent">Browser push</span>
      </div>
      <div className="rounded-lg border border-border bg-panel/40 p-3 text-xs">
        <div className="font-mono font-semibold">NVDA · score crossed 90</div>
        <div className="mt-1 text-muted">Delivered to email &amp; push · descriptive, not advice.</div>
      </div>
    </div>
  );
}

/* ── Page ─────────────────────────────────────────────────────────────────── */

export default function WhatsNewPage() {
  return (
    <main>
      <MarketingNav />

      <div className="mx-auto max-w-5xl px-4 py-14 sm:px-6">
        {/* Hero */}
        <div className="max-w-2xl">
          <div className="font-mono text-xs font-medium uppercase tracking-wider text-accent">What&rsquo;s new</div>
          <h1 className="mt-3 text-4xl font-bold tracking-tight text-balance sm:text-5xl">
            The record, in more places
          </h1>
          <p className="mt-4 text-lg leading-relaxed text-muted">
            The latest round: a public MCP server so AI assistants can read the record directly,
            embeddable score badges, ticker pages rebuilt as a decision aid, a clearer card-backed
            trial, and the ranked scanner open on the Free plan until 8 September. Same transparent
            six-factor scores and the same public record behind everything; here&rsquo;s what changed
            and where to find it.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button href="/signup" variant="primary" shape="rounded">
              Open Tapeline &rarr;
            </Button>
            <Button href="/changelog" variant="secondary" shape="rounded">
              Full changelog
            </Button>
          </div>
        </div>

        {/* Features — latest wave */}
        <FeatureRow
          where="tapeline.io/mcp — Claude, ChatGPT, or any MCP client"
          title="Ask your AI assistant for the record"
          body={
            <>
              Tapeline now runs a <strong className="text-fg">public MCP server</strong> at
              api.tapeline.io/mcp. Connect it and your assistant can pull a ticker&rsquo;s six-factor
              score, today&rsquo;s published top 10, and the full never-edited track record — losing
              picks included — through five public tools. Free, no account, no API key; setup
              instructions at tapeline.io/mcp.
            </>
          }
          mock={<McpMock />}
        />

        <FeatureRow
          flip
          where="tapeline.io/embed"
          title="A live score badge you can embed anywhere"
          body={
            <>
              Drop a live Tapeline Score into a blog post, Substack or GitHub README. Two flavours:
              an <strong className="text-fg">iframe widget</strong> for web pages and an{" "}
              <strong className="text-fg">SVG badge</strong> at tapeline.io/badge/&#123;TICKER&#125;
              that renders in GitHub markdown. Free, no auth, no API key — it shows the same score
              the site does.
            </>
          }
          mock={<EmbedMock />}
        />

        <FeatureRow
          where="any ticker page in the app"
          title="Ticker pages rebuilt as a decision aid"
          body={
            <>
              Every ticker page now carries <strong className="text-fg">key statistics</strong> —
              market cap, 52-week range, relative volume, earnings date and more — and places the
              score in context: the composite and all six factors are{" "}
              <strong className="text-fg">ranked against sector peers</strong>, with the peer group
              and its size printed next to every percentile. When there are too few peers to rank,
              the page says so instead of guessing. A{" "}
              <strong className="text-fg">six-factor radar</strong> shows the shape of the score at a
              glance, and the ticker&rsquo;s own published record — every time it appeared in a daily
              top 10 and how each entry resolved, losses included — sits on the same page.
            </>
          }
          mock={<TickerDecisionMock />}
        />

        <FeatureRow
          flip
          where="first sign-in, for accounts created from 22 August"
          title="The 14-day Premium trial now takes card details up front"
          body={
            <>
              A new account adds a card at first sign-in and starts the 14-day Premium trial:{" "}
              <strong className="text-fg">$0 charged today</strong>, first charge on day 14 at the
              plan you pick. We email you <strong className="text-fg">three days before</strong> that
              charge, and cancelling is one click on the first screen — cancel before day 14 and you
              are never charged. Existing accounts are unchanged, and the published record stays free
              to read with no account.
            </>
          }
          mock={<TrialMock />}
        />

        <FeatureRow
          where="the scanner, on the Free plan"
          title="Open-access month: the ranked scanner, open on Free"
          body={
            <>
              Until <strong className="text-fg">8 September</strong>, signed-in Free accounts see{" "}
              <strong className="text-fg">1,000 ranked scanner rows</strong> instead of the top 10 —
              the same row cap the paid plans use. On 8 September the cap simply returns to the top
              10; nothing else about the Free plan changes.
            </>
          }
          mock={<OpenAccessMock />}
        />

        {/* Features — early-August navigation wave */}
        <div className="mt-20 border-t border-border/60 pt-10">
          <div className="font-mono text-xs font-medium uppercase tracking-wider text-subtle">
            Earlier in August · navigation
          </div>
        </div>

        <FeatureRow
          where="the search bar up top — or ⌘K / Ctrl-K anywhere"
          title="Search anything, instantly"
          body={
            <>
              Jump straight to any ticker by <strong className="text-fg">symbol or company name</strong>,
              now across the full ~2,500-stock universe — on desktop and mobile. Type two symbols like
              &ldquo;AAPL MSFT&rdquo; to open a head-to-head, or start typing a page to jump there.
            </>
          }
          mock={<SearchMock />}
        />

        <FeatureRow
          flip
          where="the left sidebar, across the whole app"
          title="A cleaner way to navigate"
          body={
            <>
              The app moved to a tidy <strong className="text-fg">left sidebar</strong> with grouped
              sections and clear highlighting of where you are — so the scanner, watchlist, alerts and
              signals are always one click away, on any screen size.
            </>
          }
          mock={<SidebarMock />}
        />

        <FeatureRow
          where="Compare in the top nav, or tapeline.io/compare"
          title="Stock-vs-stock, head to head"
          body={
            <>
              A new <strong className="text-fg">Compare hub</strong> puts two tickers side by side on the
              same six-factor score, factor by factor — plus tool comparisons. Every matchup is
              descriptive and back-checked on the public scorecard.
            </>
          }
          mock={<CompareMock />}
        />

        <FeatureRow
          flip
          where="pinned in the sidebar, once you save a scan"
          title="Your screens, one click away"
          body={
            <>
              Save a scanner setup and it&rsquo;s <strong className="text-fg">pinned in the sidebar</strong> as
              its own destination — and each saved screen is a shareable link, so your recurring
              questions are always a click away.
            </>
          }
          mock={<SavedScreensMock />}
        />

        <FeatureRow
          where="the Alerts page"
          title="Alerts, simplified"
          body={
            <>
              We consolidated alerts onto the two channels people actually use —{" "}
              <strong className="text-fg">email</strong> and <strong className="text-fg">browser push</strong>.
              Same score, squeeze and regime triggers; if you&rsquo;d set up the retired Telegram channel,
              these two carry the same alerts.
            </>
          }
          mock={<AlertsMock />}
        />

        {/* Closing CTA */}
        <div className="mt-20 rounded-2xl border border-border bg-panel p-8 text-center">
          <h2 className="text-2xl font-semibold tracking-tight">See it for yourself</h2>
          <p className="mx-auto mt-2 max-w-md text-muted">
            The record is free to read with no account. The live scanner takes a card at
            first sign-in and starts a 14-day Premium trial &mdash; $0 today.
          </p>
          <Button href="/signup" variant="primary" shape="rounded" className="mt-6">
            Open Tapeline &rarr;
          </Button>
        </div>
      </div>

      <MarketingFooter />
    </main>
  );
}
