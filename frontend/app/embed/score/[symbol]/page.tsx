/**
 * /embed/score/[symbol] — iframe-able stock-score badge.
 *
 * Backlink-generating asset. Every blog, Substack, GitHub README, or
 * personal site that embeds this widget produces a dofollow link
 * back to https://tapeline.io/t/{TICKER} via the "Powered by Tapeline"
 * footer. The widget is intentionally:
 *   - Visually self-contained (fits a 480×140 iframe cleanly)
 *   - Brand-attributed (Tapeline logo + URL link)
 *   - Useful at face value (live score + signal + 1d change)
 *   - Honest (links to the public scorecard, not a paywall)
 *
 * Compared to a screenshot, an embedded iframe stays fresh — site
 * owners don't have to manually update screenshots when scores
 * change. That's the value-prop pitch in the /embed docs page.
 *
 * Each embed produces a HTTP referrer header pointing at the embedding
 * site, so we can later aggregate referrers in analytics to identify
 * the most valuable backlink sources for outreach follow-up.
 *
 * No auth required. Caches 60s server-side (same as /t/{TICKER}) so
 * embeds on high-traffic pages don't hammer the API.
 *
 * URL params (query):
 *   ?theme=light   — default; light bg + dark text
 *   ?theme=dark    — dark bg + light text
 *   ?compact=1     — narrow variant (320×80 instead of 480×140)
 */
import Link from "next/link";
import { notFound } from "next/navigation";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

type TickerData = {
  symbol: string;
  name: string;
  score: number | null;
  signal: string | null;
  price: number | null;
  change_pct_1d: number | null;
};

async function fetchTicker(symbol: string): Promise<TickerData | null> {
  try {
    const res = await fetch(`${API_BASE}/api/ticker/${symbol.toUpperCase()}`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return null;
    return (await res.json()) as TickerData;
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  const sym = symbol.toUpperCase();
  return {
    title: `${sym} — Tapeline Score Badge`,
    robots: { index: false, follow: true },
  };
}

// Map signal string to a colour token. Standalone iframe doesn't have
// access to the global Tailwind palette so colours are inline hex.
function signalColors(signal: string | null, dark: boolean) {
  const lower = (signal ?? "").toLowerCase();
  if (lower.includes("high conviction")) return { bg: "#22c55e", fg: "#fff" };
  if (lower.includes("strong setup")) return { bg: "#16a34a", fg: "#fff" };
  if (lower.includes("constructive")) return { bg: "#3b82f6", fg: "#fff" };
  if (lower.includes("neutral")) return { bg: dark ? "#52525b" : "#a1a1aa", fg: "#fff" };
  if (lower.includes("caution")) return { bg: "#f59e0b", fg: "#1c1917" };
  if (lower.includes("weak")) return { bg: "#dc2626", fg: "#fff" };
  return { bg: dark ? "#3f3f46" : "#d4d4d8", fg: dark ? "#fafafa" : "#27272a" };
}

export default async function EmbedScorePage({
  params,
  searchParams,
}: {
  params: Promise<{ symbol: string }>;
  searchParams: Promise<{ theme?: string; compact?: string }>;
}) {
  const { symbol } = await params;
  const sp = await searchParams;
  const sym = symbol.toUpperCase();
  const data = await fetchTicker(sym);
  if (!data) notFound();

  const isDark = sp.theme === "dark";
  const isCompact = sp.compact === "1";

  const bg = isDark ? "#0a0d14" : "#ffffff";
  const fg = isDark ? "#fafafa" : "#0a0d14";
  const muted = isDark ? "#a1a1aa" : "#71717a";
  const border = isDark ? "#27272a" : "#e4e4e7";
  const accent = "#2563eb";

  const score = data.score;
  const signal = data.signal ?? "—";
  const sig = signalColors(signal, isDark);
  const change = data.change_pct_1d ?? 0;
  const changeColor = change > 0 ? "#22c55e" : change < 0 ? "#dc2626" : muted;
  const tapelineUrl = `https://tapeline.io/t/${sym}?utm_source=embed&utm_medium=badge&utm_campaign=score_badge`;

  if (isCompact) {
    return (
      <a
        href={tapelineUrl}
        target="_blank"
        rel="noopener"
        style={{
          display: "block",
          textDecoration: "none",
          background: bg,
          color: fg,
          border: `1px solid ${border}`,
          borderRadius: "10px",
          padding: "12px 14px",
          width: "calc(100% - 2px)",
          maxWidth: "320px",
          boxSizing: "border-box",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              flexShrink: 0,
              width: "44px",
              height: "44px",
              borderRadius: "50%",
              background: sig.bg,
              color: sig.fg,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "16px",
              fontWeight: 700,
              letterSpacing: "-0.02em",
            }}
          >
            {score != null ? score.toFixed(0) : "—"}
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div
              style={{
                fontSize: "13px",
                fontWeight: 700,
                lineHeight: 1.2,
                fontFamily: "ui-monospace, SFMono-Regular, monospace",
              }}
            >
              {sym}
            </div>
            <div
              style={{
                fontSize: "10px",
                color: muted,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginTop: "2px",
              }}
            >
              {signal}
            </div>
          </div>
          <div
            style={{
              flexShrink: 0,
              fontSize: "10px",
              color: muted,
            }}
          >
            tapeline.io
          </div>
        </div>
      </a>
    );
  }

  // Standard variant — 480×140 target
  return (
    <a
      href={tapelineUrl}
      target="_blank"
      rel="noopener"
      style={{
        display: "block",
        textDecoration: "none",
        background: bg,
        color: fg,
        border: `1px solid ${border}`,
        borderRadius: "14px",
        padding: "16px 18px",
        width: "calc(100% - 2px)",
        maxWidth: "480px",
        boxSizing: "border-box",
      }}
    >
      {/* Header row: ticker + brand mark */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "12px" }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div
            style={{
              fontSize: "18px",
              fontWeight: 700,
              letterSpacing: "-0.01em",
              fontFamily: "ui-monospace, SFMono-Regular, monospace",
            }}
          >
            {sym}
          </div>
          <div
            style={{
              fontSize: "11px",
              color: muted,
              marginTop: "2px",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {data.name}
          </div>
        </div>
        <div
          style={{
            fontSize: "10px",
            color: muted,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            flexShrink: 0,
          }}
        >
          Tapeline
        </div>
      </div>

      {/* Body row: big score + signal pill + 1d change */}
      <div
        style={{
          marginTop: "12px",
          display: "flex",
          alignItems: "center",
          gap: "14px",
        }}
      >
        <div
          style={{
            flexShrink: 0,
            width: "62px",
            height: "62px",
            borderRadius: "50%",
            background: sig.bg,
            color: sig.fg,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "26px",
            fontWeight: 700,
            letterSpacing: "-0.03em",
            fontFamily: "ui-monospace, SFMono-Regular, monospace",
          }}
        >
          {score != null ? score.toFixed(0) : "—"}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: "12px",
              color: muted,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            Tapeline Score · /100
          </div>
          <div
            style={{
              fontSize: "15px",
              fontWeight: 600,
              marginTop: "2px",
              color: sig.bg,
            }}
          >
            {signal}
          </div>
          {data.price != null && (
            <div style={{ marginTop: "4px", display: "flex", alignItems: "baseline", gap: "8px" }}>
              <span
                style={{
                  fontSize: "13px",
                  fontFamily: "ui-monospace, SFMono-Regular, monospace",
                }}
              >
                ${data.price.toFixed(2)}
              </span>
              {data.change_pct_1d != null && (
                <span
                  style={{
                    fontSize: "11px",
                    color: changeColor,
                    fontFamily: "ui-monospace, SFMono-Regular, monospace",
                  }}
                >
                  {change >= 0 ? "+" : ""}
                  {change.toFixed(2)}%
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Footer attribution — the actual backlink. Honest "Powered by"
          phrasing + explicit URL. UTM params on the wrapping <a>
          let us attribute referrer traffic in GA4. */}
      <div
        style={{
          marginTop: "12px",
          paddingTop: "10px",
          borderTop: `1px solid ${border}`,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: "10px",
          color: muted,
        }}
      >
        <span>
          Powered by <span style={{ color: accent, fontWeight: 600 }}>tapeline.io</span> · 6-factor
          public formula
        </span>
        <span style={{ textTransform: "uppercase", letterSpacing: "0.06em" }}>Live</span>
      </div>
    </a>
  );
}
