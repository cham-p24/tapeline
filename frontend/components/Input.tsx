"use client";

import type { InputHTMLAttributes } from "react";

/**
 * The one text-Input primitive for general forms (contact, newsletter,
 * filters). Fixed height, panel fill, md radius, and a consistent focus state —
 * crucially it does NOT set `focus:outline-none`, so the app's global
 * focus-visible ring is preserved (the 2026-08 UI audit found several ad-hoc
 * inputs cancelling the ring and restyling height/background per page).
 *
 * Auth fields keep their own richer FormField (per-field validation + error
 * slots); this is for the simpler inputs everywhere else. Radius = rounded-md,
 * matching the input rung of the system's radius ladder.
 */

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "className"> & {
  className?: string;
  /** Renders the error border + sets aria-invalid. */
  invalid?: boolean;
};

export function Input({ className = "", invalid, ...rest }: Props) {
  return (
    <input
      aria-invalid={invalid || undefined}
      className={
        `block h-11 w-full rounded-md border bg-panel px-3 text-base transition-colors ` +
        (invalid ? "border-down focus:border-down" : "border-border focus:border-accent") +
        (className ? ` ${className}` : "")
      }
      {...rest}
    />
  );
}
