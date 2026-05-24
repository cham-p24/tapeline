"use client";

/**
 * Account & settings dashboard.
 *
 * Hub page for everything an authenticated user might want to manage about
 * their account. Previously each setting surface lived behind a different
 * top-nav tab or buried inside the billing flow; this page collects them in
 * one place so the "Account & settings" item in the new UserChip dropdown
 * lands somewhere useful.
 *
 * Cards link out to the existing pages — we don't duplicate functionality,
 * just give it a stable home. New settings surfaces should add a card here
 * rather than spawn a new top-level route.
 */
import Link from "next/link";
import { useUser } from "@/components/UserContext";

type Card = {
  title: string;
  href: string;
  description: string;
  badge?: string;
};

export default function AccountPage() {
  const { user, loading } = useUser();

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-panel" />
        <div className="grid gap-4 sm:grid-cols-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-32 animate-pulse rounded-lg bg-panel" />
          ))}
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="card p-6">
        <p className="text-sm">You need to be signed in to manage your account.</p>
        <Link href="/signin" className="btn-primary mt-3 inline-block text-sm">Sign in</Link>
      </div>
    );
  }

  const tierBadge =
    user.tier === "premium" ? "PREMIUM"
    : user.tier === "pro" ? "PRO"
    : "FREE";
  const tierTone =
    user.tier === "premium" ? "bg-accent/20 text-accent"
    : user.tier === "pro" ? "bg-up/20 text-up"
    : "bg-muted/20 text-muted";

  const cards: Card[] = [
    {
      title: "Billing & plan",
      href: "/app/billing",
      description: "Manage subscription, view invoices, upgrade or change plan.",
      badge: tierBadge,
    },
    {
      title: "Email preferences",
      href: "/app/settings/email",
      description: "Choose which alert digests and product emails you receive.",
    },
    {
      title: "Watchlist",
      href: "/app/watchlist",
      description: "Tickers you're tracking + their per-ticker alert rules.",
    },
    {
      title: "Alert rules",
      href: "/app/alerts",
      description: "Score thresholds, squeeze setups, regime flips — all your active rules.",
    },
  ];

  return (
    <div>
      {/* Account summary */}
      <div className="card mb-6 p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight">{user.name || user.email.split("@")[0]}</h1>
            <p className="text-sm text-muted">{user.email}</p>
          </div>
          <span className={`rounded px-2 py-1 text-xs font-semibold uppercase ${tierTone}`}>{tierBadge}</span>
        </div>
        {user.tier === "free" && (
          <Link href="/app/billing" className="btn-primary mt-4 inline-block text-sm">
            Upgrade to Pro →
          </Link>
        )}
      </div>

      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">Manage</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        {cards.map((c) => (
          <Link
            key={c.href}
            href={c.href}
            className="card card-link p-4 hover:border-accent/30 hover:bg-panel-hover"
          >
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold">{c.title}</h3>
              {c.badge && (
                <span className={`rounded px-1.5 py-0.5 text-[10px] uppercase ${tierTone}`}>{c.badge}</span>
              )}
            </div>
            <p className="mt-1 text-xs text-muted leading-relaxed">{c.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
