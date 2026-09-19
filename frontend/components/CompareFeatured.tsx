"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import type { FeaturedMatchup, FeaturedSide } from "@/lib/compareFeatured";

/**
 * The featured head-to-head on /compare: two composites, an overlaid factor
 * radar and a factor-by-factor butterfly chart, for a handful of classic pairs.
 *
 * Every number comes from the server-side read in lib/compareFeatured.ts — this
 * component only lays them out. With no matchups it renders nothing at all.
 *
 * Language is descriptive (house rule, docs/COMPLIANCE_COPY_RULES.md): a side
 * "scores higher on" a factor or "carries the higher composite"; nothing here
 * calls a winner, and no side is framed as the one to own.
 */

const EMPTY = "—";

/** Whole-number display, matching the /compare/[matchup] page. */
function fmt(v: number | null): string {
  return v == null ? EMPTY : v.toFixed(0);
}

/** Compare on the DISPLAYED value, so "62 vs 62" never reads as a lead. */
function rounded(v: number | null): number | null {
  return v == null ? null : Math.round(v);
}

function pct(v: number): string {
  return `${Math.max(0, Math.min(100, v))}%`;
}

type Tone = "a" | "b";
const DOT: Record<Tone, string> = { a: "bg-accent", b: "bg-accent2" };
const FILL: Record<Tone, string> = { a: "bg-accent", b: "bg-accent2" };

export function CompareFeatured({ matchups }: { matchups: FeaturedMatchup[] }) {
  const [index, setIndex] = useState(0);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  if (matchups.length === 0) return null;

  const current = matchups[Math.min(index, matchups.length - 1)];
  const tabId = (i: number) => `featured-tab-${i}`;
  const panelId = "featured-panel";

  function focusTab(i: number) {
    const n = matchups.length;
    const next = (i + n) % n;
    setIndex(next);
    tabRefs.current[next]?.focus();
  }

  return (
    <section
      aria-labelledby="featured-heading"
      data-testid="compare-featured"
      className="overflow-hidden rounded-3xl border border-border bg-surface shadow-md"
    >
      <div className="flex flex-col gap-4 border-b border-border bg-gradient-to-r from-accent/10 via-transparent to-accent2/10 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="min-w-0">
          <p className="eyebrow">Featured head-to-head</p>
          <h2 id="featured-heading" className="mt-1 text-xl font-semibold tracking-tight sm:text-2xl">
            {current.a.symbol} <span className="text-muted">vs</span> {current.b.symbol}
          </h2>
        </div>
        {matchups.length > 1 && (
          <div
            role="tablist"
            aria-label="Featured matchups"
            className="grid grid-cols-2 gap-1 rounded-xl border border-border bg-panel p-1 sm:flex"
          >
            {matchups.map((m, i) => {
              const selected = m === current;
              return (
                <button
                  key={m.slug}
                  ref={(el) => {
                    tabRefs.current[i] = el;
                  }}
                  id={tabId(i)}
                  type="button"
                  role="tab"
                  aria-selected={selected}
                  aria-controls={panelId}
                  tabIndex={selected ? 0 : -1}
                  onClick={() => setIndex(i)}
                  onKeyDown={(e) => {
                    if (e.key === "ArrowRight") { e.preventDefault(); focusTab(i + 1); }
                    else if (e.key === "ArrowLeft") { e.preventDefault(); focusTab(i - 1); }
                    else if (e.key === "Home") { e.preventDefault(); focusTab(0); }
                    else if (e.key === "End") { e.preventDefault(); focusTab(matchups.length - 1); }
                  }}
                  className={`whitespace-nowrap rounded-lg px-3 py-1.5 font-mono text-xs transition-colors ${
                    selected
                      ? "bg-background font-semibold text-fg shadow-sm"
                      : "text-muted hover:text-fg"
                  }`}
                >
                  {m.a.symbol} · {m.b.symbol}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div
        role="tabpanel"
        id={panelId}
        aria-labelledby={matchups.length > 1 ? tabId(matchups.indexOf(current)) : "featured-heading"}
        className="p-4 sm:p-6"
      >
        <Matchup m={current} />
      </div>
    </section>
  );
}

function Matchup({ m }: { m: FeaturedMatchup }) {
  const { a, b } = m;
  const ra = rounded(a.score);
  const rb = rounded(b.score);
  const compositeLead = ra == null || rb == null || ra === rb ? null : ra > rb ? a : b;

  const higherA: string[] = [];
  const higherB: string[] = [];
  const level: string[] = [];
  a.factors.forEach((fa, i) => {
    const va = rounded(fa.value);
    const vb = rounded(b.factors[i]?.value ?? null);
    if (va == null || vb == null) return;
    if (va > vb) higherA.push(fa.label);
    else if (vb > va) higherB.push(fa.label);
    else level.push(fa.label);
  });

  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] lg:items-stretch">
        <SideCard side={a} tone="a" />
        <div className="hidden items-center justify-center lg:flex">
          <DualRadar a={a} b={b} />
        </div>
        <SideCard side={b} tone="b" />
      </div>

      <p className="mt-5 text-sm leading-relaxed text-muted">
        {compositeLead ? (
          <>
            <strong className="text-fg">{compositeLead.symbol}</strong> carries the higher composite
            score today ({fmt(a.score)} vs {fmt(b.score)}).
          </>
        ) : (
          <>
            {a.symbol} and {b.symbol} carry the same composite score today ({fmt(a.score)}).
          </>
        )}{" "}
        Here is how the six factors line up.
      </p>

      <Butterfly a={a} b={b} />

      <dl className="mt-5 grid gap-2 text-xs sm:grid-cols-3">
        <LeadGroup label={`Higher for ${a.symbol}`} tone="a" factors={higherA} />
        <LeadGroup label={`Higher for ${b.symbol}`} tone="b" factors={higherB} />
        <LeadGroup label="Level" factors={level} />
      </dl>

      <div className="mt-6 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs leading-relaxed text-subtle">
          Descriptive, rules-based scores — a reading, not a recommendation.
        </p>
        <Link
          href={`/compare/${m.slug}`}
          className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-border2 bg-background px-4 py-2.5 text-sm font-medium text-fg transition-colors hover:border-accent/60 hover:text-accent"
        >
          Full {a.symbol} vs {b.symbol} breakdown
          <span aria-hidden="true">&rarr;</span>
        </Link>
      </div>
    </>
  );
}

function SideCard({ side, tone }: { side: FeaturedSide; tone: Tone }) {
  const frame =
    tone === "a" ? "border-accent/25 bg-accent/5" : "border-accent2/25 bg-accent2/5";
  return (
    <div className={`min-w-0 rounded-2xl border p-4 sm:p-5 ${frame}`}>
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${DOT[tone]}`} aria-hidden="true" />
        <Link href={`/t/${side.symbol}`} className="font-mono text-sm font-semibold hover:underline">
          {side.symbol}
        </Link>
      </div>
      <p className="mt-1 truncate text-xs text-muted" title={side.name}>
        {side.name}
      </p>
      <div className="mt-4 flex items-baseline gap-1">
        <span className="nums text-4xl font-bold tracking-tight sm:text-5xl">{fmt(side.score)}</span>
        <span className="text-sm text-muted">/100</span>
      </div>
      <p className="mt-0.5 text-[11px] uppercase tracking-wider text-subtle">Composite score</p>
      <div className="mt-3 h-1.5 w-full rounded-full bg-panel2" aria-hidden="true">
        <div className={`h-full rounded-full ${FILL[tone]}`} style={{ width: pct(side.score) }} />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1">
        {side.signal && (
          <span className="rounded-full border border-border2 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted">
            {side.signal}
          </span>
        )}
        {side.sector && <span className="min-w-0 truncate text-xs text-subtle">{side.sector}</span>}
      </div>
    </div>
  );
}

function LeadGroup({ label, factors, tone }: { label: string; factors: string[]; tone?: Tone }) {
  return (
    <div className="rounded-xl border border-border bg-panel px-3 py-2.5">
      <dt className="flex items-center gap-1.5 font-medium text-muted">
        {tone && <span className={`h-2 w-2 rounded-full ${DOT[tone]}`} aria-hidden="true" />}
        {label}
      </dt>
      <dd className="mt-1 text-fg">{factors.length > 0 ? factors.join(", ") : EMPTY}</dd>
    </div>
  );
}

/**
 * Factor-by-factor butterfly: the first ticker's bars grow LEFT from the
 * centre line, the second's grow RIGHT. The side that scores higher on a factor
 * is drawn at full strength, the other muted. A factor with no reading is an
 * empty track and an em-dash — never a bar at zero.
 *
 * The chart is decorative for assistive tech; an sr-only table carries the same
 * numbers in reading order.
 */
function Butterfly({ a, b }: { a: FeaturedSide; b: FeaturedSide }) {
  return (
    <div className="mt-4 rounded-2xl border border-border bg-panel p-3 sm:p-4">
      <table className="sr-only">
        <caption>
          Factor scores out of 100 for {a.symbol} and {b.symbol}
        </caption>
        <thead>
          <tr>
            <th scope="col">Factor</th>
            <th scope="col">{a.symbol}</th>
            <th scope="col">{b.symbol}</th>
          </tr>
        </thead>
        <tbody>
          {a.factors.map((f, i) => (
            <tr key={f.key}>
              <th scope="row">{f.label}</th>
              <td>{fmt(f.value)}</td>
              <td>{fmt(b.factors[i]?.value ?? null)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div aria-hidden="true">
        <div className="grid grid-cols-[2rem_minmax(0,1fr)_minmax(0,1fr)_2rem] items-center gap-x-2 pb-2 text-[11px] font-semibold uppercase tracking-wider text-subtle sm:grid-cols-[2.5rem_minmax(0,1fr)_8.5rem_minmax(0,1fr)_2.5rem] sm:gap-x-3">
          <span />
          <span className="flex items-center justify-end gap-1.5 font-mono normal-case tracking-normal text-fg">
            {a.symbol}
            <span className={`h-2 w-2 rounded-full ${DOT.a}`} />
          </span>
          <span className="hidden text-center sm:block">Factor</span>
          <span className="flex items-center gap-1.5 font-mono normal-case tracking-normal text-fg">
            <span className={`h-2 w-2 rounded-full ${DOT.b}`} />
            {b.symbol}
          </span>
          <span />
        </div>
        <div className="space-y-2.5 sm:space-y-2">
          {a.factors.map((f, i) => {
            const va = f.value;
            const vb = b.factors[i]?.value ?? null;
            const ra = rounded(va);
            const rb = rounded(vb);
            const aLeads = ra != null && rb != null && ra > rb;
            const bLeads = ra != null && rb != null && rb > ra;
            return (
              <div
                key={f.key}
                className="grid grid-cols-[2rem_minmax(0,1fr)_minmax(0,1fr)_2rem] items-center gap-x-2 gap-y-1 sm:grid-cols-[2.5rem_minmax(0,1fr)_8.5rem_minmax(0,1fr)_2.5rem] sm:gap-x-3"
              >
                <span
                  className={`nums text-right text-sm ${aLeads ? "font-semibold text-fg" : "text-muted"}`}
                >
                  {fmt(va)}
                </span>
                <div className="flex h-2.5 justify-end rounded-full bg-panel2">
                  {va != null && (
                    <div
                      className={`h-full rounded-full ${FILL.a} ${bLeads ? "opacity-40" : ""}`}
                      style={{ width: pct(va) }}
                    />
                  )}
                </div>
                <span className="order-first col-span-4 text-center text-xs text-muted sm:order-none sm:col-span-1">
                  {f.label}
                </span>
                <div className="flex h-2.5 rounded-full bg-panel2">
                  {vb != null && (
                    <div
                      className={`h-full rounded-full ${FILL.b} ${aLeads ? "opacity-40" : ""}`}
                      style={{ width: pct(vb) }}
                    />
                  )}
                </div>
                <span className={`nums text-sm ${bLeads ? "font-semibold text-fg" : "text-muted"}`}>
                  {fmt(vb)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/**
 * Both tickers' six factors on one hexagonal radar. Same absence contract as
 * components/ScoreRadial: an axis with no reading gets no vertex, the outline
 * breaks there, and only a complete ring is filled.
 */
function DualRadar({ a, b }: { a: FeaturedSide; b: FeaturedSide }) {
  // Wider than tall: the side labels ("Rel. strength", "Fundamentals") need
  // horizontal room that the top and bottom labels don't.
  const width = 300;
  const height = 236;
  const cx = width / 2;
  const cy = height / 2;
  const rMax = 78;
  const n = a.factors.length;

  function point(i: number, fraction: number, clamp = true) {
    const angle = ((-90 + (i * 360) / n) * Math.PI) / 180;
    const r = rMax * (clamp ? Math.max(0, Math.min(1, fraction)) : fraction);
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  }

  function ring(fraction: number) {
    return (
      Array.from({ length: n }, (_, i) => {
        const p = point(i, fraction);
        return `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`;
      }).join(" ") + " Z"
    );
  }

  function shape(side: FeaturedSide): { d: string; complete: boolean; dots: { x: number; y: number }[] } {
    const verts = side.factors.map((f, i) => (f.value == null ? null : point(i, f.value / 100)));
    const complete = verts.every((v) => v != null);
    const firstAfterGap = verts.findIndex((v, i) => v != null && verts[(i + n - 1) % n] == null);
    const start = !complete && firstAfterGap >= 0 ? firstAfterGap : 0;
    const segments: string[] = [];
    let cur: string[] = [];
    for (let k = 0; k < n; k++) {
      const v = verts[(start + k) % n];
      if (v == null) {
        if (cur.length > 1) segments.push(cur.join(" "));
        cur = [];
        continue;
      }
      cur.push(`${cur.length === 0 ? "M" : "L"}${v.x.toFixed(2)},${v.y.toFixed(2)}`);
    }
    if (cur.length > 1) segments.push(cur.join(" "));
    const d = segments.join(" ") + (complete ? " Z" : "");
    return { d, complete, dots: verts.filter((v): v is { x: number; y: number } => v != null) };
  }

  const shapes: { side: FeaturedSide; color: string }[] = [
    { side: a, color: "rgb(var(--accent))" },
    { side: b, color: "rgb(var(--accent2))" },
  ];

  const short: Record<string, string> = {
    trend: "Trend",
    rs: "Rel. strength",
    fundamentals: "Fundamentals",
    smart_money: "Smart money",
    macro: "Macro",
    momentum: "Momentum",
  };

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
      className="block text-muted"
    >
      {[0.25, 0.5, 0.75, 1].map((r) => (
        <path
          key={r}
          d={ring(r)}
          fill="none"
          stroke="currentColor"
          strokeOpacity={r === 1 ? 0.35 : 0.14}
          strokeWidth={r === 1 ? 1 : 0.75}
        />
      ))}
      {a.factors.map((f, i) => {
        const p = point(i, 1);
        return (
          <line
            key={f.key}
            x1={cx}
            y1={cy}
            x2={p.x}
            y2={p.y}
            stroke="currentColor"
            strokeOpacity={0.16}
            strokeWidth={0.75}
          />
        );
      })}
      {shapes.map(({ side, color }) => {
        const s = shape(side);
        return (
          <g key={side.symbol}>
            {s.d.trim() && (
              <path
                d={s.d}
                fill={s.complete ? color : "none"}
                fillOpacity={s.complete ? 0.14 : 0}
                stroke={color}
                strokeWidth={1.75}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            )}
            {s.dots.map((p, i) => (
              <circle key={i} cx={p.x} cy={p.y} r={2.5} fill={color} />
            ))}
          </g>
        );
      })}
      {a.factors.map((f, i) => {
        const p = point(i, 1.16, false);
        const anchor = p.x < cx - 1 ? "end" : p.x > cx + 1 ? "start" : "middle";
        return (
          <text
            key={f.key}
            x={p.x}
            y={p.y}
            textAnchor={anchor}
            dominantBaseline="middle"
            className="fill-current text-muted"
            style={{ fontSize: 10.5 }}
          >
            {short[f.key] ?? f.label}
          </text>
        );
      })}
    </svg>
  );
}
