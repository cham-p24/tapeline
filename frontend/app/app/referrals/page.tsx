"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useUser } from "@/components/UserContext";
import { useToast } from "@/components/Toast";
import { CardSkeleton } from "@/components/Skeleton";
import { userLocale } from "@/lib/datetime";

type ReferralStats = {
  referral_code: string | null;
  share_url: string | null;
  signed_up: number;
  converted: number;
  // Optional: the field was added to /api/referrals/me on 2026-05-13 alongside
  // the credit-grant mechanic. The Vercel frontend deploys faster than Fly's
  // manual `fly deploy`, so a freshly-deployed frontend can briefly talk to an
  // older backend that omits this field — guard with `?? 0` at every read.
  credit_months?: number;
  months_earned: number;
  referred_users: Array<{ email: string; tier: string; converted: boolean; joined: string | null }>;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function ReferralsPage() {
  const { user } = useUser();
  const { push } = useToast();
  const [stats, setStats] = useState<ReferralStats | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/referrals/me`, { credentials: "include", cache: "no-store" })
      .then((r) => r.ok ? r.json() : null)
      .then(setStats)
      .catch(() => {});
  }, []);

  async function copyLink() {
    if (!stats?.share_url) return;
    try {
      await navigator.clipboard.writeText(stats.share_url);
      push("Referral link copied!", "success");
    } catch {
      push("Couldn't copy — select the link manually", "error");
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Refer a friend, both get a free month</h1>
      <p className="text-sm text-muted">
        Every friend who signs up via your link earns you both 1 free month of Premium. Applied automatically at your next checkout.
      </p>

      {!stats ? (
        <CardSkeleton rows={4} />
      ) : (
        <>
          <div className="card mt-6 p-6">
            <label className="text-xs uppercase text-muted">Your share link</label>
            <div className="mt-2 flex gap-2">
              <input
                readOnly
                value={stats.share_url || ""}
                className="flex-1 rounded-md border border-border bg-panel px-3 py-2 text-sm font-mono"
              />
              <button onClick={copyLink} className="btn-primary text-sm">Copy</button>
            </div>
            <p className="mt-3 text-xs text-muted">
              Referral code: <code className="rounded bg-panel px-1.5 py-0.5 font-mono">{stats.referral_code || "—"}</code>
            </p>
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <Stat label="Signed up via your link" value={String(stats.signed_up)} />
            <Stat label="Free months earned" value={String(stats.months_earned)} tone="up" />
            <Stat label="Unused credit (months)" value={String(stats.credit_months ?? 0)} tone={(stats.credit_months ?? 0) > 0 ? "up" : undefined} />
          </div>

          {stats.referred_users.length > 0 && (
            <>
              <h2 className="mt-10 text-xl font-semibold">People you&apos;ve referred</h2>
              <div className="card mt-4 overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-panel text-xs uppercase text-muted">
                    <tr>
                      <th className="px-4 py-2 text-left">Email</th>
                      <th className="px-4 py-2 text-left">Tier</th>
                      <th className="px-4 py-2 text-left">Converted</th>
                      <th className="px-4 py-2 text-left">Joined</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.referred_users.map((u, i) => (
                      <tr key={i} className="border-b border-border/50">
                        <td className="px-4 py-2 font-mono text-xs">{u.email}</td>
                        <td className="px-4 py-2 text-muted">{u.tier}</td>
                        <td className="px-4 py-2">{u.converted ? "✓" : "pending"}</td>
                        <td className="px-4 py-2 text-muted text-xs">{u.joined ? new Date(u.joined).toLocaleDateString(userLocale(), { day: "numeric", month: "short", year: "numeric" }) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          <div className="card mt-10 p-6">
            <h3 className="font-semibold">How it works</h3>
            <ol className="mt-3 space-y-2 text-sm text-muted">
              <li><strong className="text-fg">1.</strong> Share your unique link anywhere.</li>
              <li><strong className="text-fg">2.</strong> Friend signs up via your link — both of you get +1 free month of Premium, credited immediately.</li>
              <li><strong className="text-fg">3.</strong> Credit applies automatically at your next paid checkout (one-shot 100%-off coupon, no code to enter).</li>
              <li><strong className="text-fg">4.</strong> Stack credits indefinitely. Refer 12 friends, get a free year.</li>
            </ol>
          </div>
        </>
      )}
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
