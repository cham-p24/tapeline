"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Wraps any block with a "visible when intersecting viewport" effect:
 * the content starts at opacity 0, translated 12px down, and fades up
 * when it enters the viewport. Linear-style polish for marketing pages.
 *
 * Honour `prefers-reduced-motion` — for users who've asked for less
 * animation, skip the transition entirely so nothing jumps.
 */
type Props = {
  children: React.ReactNode;
  /** ms after intersection before starting the transition. Useful for
      staggering siblings: 0, 80, 160 across three pillars. */
  delayMs?: number;
  className?: string;
};

export function FadeIn({ children, delayMs = 0, className = "" }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);
  const [reduce, setReduce] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduce(mql.matches);
    const handle = () => setReduce(mql.matches);
    mql.addEventListener?.("change", handle);
    return () => mql.removeEventListener?.("change", handle);
  }, []);

  useEffect(() => {
    if (!ref.current) return;
    if (reduce) {
      setVisible(true);
      return;
    }
    const el = ref.current;
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            window.setTimeout(() => setVisible(true), delayMs);
            obs.unobserve(el);
          }
        }
      },
      { threshold: 0.15, rootMargin: "0px 0px -40px 0px" },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [delayMs, reduce]);

  return (
    <div
      ref={ref}
      className={`${className} transition-all duration-700 ease-out ${
        visible || reduce ? "opacity-100 translate-y-0" : "opacity-0 translate-y-3"
      }`}
    >
      {children}
    </div>
  );
}
