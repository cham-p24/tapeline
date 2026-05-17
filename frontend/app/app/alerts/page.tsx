"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, type AlertEvent, type AlertRule } from "@/lib/api";
import { useUser } from "@/components/UserContext";

type RuleType = AlertRule["rule_type"];
type Channel = AlertRule["channel"];

const RULE_TYPES: { value: RuleType; label: string; needsSymbol: boolean; needsThreshold: boolean; help: string }[] = [
  { value: "score",    label: "Score crosses threshold", needsSymbol: true,  needsThreshold: true,  help: "Fires when this ticker's composite score crosses your threshold." },
  { value: "news",     label: "News on a ticker",         needsSymbol: true,  needsThreshold: false, help: "Fires on every fresh article tagged to this ticker." },
  { value: "squeeze",  label: "Squeeze detected",         needsSymbol: false, needsThreshold: false, help: "Fires when any ticker enters a squeeze setup." },
  { value: "regime",   label: "Regime change",            needsSymbol: false, needsThreshold: false, help: "Fires on RISK_ON → RISK_OFF or the reverse." },
  { value: "congress", label: "Congress trade disclosed", needsSymbol: true,  needsThreshold: false, help: "Fires when a politician discloses a trade on this ticker. Premium." },
];

export default function AlertsPage() {
  const { user } = useUser();
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [ruleType, setRuleType] = useState<RuleType>("score");
  const [symbol, setSymbol] = useState("");
  const [threshold, setThreshold] = useState<number>(70);
  const [channel, setChannel] = useState<Channel>("email");

  const def = RULE_TYPES.find((r) => r.value === ruleType)!;

  const load = useCallback(async () => {
    try {
      const [r, e] = await Promise.all([api.alertRules(), api.alertEvents(20)]);
      setRules(r.items);
      setEvents(e.items);
      setError(null);
    } catch (e: any) {
      const m = String(e.message || e);
      if (m.includes("401")) {
        window.location.href = `/signin?next=${encodeURIComponent("/app/alerts")}`;
        return;
      }
      setError(m);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function create() {
    setCreating(true);
    setError(null);
    const name = def.label + (def.needsSymbol && symbol ? ` · ${symbol.toUpperCase()}` : "");
    try {
      await api.alertRuleCreate({
        name,
        rule_type: ruleType,
        symbol: def.needsSymbol ? symbol.toUpperCase().trim() : null,
        threshold: def.needsThreshold ? threshold : null,
        channel,
      });
      if (def.needsSymbol) setSymbol("");
      load();
    } catch (e: any) {
      const m = String(e.message || e);
      if (m.includes("401")) {
        window.location.href = `/signin?next=${encodeURIComponent("/app/alerts")}`;
        return;
      }
      if (m.includes("403")) setError(`${channel === "telegram" ? "Telegram" : channel === "web_push" ? "Web push" : "Email"} alerts require a higher tier. Upgrade at /app/billing.`);
      else setError(m);
    } finally {
      setCreating(false);
    }
  }

  async function remove(id: number) {
    try {
      await api.alertRuleDelete(id);
      setRules((r) => r.filter((x) => x.id !== id));
    } catch (e: any) {
      const m = String(e.message || e);
      if (m.includes("401")) {
        window.location.href = `/signin?next=${encodeURIComponent("/app/alerts")}`;
        return;
      }
      setError(m);
    }
  }

  const ruleTypeLabel = (t: RuleType) => RULE_TYPES.find((r) => r.value === t)?.label ?? t;
  const channelLabel = (c: Channel) =>
    c === "telegram" ? "Telegram" : c === "web_push" ? "Web push" : "Email";

  const isPremium = user?.tier === "premium";
  const isPro = user?.tier === "pro" || isPremium;

  return (
    <div>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Alert rules</h1>
          <p className="mt-1 text-sm text-muted">
            Get notified when scores, setups, or regimes change. Email + Web push on Pro;
            Telegram on Premium.
          </p>
        </div>
      </div>

      {/* Create form */}
      <div className="card mt-6 p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">New rule</h2>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-xs text-muted">Rule type</label>
            <select
              value={ruleType}
              onChange={(e) => setRuleType(e.target.value as RuleType)}
              className="mt-1 w-full rounded-md bg-black/40 px-3 py-2 text-sm"
            >
              {RULE_TYPES.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
            <p className="mt-1 text-xs text-subtle">{def.help}</p>
          </div>

          <div>
            <label className="block text-xs text-muted">Channel</label>
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value as Channel)}
              className="mt-1 w-full rounded-md bg-black/40 px-3 py-2 text-sm"
            >
              <option value="email">Email {isPro ? "" : "(Pro)"}</option>
              <option value="web_push">Web push {isPro ? "" : "(Pro)"}</option>
              <option value="telegram">Telegram {isPremium ? "" : "(Premium)"}</option>
            </select>
          </div>

          {def.needsSymbol && (
            <div>
              <label className="block text-xs text-muted">Ticker</label>
              <input
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                placeholder="AAPL"
                className="mt-1 w-full rounded-md bg-black/40 px-3 py-2 text-sm nums font-mono uppercase"
              />
            </div>
          )}

          {def.needsThreshold && (
            <div>
              <label className="block text-xs text-muted">Score threshold (0–100)</label>
              <input
                type="number"
                min={0}
                max={100}
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className="mt-1 w-full rounded-md bg-black/40 px-3 py-2 text-sm nums"
              />
              <p className="mt-1 text-xs text-subtle">Fires when score crosses this in either direction.</p>
            </div>
          )}
        </div>

        <div className="mt-5 flex items-center gap-3">
          <button
            onClick={create}
            disabled={creating || (def.needsSymbol && !symbol.trim())}
            className="btn-primary text-sm disabled:cursor-not-allowed disabled:opacity-50"
          >
            {creating ? "Creating…" : "Create rule"}
          </button>
          {error && <p className="text-xs text-down">{error}</p>}
        </div>
      </div>

      {/* Active rules */}
      <h2 className="mt-8 mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
        Active rules {rules.length > 0 && <span className="text-subtle">({rules.length})</span>}
      </h2>

      {loading ? (
        <div className="card p-6 text-sm text-muted">Loading…</div>
      ) : rules.length === 0 ? (
        <div className="card p-6 text-sm text-muted">
          No alert rules yet. Create one above, or visit the{" "}
          <Link href="/app/scanner" className="link">scanner</Link> and tap an alert button on any ticker.
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-2 text-left">Type</th>
                <th className="px-4 py-2 text-left">Ticker</th>
                <th className="px-4 py-2 text-right">Threshold</th>
                <th className="px-4 py-2 text-left">Channel</th>
                <th className="px-4 py-2 text-left">Last fired</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id} className="border-b border-border/20 hover:bg-black/20">
                  <td className="px-4 py-2">{ruleTypeLabel(r.rule_type)}</td>
                  <td className="px-4 py-2 font-mono">{r.symbol || <span className="text-subtle">any</span>}</td>
                  <td className="px-4 py-2 text-right nums">{r.threshold ?? "—"}</td>
                  <td className="px-4 py-2">{channelLabel(r.channel)}</td>
                  <td className="px-4 py-2 text-xs text-muted">
                    {r.last_fired_at ? new Date(r.last_fired_at).toLocaleString() : "never"}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => remove(r.id)}
                      className="text-xs text-muted hover:text-down"
                    >
                      remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Recent events */}
      {events.length > 0 && (
        <>
          <h2 className="mt-8 mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
            Recent fires
          </h2>
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="text-xs uppercase text-muted">
                <tr>
                  <th className="px-4 py-2 text-left">When</th>
                  <th className="px-4 py-2 text-left">Ticker</th>
                  <th className="px-4 py-2 text-left">Message</th>
                  <th className="px-4 py-2 text-left">Channel</th>
                  <th className="px-4 py-2 text-left">Delivered</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id} className="border-b border-border/20">
                    <td className="px-4 py-2 text-xs text-muted whitespace-nowrap">
                      {new Date(e.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 font-mono">{e.symbol || "—"}</td>
                    <td className="px-4 py-2">{e.message}</td>
                    <td className="px-4 py-2">{channelLabel(e.channel as Channel)}</td>
                    <td className={`px-4 py-2 text-xs ${e.delivered ? "text-up" : "text-down"}`}>
                      {e.delivered ? "✓" : "failed"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
