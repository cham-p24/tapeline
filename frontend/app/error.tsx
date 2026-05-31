"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/**
 * Route-level error boundary for the whole app.
 *
 * Next.js renders this when ANY page throws during render or its
 * client effects bubble. Without it, an uncaught render error blanks
 * the entire route — users see a white screen and we lose the visit.
 * Sentry catches the error backend-side via /api/log-client-error,
 * but the user still needs:
 *   1. Confirmation that we know
 *   2. A way to recover (try again / go home)
 *   3. A way to talk to a human if it keeps happening
 *
 * 2026-05-22 enhancements over the previous minimal version:
 *   - Generates a short error ID the user can quote when emailing
 *     support; we log the same ID server-side so we can correlate.
 *     Format: a 6-char base36 from Date.now() + small random — long
 *     enough to be uniquely findable in 24h of logs, short enough
 *     to type in an email.
 *   - Brand-consistent shell — uses the site's existing card + button
 *     tokens rather than the placeholder dark text the prior version
 *     had.
 *   - Mailto link pre-fills the subject + body with the error ID so
 *     user-side friction is "click, send".
 *   - "Try again" prominently first because the most common error
 *     class (transient API hiccup) self-resolves on retry.
 *   - Link to /status so the user can self-serve diagnose a wider
 *     outage before emailing.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  // Stable per-render error ID. The Next.js `digest` (deployment-level
  // error hash) is preferred when present — that's what Vercel keeps
  // server-side. Otherwise generate a short client token from time +
  // randomness. Either way the same string is logged to the backend
  // so support can grep for it.
  const [errorId] = useState<string>(() => {
    if (error.digest) return error.digest.slice(0, 10).toUpperCase();
    const time = Date.now().toString(36).slice(-5);
    const rand = Math.random().toString(36).slice(2, 5);
    return `${time}${rand}`.toUpperCase();
  });

  useEffect(() => {
    console.error("[tapeline.error]", errorId, error);
    // Fire-and-forget: ship the error to the backend so it lands in Fly
    // logs (and Sentry, if configured). Browsers can't otherwise tell
    // us when something explodes client-side. Wrapped in try/catch +
    // keepalive so a network failure here can't worsen an already-
    // broken page, and the POST still flies if the user navigates away.
    try {
      fetch(`${API_BASE}/api/log-client-error`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: error.message ?? String(error),
          stack: error.stack ?? "",
          digest: error.digest ?? "",
          error_id: errorId,
          url: typeof window !== "undefined" ? window.location.href : "",
          ua: typeof navigator !== "undefined" ? navigator.userAgent : "",
        }),
        keepalive: true,
      }).catch(() => {
        /* swallowed — the error page should not throw */
      });
    } catch {
      /* swallowed */
    }
  }, [error, errorId]);

  const mailtoHref =
    `mailto:support@tapeline.io` +
    `?subject=${encodeURIComponent(`Error ${errorId}`)}` +
    `&body=${encodeURIComponent(
      `Hi Tapeline,\n\nI hit an error on ${typeof window !== "undefined" ? window.location.href : "the site"}.\n\nError ID: ${errorId}\nWhat I was doing: \n\n(thanks!)\n`,
    )}`;

  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-12">
      <div className="w-full max-w-lg">
        <div className="rounded-2xl border border-down/30 bg-panel/40 p-8 sm:p-10">
          <div className="inline-block rounded-full bg-down/15 px-3 py-1 font-mono text-xs uppercase tracking-wider text-down">
            Error
          </div>
          <h1 className="mt-4 text-3xl sm:text-4xl font-bold tracking-tight">
            Something went wrong.
          </h1>
          <p className="mt-3 text-sm sm:text-base text-muted leading-relaxed">
            We logged the failure on our side. Most one-off errors are a
            transient backend hiccup — clicking <strong>Try again</strong>{" "}
            resolves them. If it doesn&rsquo;t, email us with the ID below
            and we&rsquo;ll investigate within one business day.
          </p>

          {/* Error ID — typeable, copy-friendly. Monospace + slightly
              dimmer than body text so it reads as a reference token. */}
          <div className="mt-6 flex items-center gap-3 rounded-lg border border-border bg-background/60 px-4 py-3">
            <span className="text-[10px] uppercase tracking-wider text-subtle">
              Error ID
            </span>
            <code className="flex-1 font-mono text-sm text-fg select-all">
              {errorId}
            </code>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <button onClick={reset} className="btn-primary">
              Try again
            </button>
            <Link href="/" className="btn-ghost">
              Home
            </Link>
            <a href={mailtoHref} className="btn-ghost">
              Email support
            </a>
          </div>

          <p className="mt-6 text-xs text-subtle leading-relaxed">
            Status of all systems:{" "}
            <Link href="/status" className="text-accent hover:underline">
              tapeline.io/status
            </Link>
            . If multiple things are red there, it&rsquo;s us, not you —
            we&rsquo;re probably already on it.
          </p>
        </div>
      </div>
    </main>
  );
}
