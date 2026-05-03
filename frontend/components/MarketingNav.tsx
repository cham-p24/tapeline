/**
 * Top nav used on every public marketing page (landing, pricing,
 * how-it-works, scorecard, changelog, roadmap, status, compare/*, legal/*).
 * Extracted out of app/page.tsx so the look + link list stays in sync.
 */
import Link from "next/link";

export function MarketingNav() {
  return (
    <nav className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          <div className="h-2 w-6 rounded-full bg-accent" />
          <span className="text-lg font-semibold tracking-tight">Tapeline</span>
        </Link>
        <div className="flex items-center gap-5">
          <Link href="/how-it-works" className="hidden text-sm text-muted hover:text-fg sm:inline">
            How it works
          </Link>
          <Link href="/scorecard" className="hidden text-sm text-muted hover:text-fg sm:inline">
            Scorecard
          </Link>
          <Link href="/pricing" className="hidden text-sm text-muted hover:text-fg sm:inline">
            Pricing
          </Link>
          <Link href="/signin" className="hidden text-sm text-muted hover:text-fg sm:inline">
            Sign in
          </Link>
          <Link href="/signup" className="btn-primary">
            Start free
          </Link>
        </div>
      </div>
    </nav>
  );
}
