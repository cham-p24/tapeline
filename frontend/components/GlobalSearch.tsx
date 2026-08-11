"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type SearchResult } from "@/lib/api";
import { canonicalMatchup } from "@/lib/comparePairs";

/**
 * ⌘K / Ctrl+K command palette.
 *
 * Three kinds of action in one flat, keyboard-navigable list:
 *  - Tickers — server-backed search over the FULL active universe by symbol OR
 *    company name (/api/search, debounced). The old build preloaded 200 symbols
 *    alphabetically and filtered client-side, hiding ~92% of the universe.
 *  - Destinations — jump to Scanner / Watchlist / Alerts / … (shown when the
 *    query is empty, filtered by name otherwise).
 *  - Compare — type "AAPL vs MSFT" (or "AAPL MSFT") to open the head-to-head.
 *
 * Enter runs the highlighted action; Esc closes.
 */

const DESTINATIONS: { label: string; href: string; hint: string }[] = [
  { label: "Scanner", href: "/app/scanner", hint: "Rank the whole market" },
  { label: "Watchlist", href: "/app/watchlist", hint: "Your saved tickers" },
  { label: "Alerts", href: "/app/alerts", hint: "Score & price alerts" },
  { label: "Heatmap", href: "/app/heatmap", hint: "Sector heatmap" },
  { label: "Squeeze", href: "/app/squeeze", hint: "Short-squeeze setups" },
  { label: "Scorecard", href: "/scorecard", hint: "Public track record" },
  { label: "Billing & plan", href: "/app/billing", hint: "Manage subscription" },
];

type Action =
  | { kind: "ticker"; symbol: string; name: string; score: number | null }
  | { kind: "dest"; label: string; href: string; hint: string }
  | { kind: "compare"; a: string; b: string };

/** Detect a "X vs Y" / "X Y" / "X,Y" two-symbol compare intent. */
function parseComparePair(q: string): { a: string; b: string } | null {
  const tokens = q
    .toUpperCase()
    .split(/\s+|,|\bVS\b/)
    .map((t) => t.trim())
    .filter(Boolean);
  const syms = tokens.filter((t) => /^[A-Z][A-Z.]{0,5}$/.test(t));
  if (syms.length === 2 && syms[0] !== syms[1]) return { a: syms[0], b: syms[1] };
  return null;
}

function actionKey(a: Action): string {
  if (a.kind === "ticker") return `t:${a.symbol}`;
  if (a.kind === "dest") return `d:${a.href}`;
  return `c:${a.a}-${a.b}`;
}

export function GlobalSearch() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [tickers, setTickers] = useState<SearchResult[]>([]);
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const searchSeq = useRef(0);

  // Global hotkey
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Focus the input when the panel opens; reset on close.
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 10);
    else { setQ(""); setTickers([]); setCursor(0); }
  }, [open]);

  // Debounced server-backed ticker search (symbol OR name, full universe).
  useEffect(() => {
    const s = q.trim();
    if (!s) { setTickers([]); return; }
    let cancelled = false;
    const seq = ++searchSeq.current;
    const timer = setTimeout(() => {
      api.search(s, 8)
        .then((r) => {
          if (cancelled || seq !== searchSeq.current) return;
          setTickers(r.results);
        })
        .catch(() => { if (!cancelled && seq === searchSeq.current) setTickers([]); });
    }, 160);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [q]);

  // Combined, ordered action list: compare intent → matching destinations →
  // tickers. Empty query shows the destination quick-links.
  const actions: Action[] = useMemo(() => {
    const s = q.trim();
    if (!s) return DESTINATIONS.map((d) => ({ kind: "dest", ...d } as Action));
    const out: Action[] = [];
    const pair = parseComparePair(s);
    if (pair) out.push({ kind: "compare", a: pair.a, b: pair.b });
    const ql = s.toLowerCase();
    for (const d of DESTINATIONS) {
      if (d.label.toLowerCase().includes(ql)) out.push({ kind: "dest", ...d });
    }
    for (const t of tickers) {
      out.push({ kind: "ticker", symbol: t.symbol, name: t.name, score: t.score });
    }
    return out;
  }, [q, tickers]);

  // Keep the cursor in range as the list changes.
  useEffect(() => { setCursor(0); }, [q]);

  const run = useCallback((a: Action) => {
    setOpen(false);
    if (a.kind === "ticker") router.push(`/app/ticker/${a.symbol}`);
    else if (a.kind === "dest") router.push(a.href);
    else router.push(`/compare/${canonicalMatchup(a.a, a.b)}`);
  }, [router]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[90] flex items-start justify-center bg-black/60 px-4 pt-[10vh]"
      onClick={() => setOpen(false)}
    >
      <div className="card !bg-surface w-full max-w-xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, actions.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
            if (e.key === "Enter" && actions[cursor]) { e.preventDefault(); run(actions[cursor]); }
          }}
          placeholder="Search tickers, a page, or “AAPL vs MSFT”…"
          className="w-full bg-transparent px-5 py-4 text-lg outline-none"
        />
        {actions.length > 0 && (
          <ul className="max-h-[60vh] overflow-y-auto border-t border-border">
            {actions.map((a, i) => (
              <li
                key={actionKey(a)}
                onMouseEnter={() => setCursor(i)}
                onClick={() => run(a)}
                className={`flex cursor-pointer items-center justify-between gap-4 px-5 py-3 text-sm ${cursor === i ? "bg-panel" : ""}`}
              >
                {a.kind === "ticker" ? (
                  <>
                    <div className="min-w-0">
                      <span className="font-mono font-semibold">{a.symbol}</span>
                      <span className="ml-2 text-muted">{a.name}</span>
                    </div>
                    <span className={`nums text-xs ${a.score != null && a.score >= 75 ? "text-up" : "text-muted"}`}>
                      {a.score != null ? a.score.toFixed(0) : "—"}
                    </span>
                  </>
                ) : a.kind === "compare" ? (
                  <>
                    <div>
                      <span className="font-mono font-semibold">{a.a} vs {a.b}</span>
                      <span className="ml-2 text-muted">head-to-head</span>
                    </div>
                    <span className="rounded bg-fg/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-muted">Compare</span>
                  </>
                ) : (
                  <>
                    <div>
                      <span className="font-medium">{a.label}</span>
                      <span className="ml-2 text-muted">{a.hint}</span>
                    </div>
                    <span className="rounded bg-fg/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-muted">Go to</span>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
        <div className="flex items-center justify-between px-5 py-2 text-xs text-muted">
          <span>&uarr; &darr; navigate</span>
          <span>&crarr; open</span>
          <span>Esc close</span>
        </div>
      </div>
    </div>
  );
}
