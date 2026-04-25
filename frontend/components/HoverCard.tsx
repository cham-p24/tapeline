"use client";

import { useState } from "react";

/**
 * Tiny hover card — used on every scanner row to expose the score breakdown
 * without adding a click. Positioned to the right of the trigger.
 */
export function HoverCard({
  trigger,
  content,
}: {
  trigger: React.ReactNode;
  content: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {trigger}
      {open && (
        <span className="absolute left-full top-0 z-50 ml-2 block rounded-lg border border-border bg-panel shadow-2xl">
          {content}
        </span>
      )}
    </span>
  );
}
