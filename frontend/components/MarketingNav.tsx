"use client";

/**
 * Top nav used on every public marketing page (landing, pricing,
 * how-it-works, scorecard, changelog, roadmap, status, compare/*, legal/*).
 * Extracted out of app/page.tsx so the look + link list stays in sync.
 *
 * Mobile: links collapse into a hamburger menu that opens a full-width
 * sheet from the top of the viewport. Pre-2026-05-19, the links were
 * `hidden sm:inline` with no replacement — meaning Sign in / How it works /
 * Scorecard / Signals were UNREACHABLE on phones except by direct URL.
 * Tapeline now has hamburger parity with every elite SaaS nav (Linear /
 * Stripe / Vercel).
 */
import Link from "next/link";
import { useState } from "react";
import { ThemeToggle } from "@/components/ThemeToggle";

const LINKS = [
  { href: "/pricing", label: "Pricing" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/scorecard", label: "Scorecard" },
  { href: "/signals", label: "Signals" },
  { href: "/signin", label: "Sign in" },
];

export function MarketingNav() {
  const [open, setOpen] = useState(false);

  // No body-scroll-lock — early feedback was that locking the page felt
  // broken ("hamburger doesn't allow you to keep scrolling"). The sheet
  // is fixed-positioned below the nav so it stays attached when the page
  // scrolls underneath; the user can dismiss it via tap-outside or a link.
  // Standard iOS / Linear mobile-nav behaviour.

  // Close on route change — Next.js Link navigation doesn't unmount the nav,
  // so we listen for clicks anywhere inside the sheet's link list and close
  // imperatively. Simpler than wiring usePathname here.
  function handleLinkClick() {
    setOpen(false);
  }

  return (
    <>
      <nav className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-2 w-6 rounded-full bg-accent" />
            <span className="text-lg font-semibold tracking-tight">Tapeline</span>
          </Link>

          {/* Desktop link bar — visible at sm+ (640px+). At < sm we collapse
              into a hamburger that opens the sheet below. */}
          <div className="hidden items-center gap-5 sm:flex">
            {LINKS.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                className="text-sm text-muted hover:text-fg"
              >
                {l.label}
              </Link>
            ))}
            <ThemeToggle />
            <Link href="/signup" className="btn-primary text-sm whitespace-nowrap">
              Start free
            </Link>
          </div>

          {/* Mobile compact bar — single primary CTA + hamburger. Theme
              toggle and the link list move into the sheet to keep the bar
              uncluttered at narrow widths. */}
          <div className="flex items-center gap-2 sm:hidden">
            <Link
              href="/signup"
              className="btn-primary text-sm whitespace-nowrap"
            >
              Start free
            </Link>
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              aria-label={open ? "Close menu" : "Open menu"}
              aria-expanded={open}
              className="ml-1 inline-flex h-10 w-10 items-center justify-center rounded-full border border-border bg-panel text-fg transition-colors hover:bg-panel/80"
            >
              {open ? (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
                  <path d="M2 5h14M2 9h14M2 13h14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </nav>

      {/* Mobile menu sheet — drops down from the nav bar. Solid bg + backdrop
          blur so it reads cleanly over whatever section is behind it. Tap
          outside (the overlay) or a link to close. */}
      {open && (
        <>
          <button
            type="button"
            aria-label="Close menu"
            onClick={() => setOpen(false)}
            className="fixed inset-0 top-[65px] z-30 bg-background/40 backdrop-blur-sm sm:hidden"
          />
          <div className="fixed inset-x-0 top-[65px] z-40 border-b border-border bg-background sm:hidden">
            <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-4">
              {LINKS.map((l) => (
                <Link
                  key={l.href}
                  href={l.href}
                  onClick={handleLinkClick}
                  className="rounded-md px-3 py-3 text-base font-medium text-fg transition-colors hover:bg-panel"
                >
                  {l.label}
                </Link>
              ))}
              <div className="mt-2 border-t border-border/60 px-3 pt-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs text-muted">Appearance</span>
                  <ThemeToggle />
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
