"use client";

/**
 * Multi-watchlist tab strip for /app/watchlist.
 *
 * Renders the user's named lists as a horizontal tab row with a
 * "+ New list" affordance gated on the `watchlists` tier cap:
 *
 *   Free    → 1 list  → tabs hidden, no "+ New list" CTA (no behavioural
 *             change from the single-list UX existing Free users see today)
 *   Pro     → 5 lists
 *   Premium → 20 lists
 *
 * The active list is controlled by the parent so the items table can
 * filter by it. Parent passes `activeId` and `onChange(id)`; this
 * component is purely presentational + emits the create call.
 *
 * Cap enforcement: server-side 403 is the authoritative gate (see
 * backend/app/routers/watchlists.py). Frontend disables the "+ New
 * list" button at the cap so users don't waste a click; the server
 * still 403s as defence-in-depth if a forked client bypasses the UI.
 */

import { useState } from "react";
import { api, type WatchlistRow } from "@/lib/api";

type Props = {
  lists: WatchlistRow[];
  activeId: number | null;
  /** Tier limit for `watchlists` from the user's effective tier. */
  cap: number;
  onChange: (id: number | null) => void;
  onCreated: () => void;
};

export function WatchlistTabs({ lists, activeId, cap, onChange, onCreated }: Props) {
  const [creating, setCreating] = useState(false);
  const [draftName, setDraftName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Free tier (cap=1) hides tabs entirely — current single-list users see
  // zero UI shift. Tabs reappear the moment they're on Pro+ AND have any
  // lists at all.
  const showTabs = cap > 1 && lists.length > 0;
  if (!showTabs && !creating) return null;

  const atCap = lists.length >= cap;

  async function submit() {
    const name = draftName.trim();
    if (!name) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.watchlistCreate(name);
      setDraftName("");
      setCreating(false);
      onCreated();
    } catch (e: unknown) {
      const m = e instanceof Error ? e.message : String(e);
      if (m.includes("409")) setError("A list with that name already exists.");
      else if (m.includes("403")) setError("Watchlist limit reached. Delete a list or upgrade for more.");
      else setError(`Failed: ${m}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mt-6 border-b border-border">
      <div className="flex flex-wrap items-center gap-1 overflow-x-auto">
        {lists.map((l) => {
          const active = l.id === activeId;
          return (
            <button
              key={l.id}
              type="button"
              onClick={() => onChange(l.id)}
              className={
                "whitespace-nowrap rounded-t-md border-b-2 px-3 py-2 text-sm transition-colors " +
                (active
                  ? "border-accent text-fg"
                  : "border-transparent text-muted hover:text-fg hover:bg-panel/60")
              }
              aria-current={active ? "page" : undefined}
            >
              {l.name}
              <span className="ml-1.5 text-xs text-subtle">{l.item_count}</span>
            </button>
          );
        })}
        {creating ? (
          <div className="flex items-center gap-2 px-2 py-1">
            <input
              autoFocus
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submit();
                if (e.key === "Escape") {
                  setCreating(false);
                  setDraftName("");
                  setError(null);
                }
              }}
              maxLength={100}
              placeholder="List name"
              className="w-40 rounded-md bg-panel px-2 py-1 text-sm"
              aria-label="New list name"
            />
            <button
              type="button"
              onClick={submit}
              disabled={submitting || !draftName.trim()}
              className="btn-primary text-xs disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? "…" : "Create"}
            </button>
            <button
              type="button"
              onClick={() => {
                setCreating(false);
                setDraftName("");
                setError(null);
              }}
              className="text-xs text-muted hover:text-fg"
            >
              cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setCreating(true)}
            disabled={atCap}
            title={
              atCap
                ? `You're at the ${cap}-list cap on this tier. Delete a list or upgrade for more.`
                : "Create a new list"
            }
            className="rounded-t-md px-3 py-2 text-sm text-muted hover:text-fg hover:bg-panel/60 disabled:cursor-not-allowed disabled:opacity-50"
          >
            + New list
          </button>
        )}
      </div>
      {error ? <p className="mt-1 px-3 text-xs text-down">{error}</p> : null}
    </div>
  );
}
