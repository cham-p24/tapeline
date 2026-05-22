"use client";

import { useEffect, useState } from "react";
import { NewsletterCapture } from "@/components/NewsletterCapture";

/**
 * Last-chance email capture for visitors who scroll the pricing page
 * and then move their cursor toward the browser chrome (close tab / URL
 * bar / back button). Fires ONCE per browser session — sessionStorage
 * key prevents re-trigger after dismiss.
 *
 * Why pricing specifically: visitors who reach /pricing have shown
 * commercial intent. If they exit without converting, the second-best
 * capture is their email (newsletter funnel) — much higher-value than
 * losing them entirely. Founder-research consensus: exit-intent modals
 * typically convert 2-5% of would-be-bouncers, with effectively zero
 * downside since they only fire on the way out.
 *
 * Detection signal: pointer leaves the top of the viewport (y < 5 px).
 * This is the only reliable cross-browser cue — `onbeforeunload` and
 * `visibilitychange` are too noisy.
 *
 * Source tag on the embedded NewsletterCapture is "pricing" so the
 * `newsletter_subscribers.source` column shows this came from the
 * exit-intent path specifically.
 */
const STORAGE_KEY = "tapeline_exit_intent_shown_v1";

export function ExitIntentModal({
  source,
}: {
  /** Which page placed the modal — for analytics. */
  source: "pricing" | "homepage";
}) {
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // One-per-session — don't pester anyone who already saw it.
    try {
      if (sessionStorage.getItem(STORAGE_KEY) === "1") {
        setDismissed(true);
        return;
      }
    } catch {
      // sessionStorage unavailable (Safari private etc.) — still allow
      // the modal to fire once per page load; degrades gracefully.
    }

    // Don't trigger on touch devices — there's no cursor leaving the
    // viewport, so exit-intent is a desktop-only signal.
    if (typeof window !== "undefined" && window.matchMedia &&
        window.matchMedia("(pointer: coarse)").matches) {
      return;
    }

    function onMouseOut(e: MouseEvent) {
      // Only fire when the pointer crosses the TOP edge of the viewport
      // (heading toward the address bar / close tab area).
      if (e.clientY > 5) return;
      // relatedTarget being null means the pointer left the document
      // entirely — that's the strongest exit signal.
      if ((e as MouseEvent & { relatedTarget: EventTarget | null }).relatedTarget) return;
      setOpen(true);
      window.removeEventListener("mouseout", onMouseOut);
      try {
        sessionStorage.setItem(STORAGE_KEY, "1");
      } catch {
        /* ignore */
      }
    }

    // 5-second grace period after mount so the modal doesn't fire on
    // a fast page transition or a user nudging their mouse upward to
    // open a tab they were already planning to open.
    const t = setTimeout(() => {
      window.addEventListener("mouseout", onMouseOut);
    }, 5000);

    return () => {
      clearTimeout(t);
      window.removeEventListener("mouseout", onMouseOut);
    };
  }, []);

  if (dismissed || !open) return null;

  function close() {
    setOpen(false);
    setDismissed(true);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="exit-intent-title"
      onClick={(e) => {
        // Click outside the inner panel closes the modal.
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="relative w-full max-w-md rounded-xl border border-border bg-panel p-6 shadow-2xl sm:p-8">
        <button
          type="button"
          onClick={close}
          className="absolute right-3 top-3 rounded-md p-1 text-muted hover:bg-bg hover:text-fg"
          aria-label="Close"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="h-5 w-5"
          >
            <path
              fillRule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clipRule="evenodd"
            />
          </svg>
        </button>

        <div className="inline-flex items-center gap-2 rounded-full border border-border bg-bg px-3 py-1 text-xs text-muted">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
          Before you go
        </div>
        <h2
          id="exit-intent-title"
          className="mt-4 text-2xl font-semibold tracking-tight text-fg"
        >
          Free daily picks instead?
        </h2>
        <p className="mt-3 text-sm leading-relaxed text-muted">
          If you&rsquo;re not ready for a trial, get the daily Top 10 picks in
          your inbox each US market morning. Same composite, no card,
          unsubscribe in one click.
        </p>

        <div className="mt-5">
          <NewsletterCapture source={source} heading="" sub="" />
        </div>

        <button
          type="button"
          onClick={close}
          className="mt-4 w-full text-center text-xs text-muted hover:text-fg"
        >
          No thanks &mdash; close
        </button>
      </div>
    </div>
  );
}
