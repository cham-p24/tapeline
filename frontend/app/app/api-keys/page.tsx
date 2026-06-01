"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useUser } from "@/components/UserContext";
import { Paywall } from "@/components/Paywall";
import { canUse } from "@/lib/auth";
import { handle401, errorMessage } from "@/lib/api";

type ApiKeyRow = {
  id: string;
  name: string;
  prefix: string;
  last_used_at: string | null;
  requests_today: number;
  daily_limit: number;
  request_count_total: number;
  created_at: string | null;
};

type ListResp = {
  count: number;
  daily_limit: number;
  max_keys: number;
  items: ApiKeyRow[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const API_DOCS_BASE = "https://api.tapeline.io/api/v1";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!r.ok) {
    handle401(r.status);
    const body = await r.json().catch(() => ({}) as Record<string, unknown>);
    throw new Error((body as { detail?: string }).detail || `${r.status} ${r.statusText}`);
  }
  return r.json();
}

export default function ApiKeysPage() {
  const { user } = useUser();
  const canUseApi = canUse(user, "api");

  const [data, setData] = useState<ListResp | null>(null);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!canUseApi) return;
    try {
      setData(await apiFetch<ListResp>("/api/api-keys"));
    } catch (e: unknown) {
      setErr(errorMessage(e));
    }
  }, [canUseApi]);

  useEffect(() => {
    load();
  }, [load]);

  async function createKey(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || creating) return;
    setCreating(true);
    setErr(null);
    try {
      const created = await apiFetch<ApiKeyRow & { key: string }>("/api/api-keys", {
        method: "POST",
        body: JSON.stringify({ name: name.trim() }),
      });
      setNewKey(created.key);
      setCopied(false);
      setName("");
      await load();
    } catch (e: unknown) {
      setErr(errorMessage(e));
    } finally {
      setCreating(false);
    }
  }

  async function revoke(id: string) {
    if (!confirm("Revoke this key? Any integration using it will immediately stop working.")) return;
    try {
      await apiFetch(`/api/api-keys/${id}`, { method: "DELETE" });
      await load();
    } catch (e: unknown) {
      setErr(errorMessage(e));
    }
  }

  async function copyKey() {
    if (!newKey) return;
    try {
      await navigator.clipboard.writeText(newKey);
      setCopied(true);
    } catch {
      /* clipboard blocked — the key is still selectable in the box */
    }
  }

  return (
    <div>
      <div>
        <h1 className="text-2xl font-bold tracking-tight">API keys</h1>
        <p className="text-sm text-muted">
          Programmatic access to the Tapeline scores. Mint a key, authenticate with the{" "}
          <code className="rounded bg-panel px-1 py-0.5 text-xs">X-API-Key</code> header, and pull the
          live universe, any ticker, or the macro regime. Premium includes{" "}
          <strong className="text-fg">1,000 requests/day</strong>.
        </p>
      </div>

      <Paywall feature="api" title="The Tapeline API is a Premium feature">
        {/* Freshly-minted key — shown exactly once */}
        {newKey && (
          <div className="mt-6 rounded-lg border border-up/40 bg-up/5 p-4">
            <div className="text-sm font-semibold text-up">Your new API key</div>
            <p className="mt-1 text-xs text-muted">
              Copy it now — for your security we store only a hash, so{" "}
              <strong className="text-fg">this is the only time it&apos;s shown</strong>.
            </p>
            <div className="mt-3 flex items-center gap-2">
              <code className="flex-1 select-all overflow-x-auto rounded bg-background px-3 py-2 text-sm nums">
                {newKey}
              </code>
              <button onClick={copyKey} className="btn-primary text-sm whitespace-nowrap">
                {copied ? "Copied ✓" : "Copy"}
              </button>
            </div>
            <button onClick={() => setNewKey(null)} className="mt-3 text-xs text-muted hover:text-fg">
              I&apos;ve saved it — dismiss
            </button>
          </div>
        )}

        {err && <div className="mt-4 rounded-md border border-down/30 bg-down/5 p-3 text-sm text-down">{err}</div>}

        {/* Create */}
        <form onSubmit={createKey} className="mt-6 flex flex-wrap items-end gap-3">
          <label className="block">
            <span className="text-xs font-medium text-muted">New key label</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. prod-bot"
              maxLength={80}
              className="mt-1.5 block h-10 w-64 rounded-md border border-border bg-panel px-3 text-sm focus:border-accent focus:outline-none"
            />
          </label>
          <button
            type="submit"
            disabled={!name.trim() || creating || (data ? data.count >= data.max_keys : false)}
            className="btn-primary h-10 text-sm disabled:opacity-50"
          >
            {creating ? "Creating…" : "Create key"}
          </button>
          {data && (
            <span className="self-center text-xs text-muted">
              {data.count} / {data.max_keys} keys · {data.daily_limit.toLocaleString()} req/day each
            </span>
          )}
        </form>

        {/* List */}
        <div className="card mt-4 overflow-x-auto">
          <table className="w-full text-sm nums">
            <thead className="text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-2 text-left">Label</th>
                <th className="px-4 py-2 text-left">Key</th>
                <th className="px-4 py-2 text-right">Today</th>
                <th className="px-4 py-2 text-right">Total</th>
                <th className="px-4 py-2 text-left">Last used</th>
                <th className="px-4 py-2 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {!data ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-muted">Loading…</td></tr>
              ) : data.items.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-muted">
                  No keys yet. Create one above to start hitting the API.
                </td></tr>
              ) : data.items.map((k) => (
                <tr key={k.id} className="border-b border-border/20">
                  <td className="px-4 py-2 font-medium">{k.name}</td>
                  <td className="px-4 py-2 text-muted">{k.prefix}…</td>
                  <td className="px-4 py-2 text-right">{k.requests_today.toLocaleString()} / {k.daily_limit.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right text-muted">{k.request_count_total.toLocaleString()}</td>
                  <td className="px-4 py-2 text-xs text-muted">{k.last_used_at ? new Date(k.last_used_at).toLocaleString() : "never"}</td>
                  <td className="px-4 py-2 text-right">
                    <button onClick={() => revoke(k.id)} className="text-xs text-muted hover:text-down">Revoke</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Paywall>

      {/* Docs — visible to everyone as a teaser */}
      <h2 className="mt-10 text-xl font-semibold">Quickstart</h2>
      <p className="mt-1 text-sm text-muted">
        Base URL <code className="rounded bg-panel px-1 py-0.5 text-xs">{API_DOCS_BASE}</code>. Authenticate every
        request with your key. All endpoints are read-only.
      </p>
      <div className="card mt-4 overflow-x-auto p-4">
        <pre className="text-xs leading-relaxed nums whitespace-pre">{`# Top of the scored universe
curl ${API_DOCS_BASE}/signals?min_score=70 \\
  -H "X-API-Key: tl_live_your_key_here"

# A single ticker's score + six sub-scores
curl ${API_DOCS_BASE}/ticker/AAPL \\
  -H "X-API-Key: tl_live_your_key_here"

# Current macro regime
curl ${API_DOCS_BASE}/regime -H "X-API-Key: tl_live_your_key_here"

# Your key's identity + remaining daily quota
curl ${API_DOCS_BASE}/me -H "X-API-Key: tl_live_your_key_here"`}</pre>
      </div>
      <ul className="mt-4 space-y-1 text-sm text-muted">
        <li><code className="rounded bg-panel px-1 py-0.5 text-xs">GET /signals</code> — full universe; filter with <code className="rounded bg-panel px-1 py-0.5 text-xs">min_score</code>, <code className="rounded bg-panel px-1 py-0.5 text-xs">signal</code>; page with <code className="rounded bg-panel px-1 py-0.5 text-xs">limit</code> (max 2000) + <code className="rounded bg-panel px-1 py-0.5 text-xs">offset</code>.</li>
        <li><code className="rounded bg-panel px-1 py-0.5 text-xs">GET /ticker/&#123;symbol&#125;</code> — one ticker&apos;s score, signal, and sub-scores.</li>
        <li><code className="rounded bg-panel px-1 py-0.5 text-xs">GET /regime</code> — VIX, 10Y, DXY, breadth, sector leaders.</li>
        <li><code className="rounded bg-panel px-1 py-0.5 text-xs">GET /me</code> — quota check before a batch run.</li>
      </ul>
      <p className="mt-4 text-xs text-subtle">
        Quota is per key, {data?.daily_limit?.toLocaleString() || "1,000"} requests/day on Premium, resetting at 00:00 UTC.
        Keys can also be passed as <code className="rounded bg-panel px-1 py-0.5 text-xs">Authorization: Bearer tl_live_…</code>.
        Not investment advice — data is provided for informational purposes only.
      </p>
    </div>
  );
}
