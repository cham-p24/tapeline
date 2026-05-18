import Link from "next/link";
import type { Metadata } from "next";

// Tell crawlers not to index the 404 page itself. Without this, Google's
// "soft 404" detector will sometimes index the page template and report
// "Not found (404)" indexing issues even when the URL was a legitimate
// 404 result. Explicit noindex closes that loop.
export const metadata: Metadata = {
  title: "Not found — Tapeline",
  robots: { index: false, follow: true },
};

export default function NotFound() {
  return (
    <main className="relative flex min-h-screen items-center justify-center px-6">
      <div className="pointer-events-none absolute inset-0 bg-hero opacity-40" />
      <div className="relative max-w-md text-center">
        <div className="font-mono text-sm text-subtle">404</div>
        <h1 className="mt-3 text-5xl font-bold tracking-tight">Not found.</h1>
        <p className="mt-4 text-muted">That page doesn&rsquo;t exist. Maybe it never did.</p>
        <div className="mt-10 flex justify-center gap-3">
          <Link href="/" className="btn-accent h-10 px-5">Back to home</Link>
          <Link href="/app/scanner" className="btn-ghost h-10 px-5">Open the scanner</Link>
        </div>
      </div>
    </main>
  );
}
