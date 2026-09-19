"use client";

import { useEffect, useId, useRef, useState } from "react";
import { api, type SearchResult } from "@/lib/api";

/**
 * A labelled ticker input with a full-universe typeahead.
 *
 * Keystrokes hit api.search — the same symbol-or-name search behind the ⌘K
 * palette and the alerts typeahead — debounced so a burst of typing fires one
 * request. The field is still free text: a symbol typed by hand works without
 * touching the list, and a failed search just means no suggestions.
 *
 * WAI-ARIA combobox pattern: the input owns a listbox, ↑/↓ move the active
 * option, Enter picks it — or, with nothing highlighted, submits the
 * surrounding form — and Esc closes.
 *
 * Crypto rows are left out on purpose: their namespaced symbols ("X:BTCUSD")
 * cannot be carried in a compare slug. Company stocks are listed ahead of funds
 * (search order kept within each), because this is a stock-vs-stock picker and
 * a name query like "micros" otherwise fills the list with leveraged ETNs
 * before Microsoft itself. Funds stay pickable.
 */

const DEBOUNCE_MS = 160;
const MAX_RESULTS = 6;
/** Over-fetch so the stocks-first ordering has something to promote. */
const FETCH_LIMIT = 12;

type Result = SearchResult & { is_crypto?: boolean; asset_class?: string | null };

const isFund = (r: Result) => (r.asset_class ?? "").toLowerCase() === "etf";

export function TickerCombobox({
  label,
  value,
  onChange,
  onPick,
  placeholder,
  pickedName,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** Called with the chosen row when an option is picked. */
  onPick: (row: SearchResult) => void;
  placeholder?: string;
  /** Company name of the current pick, shown as a hint under the field. */
  pickedName?: string | null;
}) {
  const uid = useId();
  const inputId = `${uid}-input`;
  const listboxId = `${uid}-listbox`;
  const hintId = `${uid}-hint`;
  const optionId = (i: number) => `${uid}-opt-${i}`;

  const [results, setResults] = useState<Result[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const seq = useRef(0);
  // The value a pick just wrote into the field. Searching for it again would
  // only pop the list we just closed back open under the cursor.
  const pickedValue = useRef<string | null>(null);

  useEffect(() => {
    const q = value.trim();
    if (!q || q === pickedValue.current) {
      seq.current++;
      setResults([]);
      return;
    }
    pickedValue.current = null;
    const mine = ++seq.current;
    const timer = setTimeout(() => {
      api
        .search(q, FETCH_LIMIT)
        .then((r) => {
          if (mine !== seq.current) return;
          const usable = ((r.results ?? []) as Result[]).filter(
            (row) => !row.is_crypto && !row.symbol.includes(":"),
          );
          const rows = [...usable.filter((row) => !isFund(row)), ...usable.filter(isFund)].slice(
            0,
            MAX_RESULTS,
          );
          setResults(rows);
          setActive(-1);
        })
        .catch(() => {
          if (mine === seq.current) setResults([]);
        });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [value]);

  const expanded = open && results.length > 0;

  function pick(row: Result) {
    pickedValue.current = row.symbol;
    onPick(row);
    setOpen(false);
    setActive(-1);
    // A pick is a settled value — drop the stale list so re-focusing the field
    // doesn't pop the old suggestions back over the form.
    seq.current++;
    setResults([]);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      if (results.length === 0) return;
      e.preventDefault();
      setOpen(true);
      setActive((i) => (i + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      if (results.length === 0) return;
      e.preventDefault();
      setOpen(true);
      setActive((i) => (i <= 0 ? results.length - 1 : i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (expanded && active >= 0 && results[active]) {
        pick(results[active]);
        return;
      }
      // Nothing highlighted: Enter submits the surrounding form. Done by hand
      // rather than left to implicit submission, so it behaves the same in
      // every browser whether or not the list happens to be open.
      setOpen(false);
      e.currentTarget.form?.requestSubmit();
    } else if (e.key === "Escape") {
      if (expanded) {
        e.preventDefault();
        setOpen(false);
        setActive(-1);
      }
    } else if (e.key === "Tab") {
      setOpen(false);
    }
  }

  return (
    <div className="relative min-w-0">
      <label htmlFor={inputId} className="block h-4 text-[11px] font-semibold uppercase leading-4 tracking-wider text-subtle">
        {label}
      </label>
      <div className="relative mt-1.5">
        <span
          className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 select-none font-mono text-muted"
          aria-hidden="true"
        >
          $
        </span>
        <input
          id={inputId}
          type="text"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={expanded}
          aria-controls={listboxId}
          aria-activedescendant={expanded && active >= 0 ? optionId(active) : undefined}
          aria-describedby={pickedName ? hintId : undefined}
          autoComplete="off"
          autoCapitalize="characters"
          spellCheck={false}
          value={value}
          placeholder={placeholder}
          onChange={(e) => {
            onChange(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          // Delay the close so a pointer pick on an option lands first.
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={onKeyDown}
          className={`h-12 w-full rounded-xl border border-border2 bg-background pl-8 pr-3 font-mono text-base uppercase text-fg shadow-sm transition-colors placeholder:font-sans placeholder:normal-case placeholder:text-subtle focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30`}
        />
      </div>
      <p id={hintId} className="mt-1.5 h-4 truncate text-xs text-muted" aria-live="polite">
        {pickedName ?? ""}
      </p>
      <ul
        id={listboxId}
        role="listbox"
        aria-label={`${label} suggestions`}
        hidden={!expanded}
        className="absolute inset-x-0 top-[4.75rem] z-30 max-h-72 overflow-auto rounded-xl border border-border2 bg-surface py-1 shadow-xl"
      >
        {results.map((r, i) => (
          <li
            key={r.symbol}
            id={optionId(i)}
            role="option"
            aria-selected={i === active}
            onMouseEnter={() => setActive(i)}
            // onMouseDown (not onClick) so the pick lands before the input's blur.
            onMouseDown={(e) => {
              e.preventDefault();
              pick(r);
            }}
            className={`flex cursor-pointer items-center gap-3 border-l-2 px-3 py-2 text-sm ${i === active ? "border-accent bg-accent/15" : "border-transparent"}`}
          >
            <span className="w-14 shrink-0 font-mono font-semibold text-fg">{r.symbol}</span>
            <span className="min-w-0 flex-1 truncate text-muted">{r.name}</span>
            {r.sector && (
              <span className="hidden shrink-0 text-xs text-subtle sm:inline">{r.sector}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
