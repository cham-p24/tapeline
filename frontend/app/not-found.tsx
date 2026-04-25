import Link from "next/link";

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
