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
  activated_users: number;
  activation_rate: number;
  activated_to_paid_pct: number;
  active_7d: number;
  active_28d: number;
  w4_cohort: number;
  w4_retained: number;
  w4_retention_pct: number;
  gclid_capture_count: number;
  acquisition_channels: Record<string, { signups: number; paid: number }>;
  acquisition_landing_pages: LandingPageRow[];
  embed_impressions: EmbedImpressions;
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

/**
 * Top landing pages by signup — the content-level cut of the channel readout.
 * "organic brought 6 signups" isn't actionable across ~4,750 published URLs;
 * this says WHICH page did the work, so the winning format can be repeated.
 * First-touch path only (no query strings), cross-cut by channel, top 25.
 * Users created before signup_landing_path shipped carry no path and are
 * excluded server-side rather than bucketed as "unknown".
 */
type LandingPageRow = {
  channel: string;
  path: string;
  signups: number;
  paid: number;
};

/**
 * Embed distribution loop — renders of /badge/{sym} (README SVG) and
 * /embed/score/{sym} (iframe widget) on OTHER people's sites, aggregated
 * hostname-only per day. Directional, not exact: CDN-cached renders never
 * reach our origin, so real impressions always exceed these.
 */
type EmbedImpressions = {
  window_days: number;
  impressions_total: number;
  distinct_hosts: number;
  by_surface: Record<string, number>;
  top_hosts: { host: string; impressions: number; symbols: number }[];
  top_symbols: { symbol: string; impressions: number; hosts: number }[];
  by_day: { day: string; impressions: number }[];
};

/**
 * Windowed cohort funnel — every user created in the last N days, walked
 * through the five states they can reach. The rest of this page is
 * lifetime-to-date, which averages a good month and a dead month into the
 * same number; this is the cut that moves.
 */
type GrowthFunnel = {
  available: boolean;
  window_days: number;
  ending_soon_days: number;
  signups: number;
  activated: number;
  trials_started: number;
  trials_active: number;
  paying: number;
  activation_rate_pct: number;
  trial_start_rate_pct: number;
  trial_to_paid_pct: number;
  signup_to_paid_pct: number;
  trials_ending_soon: TrialEndingSoon[];
  trials_ending_soon_count: number;
};

type TrialEndingSoon = {
  id: string;
  email: string;
  name: string | null;
  tier: string;
  trial_ends_at: string;
  days_left: number;
  watchlist_count: number;
  has_alert_rule: boolean;
};

// Selectable cohort windows. 7 = "did this week do anything", 30 = default,
// 90 = enough signal to read a trend through the noise of a pre-launch month.
const FUNNEL_WINDOWS = [7, 30, 90] as const;

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
  // Funnel is fetched separately from the revenue roll-up: its window is
  // operator-selectable (changing it must not re-run the much heavier revenue
  // query) and a failure in either readout must not blank the other.
  const [funnelDays, setFunnelDays] = useState<number>(30);
  const [funnel, setFunnel] = useState<GrowthFunnel | null>(null);
  const [funnelErr, setFunnelErr] = useState<string | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) { router.push("/signin?next=/app/admin/revenue"); return; }
    if (!user.is_admin) { router.push("/app/scanner"); return; }
    adminGet<Revenue>("/api/admin/revenue")
      .then(setData)
      .catch((e) => setErr(e.message));
  }, [user, loading, router]);

  useEffect(() => {
    if (loading || !user?.is_admin) return;
    let stale = false;
    setFunnelErr(null);
    adminGet<GrowthFunnel>(`/api/admin/growth-funnel?days=${funnelDays}`)
      .then((d) => { if (!stale) setFunnel(d); })
      .catch((e) => { if (!stale) setFunnelErr(e.message); });
    // Guards against an out-of-order response overwriting a newer window.
    return () => { stale = true; };
  }, [user, loading, funnelDays]);

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

      {/* Measurement — activation (§4.2) + gclid capture (§3.7) */}
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Activation rate"
          value={`${data.activation_rate}%`}
          tone="accent"
        />
        <Stat label="Activated users" value={String(data.activated_users)} />
        <Stat label="gclid captured" value={String(data.gclid_capture_count)} />
      </div>
      <p className="mt-2 text-xs text-muted">
        Activation = signup that added a first watchlist ticker. gclid captured =
        signups arriving with a Google Ads click ID stored (available for the
        offline-conversion upload once Ads API access is enabled).
      </p>

      {/* Stage-1 signal — activity + W4+ retention. Per the CEO brief this is
          the single most honest early signal at pre-revenue: are signups still
          showing up over time? */}
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Active last 7d" value={String(data.active_7d)} tone={data.active_7d > 0 ? "accent" : undefined} />
        <Stat label="Active last 28d" value={String(data.active_28d)} />
        <Stat label="Activated → paid" value={`${data.activated_to_paid_pct}%`} />
        <Stat label="W4+ retention" value={data.w4_cohort ? `${data.w4_retention_pct}%` : "—"} tone="accent" />
      </div>
      <p className="mt-2 text-xs text-muted">
        W4+ retention = of the {data.w4_cohort} user{data.w4_cohort === 1 ? "" : "s"} who signed up 28+ days ago,
        the share still active in the last 14 days ({data.w4_retained}/{data.w4_cohort}) — the most honest early
        signal that the product sticks. If this flattens above zero as arrivals grow, you have PMF signal before revenue.
      </p>

      {/* Windowed cohort funnel — the one section on this page that is NOT
          lifetime-to-date, so it is the one that actually moves. Fails open:
          an error here renders a note, never blanks the rest of the page. */}
      <GrowthFunnelSection
        data={funnel}
        err={funnelErr}
        days={funnelDays}
        onDaysChange={setFunnelDays}
      />

      {/* Acquisition channels — first-party "where do signups come from + which converts" */}
      <h2 className="mt-10 text-xl font-semibold">Acquisition channels</h2>
      <p className="text-xs text-muted">
        Every signup by where it came from (UTM source → external referrer host →
        direct), with how many later paid. First-party — captured at landing, no
        Google Analytics/Ads connector needed.
      </p>
      <div className="card mt-4 overflow-x-auto">
        {Object.keys(data.acquisition_channels).length === 0 ? (
          <div className="p-4 text-sm text-subtle">No signups yet</div>
        ) : (
          <table className="w-full text-sm nums">
            <thead>
              <tr className="border-b border-border/50 text-xs uppercase text-muted">
                <th className="px-4 py-2 text-left font-medium">Channel</th>
                <th className="px-4 py-2 text-right font-medium">Signups</th>
                <th className="px-4 py-2 text-right font-medium">Paid</th>
                <th className="px-4 py-2 text-right font-medium">Conv.</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.acquisition_channels)
                .sort((a, b) => b[1].signups - a[1].signups)
                .map(([channel, { signups, paid }]) => (
                  <tr key={channel} className="border-b border-border/30 last:border-0">
                    <td className="px-4 py-2">{channel}</td>
                    <td className="px-4 py-2 text-right font-semibold">{signups}</td>
                    <td className="px-4 py-2 text-right font-semibold">{paid}</td>
                    <td className="px-4 py-2 text-right text-muted">
                      {signups > 0 ? `${Math.round((paid / signups) * 100)}%` : "—"}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Top landing pages — the content-level cut of the channel table above.
          Answers "which of the ~4,750 published pages actually earns signups". */}
      <LandingPages rows={data.acquisition_landing_pages} />

      {/* Embed distribution loop — who renders our badge/widget, and on which
          tickers. Previously invisible: both embed surfaces were untracked. */}
      <EmbedDistribution data={data.embed_impressions} />

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

/**
 * Growth funnel — the cohort of users who signed up inside the selected
 * window, walked through the five states they can reach, plus the trials that
 * are still open enough to act on.
 *
 * Everything else on this page is lifetime-to-date. That is the right shape
 * for MRR and the subscription book, and the wrong shape for "is growth
 * working" — a strong month and a dead month average into an identical
 * number. This section is the windowed cut.
 *
 * Fail-open: a failed fetch or a degraded (`available: false`) payload renders
 * a one-line note. It never throws and never blanks its neighbours.
 */
export function GrowthFunnelSection({
  data,
  err,
  days,
  onDaysChange,
}: {
  data: GrowthFunnel | null;
  err: string | null;
  days: number;
  onDaysChange: (d: number) => void;
}) {
  const windowPicker = (
    <div className="flex gap-1">
      {FUNNEL_WINDOWS.map((d) => (
        <button
          key={d}
          type="button"
          onClick={() => onDaysChange(d)}
          aria-pressed={d === days}
          className={`rounded px-2 py-1 text-xs ${
            d === days
              ? "bg-accent/20 text-accent"
              : "text-muted hover:text-fg"
          }`}
        >
          {d}d
        </button>
      ))}
    </div>
  );

  const header = (
    <div className="mt-10 flex items-center justify-between gap-3">
      <h2 className="text-xl font-semibold">Growth funnel</h2>
      {windowPicker}
    </div>
  );

  if (err) {
    return (
      <>
        {header}
        <div className="card mt-4 p-4 text-sm text-subtle">
          Funnel unavailable ({err}). The rest of this page is unaffected.
        </div>
      </>
    );
  }
  if (!data) {
    return (
      <>
        {header}
        <div className="card mt-4 p-4 text-sm text-subtle">Loading funnel&hellip;</div>
      </>
    );
  }
  if (!data.available) {
    return (
      <>
        {header}
        <div className="card mt-4 p-4 text-sm text-subtle">
          Funnel could not be computed. The rest of this page is unaffected.
        </div>
      </>
    );
  }

  // Step-to-step rates, each labelled with its own denominator so no reader
  // has to guess which base a percentage is against.
  const steps: { label: string; value: number; rate?: string }[] = [
    { label: "Signups", value: data.signups },
    {
      label: "Activated",
      value: data.activated,
      rate: `${data.activation_rate_pct}% of signups`,
    },
    {
      label: "Trials started",
      value: data.trials_started,
      rate: `${data.trial_start_rate_pct}% of signups`,
    },
    { label: "Trials running", value: data.trials_active },
    {
      label: "Paying",
      value: data.paying,
      rate: `${data.trial_to_paid_pct}% of trials`,
    },
  ];

  return (
    <>
      {header}
      <p className="text-xs text-muted">
        Users who signed up in the last {data.window_days} days, by how far they
        got. Activated = added a watchlist ticker or an alert rule. Trials
        running = trial still dated ahead with no card on file. Paying = a
        Stripe customer record exists. First-party data only.
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {steps.map((s) => (
          <div key={s.label} className="card p-4">
            <div className="text-xs uppercase text-muted">{s.label}</div>
            <div className="mt-1 text-2xl font-bold nums">{s.value}</div>
            <div className="mt-1 text-xs text-subtle">{s.rate || " "}</div>
          </div>
        ))}
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <Stat label={`Signup → paid (${data.window_days}d)`} value={`${data.signup_to_paid_pct}%`} tone="accent" />
        <Stat label={`Trial → paid (${data.window_days}d)`} value={`${data.trial_to_paid_pct}%`} tone="accent" />
      </div>

      {/* The only cohort on this page that is still open to influence. */}
      <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-muted">
        Trials ending within {data.ending_soon_days} days
      </h3>
      <p className="text-xs text-muted">
        No card on file, trial still running. Watchlist size and whether an
        alert rule is armed are the engagement signals already on record.
      </p>
      <div className="card mt-3 overflow-x-auto">
        {data.trials_ending_soon.length === 0 ? (
          <div className="p-4 text-sm text-subtle">No trials ending in this window</div>
        ) : (
          <table className="w-full text-sm nums">
            <thead>
              <tr className="border-b border-border/50 text-xs uppercase text-muted">
                <th className="px-4 py-2 text-left font-medium">Email</th>
                <th className="px-4 py-2 text-right font-medium">Days left</th>
                <th className="px-4 py-2 text-right font-medium">Watchlist</th>
                <th className="px-4 py-2 text-right font-medium">Alerts</th>
              </tr>
            </thead>
            <tbody>
              {data.trials_ending_soon.map((t) => (
                <tr key={t.id} className="border-b border-border/30 last:border-0">
                  <td className="px-4 py-2 break-all">{t.email}</td>
                  <td className="px-4 py-2 text-right font-semibold">{t.days_left}</td>
                  <td className="px-4 py-2 text-right">{t.watchlist_count}</td>
                  <td className="px-4 py-2 text-right text-muted">
                    {t.has_alert_rule ? "Yes" : "No"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

/**
 * Top landing pages readout. Same population as the channel table, cut by the
 * page the visitor first landed on. The list is deliberately short at first:
 * signup_landing_path is a recent column, so every pre-existing user carries
 * no path and is excluded — the caption says so rather than letting a nearly
 * empty table read as a broken section.
 */
function LandingPages({ rows }: { rows?: LandingPageRow[] }) {
  // Tolerate an older/degraded payload rather than blanking the dashboard.
  const items = rows ?? [];

  return (
    <>
      <h2 className="mt-10 text-xl font-semibold">Top landing pages</h2>
      <p className="text-xs text-muted">
        The same signups as above, cut by the page each visitor first landed on
        and cross-cut by channel. Path only &mdash; no query strings are stored.
        Top 25 by signups. Only signups recorded since first-touch capture
        shipped carry a path, so this list starts short and fills in over time.
      </p>
      <div className="card mt-4 overflow-x-auto">
        {items.length === 0 ? (
          <div className="p-4 text-sm text-subtle">
            No landing pages recorded yet. Every account created before
            first-touch capture shipped has no path stored, so rows appear here
            as new signups arrive.
          </div>
        ) : (
          <table className="w-full text-sm nums">
            <thead>
              <tr className="border-b border-border/50 text-xs uppercase text-muted">
                <th className="px-4 py-2 text-left font-medium">Landing page</th>
                <th className="px-4 py-2 text-left font-medium">Channel</th>
                <th className="px-4 py-2 text-right font-medium">Signups</th>
                <th className="px-4 py-2 text-right font-medium">Paid</th>
                <th className="px-4 py-2 text-right font-medium">Conv.</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr
                  key={`${r.channel}|${r.path}`}
                  className="border-b border-border/30 last:border-0"
                >
                  <td className="px-4 py-2 break-all font-mono text-xs">{r.path}</td>
                  <td className="px-4 py-2">{r.channel}</td>
                  <td className="px-4 py-2 text-right font-semibold">{r.signups}</td>
                  <td className="px-4 py-2 text-right font-semibold">{r.paid}</td>
                  <td className="px-4 py-2 text-right text-muted">
                    {r.signups > 0 ? `${Math.round((r.paid / r.signups) * 100)}%` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

/**
 * Embed distribution readout. The badge (/badge/{sym}) and the iframe widget
 * (/embed/score/{sym}) are rendered on other people's sites; this is the only
 * view of whether that loop actually works. Top hosts = outreach targets.
 * Top symbols = which tickers people care enough about to embed.
 */
function EmbedDistribution({ data }: { data?: EmbedImpressions }) {
  // Tolerate an older/degraded payload rather than blanking the dashboard.
  if (!data) return null;
  const hasData = data.impressions_total > 0;
  // Peak day drives the sparkline scale.
  const peak = Math.max(1, ...data.by_day.map((d) => d.impressions));

  return (
    <>
      <h2 className="mt-10 text-xl font-semibold">Embed distribution</h2>
      <p className="text-xs text-muted">
        Renders of the README badge (<code className="rounded bg-panel px-1 py-0.5">/badge/SYM</code>)
        and the iframe widget (<code className="rounded bg-panel px-1 py-0.5">/embed/score/SYM</code>)
        on other people&apos;s sites, last {data.window_days} days. Hostname only &mdash; no URLs,
        paths or query strings are stored. Counts are <strong>directional, not exact</strong>:
        CDN-cached renders never reach our origin, so real impressions are higher.
        Use them for ranking and trend.
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Impressions"
          value={String(data.impressions_total)}
          tone={hasData ? "accent" : undefined}
        />
        <Stat label="Embedding sites" value={String(data.distinct_hosts)} />
        <Stat label="Badge (SVG)" value={String(data.by_surface.badge ?? 0)} />
        <Stat label="Widget (iframe)" value={String(data.by_surface.iframe ?? 0)} />
      </div>

      {!hasData ? (
        <div className="card mt-4 p-4 text-sm text-subtle">
          No embed impressions recorded yet. Either nobody has embedded the badge
          or widget on an external site, or every render so far has been served
          from the CDN cache.
        </div>
      ) : (
        <>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <div className="card overflow-x-auto">
              <div className="px-4 pt-4 text-xs uppercase text-muted">
                Top embedding sites
              </div>
              <table className="mt-2 w-full text-sm nums">
                <thead>
                  <tr className="border-b border-border/50 text-xs uppercase text-muted">
                    <th className="px-4 py-2 text-left font-medium">Host</th>
                    <th className="px-4 py-2 text-right font-medium">Impr.</th>
                    <th className="px-4 py-2 text-right font-medium">Tickers</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_hosts.map((h) => (
                    <tr key={h.host} className="border-b border-border/30 last:border-0">
                      <td className="px-4 py-2 break-all">{h.host}</td>
                      <td className="px-4 py-2 text-right font-semibold">{h.impressions}</td>
                      <td className="px-4 py-2 text-right text-muted">{h.symbols}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="card overflow-x-auto">
              <div className="px-4 pt-4 text-xs uppercase text-muted">
                Most-embedded tickers
              </div>
              <table className="mt-2 w-full text-sm nums">
                <thead>
                  <tr className="border-b border-border/50 text-xs uppercase text-muted">
                    <th className="px-4 py-2 text-left font-medium">Symbol</th>
                    <th className="px-4 py-2 text-right font-medium">Impr.</th>
                    <th className="px-4 py-2 text-right font-medium">Sites</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_symbols.map((s) => (
                    <tr key={s.symbol} className="border-b border-border/30 last:border-0">
                      <td className="px-4 py-2 font-mono">{s.symbol}</td>
                      <td className="px-4 py-2 text-right font-semibold">{s.impressions}</td>
                      <td className="px-4 py-2 text-right text-muted">{s.hosts}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Per-day bars — is the loop growing or flat? */}
          <div className="card mt-3 p-4">
            <div className="text-xs uppercase text-muted">Impressions by day</div>
            <div className="mt-3 flex h-24 items-end gap-1">
              {data.by_day.map((d) => (
                <div
                  key={d.day}
                  className="flex-1 rounded-t bg-accent/70"
                  style={{ height: `${Math.max(2, (d.impressions / peak) * 100)}%` }}
                  title={`${d.day}: ${d.impressions}`}
                />
              ))}
            </div>
            <div className="mt-2 flex justify-between text-xs text-subtle">
              <span>{data.by_day[0]?.day ?? ""}</span>
              <span>{data.by_day[data.by_day.length - 1]?.day ?? ""}</span>
            </div>
          </div>
        </>
      )}
    </>
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
