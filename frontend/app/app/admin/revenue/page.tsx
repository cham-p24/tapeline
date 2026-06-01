"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@/components/UserContext";
import { CardSkeleton } from "@/components/Skeleton";
import { handle401 } from "@/lib/api";

type Revenue = {
  mrr_usd: number;
  arr_usd: number;
  active_subscriptions: number;
  subs_by_tier: Record<string, number>;
  subs_by_period: Record<string, number>;
  subs_by_status: Record<string, number>;
  users_total: number;
  trials_active: number;
  paid_customers: number;
  signup_to_paid_pct: number;
  cancellations_scheduled: number;
  cancellation_reasons: Record<string, number>;
  save_offers_redeemed: number;
  subscriptions_paused: number;
  in_dunning: number;
  checkouts_in_flight: number;
  referred_users: number;
  referral_credits_outstanding: number;
  drip_reach: Record<string, number>;
  webhook_events: Record<string, number>;
  generated_at: string;
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

const money = (n: number) =>
  `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// Friendly labels for the lifecycle-drip tokens stored in drip_state/winback_state.
const DRIP_LABELS: Record<string, string> = {
  abandon1: "Checkout recovery",
  re14: "Re-engagement (14d dormant)",
  annual_p: "Annual-plan upgrade nudge",
  ref_m3: "Referral milestone · 3",
  ref_m5: "Referral milestone · 5",
  ref_m10: "Referral milestone · 10",
  ref_m25: "Referral milestone · 25",
  wb30: "Winback · 30d",
  wb60: "Winback · 60d",
  wb90: "Winback · 90d",
};

export default function RevenuePage() {
  const router = useRouter();
  const { user, loading } = useUser();
  const [data, setData] = useState<Revenue | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) { router.push("/signin?next=/app/admin/revenue"); return; }
    if (!user.is_admin) { router.push("/app/scanner"); return; }
    adminGet<Revenue>("/api/admin/revenue")
      .then(setData)
      .catch((e) => setErr(e.message));
  }, [user, loading, router]);

  if (loading) return <CardSkeleton rows={6} />;
  if (err) {
    return (
      <div className="card p-8">
        <h1 className="text-2xl font-bold">Admin access required</h1>
        <p className="mt-2 text-sm text-muted">{err}</p>
        <p className="mt-4 text-sm text-muted">Your account must have <code className="rounded bg-panel px-1.5 py-0.5">is_admin=true</code>.</p>
      </div>
    );
  }
  if (!data) return <CardSkeleton rows={6} />;

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Revenue</h1>
          <p className="text-sm text-muted">Exact MRR/ARR, the subscription book, churn, and lifecycle-lever reach.</p>
        </div>
        <a href="/app/admin" className="link text-sm">&larr; Admin</a>
      </div>

      {/* Headline */}
      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="MRR" value={money(data.mrr_usd)} tone="up" />
        <Stat label="ARR" value={money(data.arr_usd)} tone="up" />
        <Stat label="Active subs" value={String(data.active_subscriptions)} />
        <Stat label="Paid customers" value={String(data.paid_customers)} />
      </div>

      {/* Funnel + leak */}
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Trials active" value={String(data.trials_active)} tone="accent" />
        <Stat label="Signup → paid" value={`${data.signup_to_paid_pct}%`} />
        <Stat label="In dunning" value={String(data.in_dunning)} tone={data.in_dunning > 0 ? "warn" : undefined} />
        <Stat label="Checkouts in-flight" value={String(data.checkouts_in_flight)} tone={data.checkouts_in_flight > 0 ? "accent" : undefined} />
      </div>

      {/* Subscription book */}
      <h2 className="mt-10 text-xl font-semibold">Subscription book</h2>
      <p className="text-xs text-muted">Tier &amp; billing-period counts are active subs only; status covers the whole book.</p>
      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <Breakdown title="By tier (active)" map={data.subs_by_tier} />
        <Breakdown title="By period (active)" map={data.subs_by_period} />
        <Breakdown title="By status (all)" map={data.subs_by_status} />
      </div>

      {/* Churn & retention */}
      <h2 className="mt-10 text-xl font-semibold">Churn &amp; retention</h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Cancel scheduled" value={String(data.cancellations_scheduled)} tone={data.cancellations_scheduled > 0 ? "warn" : undefined} />
        <Stat label="Save offers used" value={String(data.save_offers_redeemed)} />
        <Stat label="Paused subs" value={String(data.subscriptions_paused)} />
        <Stat label="Referred users" value={String(data.referred_users)} />
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <Breakdown title="Cancellation reasons" map={data.cancellation_reasons} empty="No cancellations yet" />
        <div className="card p-4">
          <div className="text-xs uppercase text-muted">Referral credits outstanding</div>
          <div className="mt-1 text-2xl font-bold nums">{data.referral_credits_outstanding} <span className="text-sm font-normal text-muted">free months owed</span></div>
        </div>
      </div>

      {/* Lifecycle-lever reach */}
      <h2 className="mt-10 text-xl font-semibold">Lifecycle-lever reach</h2>
      <p className="text-xs text-muted">Distinct users each automated email lever has touched (lifetime).</p>
      <div className="card mt-4 overflow-x-auto">
        <table className="w-full text-sm nums">
          <tbody>
            {Object.entries(data.drip_reach).map(([tok, n]) => (
              <tr key={tok} className="border-b border-border/30 last:border-0">
                <td className="px-4 py-2">{DRIP_LABELS[tok] || tok}</td>
                <td className="px-4 py-2 text-right font-semibold">{n}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Webhook volume */}
      <h2 className="mt-10 text-xl font-semibold">Stripe webhook volume</h2>
      <p className="text-xs text-muted">Lifetime processed events by type — the billing system's heartbeat.</p>
      <div className="mt-4">
        <Breakdown title="" map={data.webhook_events} empty="No webhooks processed yet" />
      </div>

      <p className="mt-8 text-xs text-subtle">Generated {new Date(data.generated_at).toLocaleString()}.</p>
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

function Breakdown({ title, map, empty }: { title: string; map: Record<string, number>; empty?: string }) {
  const entries = Object.entries(map);
  return (
    <div className="card p-4">
      {title && <div className="mb-2 text-xs uppercase text-muted">{title}</div>}
      {entries.length === 0 ? (
        <div className="text-sm text-subtle">{empty || "None yet"}</div>
      ) : (
        <table className="w-full text-sm nums">
          <tbody>
            {entries.map(([k, v]) => (
              <tr key={k} className="border-b border-border/30 last:border-0">
                <td className="px-1 py-1.5 capitalize">{k}</td>
                <td className="px-1 py-1.5 text-right font-semibold">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
