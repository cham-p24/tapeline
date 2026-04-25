"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function GlobalError({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => { console.error(error); }, [error]);
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
