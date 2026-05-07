"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useUser } from "@/components/UserContext";
import { Paywall } from "@/components/Paywall";
import { ComparisonTable } from "@/components/ComparisonTable";
import {
  getWebPushStatus,
  subscribeToWebPush,
  testWebPush,
  unsubscribeFromWebPush,
} from "@/lib/webPush";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// Tier metadata used by the hero + upgrade flow. Single source of truth — when
// pricing changes, edit here and the comparison/pricing pages stay in sync via
// the shared ComparisonTable + PricingTable components.
const TIER_META = {
  free: {
    name: "Free",
    monthly: 0,
    annual: 0,
    annualMonthly: 0,
    blurb: "Top 20 tickers, 24-hour delayed",
  },
  pro: {
    name: "Pro",
    monthly: 29,
    annual: 299,
    annualMonthly: 24.99,
    blurb: "Live scanner. Daily edge.",
  },
  premium: {
    name: "Premium",
    monthly: 49,
    annual: 479,
    annualMonthly: 39.99,
    blurb: "Everything, no limits.",
  },
} as const;

type TierKey = keyof typeof TIER_META;

export default function BillingPage() {
  const { user } = useUser();
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ kind: "info" | "err"; text: string } | null>(null);
  const [billingPeriod, setBillingPeriod] = useState<"monthly" | "annual">("annual");
  const [showPlans, setShowPlans] = useState(false);

  const tier = (user?.tier || "free") as TierKey;
  const meta = TIER_META[tier] ?? TIER_META.free;
  const trialEndsAt = user?.trial_ends_at ? new Date(user.trial_ends_at) : null;
  const trialDaysLeft = trialEndsAt
    ? Math.max(0, Math.ceil((trialEndsAt.getTime() - Date.now()) / 86_400_000))
    : 0;
  const isOnTrial = !!trialEndsAt && trialDaysLeft > 0;

  // Free users see the upgrade picker by default. Paid users see a tucked
  // "Change plan" button — they're not here to be sold to every visit.
  useEffect(() => {
    if (tier === "free") setShowPlans(true);
  }, [tier]);

  async function startCheckout(target: "pro" | "premium") {
    setBusy(target);
    setMsg(null);
    try {
      const res = await fetch(`${API_BASE}/api/billing/checkout`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tier: target, billing_period: billingPeriod }),
      });
      const body = await res.json();
      if (res.ok && body.url) {
        window.location.href = body.url;
      } else if (res.status === 502 || res.status === 503 || body.detail?.includes("not configured")) {
        setMsg({ kind: "info", text: "Checkout isn't live yet — Stripe activation pending. Email support@tapeline.io if you want to upgrade in the meantime." });
      } else {
        setMsg({ kind: "err", text: body.detail || `Checkout failed (${res.status})` });
      }
    } catch (e: any) {
      setMsg({ kind: "err", text: e.message || "Checkout failed" });
    } finally {
      setBusy(null);
    }
  }

  async function openPortal() {
    try {
      const res = await fetch(`${API_BASE}/api/billing/portal`, {
        method: "POST",
        credentials: "include",
      });
      const body = await res.json();
      if (res.ok && body.url) window.location.href = body.url;
      else setMsg({ kind: "err", text: body.detail || "Portal not available — Stripe activation pending." });
    } catch (e: any) {
      setMsg({ kind: "err", text: e.message });
    }
  }

  return (
    <div className="space-y-10">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header>
        <div className="flex items-center gap-2 text-xs text-subtle">
          <Link href="/app/scanner" className="hover:text-fg transition-colors">App</Link>
          <span>›</span>
          <span className="text-muted">Billing</span>
        </div>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Billing &amp; plan</h1>
        <p className="mt-1 text-sm text-muted">
          Your current subscription, usage at a glance, and how to change it.
        </p>
      </header>

      {msg && (
        <div className={`rounded-lg border p-4 text-sm ${
          msg.kind === "err"
            ? "border-down/40 bg-down/5 text-down"
            : "border-yellow-500/30 bg-yellow-500/5 text-yellow-400"
        }`}>
          {msg.text}
        </div>
      )}

      {/* ── Hero: current plan + next charge + trial countdown ────────────── */}
      <section className="grid gap-4 md:grid-cols-5">
        {/* Plan summary — spans 3 of 5 cols */}
        <div className={`md:col-span-3 relative overflow-hidden rounded-2xl border p-6 ${
          tier === "premium"
            ? "border-accent/40 bg-gradient-to-br from-accent/15 via-panel to-panel"
            : tier === "pro"
            ? "border-fg/30 bg-gradient-to-br from-fg/8 via-panel to-panel"
            : "border-border bg-panel"
        }`}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-muted">Current plan</div>
              <div className="mt-1 flex items-baseline gap-3">
                <span className="text-3xl font-bold tracking-tight">{meta.name}</span>
                {isOnTrial && (
                  <span className="rounded-full bg-accent/15 px-2.5 py-0.5 text-[11px] font-semibold uppercase text-accent">
                    Trial · {trialDaysLeft} day{trialDaysLeft === 1 ? "" : "s"} left
                  </span>
                )}
              </div>
              <p className="mt-1.5 text-sm text-muted">{meta.blurb}</p>
            </div>
            <div className="text-right text-xs">
              <div className="text-subtle">Signed in as</div>
              <div className="mt-0.5 text-muted nums break-all">{user?.email}</div>
            </div>
          </div>

          {tier !== "free" && (
            <div className="mt-6 flex flex-wrap gap-2">
              <button onClick={openPortal} className="btn-ghost text-xs">
                Manage payment in Stripe portal →
              </button>
              <button
                onClick={() => setShowPlans((v) => !v)}
                className="btn-ghost text-xs"
              >
                {showPlans ? "Hide plans" : "Change plan"}
              </button>
            </div>
          )}
          {tier === "free" && (
            <div className="mt-6">
              <Link href="/signup" className="btn-accent text-sm">
                Start 14-day Premium trial →
              </Link>
            </div>
          )}
        </div>

        {/* Next charge / trial preview — spans 2 of 5 cols */}
        <div className="md:col-span-2 rounded-2xl border border-border bg-panel p-6">
          <div className="text-[11px] uppercase tracking-wider text-muted">
            {isOnTrial ? "When the trial ends" : tier === "free" ? "What you get on Premium" : "Next charge"}
          </div>

          {isOnTrial ? (
            <>
              <div className="mt-2 text-2xl font-bold nums">
                {trialEndsAt!.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}
              </div>
              <p className="mt-2 text-xs text-muted leading-relaxed">
                Add a card before then to lock in {meta.name} access. Otherwise your account drops to Free
                — top 20 tickers, 24-hour delayed.
              </p>
              <button onClick={() => setShowPlans(true)} className="mt-4 text-xs text-accent hover:underline">
                Pick a plan to keep it →
              </button>
            </>
          ) : tier === "free" ? (
            <>
              <div className="mt-2 text-2xl font-bold nums">$0 <span className="text-sm font-normal text-muted">today</span></div>
              <ul className="mt-3 space-y-1 text-xs text-muted">
                <li>· Full 2,500-ticker live universe</li>
                <li>· Watchlist of 200 with smart alerts</li>
                <li>· Congressional trades + 13F holdings</li>
                <li>· Telegram alerts unlimited</li>
              </ul>
            </>
          ) : (
            <>
              <div className="mt-2 text-2xl font-bold nums">
                ${billingPeriod === "annual" ? meta.annual : meta.monthly}
                <span className="text-sm font-normal text-muted"> / {billingPeriod === "annual" ? "year" : "month"}</span>
              </div>
              <p className="mt-2 text-xs text-muted">
                {billingPeriod === "annual"
                  ? `Effective $${meta.annualMonthly}/mo · 7-day money-back if you change your mind.`
                  : "Switch to annual to save ~14-19% and lock the price forever."}
              </p>
            </>
          )}
        </div>
      </section>

      {/* ── Usage at a glance ─────────────────────────────────────────────── */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">Plan limits</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <UsageTile
            label="Watchlist tickers"
            limit={tier === "free" ? 5 : tier === "pro" ? 50 : 200}
            unit="tickers"
          />
          <UsageTile
            label="Email alerts / day"
            limit={tier === "free" ? 0 : tier === "pro" ? 10 : 10000}
            unit={tier === "premium" ? "unlimited" : "per day"}
            unlimited={tier === "premium"}
          />
          <UsageTile
            label="Saved scans"
            limit={tier === "free" ? 0 : tier === "pro" ? 10 : 100}
            unit="scans"
          />
          <UsageTile
            label="Scanner rows"
            limit={tier === "free" ? 20 : 2500}
            unit="rows"
          />
        </div>
      </section>

      {/* ── Plan picker (collapsible for paid users) ──────────────────────── */}
      {showPlans && (
        <section className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold">{tier === "free" ? "Pick a plan" : "Change plan"}</h2>
              <p className="mt-1 text-sm text-muted">
                7-day money-back. Cancel in one click. Annual locks the price forever.
              </p>
            </div>
            <div className="inline-flex rounded-full border border-border bg-panel p-1">
              {(["monthly", "annual"] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setBillingPeriod(p)}
                  className={`relative rounded-full px-4 py-1.5 text-xs font-medium transition-all ${
                    billingPeriod === p ? "bg-fg text-background" : "text-muted hover:text-fg"
                  }`}
                >
                  {p === "annual" ? "Annual" : "Monthly"}
                  {p === "annual" && billingPeriod !== "annual" && (
                    <span className="absolute -right-2 -top-2 rounded-full bg-up px-1.5 py-0.5 text-[9px] font-bold text-background">save</span>
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <Plan
              name="Free"
              price="$0"
              note="Forever free"
              items={[
                "Top 20 tickers, 24-hour delayed",
                "Public scorecard + basic regime",
                "Watchlist of 5, no alerts",
              ]}
              highlight={tier === "free"}
            />
            <Plan
              name="Pro"
              price={billingPeriod === "annual" ? "$24.99" : "$29"}
              note={billingPeriod === "annual" ? "$299/yr · billed annually · save $49" : "billed monthly"}
              items={[
                "Full ~2,500 ticker universe, live",
                "Score breakdown + Why on every row",
                "Squeeze Watch + Regime + Heatmap",
                "Watchlist (50) with smart alerts",
                "TradingView charts + news",
                "IPO + Earnings calendars",
                "10 email alerts/day · CSV export",
              ]}
              cta={tier === "premium" ? "Switch to Pro" : "Upgrade to Pro"}
              highlight={tier === "pro"}
              disabled={tier === "pro"}
              busy={busy === "pro"}
              onUpgrade={() => startCheckout("pro")}
            />
            <Plan
              name="Premium"
              price={billingPeriod === "annual" ? "$39.99" : "$49"}
              note={billingPeriod === "annual" ? "$479/yr · billed annually · save $109" : "billed monthly"}
              proPlus
              items={[
                "Congressional trades feed (House + Senate)",
                "Elite 13F — Buffett, Burry, Tepper, Ackman + 4 more",
                "Telegram alerts · unlimited (Pro: none)",
                "Email alerts · unlimited (Pro: 10/day)",
                "Watchlist 200 · saved scans 100 (Pro: 50 · 10)",
                "Public API · 1,000 req/day",
                "Priority support · same-day reply",
              ]}
              cta="Upgrade to Premium"
              highlight={tier === "premium"}
              disabled={tier === "premium"}
              busy={busy === "premium"}
              onUpgrade={() => startCheckout("premium")}
            />
          </div>

          <div>
            <details className="group rounded-xl border border-border bg-panel/40">
              <summary className="flex cursor-pointer items-center justify-between gap-3 p-5 list-none">
                <div>
                  <h3 className="font-semibold">Compare every feature</h3>
                  <p className="mt-0.5 text-xs text-muted">Six sections · every limit · no asterisks</p>
                </div>
                <span className="text-muted transition-transform group-open:rotate-45">+</span>
              </summary>
              <div className="border-t border-border/60 p-5 pt-2">
                <ComparisonTable />
              </div>
            </details>
          </div>
        </section>
      )}

      {/* ── Why Tapeline (sales reinforcement only on the change-plan view) ─ */}
      {showPlans && tier !== "premium" && (
        <section className="rounded-2xl border border-border bg-panel/30 p-6">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">Why people pay</h2>
          <div className="mt-4 grid gap-5 md:grid-cols-3">
            <Selling
              title="Bloomberg-grade data"
              body="Same market feed (Massive, formerly Polygon), Fed data (FRED), fundamentals (Finnhub) used by quant funds. Bloomberg Terminal: $31,980/yr. You: $479/yr."
            />
            <Selling
              title="Public scorecard, day 1"
              body="Every score we publish is back-checked against next-day prices and shown on /scorecard. No newsletter shop publishes its losses. We do it automatically."
            />
            <Selling
              title="Open formula"
              body="The 6-factor weights are on /how-it-works. TipRanks, Zacks, Kavout, WallStreetZen all hide theirs. Ours is the only one you can audit."
            />
          </div>
        </section>
      )}

      {/* ── Alert delivery channels ───────────────────────────────────────── */}
      <section>
        <div className="flex items-baseline justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold">Alert delivery channels</h2>
            <p className="mt-1 text-sm text-muted">
              Email is the default. Add any channel below for richer or faster delivery.
            </p>
          </div>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <Paywall feature="alerts.web_push" title="Browser push">
            <WebPushCard />
          </Paywall>
          <Paywall feature="alerts.telegram" title="Telegram">
            <NotificationsCard />
          </Paywall>
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────────────────────── */}
      <footer className="border-t border-border/60 pt-6 text-xs text-muted">
        Questions about a charge or want to cancel?
        Email <a href="mailto:support@tapeline.io" className="text-accent hover:underline">support@tapeline.io</a>
        — usually replied to within a business day.
      </footer>
    </div>
  );
}

/**
 * Single-stat tile — label + the cap allowed on the current tier. We don't
 * surface live "used" counts yet (would need a per-user usage endpoint); the
 * limit alone is the most-asked-about question on the billing page anyway.
 */
function UsageTile({
  label,
  limit,
  unit,
  unlimited = false,
}: {
  label: string;
  limit: number;
  unit: string;
  unlimited?: boolean;
}) {
  const display = unlimited ? "∞" : limit === 0 ? "—" : limit.toLocaleString();
  return (
    <div className="rounded-xl border border-border bg-panel p-4">
      <div className="text-[11px] uppercase tracking-wider text-subtle">{label}</div>
      <div className="mt-1.5 flex items-baseline gap-1.5">
        <span className="text-2xl font-bold nums">{display}</span>
        <span className="text-xs text-muted">{unit}</span>
      </div>
    </div>
  );
}

function Selling({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <div className="flex items-center gap-2">
        <span className="h-1 w-6 rounded-full bg-accent" />
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      <p className="mt-2 text-xs text-muted leading-relaxed">{body}</p>
    </div>
  );
}

function NotificationsCard() {
  const { user, refresh } = useUser();
  const [chatId, setChatId] = useState(user?.telegram_chat_id ?? "");
  const [busy, setBusy] = useState<"save" | "test" | "clear" | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  async function save() {
    setBusy("save"); setMsg(null);
    try {
      const r = await fetch(`${API_BASE}/api/me/telegram`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: chatId.trim() }),
      });
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail || `Save failed (${r.status})`);
      setMsg({ kind: "ok", text: "Saved. Hit Test to verify the wiring." });
      await refresh();
    } catch (e: any) {
      setMsg({ kind: "err", text: e.message });
    } finally { setBusy(null); }
  }

  async function test() {
    setBusy("test"); setMsg(null);
    try {
      const r = await fetch(`${API_BASE}/api/me/telegram/test`, {
        method: "POST", credentials: "include",
      });
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail || `Test failed (${r.status})`);
      setMsg({ kind: "ok", text: "Sent. Check your Telegram." });
    } catch (e: any) {
      setMsg({ kind: "err", text: e.message });
    } finally { setBusy(null); }
  }

  async function clear() {
    setBusy("clear"); setMsg(null);
    try {
      const r = await fetch(`${API_BASE}/api/me/telegram`, {
        method: "DELETE", credentials: "include",
      });
      if (!r.ok) throw new Error("Disconnect failed");
      setChatId("");
      setMsg({ kind: "ok", text: "Disconnected. Hourly digest stopped." });
      await refresh();
    } catch (e: any) {
      setMsg({ kind: "err", text: e.message });
    } finally { setBusy(null); }
  }

  const connected = !!user?.telegram_chat_id;

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Telegram</h3>
        <span className={`rounded-full px-2 py-0.5 text-xs ${connected ? "bg-up/10 text-up" : "bg-muted/20 text-muted"}`}>
          {connected ? "Connected" : "Not connected"}
        </span>
      </div>

      <div className="mt-4">
        <label className="block text-xs font-medium text-muted">Telegram chat ID</label>
        <input
          type="text"
          inputMode="numeric"
          value={chatId}
          onChange={(e) => setChatId(e.target.value)}
          placeholder="e.g. 123456789"
          className="mt-1.5 block h-10 w-full rounded-md border border-border bg-panel px-3 text-sm focus:border-accent focus:outline-none nums"
        />
        <p className="mt-2 text-xs text-subtle">
          Don&rsquo;t have one? DM <code className="text-accent">@TapelineBot</code> the message <code className="text-accent">/start</code>{" "}
          and it will reply with your numeric ID. Paste that here.
        </p>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        <button
          onClick={save}
          disabled={busy !== null || !chatId.trim() || chatId.trim() === user?.telegram_chat_id}
          className="btn-primary text-sm disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy === "save" ? "Saving…" : "Save"}
        </button>
        <button
          onClick={test}
          disabled={busy !== null || !connected}
          className="btn-ghost text-sm disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy === "test" ? "Sending…" : "Send test message"}
        </button>
        {connected && (
          <button
            onClick={clear}
            disabled={busy !== null}
            className="btn-ghost text-sm text-down hover:text-down disabled:opacity-50"
          >
            {busy === "clear" ? "Disconnecting…" : "Disconnect"}
          </button>
        )}
      </div>

      {msg && (
        <div className={`mt-4 rounded-md border p-3 text-sm ${
          msg.kind === "ok"
            ? "border-up/30 bg-up/5 text-up"
            : "border-down/30 bg-down/5 text-down"
        }`}>
          {msg.text}
        </div>
      )}
    </div>
  );
}

function WebPushCard() {
  const [status, setStatus] = useState<"loading" | "granted" | "denied" | "default" | "unsupported">("loading");
  const [busy, setBusy] = useState<"enable" | "test" | "disable" | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    getWebPushStatus().then((s) => setStatus(s as any));
  }, []);

  async function enable() {
    setBusy("enable"); setMsg(null);
    const r = await subscribeToWebPush();
    if (r.ok) {
      setStatus("granted");
      setMsg({ kind: "ok", text: "Subscribed. Hit Test to verify." });
    } else {
      setMsg({ kind: "err", text: r.reason });
    }
    setBusy(null);
  }

  async function test() {
    setBusy("test"); setMsg(null);
    const r = await testWebPush();
    if (r.ok) setMsg({ kind: "ok", text: `Sent to ${r.delivered}/${r.total} subscribed device${r.total === 1 ? "" : "s"}.` });
    else setMsg({ kind: "err", text: r.reason });
    setBusy(null);
  }

  async function disable() {
    setBusy("disable"); setMsg(null);
    await unsubscribeFromWebPush();
    setStatus("default");
    setMsg({ kind: "ok", text: "Disabled on this browser." });
    setBusy(null);
  }

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Browser push</h3>
        <span className={`rounded-full px-2 py-0.5 text-xs ${
          status === "granted" ? "bg-up/10 text-up"
          : status === "denied" ? "bg-down/10 text-down"
          : status === "unsupported" ? "bg-muted/20 text-muted"
          : "bg-muted/20 text-muted"
        }`}>
          {status === "granted" ? "Connected" : status === "denied" ? "Blocked" : status === "unsupported" ? "Unsupported" : "Not connected"}
        </span>
      </div>

      <p className="mt-3 text-sm text-muted leading-relaxed">
        Lock-screen notifications on desktop and Android. iOS requires the PWA to be installed.
        Free at any volume, one click to enable.
      </p>

      {status === "denied" && (
        <p className="mt-3 text-xs text-down">
          You blocked notifications for this site. Re-enable in browser settings (lock icon → Permissions → Notifications → Allow), then refresh.
        </p>
      )}
      {status === "unsupported" && (
        <p className="mt-3 text-xs text-subtle">
          Your browser doesn't support Web Push. Try Chrome, Firefox, or Edge on desktop.
        </p>
      )}

      <div className="mt-5 flex flex-wrap gap-2">
        {status !== "granted" && status !== "unsupported" && (
          <button
            onClick={enable}
            disabled={busy !== null || status === "denied"}
            className="btn-primary text-sm disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy === "enable" ? "Subscribing…" : "Enable browser push"}
          </button>
        )}
        {status === "granted" && (
          <>
            <button
              onClick={test}
              disabled={busy !== null}
              className="btn-ghost text-sm disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy === "test" ? "Sending…" : "Send test notification"}
            </button>
            <button
              onClick={disable}
              disabled={busy !== null}
              className="btn-ghost text-sm text-down hover:text-down disabled:opacity-50"
            >
              {busy === "disable" ? "Disabling…" : "Disable on this browser"}
            </button>
          </>
        )}
      </div>

      {msg && (
        <div className={`mt-4 rounded-md border p-3 text-sm ${
          msg.kind === "ok" ? "border-up/30 bg-up/5 text-up" : "border-down/30 bg-down/5 text-down"
        }`}>
          {msg.text}
        </div>
      )}
    </div>
  );
}


function Plan({
  name, price, items, note, cta, highlight, disabled, busy, onUpgrade, proPlus,
}: {
  name: string; price: string; items: string[]; note?: string;
  cta?: string; highlight?: boolean; disabled?: boolean; busy?: boolean;
  onUpgrade?: () => void; proPlus?: boolean;
}) {
  return (
    <div className={`card p-6 ${highlight ? "ring-2 ring-accent" : ""}`}>
      <div className="flex items-baseline justify-between">
        <h3 className="text-lg font-semibold">{name}</h3>
        {highlight && <span className="rounded-full bg-up/10 px-2 py-0.5 text-xs text-up">Current</span>}
      </div>
      <div className="mt-2 flex items-baseline gap-1"><span className="text-3xl font-bold">{price}</span><span className="text-muted">/mo</span></div>
      {note && <p className="mt-1 text-xs text-muted">{note}</p>}
      {/* "Everything in Pro" anchor strip — makes the upgrade reason
          obviously the additions, not a duplicated bullet list. */}
      {proPlus && (
        <div className="mt-4 flex items-center gap-2 rounded-md border border-border bg-black/30 px-2.5 py-1.5 text-[11px] text-muted">
          <span className="text-up">✓</span>
          <span>Everything in Pro</span>
          <span className="ml-auto text-accent font-medium">+ all of:</span>
        </div>
      )}
      <ul className={`${proPlus ? "mt-3" : "mt-4"} space-y-1 text-sm`}>
        {items.map((i) => <li key={i} className="flex gap-2"><span className="text-accent">✓</span><span>{i}</span></li>)}
      </ul>
      {cta && (
        <button
          disabled={disabled || busy}
          onClick={onUpgrade}
          className="btn-primary mt-6 w-full text-sm disabled:cursor-not-allowed disabled:opacity-50"
        >
          {disabled ? "Current plan" : busy ? "Redirecting…" : cta}
        </button>
      )}
    </div>
  );
}
