"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { ToastProvider } from "@/components/Toast";
import { GlobalSearch } from "@/components/GlobalSearch";
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
import { EmailVerificationBanner } from "@/components/EmailVerificationBanner";

/**
 * Platform-aware shortcut key for the Search button.
 *
 * Was hardcoded to ⌘K which is confusing on Windows / Linux (and a real
 * user reported this on 2026-05-16: "what does the hashtag looking thing
 * and the K mean?" — the ⌘ glyph reads as a hashtag-ish symbol when you
 * don't know it means Command).
 *
 * We can't read navigator.platform during SSR, so the hook returns "⌘K"
 * as the default and updates to "Ctrl K" on Windows after hydration.
 * The label always says "Search" before the chip so the function is
 * obvious even if the chip is misread.
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

const tabs = [
  { href: "/app/scanner", label: "Scanner" },
  { href: "/app/heatmap", label: "Heatmap" },
  { href: "/app/watchlist", label: "Watchlist" },
  // Alerts is the #1 pay-driver — it belongs in the main nav (desktop AND
  // mobile, which both render this array), not buried in the account
  // dropdown. Sits next to Watchlist since watchlist → alert is the
  // natural flow.
  { href: "/app/alerts", label: "Alerts" },
  { href: "/app/squeeze", label: "Squeeze" },
  { href: "/app/regime", label: "Regime" },
  { href: "/app/congress", label: "Congress" },
  { href: "/app/holdings", label: "Insider buys" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  // Path key for the fade-in wrapper — remounts the children on every
  // route change so the .fade-in CSS animation re-fires. Without the
  // key, client-side nav reuses the same div and the animation only
  // runs once on first mount.
  const pathname = usePathname();
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
              <SearchButton />
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
            <div className="md:hidden">
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
          <DunningBanner />
          <StaleDataBanner />
          <EmailVerificationBanner />
          <TrialBanner />
          {/* Free→Pro nudge. Trialing users are on Premium → TrialBanner owns
              their conversion moment; genuine Free users get this instead, so
              the two never show together. Self-gating on /api/me.nudge. */}
          <UpgradeNudge />
          <BreakingNewsBar />
          <OnboardingTip />
          {/* fade-in: 180ms opacity + 4px translateY on every route entry.
              `key={pathname}` forces a remount on each client-side nav so
              the CSS animation re-fires; without it the animation would
              only run on initial page load. Reduced-motion users get the
              final state immediately. */}
          <div key={pathname} className="fade-in">{children}</div>
        </div>

        {/* Card-capture moments. Both are self-gating on user/tier state:
            - TrialEndedModal fires once when an expired-trial user lands on /app.
            - TrialEarlyCapture fires once mid-trial (days 5-9 remaining).
            They render nothing when their conditions aren't met, so they're
            safe to mount globally. */}
        <TrialEndedModal />
        <TrialEarlyCapture />

        <footer className="mt-16">
          <div className="mx-auto max-w-7xl px-6 py-4 text-xs text-muted">
            Not investment advice. For informational purposes only.&nbsp;
            <Link href="/legal/risk" className="hover:text-fg">Risk disclosure</Link>
          </div>
        </footer>
      </div>
    </ToastProvider>
  );
}

function SearchButton() {
  const label = useShortcutLabel();
  return (
    <button
      onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }))}
      className="ml-3 flex items-center gap-2 rounded-md border border-border bg-panel px-3 py-1.5 text-xs text-muted hover:text-fg"
      title="Search any ticker — keyboard shortcut shown next to the label"
    >
      Search&nbsp;
      <kbd className="rounded bg-panel px-1.5 py-0.5 text-[10px] font-mono" aria-label="Keyboard shortcut">
        {label}
      </kbd>
    </button>
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

  // Prefer the user's first name; fall back to the email local-part if name is
  // blank (some OAuth providers return empty names). Title-cased for display.
  const displayName = (user.name?.split(" ")[0] || user.email.split("@")[0] || "").trim();

  return (
    <div className="relative ml-2">
      <button
        onClick={() => setOpen((o) => !o)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        className="flex items-center gap-2 rounded-md border border-border bg-panel px-3 py-1.5 text-sm hover:bg-panel-hover"
        aria-label={`Account menu for ${displayName}`}
      >
        <span className="font-medium">{displayName}</span>
        <span className={`rounded px-1.5 py-0.5 text-[10px] uppercase ${tierColor}`}>{user.tier}</span>
        <svg width="10" height="10" viewBox="0 0 10 10" className="text-muted" aria-hidden="true">
          <path d="M2 4l3 3 3-3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-60 rounded-lg border border-border bg-panel shadow-xl">
          {/* Header — full email + display name so the user can confirm which
              account is active at a glance. */}
          <div className="border-b border-border px-4 py-3">
            <div className="text-sm font-medium">{displayName}</div>
            <div className="truncate text-xs text-muted">{user.email}</div>
          </div>
          <Link href="/app/account" className="block px-4 py-2 text-sm hover:bg-panel-hover">
            Account &amp; settings
          </Link>
          <Link href="/app/watchlist" className="block px-4 py-2 text-sm hover:bg-panel-hover">
            My watchlist
          </Link>
          <Link href="/app/alerts" className="block px-4 py-2 text-sm hover:bg-panel-hover">
            Alert rules
          </Link>
          <Link href="/app/settings/email" className="block px-4 py-2 text-sm hover:bg-panel-hover">
            Email preferences
          </Link>
          <Link href="/app/api-keys" className="block px-4 py-2 text-sm hover:bg-panel-hover">
            API keys
          </Link>
          <div className="border-t border-border" />
          {/* Theme picker — iOS-style three-segment group. System mode
              respects OS prefers-color-scheme so a user who has Dark Mode
              scheduled at sunset on their Mac gets it automatically. */}
          <ThemeSwitcher />
          <div className="border-t border-border" />
          <Link href="/app/billing" className="block px-4 py-2 text-sm hover:bg-panel-hover">
            Billing &amp; plan
          </Link>
          {user.tier === "free" && (
            <Link href="/app/billing" className="block px-4 py-2 text-sm text-accent hover:bg-panel-hover">
              Upgrade to Pro →
            </Link>
          )}
          {/* Referral program — double-sided (+1 free month of Premium for
              both parties, see /app/referrals). The page shipped fully built
              but was linked from nowhere; the account menu is its home so
              every signed-in user can find it. */}
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
 * Three-segment theme picker. iOS-style — pill background, sliding selected
 * state via just a different bg class. No external dependency.
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
      <div className="text-[10px] uppercase tracking-wider text-subtle mb-1.5">Appearance</div>
      <div className="flex gap-1 rounded-full bg-fg/5 p-1">
        {options.map((opt) => {
          const active = theme === opt.value;
          return (
            <button
              key={opt.value}
              onClick={() => setTheme(opt.value)}
              className={`flex-1 rounded-full px-2 py-1 text-xs font-medium transition ${
                active
                  ? "bg-fg/10 text-fg"
                  : "text-muted hover:text-fg"
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
      <div className="mt-2 pt-2 text-xs text-muted">{user.email} · {user.tier}</div>
      <Link href="/app/billing" className="px-3 py-2 text-sm text-muted">Billing &amp; plan</Link>
      <Link href="/app/referrals" className="px-3 py-2 text-sm text-muted">
        Refer a friend — you both get a free month
      </Link>
      <button onClick={async () => { await signout(); window.location.href = "/"; }} className="px-3 py-2 text-left text-sm text-down">
        Sign out
      </button>
    </>
  );
}
