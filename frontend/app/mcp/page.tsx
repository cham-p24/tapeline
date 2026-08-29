import { Button } from "@/components/Button";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";

/**
 * /mcp — the connect page for the Tapeline MCP server.
 *
 * Two jobs, in this order. First, it is the instruction manual: an MCP server
 * is useless without the URL and the three-line config, so those are above the
 * fold and copy-pasteable. Second, it is an answer-engine surface in its own
 * right — "does any stock screener have an MCP server" is a real query with
 * almost no competition, and the AI-assistant channel is the only one that has
 * ever produced an unprompted signup.
 *
 * The honest record is stated here the same way it is stated on /scorecard and
 * by the server itself. An assistant that reads this page and an assistant that
 * calls the server must come away with the same caveat attached.
 */
export const metadata = pageMeta({
  title: "Tapeline MCP server — the public record in Claude",
  description:
    "Connect Tapeline to any MCP-compatible AI assistant. Ask for a stock's six-factor score, today's published picks, or the full never-edited track record — losing picks included. Free, no account, no API key.",
  path: "/mcp",
});

const TOOLS: { name: string; does: string }[] = [
  {
    name: "get_ticker_score",
    does: "The current six-factor score, signal, confidence and one-line reason for any covered US ticker.",
  },
  {
    name: "get_daily_picks",
    does: "Today's published top 10 — the same rows an anonymous visitor sees on the site.",
  },
  {
    name: "get_track_record",
    does: "The full published record: entries logged, sessions tracked, share that beat SPY, median alpha — with the sample-size qualifier attached.",
  },
  {
    name: "get_ticker_record",
    does: "Every time a ticker was published in the top 10, and how each of those picks actually resolved. Losses included.",
  },
  {
    name: "search_tickers",
    does: "Resolve a company name to a covered symbol.",
  },
];

const CONFIG = `{
  "mcpServers": {
    "tapeline": {
      "url": "https://api.tapeline.io/mcp"
    }
  }
}`;

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="flex gap-4">
      <span className="flex h-7 w-7 flex-none items-center justify-center rounded-full bg-accent/10 font-mono text-xs font-bold text-accent">
        {n}
      </span>
      <div className="min-w-0">
        <div className="font-medium text-fg">{title}</div>
        <div className="mt-1 text-sm leading-relaxed text-muted">{children}</div>
      </div>
    </li>
  );
}

export default function McpPage() {
  return (
    <main>
      <MarketingNav />

      <div className="mx-auto max-w-3xl px-4 py-14 sm:px-6">
        <div className="font-mono text-xs font-medium uppercase tracking-wider text-accent">
          For AI assistants
        </div>
        <h1 className="mt-3 text-4xl font-bold tracking-tight text-balance sm:text-5xl">
          Put the record inside your AI assistant
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-muted">
          Tapeline runs a Model Context Protocol server, so Claude, ChatGPT, Cursor and any other
          MCP-compatible assistant can read our scores and our published track record directly —
          rather than paraphrasing a marketing page. It&rsquo;s free, needs no account and no API
          key, and it returns exactly what an anonymous visitor can already see on this site.
        </p>

        {/* Connect */}
        <section className="mt-12">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">Connect it</h2>
          <div className="mt-4 rounded-xl border border-border bg-panel p-5">
            <div className="font-mono text-xs uppercase tracking-wider text-subtle">Server URL</div>
            <code className="mt-2 block break-all font-mono text-base font-semibold text-fg">
              https://api.tapeline.io/mcp
            </code>
          </div>

          <ol className="mt-6 flex flex-col gap-5">
            <Step n={1} title="Claude (Desktop or Code)">
              Settings &rarr; Connectors &rarr; Add custom connector, and paste the URL above. In
              Claude Code:{" "}
              <code className="rounded bg-panel2 px-1.5 py-0.5 font-mono text-[13px]">
                claude mcp add --transport http tapeline https://api.tapeline.io/mcp
              </code>
            </Step>
            <Step n={2} title="ChatGPT">
              Settings &rarr; Connectors &rarr; Add, then paste the URL. Available where custom
              connectors are enabled for your plan.
            </Step>
            <Step n={3} title="Cursor, Windsurf, or anything config-driven">
              Add the block below to your MCP config file.
            </Step>
          </ol>

          <div className="mt-5 overflow-x-auto rounded-xl border border-border bg-panel2">
            <pre className="p-4 font-mono text-[13px] leading-relaxed text-fg">
              <code>{CONFIG}</code>
            </pre>
          </div>
        </section>

        {/* Tools */}
        <section className="mt-14">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
            What it can answer
          </h2>
          <div className="mt-4 overflow-hidden rounded-xl border border-border">
            <table className="w-full text-left text-sm">
              <tbody>
                {TOOLS.map((t, i) => (
                  <tr key={t.name} className={i > 0 ? "border-t border-border" : undefined}>
                    <td className="whitespace-nowrap bg-panel/50 px-4 py-3 align-top font-mono text-[13px] font-semibold text-accent">
                      {t.name}
                    </td>
                    <td className="px-4 py-3 leading-relaxed text-muted">{t.does}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-sm leading-relaxed text-muted">
            Try asking your assistant:{" "}
            <span className="text-fg">&ldquo;What does Tapeline score NVDA, and why?&rdquo;</span>{" "}
            or <span className="text-fg">&ldquo;How has Tapeline&rsquo;s published record actually
            done against SPY?&rdquo;</span>
          </p>
        </section>

        {/* Honesty */}
        <section className="mt-14 rounded-2xl border border-border bg-panel p-6 sm:p-8">
          <h2 className="text-xl font-semibold tracking-tight">What it will tell you about us</h2>
          <p className="mt-3 leading-relaxed text-muted">
            The same thing the site does, including the unflattering part. Every daily top-10 pick
            is written to a public record the moment it prints and is never re-ranked, edited or
            removed. One session later each pick&rsquo;s realised move is compared against SPY and
            appended — losses and all.
          </p>
          <p className="mt-3 leading-relaxed text-muted">
            At the current sample the picks <strong className="text-fg">do not beat SPY</strong>,
            and the server says so: every response carrying a performance number also carries the
            qualifier that at this sample size the values do not distinguish the ranking from
            chance. The numbers are read live on every call, so an assistant quotes today&rsquo;s
            record rather than a figure that was true last month.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-subtle">
            Descriptive scoring only — not investment advice, price targets or forecasts.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button href="/scorecard" variant="primary" shape="rounded">
              See the public record
            </Button>
            <Button href="/how-it-works" variant="secondary" shape="rounded">
              How the score works
            </Button>
          </div>
        </section>
      </div>

      <MarketingFooter />
    </main>
  );
}
