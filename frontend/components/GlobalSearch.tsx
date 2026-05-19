"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type ScannerRow } from "@/lib/api";

/**
 * ⌘K / Ctrl+K opens a ticker search. Matches on symbol prefix first, then name contains.
 * Enter jumps to /app/ticker/{symbol}. Escape closes.
 */
export function GlobalSearch() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<ScannerRow[]>([]);
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const universeRef = useRef<ScannerRow[]>([]);

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

  // Preload universe when first opened
  useEffect(() => {
    if (!open || universeRef.current.length) return;
    api.scanner({ limit: 200, sort: "symbol", order: "asc" })
      .then((r) => { universeRef.current = r.items; })
      .catch(() => {});
  }, [open]);

  // Focus the input when the panel opens
  useEffect(() => { if (open) setTimeout(() => inputRef.current?.focus(), 10); }, [open]);

  // Filter on every keystroke
  useEffect(() => {
    const s = q.trim().toUpperCase();
    if (!s) { setResults([]); return; }
    const u = universeRef.current;
    const prefix = u.filter((t) => t.symbol.startsWith(s));
    const contains = u.filter((t) => !t.symbol.startsWith(s) && (t.symbol.includes(s) || t.name.toUpperCase().includes(s)));
    setResults([...prefix, ...contains].slice(0, 10));
    setCursor(0);
  }, [q]);

  const go = useCallback((sym: string) => {
    setOpen(false);
    setQ("");
    router.push(`/app/ticker/${sym}`);
  }, [router]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[90] flex items-start justify-center bg-black/60 px-4 pt-[10vh]" onClick={() => setOpen(false)}>
      <div className="card w-full max-w-xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, results.length - 1)); }
            if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
            if (e.key === "Enter" && results[cursor]) { e.preventDefault(); go(results[cursor].symbol); }
          }}
          placeholder="Search ticker or company…"
          className="w-full bg-transparent px-5 py-4 text-lg outline-none"
        />
        {results.length > 0 && (
          <ul className="max-h-[60vh] overflow-y-auto border-t border-border">
            {results.map((r, i) => (
              <li
                key={r.symbol}
                onMouseEnter={() => setCursor(i)}
                onClick={() => go(r.symbol)}
                className={`flex cursor-pointer items-center justify-between gap-4 px-5 py-3 text-sm ${cursor === i ? "bg-panel" : ""}`}
              >
                <div>
                  <span className="font-mono font-semibold">{r.symbol}</span>
                  <span className="ml-2 text-muted">{r.name}</span>
                </div>
                <div className="flex items-center gap-3 nums text-xs">
                  <span className={r.score >= 75 ? "text-up" : r.score >= 45 ? "" : "text-muted"}>{r.score?.toFixed(0)}</span>
                  <span className={(r.change_pct_1d ?? 0) > 0 ? "text-up" : (r.change_pct_1d ?? 0) < 0 ? "text-down" : "text-muted"}>
                    {r.change_pct_1d != null ? `${r.change_pct_1d >= 0 ? "+" : ""}${r.change_pct_1d.toFixed(2)}%` : "—"}
                  </span>
                </div>
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
