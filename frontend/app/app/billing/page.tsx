"use client";

import { useState } from "react";
import { useUser } from "@/components/UserContext";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function BillingPage() {
  const { user, refresh } = useUser();
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function startCheckout(tier: "pro" | "premium") {
    setBusy(tier);
    setMsg(null);
    try {
      const res = await fetch(`${API_BASE}/api/billing/checkout`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tier }),
      });
      const body = await res.json();
      if (res.ok && body.url) {
        window.location.href = body.url;  // Redirect to Stripe Checkout
      } else if (res.status === 502 || res.status === 503 || body.detail?.includes("not configured")) {
        setMsg("Stripe checkout isn't live yet — set STRIPE_SECRET_KEY in .env. For now, contact the admin to adjust your tier.");
      } else {
        setMsg(body.detail || `Checkout failed (${res.status})`);
      }
    } catch (e: any) {
      setMsg(e.message || "Checkout failed");
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
      else setMsg(body.detail || "Portal not available");
    } catch (e: any) {
      setMsg(e.message);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight">Billing &amp; plan</h1>
      <p className="text-sm text-muted">Manage your subscription.</p>

      <div className="card mt-6 p-6">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-xs uppercase text-muted">Current plan</div>
            <div className="mt-1 text-2xl font-bold uppercase">{user?.tier || "free"}</div>
          </div>
          <div className="text-right">
            <div className="text-xs text-muted">Signed in as</div>
            <div className="text-sm">{user?.email}</div>
          </div>
        </div>
        {user?.tier !== "free" && (
          <button onClick={openPortal} className="btn-ghost mt-4 text-sm">
            Manage billing in Stripe portal →
          </button>
        )}
      </div>

      {msg && <p className="mt-4 rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-3 text-sm text-yellow-400">{msg}</p>}

      <h2 className="mt-10 text-xl font-semibold">Upgrade</h2>
      <p className="mt-2 text-sm text-muted">7-day money-back guarantee. Cancel in one click, anytime.</p>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <Plan
          name="Free"
          price="$0"
          note="Forever free"
          items={[
            "Top 10 tickers, 15-min delayed",
            "Public scorecard + basic regime",
            "No watchlist, no alerts",
          ]}
          highlight={user?.tier === "free"}
        />
        <Plan
          name="Pro"
          price="$29"
          items={[
            "Full ~870 ticker universe, live",
            "Score breakdown + Why on every row",
            "Squeeze Watch + Regime",
            "Watchlist with smart alerts",
            "TradingView charts + news",
            "IPO + Earnings calendars",
            "10 email alerts/day",
          ]}
          cta="Upgrade to Pro"
          highlight={user?.tier === "pro"}
          disabled={user?.tier === "pro"}
          busy={busy === "pro"}
          onUpgrade={() => startCheckout("pro")}
        />
        <Plan
          name="Elite"
          price="$49"
          items={[
            "Everything in Pro",
            "Congressional trades feed",
            "Telegram hourly digest",
            "Daily briefing email",
            "API access (1,000 req/day)",
            "Priority support",
          ]}
          cta="Upgrade to Elite"
          highlight={user?.tier === "premium"}
          disabled={user?.tier === "premium"}
          busy={busy === "premium"}
          onUpgrade={() => startCheckout("premium")}
        />
      </div>

      <div className="mt-10 text-xs text-muted">
        <p>Questions? Email <a href="mailto:support@tapeline.io" className="text-accent">support@tapeline.io</a></p>
      </div>
    </div>
  );
}

function Plan({
  name, price, items, note, cta, highlight, disabled, busy, onUpgrade,
}: {
  name: string; price: string; items: string[]; note?: string;
  cta?: string; highlight?: boolean; disabled?: boolean; busy?: boolean;
  onUpgrade?: () => void;
}) {
  return (
    <div className={`card p-6 ${highlight ? "ring-2 ring-accent" : ""}`}>
      <div className="flex items-baseline justify-between">
        <h3 className="text-lg font-semibold">{name}</h3>
        {highlight && <span className="rounded-full bg-up/10 px-2 py-0.5 text-xs text-up">Current</span>}
      </div>
      <div className="mt-2 flex items-baseline gap-1"><span className="text-3xl font-bold">{price}</span><span className="text-muted">/mo</span></div>
      {note && <p className="mt-1 text-xs text-muted">{note}</p>}
      <ul className="mt-4 space-y-1 text-sm">
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
