"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { canonicalMatchup, type CompareGroup } from "@/lib/comparePairs";

/**
 * The curated head-to-heads on /compare, one card per theme, with a filter.
 *
 * Every link is in the server-rendered HTML: the filter starts empty, so the
 * first render — the one crawlers and no-JS readers get — lists every pair.
 * These are the SEO pages of the stock-vs-stock cluster; a test pins that the
 * full set of hrefs is present.
 */

type Pair = { a: string; b: string };
type Group = CompareGroup & { pairs: Pair[] };

function matches(pair: Pair, q: string, names: Record<string, string>): boolean {
  const upper = q.toUpperCase();
  const lower = q.toLowerCase();
  return [pair.a, pair.b].some(
    (s) => s.startsWith(upper) || (names[s] ?? "").toLowerCase().includes(lower),
  );
}

export function CompareDirectory({
  groups,
  names,
}: {
  groups: Group[];
  names: Record<string, string>;
}) {
  const [query, setQuery] = useState("");
  const q = query.trim();
  const total = groups.reduce((n, g) => n + g.pairs.length, 0);

  const visible = useMemo(() => {
    if (!q) return groups;
    return groups
      .map((g) => {
        // A theme-name hit keeps the whole theme ("banks" → every bank pair).
        if (g.label.toLowerCase().includes(q.toLowerCase())) return g;
        return { ...g, pairs: g.pairs.filter((p) => matches(p, q, names)) };
      })
      .filter((g) => g.pairs.length > 0);
  }, [groups, names, q]);

  const shown = visible.reduce((n, g) => n + g.pairs.length, 0);

  return (
    <div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="w-full sm:max-w-sm">
          <label htmlFor="compare-filter" className="block text-[11px] font-semibold uppercase tracking-wider text-subtle">
            Filter matchups
          </label>
          <div className="relative mt-1.5">
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-subtle"
            >
              <circle cx="7" cy="7" r="4.75" stroke="currentColor" strokeWidth="1.5" />
              <path d="m10.5 10.5 3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <input
              id="compare-filter"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ticker, company or theme"
              autoComplete="off"
              spellCheck={false}
              className="h-10 w-full rounded-xl border border-border2 bg-background pl-9 pr-3 text-sm text-fg placeholder:text-subtle focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
            />
          </div>
        </div>
        <p className="nums text-xs text-muted" aria-live="polite">
          {q ? `${shown} of ${total} matchups` : `${total} matchups · ${groups.length} themes`}
        </p>
      </div>

      <nav aria-label="Jump to a theme" className="mt-4 flex flex-wrap gap-1.5">
        {visible.map((g) => (
          <a
            key={g.id}
            href={`#${g.id}`}
            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-panel px-3 py-1 text-xs text-muted transition-colors hover:border-accent/50 hover:text-fg"
          >
            {g.label}
            <span className="nums rounded-full bg-panel2 px-1.5 text-[10px] text-subtle">{g.pairs.length}</span>
          </a>
        ))}
      </nav>

      {visible.length === 0 ? (
        <div className="mt-6 rounded-2xl border border-dashed border-border2 px-6 py-10 text-center">
          <p className="text-sm font-medium">No curated matchup for &ldquo;{q}&rdquo;.</p>
          <p className="mt-1 text-sm text-muted">
            The picker at the top of the page compares any two tickers, listed here or not.
          </p>
        </div>
      ) : (
        <div className="mt-6 space-y-5">
          {visible.map((g) => (
            <ThemeCard key={g.id} group={g} names={names} />
          ))}
        </div>
      )}
    </div>
  );
}

function ThemeCard({ group, names }: { group: Group; names: Record<string, string> }) {
  const headingId = `${group.id}-heading`;
  return (
    <section
      id={group.id}
      aria-labelledby={headingId}
      className="scroll-mt-28 rounded-2xl border border-border bg-panel p-4 sm:p-6"
    >
      <div className="grid gap-5 lg:grid-cols-[15rem_minmax(0,1fr)] lg:gap-8">
        <div className="min-w-0">
          <div className="flex items-start justify-between gap-3 lg:block">
            <div>
              <h3 id={headingId} className="text-lg font-semibold tracking-tight">
                {group.label}
              </h3>
              <p className="mt-0.5 text-sm text-muted">{group.blurb}</p>
            </div>
            <span className="nums mt-0.5 shrink-0 rounded-full border border-border bg-panel2 px-2.5 py-0.5 text-[11px] text-muted lg:mt-3 lg:inline-block">
              {group.pairs.length} {group.pairs.length === 1 ? "matchup" : "matchups"}
            </span>
          </div>
          <ul className="mt-3 flex flex-wrap gap-1.5 lg:mt-4 lg:flex-col lg:gap-1" aria-label={`${group.label} tickers`}>
            {group.symbols.map((s) => (
              <li key={s}>
                <Link
                  href={`/t/${s}`}
                  className="group inline-flex items-baseline gap-2 rounded-md border border-border bg-background px-2 py-0.5 text-xs transition-colors hover:border-accent/50 lg:border-transparent lg:bg-transparent lg:px-0 lg:py-0"
                >
                  <span className="font-mono font-semibold text-fg lg:inline-block lg:w-12">{s}</span>
                  <span className="hidden truncate text-muted group-hover:text-fg lg:inline">{names[s] ?? ""}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>

        {/* Two columns even on a phone: one row per pair made the full list
            ~9,000px tall at 375px wide. */}
        <ul className="grid grid-cols-2 content-start gap-2 xl:grid-cols-3">
          {group.pairs.map(({ a, b }) => {
            const slug = canonicalMatchup(a, b);
            return (
              <li key={slug}>
                <Link
                  href={`/compare/${slug}`}
                  className="group flex h-full items-center justify-between gap-2 rounded-xl border border-border bg-background px-3 py-2 transition-colors hover:border-accent/50 hover:bg-accent/5 sm:gap-3 sm:px-3.5 sm:py-2.5"
                >
                  <span className="min-w-0">
                    <span className="flex items-baseline gap-1 font-mono text-[13px] font-semibold text-fg sm:gap-1.5 sm:text-sm">
                      {a}
                      <span className="font-sans text-[10px] font-medium uppercase tracking-wider text-subtle">vs</span>
                      {b}
                    </span>
                    <span className="mt-0.5 block truncate text-[11px] text-muted sm:text-xs">
                      {names[a] ?? a} · {names[b] ?? b}
                    </span>
                  </span>
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 16 16"
                    fill="none"
                    aria-hidden="true"
                    className="hidden shrink-0 text-subtle transition-transform group-hover:translate-x-0.5 group-hover:text-accent sm:block"
                  >
                    <path d="M6 3.5 10.5 8 6 12.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
