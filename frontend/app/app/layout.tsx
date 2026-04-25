"use client";

import Link from "next/link";
import { useState } from "react";
import { ToastProvider } from "@/components/Toast";
import { GlobalSearch } from "@/components/GlobalSearch";
import { useUser } from "@/components/UserContext";
import { TrialBanner } from "@/components/TrialBanner";

const tabs = [
  { href: "/app/scanner", label: "Scanner" },
  { href: "/app/heatmap", label: "Heatmap" },
  { href: "/app/watchlist", label: "Watchlist" },
  { href: "/app/squeeze", label: "Squeeze" },
  { href: "/app/regime", label: "Regime" },
  { href: "/app/congress", label: "Congress" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  return (
    <ToastProvider>
      <div className="min-h-screen">
        <nav className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
            <Link href="/" className="flex items-center gap-2">
              <div className="h-2 w-6 rounded-full bg-accent" />
              <span className="text-base font-semibold tracking-tight">Tapeline</span>
            </Link>

            <div className="hidden items-center gap-1 md:flex">
              {tabs.map((t) => (
                <Link
                  key={t.href}
                  href={t.href}
                  className="rounded-md px-3 py-1.5 text-sm text-muted hover:bg-panel hover:text-fg"
                >
                  {t.label}
                </Link>
              ))}
              <button
                onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }))}
                className="ml-3 flex items-center gap-2 rounded-md border border-border bg-panel px-3 py-1.5 text-xs text-muted hover:text-fg"
              >
                Search&nbsp;<kbd className="rounded bg-black/50 px-1.5 py-0.5 text-[10px]">⌘K</kbd>
              </button>
              <UserChip />
            </div>

            <button
              onClick={() => setMobileOpen((o) => !o)}
              className="rounded-md px-3 py-2 text-muted md:hidden"
              aria-label="Menu"
            >
              <span className="block h-0.5 w-5 bg-current"></span>
              <span className="mt-1 block h-0.5 w-5 bg-current"></span>
              <span className="mt-1 block h-0.5 w-5 bg-current"></span>
            </button>
          </div>

          {mobileOpen && (
            <div className="border-t border-border md:hidden">
              <div className="mx-auto flex max-w-7xl flex-col gap-1 px-6 py-3">
                {tabs.map((t) => (
                  <Link
                    key={t.href}
                    href={t.href}
                    onClick={() => setMobileOpen(false)}
                    className="rounded-md px-3 py-2 text-sm text-muted hover:bg-panel hover:text-fg"
                  >
                    {t.label}
                  </Link>
                ))}
                <MobileUserChip />
              </div>
            </div>
          )}
        </nav>

        <GlobalSearch />

        <div className="mx-auto max-w-7xl px-6 py-6">
          <TrialBanner />
          {children}
        </div>

        <footer className="mt-16 border-t border-border">
          <div className="mx-auto max-w-7xl px-6 py-4 text-xs text-muted">
            Not investment advice. For informational purposes only.&nbsp;
            <Link href="/legal/risk" className="hover:text-fg">Risk disclosure</Link>
          </div>
        </footer>
      </div>
    </ToastProvider>
  );
}

function UserChip() {
  const { user, loading, signout } = useUser();
  const [open, setOpen] = useState(false);
  if (loading) return <div className="ml-2 h-7 w-20 animate-pulse rounded bg-panel" />;
  if (!user) {
    return (
      <Link href="/signin" className="btn-primary ml-2 text-sm">Sign in</Link>
    );
  }

  const tierColor =
    user.tier === "premium" ? "bg-accent/20 text-accent"
    : user.tier === "pro" ? "bg-up/20 text-up"
    : "bg-muted/20 text-muted";

  return (
    <div className="relative ml-2">
      <button
        onClick={() => setOpen((o) => !o)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        className="flex items-center gap-2 rounded-md border border-border bg-panel px-3 py-1.5 text-sm hover:bg-black/30"
      >
        <span className="font-medium">{user.name?.split(" ")[0] || user.email.split("@")[0]}</span>
        <span className={`rounded px-1.5 py-0.5 text-[10px] uppercase ${tierColor}`}>{user.tier}</span>
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-56 rounded-lg border border-border bg-panel shadow-xl">
          <div className="border-b border-border px-4 py-3 text-xs text-muted">{user.email}</div>
          <Link href="/app/billing" className="block px-4 py-2 text-sm hover:bg-black/30">Billing &amp; plan</Link>
          {user.tier === "free" && (
            <Link href="/app/billing" className="block px-4 py-2 text-sm text-accent hover:bg-black/30">
              Upgrade to Pro →
            </Link>
          )}
          <button
            onClick={async () => { await signout(); window.location.href = "/"; }}
            className="block w-full border-t border-border px-4 py-2 text-left text-sm text-muted hover:text-down"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

function MobileUserChip() {
  const { user, signout } = useUser();
  if (!user) {
    return (
      <Link href="/signin" className="mt-2 rounded-md border border-border px-3 py-2 text-sm">
        Sign in
      </Link>
    );
  }
  return (
    <>
      <div className="mt-2 border-t border-border pt-2 text-xs text-muted">{user.email} · {user.tier}</div>
      <Link href="/app/billing" className="px-3 py-2 text-sm text-muted">Billing &amp; plan</Link>
      <button onClick={async () => { await signout(); window.location.href = "/"; }} className="px-3 py-2 text-left text-sm text-down">
        Sign out
      </button>
    </>
  );
}
