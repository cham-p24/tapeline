"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Animate an integer from 0 to `target` over `durationMs` the first time
 * a non-null value arrives. Subsequent updates snap (no re-animation per
 * refresh) so this is safe to use on live-polled values without the UI
 * jittering on every poll.
 *
 * Honours prefers-reduced-motion — those users see the final value
 * immediately, no animation.
 *
 * Extracted from components/LiveCounters.tsx 2026-05-24 so the score
 * radials, fear & greed dial, scorecard summary, and any other "live
 * number" surface can share the same effect — was getting copy-pasted
 * inline three times.
 *
 * Returns the integer to display, or null while target is null.
 */
export function useCountUp(
  target: number | null,
  durationMs = 1200,
): number | null {
  const [value, setValue] = useState<number | null>(null);
  const seenRef = useRef(false);

  useEffect(() => {
    if (target == null) return;
    // After the initial draw, snap to the latest value. Re-animating on
    // every 60s poll would be visually exhausting.
    if (seenRef.current) {
      setValue(target);
      return;
    }
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // A hidden/background tab pauses requestAnimationFrame, so the rAF-driven
    // animation below never runs and the value would stay stuck at null (the UI
    // shows "—" / 0.0 indefinitely — e.g. when the page is opened in a
    // background tab). Snap straight to the final value in that case, same as
    // for reduced-motion users.
    const hidden = typeof document !== "undefined" && document.hidden;
    if (reduce || hidden) {
      setValue(target);
      seenRef.current = true;
      return;
    }
    const start = 0;
    const startTime = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - startTime) / durationMs);
      // easeOutCubic — fast then settles, feels alive but not bouncy.
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(start + (target - start) * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
      else seenRef.current = true;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, durationMs]);

  return value;
}
