"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { ToastProvider } from "@/components/Toast";
import { GlobalSearch } from "@/components/GlobalSearch";
import { api } from "@/lib/api";
import { useUser } from "@/components/UserContext";
import { useTheme, type Theme } from "@/components/ThemeProvider";
import { TrialBanner } from "@/components/TrialBanner";
import { TrialEndedModal } from "@/components/TrialEndedModal";
import { TrialEarlyCapture } from "@/components/TrialEarlyCapture";
import { StaleDataBanner } from "@/components/StaleDataBanner";
import { DunningBanner } from "@/components/DunningBanner";
import { UpgradeNudge } from "@/components/UpgradeNudge";
import { OnboardingTip } from "@/components/OnboardingTip";
import { BreakingNewsBar } from "@/components/BreakingNewsBar";
import { FirstRunTipProvider } from "@/components/FirstRunTip";
import { EmailVerificationBanner } from "@/components/EmailVerificationBanner";

/**
 * Platform-aware shortcut label for the search trigger. ⌘K on Mac, Ctrl K
 * elsewhere (a real user misread the ⌘ glyph as a hashtag on 2026-05-16). We
 * can't read navigator during SSR, so it defaults to ⌘K and corrects after
 * hydration; the word "Search" always precedes the chip.
 */
function useShortcutLabel(): string {
  const [label, setLabel] = useState("⌘K");
  useEffect(() => {
    if (typeof navigator === "undefined") return;
    const isMac = /mac|iphone|ipad/i.test(navigator.platform || navigator.userAgent || "");
    setLabel(isMac ? "⌘K" : "Ctrl K");
  }, []);
  return label;
}

/**
 * App navigation, grouped for a left rail. The old flat 8-tab top bar was at
 * its width limit and left several built routes (News, Earnings, IPOs) with no
 * inbound link at all — a sidebar has room to surface them. "Alerts" stays a
 * top-group item since it's the #1 pay-driver and watchlist→alert is the flow.
 */
const NAV_GROUPS: { label: string; items: { href: string; label: string }[] }[] = [
  {
    label: "Trade",
    items: [
      { href: "/app/scanner", label: "Scanner" },
      { href: "/app/watchlist", label: "Watchlist" },
      { href: "/app/alerts", label: "Alerts" },
    ],
  },
  {
    label: "Signals",
    items: [
      { href: "/app/heatmap", label: "Heatmap" },
      { href: "/app/squeeze", label: "Squeeze" },
      { href: "/app/regime", label: "Regime" },
    ],
  },
  {
    label: "Ownership & markets",
    items: [
      { href: "/app/congress", label: "Congress" },
      { href: "/app/holdings", label: "Insider buys" },
      { href: "/app/news", label: "News" },
      { href: "/app/earnings", label: "Earnings" },
      { href: "/app/ipos", label: "IPOs" },
    ],
  },
];

function openSearch() {
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }));
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();
  const isActive = (href: string) =>
    !!pathname && (pathname === href || pathname.startsWith(`${href}/`));

  return (
    <ToastProvider>
      <div className="flex min-h-screen">
        {/* ── Left sidebar (desktop) — destinations ─────────────────────── */}
        <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col border-r border-border bg-panel/30 md:flex">
          <div className="px-5 py-4">
            <Link href="/" className="flex items-center gap-2">
              <div className="h-2 w-6 rounded-full bg-accent" />
              <span className="text-base font-semibold tracking-tight">Tapeline</span>
            </Link>
          </div>
          <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-2">
            {NAV_GROUPS.map((group) => (
              <div key={group.label}>
                <div className="px-2 pb-1.5 text-[10px] font-medium uppercase tracking-wider text-subtle">
                  {group.label}
                </div>
                <div className="space-y-0.5">
                  {group.items.map((item) => (
                    <SidebarLink key={item.href} href={item.href} label={item.label} active={isActive(item.href)} />
                  ))}
                </div>
              </div>
            ))}
            <SavedScreens />
          </nav>
          <div className="border-t border-border p-3">
            <AccountMenu />
          </div>
        </aside>

        {/* ── Main column ───────────────────────────────────────────────── */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Thin top bar — context: search (+ mobile logo/menu) */}
          <header className="sticky top-0 z-40 flex items-center gap-3 border-b border-border bg-background/90 px-4 py-2.5 backdrop-blur">
            <button
              onClick={() => setMobileOpen(true)}
              className="rounded-md p-2 text-muted hover:text-fg md:hidden"
              aria-label="Open menu"
            >
              <span className="block h-0.5 w-5 bg-current"></span>
              <span className="mt-1 block h-0.5 w-5 bg-current"></span>
              <span className="mt-1 block h-0.5 w-5 bg-current"></span>
            </button>
            <Link href="/" className="flex items-center gap-2 md:hidden">
              <div className="h-2 w-5 rounded-full bg-accent" />
              <span className="text-sm font-semibold tracking-tight">Tapeline</span>
            </Link>
            <SearchTrigger />
          </header>

          <GlobalSearch />

          <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">
            {/* Account-health banners (always shown, action-required) sit OUTSIDE
                the first-run provider so a welcome card can never hide a payment,
                data, or verification warning. */}
            <DunningBanner />
            <StaleDataBanner />
            <EmailVerificationBanner />
            {/* First-run coordination: while OnboardingTip is up, the promo/status
                banners yield so a brand-new user gets a clean welcome. */}
            <FirstRunTipProvider>
              <TrialBanner />
              <UpgradeNudge />
              <BreakingNewsBar />
              <OnboardingTip />
            </FirstRunTipProvider>
            {/* fade-in: key={pathname} remounts children per route so the CSS
                animation re-fires. Reduced-motion users get the final state. */}
            <div key={pathname} className="fade-in">{children}</div>
          </main>

          {/* Self-gating card-capture moments — render nothing unless their
              user/tier conditions are met, so safe to mount globally. */}
          <TrialEndedModal />
          <TrialEarlyCapture />

          <footer className="mt-16">
            <div className="mx-auto max-w-7xl px-6 py-4 text-xs text-muted">
              Not investment advice. For informational purposes only.&nbsp;
              <Link href="/legal/risk" className="hover:text-fg">Risk disclosure</Link>
            </div>
          </footer>
        </div>
      </div>

      {/* ── Mobile drawer — the sidebar as a slide-over ───────────────────── */}
      {mobileOpen && (
        <div className="md:hidden">
          <button
            aria-label="Close menu"
            onClick={() => setMobileOpen(false)}
            className="fixed inset-0 z-40 bg-black/50"
          />
          <div className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85%] flex-col overflow-y-auto border-r border-border bg-background">
            <div className="flex items-center justify-between px-5 py-4">
              <Link href="/" onClick={() => setMobileOpen(false)} className="flex items-center gap-2">
                <div className="h-2 w-6 rounded-full bg-accent" />
                <span className="text-base font-semibold tracking-tight">Tapeline</span>
              </Link>
              <button
                onClick={() => setMobileOpen(false)}
                aria-label="Close menu"
                className="rounded-md p-2 text-muted hover:text-fg"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
              </button>
            </div>
            <nav className="flex-1 space-y-5 px-3 py-2">
              {NAV_GROUPS.map((group) => (
                <div key={group.label}>
                  <div className="px-2 pb-1.5 text-[10px] font-medium uppercase tracking-wider text-subtle">
                    {group.label}
                  </div>
                  <div className="space-y-0.5">
                    {group.items.map((item) => (
                      <SidebarLink
                        key={item.href}
                        href={item.href}
                        label={item.label}
                        active={isActive(item.href)}
                        onNavigate={() => setMobileOpen(false)}
                      />
                    ))}
                  </div>
                </div>
              ))}
              <SavedScreens onNavigate={() => setMobileOpen(false)} />
            </nav>
            <div className="border-t border-border px-3 py-3">
              <MobileAccount onNavigate={() => setMobileOpen(false)} />
            </div>
          </div>
        </div>
      )}
    </ToastProvider>
  );
}

function SidebarLink({
  href,
  label,
  active,
  onNavigate,
}: {
  href: string;
  label: string;
  active: boolean;
  onNavigate?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={`block rounded-md px-2.5 py-2 text-sm transition-colors ${
        active
          ? "bg-accent/10 font-medium text-fg"
          : "text-muted hover:bg-panel hover:text-fg"
      }`}
    >
      {label}
    </Link>
  );
}

/**
 * "Saved screens" sidebar group — the user's saved scanner presets as nav
 * objects (the plan's retention lever). Each links to /app/scanner?preset=<id>,
 * which the scanner reads on mount and applies. Fetched once when the layout
 * mounts (the app layout persists across route changes, so this is one call per
 * session, not per page); renders nothing when there are no presets, and never
 * throws — a saved-screens list is a nicety, not load-bearing chrome.
 */
function SavedScreens({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useUser();
  const [items, setItems] = useState<{ id: number; name: string }[]>([]);
  useEffect(() => {
    if (!user) { setItems([]); return; }
    let cancelled = false;
    api.presets()
      .then((r) => { if (!cancelled) setItems(r.items.map((x) => ({ id: x.id, name: x.name }))); })
      .catch(() => { /* nicety — never break the sidebar */ });
    return () => { cancelled = true; };
  }, [user]);
  if (items.length === 0) return null;
  return (
    <div>
      <div className="px-2 pb-1.5 text-[10px] font-medium uppercase tracking-wider text-subtle">
        Saved screens
      </div>
      <div className="space-y-0.5">
        {items.map((p) => (
          <SidebarLink
            key={p.id}
            href={`/app/scanner?preset=${p.id}`}
            label={p.name}
            active={false}
            onNavigate={onNavigate}
          />
        ))}
      </div>
    </div>
  );
}

function SearchTrigger() {
  const label = useShortcutLabel();
  return (
    <button
      onClick={openSearch}
      className="flex w-full max-w-md items-center gap-2 rounded-lg border border-border bg-panel/60 px-3 py-2 text-sm text-muted transition-colors hover:text-fg"
      title="Search any ticker"
    >
      <svg width="16" height="16" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <circle cx="8" cy="8" r="5.25" stroke="currentColor" strokeWidth="1.6" />
        <path d="M12 12l3.5 3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
      <span>Search any ticker…</span>
      <kbd className="ml-auto rounded bg-panel px-1.5 py-0.5 font-mono text-[10px]" aria-label="Keyboard shortcut">
        {label}
      </kbd>
    </button>
  );
}

/**
 * Account menu in the sidebar footer. Trigger sits at the bottom-left, so the
 * menu opens UPWARD. Carries the full destination set (Account, Usage, Email
 * prefs, API keys, Billing, Referrals) + theme + sign out.
 */
function AccountMenu() {
  const { user, loading, signout } = useUser();
  const [open, setOpen] = useState(false);
  if (loading) return <div className="h-9 animate-pulse rounded-md bg-panel" />;
  if (!user) {
    return (
      <Link href="/signin" className="btn-primary block text-center text-sm">Sign in</Link>
    );
  }

  const tierColor =
    user.tier === "premium" ? "bg-accent/20 text-accent"
    : user.tier === "pro" ? "bg-up/20 text-up"
    : "bg-muted/20 text-muted";
  const displayName = (user.name?.split(" ")[0] || user.email.split("@")[0] || "").trim();

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm hover:bg-panel"
        aria-label={`Account menu for ${displayName}`}
      >
        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-gradient-to-br from-accent to-accent2 text-[11px] font-semibold text-white">
          {displayName.slice(0, 1).toUpperCase()}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{displayName}</span>
          <span className="block truncate text-xs text-muted">{user.email}</span>
        </span>
        <span className={`rounded px-1.5 py-0.5 text-[10px] uppercase ${tierColor}`}>{user.tier}</span>
      </button>
      {open && (
        <div className="absolute bottom-full left-0 right-0 mb-2 max-h-[70vh] overflow-y-auto rounded-lg border border-border bg-surface shadow-xl">
          <Link href="/app/account" className="block px-4 py-2 text-sm hover:bg-panel-hover">Account &amp; settings</Link>
          <Link href="/app/usage" className="block px-4 py-2 text-sm hover:bg-panel-hover">Usage &amp; limits</Link>
          <Link href="/app/settings/email" className="block px-4 py-2 text-sm hover:bg-panel-hover">Email preferences</Link>
          <Link href="/app/api-keys" className="block px-4 py-2 text-sm hover:bg-panel-hover">API keys</Link>
          <div className="border-t border-border" />
          <ThemeSwitcher />
          <div className="border-t border-border" />
          <Link href="/app/billing" className="block px-4 py-2 text-sm hover:bg-panel-hover">Billing &amp; plan</Link>
          {user.tier === "free" && (
            <Link href="/app/billing" className="block px-4 py-2 text-sm text-accent hover:bg-panel-hover">Upgrade to Pro →</Link>
          )}
          <Link href="/app/referrals" className="block px-4 py-2 text-sm hover:bg-panel-hover">
            Refer a friend
            <span className="block text-xs text-muted">You both get a free month</span>
          </Link>
          <button
            onClick={async () => { await signout(); window.location.href = "/"; }}
            className="block w-full px-4 py-2 text-left text-sm text-muted hover:text-down"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Three-segment theme picker (Light / Dark / System). System respects OS
 * prefers-color-scheme. No external dependency.
 */
function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  const options: { value: Theme; label: string; icon: string }[] = [
    { value: "light",  label: "Light",  icon: "☀" },
    { value: "dark",   label: "Dark",   icon: "☾" },
    { value: "system", label: "System", icon: "⚙" },
  ];
  return (
    <div className="px-4 py-2">
      <div className="mb-1.5 text-[10px] uppercase tracking-wider text-subtle">Appearance</div>
      <div className="flex gap-1 rounded-full bg-fg/5 p-1">
        {options.map((opt) => {
          const active = theme === opt.value;
          return (
            <button
              key={opt.value}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => setTheme(opt.value)}
              className={`flex-1 rounded-full px-2 py-1 text-xs font-medium transition ${
                active ? "bg-fg/10 text-fg" : "text-muted hover:text-fg"
              }`}
            >
              <span className="mr-1" aria-hidden="true">{opt.icon}</span>
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Account block for the mobile drawer footer — same destinations, flat list. */
function MobileAccount({ onNavigate }: { onNavigate: () => void }) {
  const { user, signout } = useUser();
  if (!user) {
    return (
      <Link href="/signin" onClick={onNavigate} className="block rounded-md border border-border px-3 py-2 text-sm">
        Sign in
      </Link>
    );
  }
  const link = "block rounded-md px-3 py-2 text-sm text-muted hover:bg-panel hover:text-fg";
  return (
    <div className="space-y-0.5">
      <div className="px-3 pb-1 text-xs text-muted">{user.email} · {user.tier}</div>
      <Link href="/app/account" onClick={onNavigate} className={link}>Account &amp; settings</Link>
      <Link href="/app/usage" onClick={onNavigate} className={link}>Usage &amp; limits</Link>
      <Link href="/app/settings/email" onClick={onNavigate} className={link}>Email preferences</Link>
      <Link href="/app/api-keys" onClick={onNavigate} className={link}>API keys</Link>
      <Link href="/app/billing" onClick={onNavigate} className={link}>Billing &amp; plan</Link>
      <Link href="/app/referrals" onClick={onNavigate} className={link}>Refer a friend</Link>
      <button
        onClick={async () => { await signout(); window.location.href = "/"; }}
        className="block w-full rounded-md px-3 py-2 text-left text-sm text-down hover:bg-panel"
      >
        Sign out
      </button>
    </div>
  );
}
