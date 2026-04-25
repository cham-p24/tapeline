"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@/components/UserContext";

type Stats = {
  users_total: number; users_pro: number; users_premium: number;
  active_subscriptions: number; alerts_delivered: number; mrr_usd: number;
};

type UserRow = { id: string; email: string; tier: string; created_at: string };

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function adminGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { credentials: "include", cache: "no-store" });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function adminPatch(path: string, body: any) {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "PATCH", credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export default function AdminPage() {
  const router = useRouter();
  const { user, loading } = useUser();
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) { router.push("/signin?next=/app/admin"); return; }
    // Backend returns 401 if not admin — catch and show a message
    Promise.all([
      adminGet<Stats>("/api/admin/stats"),
      adminGet<{ items: UserRow[] }>("/api/admin/users"),
    ]).then(([s, u]) => { setStats(s); setUsers(u.items); })
      .catch((e) => setErr(e.message));
  }, [user, loading, router]);

  async function setTier(userId: string, tier: string) {
    try {
      await adminPatch(`/api/admin/users/${userId}/tier`, { tier });
      setUsers((prev) => prev.map((u) => u.id === userId ? { ...u, tier } : u));
    } catch (e: any) { alert(e.message); }
  }

  if (loading) return <div className="text-muted">Loading…</div>;
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

      {stats && (
        <div className="mt-6 grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Users (total)" value={String(stats.users_total)} />
          <Stat label="Pro" value={String(stats.users_pro)} />
          <Stat label="Premium" value={String(stats.users_premium)} />
          <Stat label="Active subs" value={String(stats.active_subscriptions)} />
          <Stat label="Alerts sent" value={String(stats.alerts_delivered)} />
          <Stat label="MRR (est)" value={`$${stats.mrr_usd}`} tone="up" />
        </div>
      )}

      <h2 className="mt-10 text-xl font-semibold">Users</h2>
      <div className="card mt-4 overflow-x-auto">
        <table className="w-full text-sm nums">
          <thead className="border-b border-border bg-black/40 text-xs uppercase text-muted">
            <tr>
              <th className="px-4 py-2 text-left">Email</th>
              <th className="px-4 py-2 text-left">User ID</th>
              <th className="px-4 py-2 text-left">Tier</th>
              <th className="px-4 py-2 text-left">Created</th>
              <th className="px-4 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-border/50 hover:bg-black/20">
                <td className="px-4 py-2 font-medium">{u.email}</td>
                <td className="px-4 py-2 text-muted text-xs font-mono">{u.id}</td>
                <td className="px-4 py-2"><span className="rounded bg-panel px-2 py-0.5 text-xs uppercase">{u.tier}</span></td>
                <td className="px-4 py-2 text-xs text-muted">{new Date(u.created_at).toLocaleDateString()}</td>
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

function Stat({ label, value, tone }: { label: string; value: string; tone?: "up" }) {
  return (
    <div className="card p-4">
      <div className="text-xs uppercase text-muted">{label}</div>
      <div className={`mt-1 text-2xl font-bold nums ${tone === "up" ? "text-up" : ""}`}>{value}</div>
    </div>
  );
}
