/**
 * Top nav used on every public marketing page (landing, pricing,
 * how-it-works, scorecard, changelog, roadmap, status, compare/*, legal/*).
 * Extracted out of app/page.tsx so the look + link list stays in sync.
 */
import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle";

export function MarketingNav() {
  return (
    <nav className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          <div className="h-2 w-6 rounded-full bg-accent" />
          <span className="text-lg font-semibold tracking-tight">Tapeline</span>
        </Link>
        <div className="flex items-center gap-3 sm:gap-5">
          {/* Pricing visible even on mobile — it's the conversion page and the
              one users genuinely look for first. The rest stay sm+ only to
              keep the bar from crowding "Start free" on iPhone. */}
          <Link href="/pricing" className="text-sm text-muted hover:text-fg">
            Pricing
          </Link>
          <Link href="/how-it-works" className="hidden text-sm text-muted hover:text-fg sm:inline">
            How it works
          </Link>
          <Link href="/scorecard" className="hidden text-sm text-muted hover:text-fg sm:inline">
            Scorecard
          </Link>
          <Link href="/signals" className="hidden text-sm text-muted hover:text-fg sm:inline">
            Signals
          </Link>
          <Link href="/signin" className="hidden text-sm text-muted hover:text-fg sm:inline">
            Sign in
          </Link>
          {/* Theme toggle — labeled pill so anonymous visitors can spot it.
              Visible on every breakpoint; the previous icon-only version
              hidden behind sm+ was invisible in practice. */}
          <ThemeToggle />
          <Link href="/signup" className="btn-primary text-sm whitespace-nowrap">
            Start free
          </Link>
        </div>
      </div>
    </nav>
  );
}
