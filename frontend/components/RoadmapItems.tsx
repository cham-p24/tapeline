"use client";

import { useCallback, useEffect, useState } from "react";
import { useUser } from "@/components/UserContext";

export type Status = "shipped" | "in_progress" | "next" | "later";

export type RoadmapItem = {
  slug: string;
  title: string;
  detail: string;
  status: Status;
};

const STATUS_META: Record<Status, { label: string; color: string; ring: string }> = {
  shipped:     { label: "Shipped",     color: "text-up",         ring: "border-up/30 bg-up/5" },
  in_progress: { label: "In progress", color: "text-accent",     ring: "border-accent/30 bg-accent/5" },
  next:        { label: "Next",        color: "text-yellow-400", ring: "border-yellow-500/30 bg-yellow-500/5" },
  later:       { label: "Later",       color: "text-muted",      ring: "border-border bg-panel" },
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export function RoadmapItems({ items }: { items: RoadmapItem[] }) {
  const { user } = useUser();
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [myVotes, setMyVotes] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/api/roadmap/votes`, { credentials: "include", cache: "no-store" });
      if (!r.ok) return;
      const data = await r.json();
      setCounts(data.counts || {});
      setMyVotes(new Set(data.my_votes || []));
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function toggleVote(slug: string) {
    if (!user) {
      setErr("Sign in to vote.");
      return;
    }
    if (user.tier !== "premium") {
      setErr("Roadmap voting is a Premium feature.");
      return;
    }
    setBusy(slug); setErr(null);
    const wasVoted = myVotes.has(slug);
    try {
      const url = `${API_BASE}/api/roadmap/vote${wasVoted ? `?item_slug=${encodeURIComponent(slug)}` : ""}`;
      const r = await fetch(url, {
        method: wasVoted ? "DELETE" : "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: wasVoted ? undefined : JSON.stringify({ item_slug: slug }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({} as any));
        throw new Error(body.detail || `${r.status}`);
      }
      // Optimistic update
      setMyVotes((prev) => {
        const next = new Set(prev);
        if (wasVoted) next.delete(slug);
        else next.add(slug);
        return next;
      });
      setCounts((prev) => ({ ...prev, [slug]: (prev[slug] || 0) + (wasVoted ? -1 : 1) }));
    } catch (e: any) {
      setErr(e.message || "Vote failed");
    } finally {
      setBusy(null);
    }
  }

  const groups: Status[] = ["in_progress", "next", "later", "shipped"];

  return (
    <div className="space-y-10">
      {err && (
        <div className="rounded-md border border-yellow-500/30 bg-yellow-500/5 p-3 text-sm text-yellow-400">
          {err}
        </div>
      )}
      {groups.map((status) => {
        const groupItems = items.filter((i) => i.status === status);
        if (groupItems.length === 0) return null;
        const meta = STATUS_META[status];
        return (
          <div key={status}>
            <div className="flex items-baseline justify-between">
              <h2 className={`text-2xl font-semibold ${meta.color}`}>{meta.label}</h2>
              <span className="text-sm text-muted nums">{groupItems.length}</span>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {groupItems.map((it) => {
                const count = counts[it.slug] || 0;
                const voted = myVotes.has(it.slug);
                const canVote = status !== "shipped";
                return (
                  <div key={it.slug} className={`rounded-xl border p-5 transition-all ${meta.ring}`}>
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="font-semibold">{it.title}</h3>
                      {canVote && (
                        <button
                          onClick={() => toggleVote(it.slug)}
                          disabled={busy === it.slug}
                          title={user
                            ? user.tier === "premium"
                              ? (voted ? "Withdraw vote" : "Vote for this")
                              : "Premium-only feature"
                            : "Sign in to vote"}
                          className={`flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-xs nums transition-all ${
                            voted
                              ? "border-accent bg-accent/15 text-accent"
                              : "border-border bg-background text-muted hover:border-border2 hover:text-fg"
                          } disabled:cursor-not-allowed disabled:opacity-50`}
                        >
                          ▲ {count}
                        </button>
                      )}
                    </div>
                    <p className="mt-2 text-sm text-muted leading-relaxed">{it.detail}</p>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
