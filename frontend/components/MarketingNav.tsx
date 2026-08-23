"use client";

/**
 * Top nav used on every public marketing page (landing, pricing,
 * how-it-works, scorecard, changelog, roadmap, status, compare/*, legal/*).
 * Extracted out of app/page.tsx so the look + link list stays in sync.
 *
 * Desktop links: Product ▾ (dropdown) · Track record · Compare · Pricing.
 * The Product ▾ dropdown opens on click and closes on outside-click, Esc, or
 * route change. It groups the product/education pages (how-it-works, scorecard,
 * verify, signals, sectors, stocks) with a one-line description each. The panel
 * is a FLOATING overlay, so it uses the SOLID `bg-surface` token (never the
 * translucent bg-panel), per the `.card` note in app/globals.css.
 *
 * Mobile: links collapse into a hamburger menu that opens a full-width
 * sheet from the top of the viewport. Pre-2026-05-19, the links were
 * `hidden sm:inline` with no replacement — meaning Sign in / How it works /
 * Scorecard / Signals were UNREACHABLE on phones except by direct URL.
 * Tapeline now has hamburger parity with every elite SaaS nav (Linear /
 * Stripe / Vercel). On mobile the Product items render as a labeled group
 * (no dropdown needed in the sheet).
 *
 * Auth-aware: when a session exists (via UserContext) the Sign in / Sign up
 * pair is replaced by a single "Dashboard →" — a logged-in reader on a public
 * page shouldn't be shown a signup wall. Active-page highlighting via
 * usePathname gives a "where am I" anchor the bar previously lacked.
 */
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useUser } from "@/components/UserContext";

// Product/education pages grouped under the "Product ▾" dropdown (desktop) and
// the "Product" labeled group (mobile sheet). Each carries a one-line blurb.
const PRODUCT_ITEMS = [
  { href: "/how-it-works", label: "How it works", desc: "The method behind every signal" },
  { href: "/scorecard", label: "Public scorecard", desc: "Every call, scored and public" },
  { href: "/verify", label: "Verify the record", desc: "Audit the track record yourself" },
  { href: "/signals", label: "All signals", desc: "Browse the full signal feed" },
  { href: "/sectors", label: "Sectors", desc: "Signals grouped by sector" },
  { href: "/stocks", label: "Stock directory", desc: "Every ticker we cover" },
];

// Top-level content links shown after the Product ▾ trigger. "Track record"
// points at the public scorecard; Compare + Pricing are standalone pages.
const TOP_LINKS = [
  { href: "/scorecard", label: "Track record" },
  { href: "/compare", label: "Compare" },
  { href: "/pricing", label: "Pricing" },
];

function SearchIcon({ className = "" }: { className?: string }) {
  return (
    <svg width="17" height="17" viewBox="0 0 18 18" fill="none" aria-hidden="true" className={className}>
      <circle cx="8" cy="8" r="5.25" stroke="currentColor" strokeWidth="1.6" />
      <path d="M12 12l3.5 3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function ChevronDown({ className = "" }: { className?: string }) {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true" className={className}>
      <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function MarketingNav() {
  const [open, setOpen] = useState(false);
  const [productOpen, setProductOpen] = useState(false);
  const productRef = useRef<HTMLDivElement>(null);
  const pathname = usePathname();
  const { user } = useUser();

  const isActive = (href: string) =>
    !!pathname && (pathname === href || pathname.startsWith(`${href}/`));

  // The Product trigger reads as active when any of its pages is the current one.
  const productActive = PRODUCT_ITEMS.some((item) => isActive(item.href));

  function handleLinkClick() {
    setOpen(false);
  }

  // Close the Product dropdown on outside-click and Esc while it's open.
  useEffect(() => {
    if (!productOpen) return;
    function onPointerDown(e: PointerEvent) {
      if (productRef.current && !productRef.current.contains(e.target as Node)) {
        setProductOpen(false);
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setProductOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [productOpen]);

  // Any navigation closes both the dropdown and the mobile sheet.
  useEffect(() => {
    setProductOpen(false);
    setOpen(false);
  }, [pathname]);

  // Auth-aware account actions, shared by desktop bar + mobile compact bar.
  const accountActions = user ? (
    <Link href="/app/scanner" className="btn-primary text-sm whitespace-nowrap">
      Dashboard &rarr;
    </Link>
  ) : (
    <>
      <Link href="/signin" className="hidden min-[381px]:inline whitespace-nowrap text-sm text-muted hover:text-fg">
        Sign in
      </Link>
      <Link href="/signup" className="btn-primary text-sm whitespace-nowrap">
        Sign up
      </Link>
    </>
  );

  return (
    <>
      <div className="sticky top-0 z-40 px-3 pt-3 sm:px-4 sm:pt-4">
        {/* Frosted-glass floating bar. */}
        <nav className="mx-auto flex max-w-6xl items-center justify-between rounded-2xl bg-background/55 px-5 py-3 shadow-[0_10px_40px_-12px_rgb(var(--shadow))] ring-1 ring-border backdrop-blur-2xl backdrop-saturate-150 supports-[backdrop-filter]:bg-background/45">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-2 w-6 rounded-full bg-accent" />
            <span className="text-lg font-semibold tracking-tight">Tapeline</span>
          </Link>

          {/* Desktop link bar — visible at sm+ (640px+). */}
          <div className="hidden items-center gap-5 sm:flex">
            {/* Product ▾ dropdown. */}
            <div className="relative" ref={productRef}>
              <button
                type="button"
                onClick={() => setProductOpen((o) => !o)}
                aria-expanded={productOpen}
                aria-haspopup="menu"
                className={`inline-flex items-center gap-1 text-sm ${
                  productActive ? "font-medium text-fg" : "text-muted hover:text-fg"
                }`}
              >
                Product
                <ChevronDown className={`transition-transform ${productOpen ? "rotate-180" : ""}`} />
              </button>
              {productOpen && (
                <div
                  role="menu"
                  aria-label="Product"
                  className="absolute left-0 top-full z-50 mt-2 w-72 rounded-xl border border-border bg-surface p-2 shadow-[0_10px_40px_-12px_rgb(var(--shadow))]"
                >
                  {PRODUCT_ITEMS.map((item) => {
                    const active = isActive(item.href);
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        role="menuitem"
                        onClick={() => setProductOpen(false)}
                        aria-current={active ? "page" : undefined}
                        className={`block rounded-lg px-3 py-2 transition-colors hover:bg-panel ${active ? "bg-panel" : ""}`}
                      >
                        <span className={`block text-sm ${active ? "font-medium text-fg" : "text-fg"}`}>
                          {item.label}
                        </span>
                        <span className="mt-0.5 block text-xs text-muted">{item.desc}</span>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>

            {TOP_LINKS.map((l) => {
              const active = isActive(l.href);
              return (
                <Link
                  key={l.label}
                  href={l.href}
                  aria-current={active ? "page" : undefined}
                  className={`text-sm ${active ? "font-medium text-fg" : "text-muted hover:text-fg"}`}
                >
                  {l.label}
                </Link>
              );
            })}
            <Link
              href="/search"
              aria-label="Search any ticker"
              className="text-muted hover:text-fg"
            >
              <SearchIcon />
            </Link>
            <ThemeToggle />
            {accountActions}
          </div>

          {/* Mobile compact bar — search + account actions + hamburger. */}
          <div className="flex items-center gap-2 sm:hidden">
            <Link
              href="/search"
              aria-label="Search any ticker"
              className="inline-flex h-11 w-11 items-center justify-center text-muted hover:text-fg"
            >
              <SearchIcon />
            </Link>
            {accountActions}
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              aria-label={open ? "Close menu" : "Open menu"}
              aria-expanded={open}
              className="ml-1 inline-flex h-11 w-11 items-center justify-center rounded-full border border-border bg-panel text-fg transition-colors hover:bg-panel/80"
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
        </nav>
      </div>

      {/* Mobile menu sheet. */}
      {open && (
        <>
          <button
            type="button"
            aria-label="Close menu"
            onClick={() => setOpen(false)}
            className="fixed inset-0 top-[76px] z-30 bg-background/40 backdrop-blur-sm sm:hidden"
          />
          <div className="fixed inset-x-3 top-[76px] z-40 rounded-2xl border border-border bg-background shadow-lg sm:hidden">
            <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-4">
              <Link
                href="/search"
                onClick={handleLinkClick}
                className="flex items-center gap-2 rounded-md px-3 py-3 text-base font-medium text-fg transition-colors hover:bg-panel"
              >
                <SearchIcon /> Search tickers
              </Link>

              {/* Product items as a labeled group (no dropdown on mobile). */}
              <p className="px-3 pb-1 pt-3 text-xs font-medium uppercase tracking-wide text-subtle">
                Product
              </p>
              {PRODUCT_ITEMS.map((l) => {
                const active = isActive(l.href);
                return (
                  <Link
                    key={l.href}
                    href={l.href}
                    onClick={handleLinkClick}
                    aria-current={active ? "page" : undefined}
                    className={`rounded-md px-3 py-3 text-base font-medium transition-colors hover:bg-panel ${active ? "bg-panel text-fg" : "text-fg"}`}
                  >
                    {l.label}
                  </Link>
                );
              })}

              {/* Top-level links. */}
              <div className="mt-1 border-t border-border pt-1">
                {TOP_LINKS.map((l) => {
                  const active = isActive(l.href);
                  return (
                    <Link
                      key={l.label}
                      href={l.href}
                      onClick={handleLinkClick}
                      aria-current={active ? "page" : undefined}
                      className={`block rounded-md px-3 py-3 text-base font-medium transition-colors hover:bg-panel ${active ? "bg-panel text-fg" : "text-fg"}`}
                    >
                      {l.label}
                    </Link>
                  );
                })}
              </div>

              <div className="mt-2 px-3 pt-3">
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
