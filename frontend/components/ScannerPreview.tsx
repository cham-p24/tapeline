import Link from "next/link";

/**
 * Landing-hero product shot — the REAL anonymous scanner top list.
 *
 * Server component. Fetches the same anonymous /api/scanner feed that powers
 * /daily-picks (free tier = today's top-scoring rows) with the same 30-min
 * ISR budget, and renders the top slice in the exact layout of the auth'd
 * /app/scanner: same column order, same signal pill colours, same "Why"
 * sentence per row — except now every number, signal, and sentence is the
 * real current read, and every ticker links to its public /t/[symbol] page.
 *
 * History: until 2026-07 this was a hardcoded mock with randomly nudged
 * scores, a pulsing "Live" badge, and a fake "updated just now" counter —
 * simulated liveness on a radical-transparency brand. Retired. The only
 * remaining mock is SAMPLE_ROWS, a build-time fallback for when the API is
 * unreachable, and it is labeled "Sample data" with no liveness claims and
 * no invented per-ticker statements (the sample "Why" cells describe the
 * scoring bands and factor weighting — methodology facts, not fabricated
 * reads of real tickers).
 */

type Row = {
  sym: string;
  sector: string | null;
  score: number;
  conf: number | null;
  sig: string | null;
  d1: number | null;
  why: string | null;
};

type ApiScannerItem = {
  symbol?: string | null;
  sector?: string | null;
  score?: number | null;
  signal?: string | null;
  change_pct_1d?: number | null;
  confidence_pct?: number | null;
  reason?: string | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

/** Rows shown in the hero card — the top slice of today's anonymous Top 10.
    Six keeps the card the same height as the old mock so the fold layout is
    unchanged; the "See today's full Top 10" link under the card carries the
    rest. */
const HERO_ROWS = 6;

/**
 * Build-time fallback ONLY — rendered when /api/scanner is unreachable
 * (labeled "Sample data" in the card header, no Live badge, ISR retries
 * every 30 min). The "Why" cells intentionally describe the published
 * scoring bands and factor weighting rather than making claims about the
 * sample tickers themselves — we never invent per-ticker statements.
 * Bands match backend sheet_feed/mock_feed + /how-it-works copy:
 * 85+ HIGH CONVICTION · 70–84 STRONG SETUP · 55–69 CONSTRUCTIVE ·
 * 40–54 NEUTRAL · 25–39 CAUTION · <25 WEAK.
 */
export const SAMPLE_ROWS: Row[] = [
  { sym: "NVDA", sector: "Tech",        score: 92.4, conf: 94, sig: "HIGH CONVICTION", d1:  2.14, why: "Sample row — each live row carries a one-sentence read generated from its six factor scores." },
  { sym: "MSFT", sector: "Tech",        score: 88.7, conf: 91, sig: "HIGH CONVICTION", d1:  1.02, why: "Scores of 85+ read HIGH CONVICTION: most of the six factors aligned in the same direction." },
  { sym: "LLY",  sector: "Healthcare",  score: 81.3, conf: 88, sig: "STRONG SETUP",    d1:  0.74, why: "Scores of 70–84 read STRONG SETUP: the factor mix leans positive without full agreement." },
  { sym: "CAT",  sector: "Industrials", score: 76.1, conf: 82, sig: "STRONG SETUP",    d1:  0.45, why: "Trend and Relative Strength carry the most weight, Momentum the least — same formula on every row." },
  { sym: "XOM",  sector: "Energy",      score: 68.9, conf: 78, sig: "CONSTRUCTIVE",    d1: -0.32, why: "Scores of 55–69 read CONSTRUCTIVE: a mildly positive composite read of the tape." },
  { sym: "AAPL", sector: "Tech",        score: 48.4, conf: 91, sig: "NEUTRAL",         d1: -0.15, why: "Scores of 40–54 read NEUTRAL: the factors offset each other — no lean either way." },
];

/**
 * Same anonymous fetch + ISR pattern as app/daily-picks/page.tsx: the free
 * tier caps at 10 rows (today's Top 10), 30-min revalidate, 8s abort so a
 * degraded API can't hang the static build past Next's budget. Returns null
 * on any failure so the caller can fall back to labeled sample data.
 */
async function fetchTopScored(): Promise<Row[] | null> {
  try {
    const res = await fetch(`${API_BASE}/api/scanner?limit=10`, {
      next: { revalidate: 1800 },
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { items?: ApiScannerItem[] };
    const rows: Row[] = (body.items || [])
      .filter(
        (r): r is ApiScannerItem & { symbol: string; score: number } =>
          typeof r.symbol === "string" && r.symbol.length > 0 && typeof r.score === "number",
      )
      .slice(0, HERO_ROWS)
      .map((r) => ({
        sym: r.symbol,
        sector: r.sector ?? null,
        score: r.score,
        conf: r.confidence_pct ?? null,
        sig: r.signal ?? null,
        d1: r.change_pct_1d ?? null,
        why: r.reason ?? null,
      }));
    return rows.length > 0 ? rows : null;
  } catch {
    return null;
  }
}

export async function ScannerPreview() {
  const rows = await fetchTopScored();
  return <ScannerPreviewTable rows={rows ?? SAMPLE_ROWS} real={rows !== null} />;
}

/**
 * Pure presentational table — exported separately so tests can render it
 * synchronously. `real` switches the truthful data label vs the clearly
 * marked sample-data fallback; nothing pulses in either mode because
 * nothing on this surface genuinely streams (the data refreshes on a
 * 30-min ISR cadence).
 */
export function ScannerPreviewTable({ rows, real }: { rows: Row[]; real: boolean }) {
  return (
    <div className="card overflow-hidden shadow-2xl">
      {/* Page-title row — mirrors the auth'd /app/scanner header. */}
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-baseline justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold tracking-tight">Scanner</h3>
            <p className="text-[11px] text-muted">
              {real
                ? "Today’s actual top-scoring tickers · refreshed every 30 min"
                : "Sample data — the live top-scoring list is temporarily unavailable"}
            </p>
          </div>
          {!real && (
            <span className="inline-flex items-center rounded-full bg-muted/20 px-2 py-0.5 text-[11px] text-muted">
              Sample data
            </span>
          )}
        </div>
      </div>
      {/* Filter row — visual only on the marketing surface; the auth'd page
          wires these to query params. The pills describe the ACTUAL query
          behind this table: no filters, sorted by score descending. */}
      <div className="flex items-center justify-between gap-3 border-b border-border bg-panel px-4 py-2 text-[11px]">
        <div className="flex items-center gap-3 text-muted">
          <span className="rounded border border-border bg-panel px-2 py-1">Min score &middot; 0</span>
          <span className="rounded border border-border bg-panel px-2 py-1">All sectors</span>
          <span className="rounded border border-border bg-panel px-2 py-1">&darr; Score (high first)</span>
        </div>
        <div className="text-muted">
          {real ? (
            <>Top {rows.length} of today&rsquo;s Top 10</>
          ) : (
            <>Sample rows &mdash; not live data</>
          )}
        </div>
      </div>
      <table className="w-full text-sm nums">
        <thead className="border-b border-border/50 text-[11px] uppercase text-muted">
          <tr>
            <th className="px-3 py-2 text-left">Ticker</th>
            <th className="hidden px-3 py-2 text-left md:table-cell">Sector</th>
            <th className="px-3 py-2 text-right">Score</th>
            <th className="hidden px-3 py-2 text-right sm:table-cell">Conf</th>
            <th className="px-3 py-2 text-left">Signal</th>
            <th className="px-3 py-2 text-right">1D</th>
            <th className="hidden px-3 py-2 text-left lg:table-cell">Why</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const sig = (r.sig || "").toUpperCase();
            return (
              <tr key={r.sym} className="border-b border-border/30 transition-colors hover:bg-panel/40">
                <td className="px-3 py-2 font-mono font-medium">
                  {/* Every ticker links to its real public page — ~8,400 of
                      them exist unmetered, so the hero doubles as a door
                      into the zero-signup surface. */}
                  <Link href={`/t/${r.sym}`} className="hover:text-accent hover:underline">
                    {r.sym}
                  </Link>
                </td>
                <td className="hidden px-3 py-2 text-xs text-muted md:table-cell">{r.sector || "—"}</td>
                <ScoreCell score={r.score} />
                <td className="hidden px-3 py-2 text-right text-xs text-muted sm:table-cell">
                  {r.conf == null ? "—" : `${Math.round(r.conf)}%`}
                </td>
                <td className="px-3 py-2">
                  {sig ? (
                    <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${sigClasses(sig)}`}>{sig}</span>
                  ) : (
                    <span className="text-xs text-muted">&mdash;</span>
                  )}
                </td>
                <td className={`px-3 py-2 text-right ${r.d1 == null ? "text-muted" : r.d1 > 0 ? "text-up" : r.d1 < 0 ? "text-down" : "text-muted"}`}>
                  {r.d1 == null ? "—" : `${r.d1 >= 0 ? "+" : ""}${r.d1.toFixed(2)}%`}
                </td>
                {/* WHY column — 2-line clamp so the sentence reads as a
                    finished thought rather than ".." mid-word. */}
                <td className="hidden px-3 py-2 align-top text-xs text-muted lg:table-cell">
                  <span className="line-clamp-2 whitespace-normal break-words leading-snug">
                    {(r.why || "").trim() || "—"}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function sigClasses(sig: string): string {
  return sig === "HIGH CONVICTION" ? "bg-up/20 text-up"
    : sig === "STRONG SETUP" ? "bg-up/10 text-up"
    : sig === "CONSTRUCTIVE" ? "bg-accent/10 text-accent"
    : sig === "CAUTION" ? "bg-warn/10 text-warn"
    : sig === "WEAK" ? "bg-down/10 text-down"
    : "bg-muted/20 text-muted";
}

function ScoreCell({ score }: { score: number }) {
  const colour = score >= 80 ? "text-up" : score >= 60 ? "text-up/80" : "text-fg";
  return (
    <td className={`px-3 py-2 text-right font-semibold ${colour}`}>
      {score.toFixed(1)}
    </td>
  );
}
