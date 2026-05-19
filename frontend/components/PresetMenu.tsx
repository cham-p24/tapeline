"use client";

/**
 * Scanner preset save + load UI (Phase A frontend).
 *
 * Two affordances rolled into one component:
 *   1. "Save preset" button → opens a small inline form to name the
 *      current filter state. POST /api/presets with a JSON-encoded
 *      blob of the current filters; success closes the form + refreshes.
 *   2. "Load preset" dropdown → lists the user's saved presets, click
 *      one to apply its filter blob back into the scanner state.
 *
 * Gating: the `saved_scans` tier cap controls preset creation
 * (Free=0 blocks all creation; Pro=10; Premium=100). Free users see
 * the load dropdown but the Save button is disabled with an upgrade
 * tooltip.
 *
 * Parent owns the filter state. We pass it in via `currentFilters`
 * (the object that will be JSON.stringify'd) and call `onApply` with
 * the parsed filter object when the user picks a preset.
 */

import { useEffect, useState } from "react";
import { api, type ScannerPresetRow } from "@/lib/api";

type Props<T> = {
  /** Tier limit for `saved_scans`. Free=0 disables Save. */
  cap: number;
  /** Current filter state — gets serialised on Save. */
  currentFilters: T;
  /** Called with the parsed filter object when a preset is loaded. */
  onApply: (filters: T) => void;
};

export function PresetMenu<T>({ cap, currentFilters, onApply }: Props<T>) {
  const [presets, setPresets] = useState<ScannerPresetRow[]>([]);
  const [loadOpen, setLoadOpen] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const [draftName, setDraftName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [loadingList, setLoadingList] = useState(false);

  async function refresh() {
    setLoadingList(true);
    try {
      const r = await api.presets();
      setPresets(r.items);
    } catch {
      // Silently fail — preset menu isn't critical to scanner functionality.
    } finally {
      setLoadingList(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  async function save() {
    const name = draftName.trim();
    if (!name) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.presetCreate(name, JSON.stringify(currentFilters));
      setDraftName("");
      setSaveOpen(false);
      refresh();
    } catch (e: unknown) {
      const m = e instanceof Error ? e.message : String(e);
      if (m.includes("409")) setError("A preset with that name already exists.");
      else if (m.includes("403")) setError("Saved-scans limit reached. Delete a preset or upgrade.");
      else setError(`Failed: ${m}`);
    } finally {
      setSubmitting(false);
    }
  }

  function applyPreset(p: ScannerPresetRow) {
    try {
      const parsed = JSON.parse(p.filters_json) as T;
      onApply(parsed);
      setLoadOpen(false);
    } catch {
      setError("Preset data is corrupted; please delete and re-create it.");
    }
  }

  async function deletePreset(id: number, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      await api.presetDelete(id);
      refresh();
    } catch {
      // Silent — list refresh on next interaction will reconcile.
    }
  }

  const saveDisabled = cap <= 0;

  return (
    <div className="flex items-center gap-2">
      {/* Load preset dropdown */}
      <div className="relative">
        <button
          type="button"
          onClick={() => setLoadOpen((v) => !v)}
          className="rounded-md bg-panel px-3 py-2 text-xs text-muted hover:text-fg"
          aria-haspopup="listbox"
          aria-expanded={loadOpen}
        >
          Presets {presets.length > 0 ? `(${presets.length})` : ""}
        </button>
        {loadOpen ? (
          <div className="absolute right-0 z-20 mt-1 w-64 rounded-md border border-border bg-background py-1 shadow-lg">
            {loadingList ? (
              <div className="px-3 py-2 text-xs text-subtle">Loading…</div>
            ) : presets.length === 0 ? (
              <div className="px-3 py-2 text-xs text-subtle">
                No saved presets yet. Save the current filter state to recall it later.
              </div>
            ) : (
              presets.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => applyPreset(p)}
                  className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs hover:bg-panel/60"
                >
                  <span className="truncate">{p.name}</span>
                  <button
                    type="button"
                    onClick={(e) => deletePreset(p.id, e)}
                    className="text-subtle hover:text-down"
                    aria-label={`Delete preset ${p.name}`}
                  >
                    ×
                  </button>
                </button>
              ))
            )}
          </div>
        ) : null}
      </div>

      {/* Save preset — inline form on click */}
      {saveOpen ? (
        <div className="flex items-center gap-1.5">
          <input
            autoFocus
            value={draftName}
            onChange={(e) => setDraftName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") save();
              if (e.key === "Escape") {
                setSaveOpen(false);
                setDraftName("");
                setError(null);
              }
            }}
            maxLength={100}
            placeholder="Preset name"
            className="w-40 rounded-md bg-panel px-2 py-1.5 text-xs"
            aria-label="New preset name"
          />
          <button
            type="button"
            onClick={save}
            disabled={submitting || !draftName.trim()}
            className="btn-primary text-xs disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "…" : "Save"}
          </button>
          <button
            type="button"
            onClick={() => { setSaveOpen(false); setDraftName(""); setError(null); }}
            className="text-xs text-muted hover:text-fg"
          >
            cancel
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setSaveOpen(true)}
          disabled={saveDisabled}
          title={
            saveDisabled
              ? "Saved presets are a Pro feature. Upgrade to keep filter snapshots."
              : "Save the current filter state as a named preset"
          }
          className="rounded-md bg-panel px-3 py-2 text-xs text-muted hover:text-fg disabled:cursor-not-allowed disabled:opacity-50"
        >
          + Save preset
        </button>
      )}

      {error ? <span className="ml-1 text-xs text-down">{error}</span> : null}
    </div>
  );
}
