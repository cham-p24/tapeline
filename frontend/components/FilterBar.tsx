"use client";

/**
 * Shared filter-bar primitives for every live-monitor page.
 *
 * The scanner page (/app/scanner) already had a hand-rolled filter row;
 * these components are extracted from that exact markup so the squeeze,
 * congress, news, earnings and IPO pages get a visually + behaviourally
 * identical bar — same `card` chrome, same `text-muted` labels, same
 * keyboard/clear affordances — without each page reinventing it.
 *
 * Everything here is theme-aware by construction: we only use the project's
 * CSS-variable utility classes (card / text-muted / text-fg / bg-transparent
 * / placeholder:text-muted), which resolve to the right light/dark values in
 * globals.css. No hard-coded hex colours.
 *
 * Accessibility:
 *  - SearchBox renders a real <input type="search"> with an aria-label and a
 *    keyboard-reachable Clear button.
 *  - SelectFilter / RangeFilter render real <label>+<select>/<input> pairs
 *    wired with htmlFor/id so screen readers announce them.
 */

import { useEffect, useId, useState } from "react";

/**
 * Layout wrapper — the flex container that holds the search box + filter
 * controls. Mirrors the scanner's `mt-6 flex flex-wrap items-center gap-3`.
 * Children are the individual controls; pass a trailing "count" node via the
 * `trailing` prop to pin it to the right (ml-auto) like the scanner does.
 */
export function FilterBar({
  children,
  trailing,
  className = "",
}: {
  children: React.ReactNode;
  trailing?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      role="search"
      className={`mt-6 flex flex-wrap items-center gap-3 ${className}`}
    >
      {children}
      {trailing != null && (
        <span className="ml-auto self-center text-xs text-muted">{trailing}</span>
      )}
    </div>
  );
}

/**
 * The primary search box. Symbol / company-name search, debounced via the
 * caller (we keep this controlled so the parent owns the debounce + the
 * actual filtering). Widest control, magnifier icon, inline Clear.
 */
export function SearchBox({
  value,
  onChange,
  placeholder = "Search ticker or company…",
  ariaLabel = "Search",
  maxLength = 40,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  ariaLabel?: string;
  maxLength?: number;
}) {
  return (
    <div className="card flex items-center gap-2 px-3 py-2 min-w-[220px]">
      <svg
        className="h-4 w-4 text-muted"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" />
        <path d="m21 21-4.3-4.3" />
      </svg>
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="flex-1 bg-transparent text-base outline-none placeholder:text-muted"
        autoComplete="off"
        spellCheck={false}
        maxLength={maxLength}
        aria-label={ariaLabel}
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange("")}
          className="text-xs text-muted hover:text-fg"
          aria-label="Clear search"
        >
          clear
        </button>
      )}
    </div>
  );
}

/**
 * A labelled <select> dropdown filter. `options` is a list of {value,label};
 * the caller is responsible for prepending the "All …" sentinel (value "").
 */
export function SelectFilter({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  const id = useId();
  return (
    <div className="card px-3 py-2">
      <label htmlFor={id} className="block text-xs text-muted">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-transparent text-base"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

/**
 * A single labelled numeric input (e.g. "Min score"). Kept separate from a
 * full range widget so pages can compose min-only, max-only, or both.
 */
export function NumberFilter({
  label,
  value,
  onChange,
  min,
  max,
  width = "w-20",
  placeholder,
}: {
  label: string;
  value: number | "";
  onChange: (v: number | "") => void;
  min?: number;
  max?: number;
  width?: string;
  placeholder?: string;
}) {
  const id = useId();
  return (
    <div className="card px-3 py-2">
      <label htmlFor={id} className="block text-xs text-muted">
        {label}
      </label>
      <input
        id={id}
        type="number"
        min={min}
        max={max}
        value={value}
        placeholder={placeholder}
        onChange={(e) => {
          const raw = e.target.value;
          onChange(raw === "" ? "" : Number(raw));
        }}
        className={`${width} bg-transparent text-base nums`}
      />
    </div>
  );
}

/**
 * A min/max numeric range packed into a single card (e.g. "Score" 0–100).
 * Both inputs share one label so the bar stays compact.
 */
export function RangeFilter({
  label,
  min,
  max,
  onMin,
  onMax,
  bound = [0, 100],
  step,
}: {
  label: string;
  min: number | "";
  max: number | "";
  onMin: (v: number | "") => void;
  onMax: (v: number | "") => void;
  bound?: [number, number];
  step?: number;
}) {
  const minId = useId();
  const maxId = useId();
  return (
    <div className="card px-3 py-2">
      <span className="block text-xs text-muted">{label}</span>
      <div className="flex items-center gap-1">
        <input
          id={minId}
          type="number"
          aria-label={`${label} minimum`}
          min={bound[0]}
          max={bound[1]}
          step={step}
          value={min}
          placeholder="min"
          onChange={(e) =>
            onMin(e.target.value === "" ? "" : Number(e.target.value))
          }
          className="w-16 bg-transparent text-base nums"
        />
        <span className="text-muted text-xs">–</span>
        <input
          id={maxId}
          type="number"
          aria-label={`${label} maximum`}
          min={bound[0]}
          max={bound[1]}
          step={step}
          value={max}
          placeholder="max"
          onChange={(e) =>
            onMax(e.target.value === "" ? "" : Number(e.target.value))
          }
          className="w-16 bg-transparent text-base nums"
        />
      </div>
    </div>
  );
}

/**
 * A small "Reset filters" link. Rendered by pages when any filter is active.
 */
export function ResetFiltersButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="btn-ghost text-sm"
    >
      Reset filters
    </button>
  );
}

/**
 * Debounce hook — returns a value that trails `value` by `delayMs`. Used by
 * pages that filter client-side on every keystroke so typing "NVDA" doesn't
 * re-filter (or, for the scanner, re-fetch) four times. Mirrors the inline
 * debounce the scanner page already used.
 */
export function useDebounced<T>(value: T, delayMs = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}
