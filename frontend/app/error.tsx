"use client";

import Link from "next/link";
import { useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function GlobalError({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => {
    console.error(error);
    // Fire-and-forget: ship the error to the backend so it lands in Fly logs
    // (and Sentry, if configured). Browsers can't otherwise tell us when
    // something explodes client-side. Wrapped in try/catch + AbortSignal so
    // a network failure here can't worsen an already-broken page.
    try {
      fetch(`${API_BASE}/api/log-client-error`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: error.message ?? String(error),
          stack: error.stack ?? "",
          url: typeof window !== "undefined" ? window.location.href : "",
        }),
        keepalive: true,  // request still goes if the page is unloading
      }).catch(() => { /* swallowed */ });
    } catch {
      /* swallowed */
    }
  }, [error]);
  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="max-w-md text-center">
        <div className="inline-block font-mono text-sm text-down">Error</div>
        <h1 className="mt-3 text-4xl font-bold tracking-tight">Something went wrong.</h1>
        <p className="mt-3 text-muted">
          We&apos;ve logged the error. If this keeps happening, email
          {" "}<a href="mailto:support@tapeline.io" className="text-accent">support@tapeline.io</a>.
        </p>
        <div className="mt-8 flex justify-center gap-3">
          <button onClick={reset} className="btn-primary">Try again</button>
          <Link href="/" className="btn-ghost">Home</Link>
        </div>
      </div>
    </main>
  );
}
