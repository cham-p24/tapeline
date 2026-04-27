"use client";

import { useState } from "react";
import { useUser } from "@/components/UserContext";
import { Paywall } from "@/components/Paywall";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function BillingPage() {
  const { user, refresh } = useUser();
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [billingPeriod, setBillingPeriod] = useState<"monthly" | "annual">("annual");

  async function startCheckout(tier: "pro" | "premium") {
    setBusy(tier);
    setMsg(null);
    try {
      const res = await fetch(`${API_BASE}/api/billing/checkout`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tier, billing_period: billingPeriod }),
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

      {/* Billing period toggle */}
      <div className="mt-5 inline-flex rounded-full border border-border bg-panel p-1">
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
              <span className="absolute -right-2 -top-2 rounded-full bg-up px-1.5 py-0.5 text-[9px] font-bold text-background">−17%</span>
            )}
          </button>
        ))}
      </div>
      {billingPeriod === "annual" && <p className="mt-2 text-xs text-up">Save 2 months with annual · price locked forever</p>}

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <Plan
          name="Free"
          price="$0"
          note="Forever free"
          items={[
            "Top 20 tickers, 24-hour delayed",
            "Public scorecard + basic regime",
            "Small watchlist (5), no alerts",
          ]}
          highlight={user?.tier === "free"}
        />
        <Plan
          name="Pro"
          price={billingPeriod === "annual" ? "$24" : "$29"}
          note={billingPeriod === "annual" ? "$290/yr · billed annually" : undefined}
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
          name="Premium"
          price={billingPeriod === "annual" ? "$41" : "$49"}
          note={billingPeriod === "annual" ? "$490/yr · billed annually" : undefined}
          items={[
            "Everything in Pro",
            "Congressional trades feed",
            "Telegram alerts (unlimited)",
            "Email alerts (unlimited)",
            "API access (1,000 req/day)",
            "Elite 13F holdings",
            "Priority support",
          ]}
          cta="Upgrade to Premium"
          highlight={user?.tier === "premium"}
          disabled={user?.tier === "premium"}
          busy={busy === "premium"}
          onUpgrade={() => startCheckout("premium")}
        />
      </div>

      {/* Notifications — Telegram + SMS. Both paywalled to Premium. */}
      <h2 className="mt-12 text-xl font-semibold">Notifications</h2>
      <p className="mt-2 text-sm text-muted">Receive watchlist alerts, the hourly market digest, and per-rule alerts.</p>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <Paywall feature="alerts.telegram" title="Telegram alerts">
          <NotificationsCard />
        </Paywall>
        <Paywall feature="alerts.sms" title="SMS alerts">
          <SMSCard />
        </Paywall>
      </div>

      <div className="mt-10 text-xs text-muted">
        <p>Questions? Email <a href="mailto:support@tapeline.io" className="text-accent">support@tapeline.io</a></p>
      </div>
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

function SMSCard() {
  const { user, refresh } = useUser();
  const [phone, setPhone] = useState((user as any)?.phone_number ?? "");
  const [busy, setBusy] = useState<"save" | "test" | "clear" | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  async function save() {
    setBusy("save"); setMsg(null);
    try {
      const r = await fetch(`${API_BASE}/api/me/phone`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: phone.trim() }),
      });
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail || `Save failed (${r.status})`);
      setMsg({ kind: "ok", text: `Saved as ${body.phone_number}. Hit Test to verify.` });
      await refresh();
    } catch (e: any) {
      setMsg({ kind: "err", text: e.message });
    } finally { setBusy(null); }
  }

  async function test() {
    setBusy("test"); setMsg(null);
    try {
      const r = await fetch(`${API_BASE}/api/me/phone/test`, {
        method: "POST", credentials: "include",
      });
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail || `Test failed (${r.status})`);
      setMsg({ kind: "ok", text: "Sent. Check your phone." });
    } catch (e: any) {
      setMsg({ kind: "err", text: e.message });
    } finally { setBusy(null); }
  }

  async function clear() {
    setBusy("clear"); setMsg(null);
    try {
      const r = await fetch(`${API_BASE}/api/me/phone`, {
        method: "DELETE", credentials: "include",
      });
      if (!r.ok) throw new Error("Disconnect failed");
      setPhone("");
      setMsg({ kind: "ok", text: "Disconnected. SMS alerts off." });
      await refresh();
    } catch (e: any) {
      setMsg({ kind: "err", text: e.message });
    } finally { setBusy(null); }
  }

  const connected = !!(user as any)?.phone_number;

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">SMS</h3>
        <span className={`rounded-full px-2 py-0.5 text-xs ${connected ? "bg-up/10 text-up" : "bg-muted/20 text-muted"}`}>
          {connected ? "Connected" : "Not connected"}
        </span>
      </div>

      <div className="mt-4">
        <label className="block text-xs font-medium text-muted">Phone number (E.164)</label>
        <input
          type="tel"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="+1 555 123 4567"
          className="mt-1.5 block h-10 w-full rounded-md border border-border bg-panel px-3 text-sm focus:border-accent focus:outline-none nums"
        />
        <p className="mt-2 text-xs text-subtle">
          Twilio-delivered. Reserve SMS for high-conviction rules — every message is billed
          (~$0.008 US, more elsewhere). Email and Telegram are free per-message.
        </p>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        <button
          onClick={save}
          disabled={busy !== null || !phone.trim() || phone.trim() === (user as any)?.phone_number}
          className="btn-primary text-sm disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy === "save" ? "Saving…" : "Save"}
        </button>
        <button
          onClick={test}
          disabled={busy !== null || !connected}
          className="btn-ghost text-sm disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy === "test" ? "Sending…" : "Send test SMS"}
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
