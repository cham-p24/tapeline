"use client";

import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";

/**
 * Small hover/press card — used on every scanner row to expose the score
 * breakdown. The trigger is a real <button> so the card is reachable on touch
 * and keyboard, not just pointer hover:
 *  - hover opens it on pointer devices;
 *  - click/tap and Enter/Space toggle it (native button key handling);
 *  - Escape closes it and returns focus to the trigger;
 *  - it flips to the other side / clamps vertically to stay in the viewport;
 *  - the trigger carries aria-expanded + aria-describedby, the card role="tooltip".
 * Public API (trigger/content) is unchanged so existing callers need no edits.
 */
export function HoverCard({
  trigger,
  content,
}: {
  trigger: React.ReactNode;
  content: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ side: "right" | "left"; shift: number }>({
    side: "right",
    shift: 0,
  });

  const contentId = useId();
  const wrapperRef = useRef<HTMLSpanElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const contentRef = useRef<HTMLSpanElement>(null);

  const close = useCallback(() => setOpen(false), []);
  const closeAndRefocus = useCallback(() => {
    setOpen(false);
    triggerRef.current?.focus();
  }, []);

  // Decide which side to render on and how far to nudge vertically so the card
  // stays within the viewport regardless of the trigger's position on screen.
  const reposition = useCallback(() => {
    const trigger = triggerRef.current;
    const card = contentRef.current;
    if (!trigger || !card) return;
    const t = trigger.getBoundingClientRect();
    const c = card.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const gap = 8;

    const roomRight = vw - t.right;
    const roomLeft = t.left;
    const side: "right" | "left" =
      roomRight < c.width + gap && roomLeft > roomRight ? "left" : "right";

    // Card top aligns with the trigger top; pull it up if it would overflow.
    let shift = 0;
    const overflowBottom = t.top + c.height - (vh - gap);
    if (overflowBottom > 0) shift = -Math.min(overflowBottom, t.top - gap);

    setPos((prev) =>
      prev.side === side && prev.shift === shift ? prev : { side, shift },
    );
  }, []);

  useLayoutEffect(() => {
    if (!open) return;
    reposition();
  }, [open, reposition]);

  useEffect(() => {
    if (!open) return;
    const onScroll = () => reposition();
    window.addEventListener("resize", onScroll);
    window.addEventListener("scroll", onScroll, true);
    // Close when focus or pointer moves entirely outside the widget.
    const onPointerDown = (e: PointerEvent | MouseEvent) => {
      if (!wrapperRef.current?.contains(e.target as Node)) close();
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener("resize", onScroll);
      window.removeEventListener("scroll", onScroll, true);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [open, reposition, close]);

  return (
    <span
      ref={wrapperRef}
      className="relative inline-block"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onKeyDown={(e) => {
        if (e.key === "Escape" && open) {
          e.stopPropagation();
          closeAndRefocus();
        }
      }}
    >
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={open}
        aria-describedby={open ? contentId : undefined}
        onClick={() => setOpen((o) => !o)}
        className="inline cursor-help appearance-none border-0 bg-transparent p-0 text-left align-baseline text-inherit"
      >
        {trigger}
      </button>
      {open && (
        <span
          ref={contentRef}
          id={contentId}
          role="tooltip"
          style={{ top: pos.shift || undefined }}
          className={`absolute top-0 z-50 block rounded-lg border border-border bg-surface shadow-2xl ${
            pos.side === "left" ? "right-full mr-2" : "left-full ml-2"
          }`}
        >
          {content}
        </span>
      )}
    </span>
  );
}
