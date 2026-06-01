"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@/components/UserContext";
import { CardSkeleton } from "@/components/Skeleton";
import { userLocale } from "@/lib/datetime";
import { handle401, errorMessage } from "@/lib/api";

type Stats = {
  users_total: number; users_pro: number; users_premium: number;
  trials_active: number; trials_expiring_7d: number;
  active_subscriptions: number; alerts_delivered: number; mrr_usd: number;
};

type UserRow = {
  id: string; email: string; name: string | null; tier: string;
  is_admin: boolean; is_lifetime: boolean;
  trial_ends_at: string | null; trial_days_left: number | null;
  has_stripe: boolean; has_telegram: boolean;
  drip_state: string;
  created_at: string;
};

type ExpiringRow = {
  id: string; email: string; name: string | null; tier: string;
  trial_ends_at: string; days_left: number;
  drip_state: string; has_telegram: boolean;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function adminGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { credentials: "include", cache: "no-store" });
  if (!r.ok) {
    handle401(r.status);
    throw new Error(`${r.status} ${r.statusText}`);
  }
  return r.json();
}

async function adminPatch(path: string, body: any) {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "PATCH", credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    handle401(r.status);
    throw new Error(`${r.status} ${r.statusText}`);
  }
  return r.json();
}

export default function AdminPage() {
  const router = useRouter();
  const { user, loading } = useUser();
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [expiring, setExpiring] = useState<ExpiringRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) { router.push("/signin?next=/app/admin"); return; }
    // Backend /api/admin/* returns 401 (not 403) for non-admins — without
    // this client-side guard, a signed-in non-admin who bookmarks /app/admin
    // hits the API, gets 401, gets redirected to /signin, signs in again
    // (already signed in!), bounces back to /app/admin, and loops. Bounce
    // them to /app/scanner with a notice instead.
    if (!user.is_admin) { router.push("/app/scanner"); return; }
    Promise.all([
      adminGet<Stats>("/api/admin/stats"),
      adminGet<{ items: UserRow[] }>("/api/admin/users"),
      adminGet<{ items: ExpiringRow[] }>("/api/admin/users/expiring?days=7"),
    ]).then(([s, u, e]) => { setStats(s); setUsers(u.items); setExpiring(e.items); })
      .catch((e) => setErr(e.message));
  }, [user, loading, router]);

  async function setTier(userId: string, tier: string) {
    try {
      await adminPatch(`/api/admin/users/${userId}/tier`, { tier });
      setUsers((prev) => prev.map((u) => u.id === userId ? { ...u, tier } : u));
    } catch (e: unknown) { alert(errorMessage(e)); }
  }

  if (loading) return <CardSkeleton rows={6} />;
  if (err) {
    return (
      <div className="card p-8">
        <h1 className="text-2xl font-bold">Admin access required</h1>
        <p className="mt-2 text-sm text-muted">{err}</p>
        <p className="mt-4 text-sm text-muted">Your account must have <code className="rounded bg-panel px-1.5 py-0.5">is_admin=true</code>. Run the seed-owner script.</p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Admin</h1>
      <p className="text-sm text-muted">Owner-only operational dashboard.</p>

      <div className="mt-3 flex flex-wrap gap-3 text-sm">
        <a href="/app/admin/revenue" className="link">Revenue &rarr;</a>
        <a href="/app/admin/email-preview" className="link">Email preview &rarr;</a>
        <a href="/app/inbox" className="link">Inbox auto-handler &rarr;</a>
      </div>

      {stats && (
        <div className="mt-6 grid gap-3 sm:grid-cols-3 lg:grid-cols-8">
          <Stat label="Users" value={String(stats.users_total)} />
          <Stat label="Pro" value={String(stats.users_pro)} />
          <Stat label="Premium" value={String(stats.users_premium)} tone="up" />
          <Stat label="Active subs" value={String(stats.active_subscriptions)} />
          <Stat label="Trials active" value={String(stats.trials_active)} tone="accent" />
          <Stat label="Trials end ≤7d" value={String(stats.trials_expiring_7d)} tone={stats.trials_expiring_7d > 0 ? "warn" : undefined} />
          <Stat label="Alerts sent" value={String(stats.alerts_delivered)} />
          <Stat label="MRR" value={`$${stats.mrr_usd.toLocaleString()}`} tone="up" />
        </div>
      )}

      {/* Conversion-priority users */}
      {expiring.length > 0 && (
        <>
          <h2 className="mt-10 text-xl font-semibold">Trials expiring in next 7 days</h2>
          <p className="text-xs text-muted">No card on file. These are the highest-leverage outreach targets in the first 100 customers.</p>
          <div className="card mt-4 overflow-x-auto border-warn/30">
            <table className="w-full text-sm nums">
              <thead className="border-b border-border bg-warn/5 text-xs uppercase text-muted">
                <tr>
                  <th className="px-4 py-2 text-left">Email</th>
                  <th className="px-4 py-2 text-left">Name</th>
                  <th className="px-4 py-2 text-left">Tier</th>
                  <th className="px-4 py-2 text-right">Days left</th>
                  <th className="px-4 py-2 text-left">Drip sent</th>
                  <th className="px-4 py-2 text-center">Telegram?</th>
                </tr>
              </thead>
              <tbody>
                {expiring.map((u) => (
                  <tr key={u.id} className="border-b border-border/50">
                    <td className="px-4 py-2 font-medium">{u.email}</td>
                    <td className="px-4 py-2 text-muted">{u.name || "—"}</td>
                    <td className="px-4 py-2"><TierBadge tier={u.tier} /></td>
                    <td className={`px-4 py-2 text-right font-semibold ${u.days_left <= 1 ? "text-down" : u.days_left <= 3 ? "text-warn" : ""}`}>
                      {u.days_left}d
                    </td>
                    <td className="px-4 py-2 text-xs text-muted nums">{u.drip_state || "—"}</td>
                    <td className="px-4 py-2 text-center">{u.has_telegram ? "✓" : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h2 className="mt-10 text-xl font-semibold">All users</h2>
      <div className="card mt-4 overflow-x-auto">
        <table className="w-full text-sm nums">
          <thead className="text-xs uppercase text-muted">
            <tr>
              <th className="px-4 py-2 text-left">Email</th>
              <th className="px-4 py-2 text-left">Name</th>
              <th className="px-4 py-2 text-left">Tier</th>
              <th className="px-4 py-2 text-right">Trial</th>
              <th className="px-4 py-2 text-center">Card</th>
              <th className="px-4 py-2 text-center">TG</th>
              <th className="px-4 py-2 text-left">Created</th>
              <th className="px-4 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-border/20 hover:bg-panel/60">
                <td className="px-4 py-2 font-medium">
                  {u.email}
                  {u.is_admin && <span className="ml-2 rounded bg-accent/20 px-1.5 py-0.5 text-[10px] uppercase text-accent">admin</span>}
                  {u.is_lifetime && <span className="ml-2 rounded bg-up/20 px-1.5 py-0.5 text-[10px] uppercase text-up">lifetime</span>}
                </td>
                <td className="px-4 py-2 text-muted">{u.name || "—"}</td>
                <td className="px-4 py-2"><TierBadge tier={u.tier} /></td>
                <td className="px-4 py-2 text-right text-xs">
                  {u.trial_days_left !== null
                    ? <span className={u.trial_days_left <= 1 ? "text-down" : u.trial_days_left <= 3 ? "text-warn" : "text-muted"}>{u.trial_days_left}d</span>
                    : <span className="text-subtle">—</span>}
                </td>
                <td className="px-4 py-2 text-center text-xs">{u.has_stripe ? "✓" : "—"}</td>
                <td className="px-4 py-2 text-center text-xs">{u.has_telegram ? "✓" : "—"}</td>
                <td className="px-4 py-2 text-xs text-muted">{new Date(u.created_at).toLocaleDateString(userLocale(), { day: "numeric", month: "short", year: "numeric" })}</td>
                <td className="px-4 py-2 text-right">
                  <select
                    value={u.tier}
                    onChange={(e) => setTier(u.id, e.target.value)}
                    className="bg-transparent text-sm"
                  >
                    <option value="free">free</option>
                    <option value="pro">pro</option>
                    <option value="premium">premium</option>
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "up" | "accent" | "warn" }) {
  const cls =
    tone === "up" ? "text-up"
    : tone === "accent" ? "text-accent"
    : tone === "warn" ? "text-warn"
    : "";
  return (
    <div className="card p-4">
      <div className="text-xs uppercase text-muted">{label}</div>
      <div className={`mt-1 text-2xl font-bold nums ${cls}`}>{value}</div>
    </div>
  );
}

function TierBadge({ tier }: { tier: string }) {
  const cls =
    tier === "premium" ? "bg-accent/20 text-accent"
    : tier === "pro" ? "bg-up/20 text-up"
    : "bg-panel text-muted";
  return <span className={`rounded px-2 py-0.5 text-xs uppercase ${cls}`}>{tier}</span>;
}
