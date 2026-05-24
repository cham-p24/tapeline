"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@/components/UserContext";
import { CardSkeleton } from "@/components/Skeleton";
import { handle401 } from "@/lib/api";

// Mirrors `routers/inbox.py:InboxListItem`. Keep the shapes in sync —
// every field here lands somewhere in the table.
type InboxListItem = {
  id: number;
  channel: string;
  author: string;
  subject: string | null;
  body_preview: string;
  tier: number | null;
  tier_reason: string | null;
  status: string;
  suggested_reply: string | null;
  received_at: string;
  handled_at: string | null;
  created_at: string;
};

type InboxDetail = InboxListItem & {
  body: string;
  channel_msg_id: string;
  telegram_alert_message_id: number | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function adminGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!r.ok) {
    handle401(r.status);
    throw new Error(`${r.status} ${r.statusText}`);
  }
  return r.json();
}

async function adminPost<T>(path: string, body?: any): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    handle401(r.status);
    const text = await r.text();
    throw new Error(`${r.status} ${text}`);
  }
  return r.json();
}

const CHANNELS = [
  "all",
  "email",
  "telegram",
  "reddit_comment",
  "reddit_dm",
  "reddit_mention",
];

const STATUSES = [
  "all",
  "new",
  "classified",
  "approved",
  "auto_replied",
  "rejected",
  "ignored",
];

const TIERS: { label: string; value: string }[] = [
  { label: "all", value: "all" },
  { label: "Tier 1 (manual)", value: "1" },
  { label: "Tier 2 (auto)", value: "2" },
  { label: "Tier 3 (ignored)", value: "3" },
];

export default function InboxAdminPage() {
  const router = useRouter();
  const { user, loading } = useUser();
  const [items, setItems] = useState<InboxListItem[]>([]);
  const [tierFilter, setTierFilter] = useState("all");
  const [channelFilter, setChannelFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selected, setSelected] = useState<InboxDetail | null>(null);
  const [editBody, setEditBody] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  async function refresh() {
    setRefreshing(true);
    setErr(null);
    try {
      const params = new URLSearchParams();
      if (tierFilter !== "all") params.set("tier", tierFilter);
      if (channelFilter !== "all") params.set("channel", channelFilter);
      if (statusFilter !== "all") params.set("status", statusFilter);
      params.set("limit", "100");
      const data = await adminGet<{ items: InboxListItem[] }>(
        `/api/inbox?${params.toString()}`,
      );
      setItems(data.items);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.push("/signin?next=/app/admin/inbox");
      return;
    }
    if (!user.is_admin) {
      router.push("/app/scanner");
      return;
    }
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, loading, router, tierFilter, channelFilter, statusFilter]);

  async function openDetail(id: number) {
    setErr(null);
    try {
      const data = await adminGet<InboxDetail>(`/api/inbox/${id}`);
      setSelected(data);
      setEditBody(data.suggested_reply || "");
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function approve(id: number, overrideBody?: string) {
    try {
      await adminPost(`/api/inbox/${id}/approve`, {
        reply: overrideBody?.trim() || undefined,
      });
      setSelected(null);
      await refresh();
    } catch (e: any) {
      alert(`Approve failed: ${e.message}`);
    }
  }

  async function reject(id: number) {
    if (!confirm(`Reject inbound #${id}? No reply will be sent.`)) return;
    try {
      await adminPost(`/api/inbox/${id}/reject`);
      setSelected(null);
      await refresh();
    } catch (e: any) {
      alert(`Reject failed: ${e.message}`);
    }
  }

  if (loading) return <CardSkeleton rows={6} />;

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Inbox</h1>
          <p className="text-sm text-muted">
            Inbound messages across email, Reddit, and Telegram. Tier 1 needs
            your voice — approve, edit, or reject below. Tier 2 / 3 are auto-
            handled and shown for audit.
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={refreshing}
          className="btn btn-secondary text-sm"
        >
          {refreshing ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {/* Filter row */}
      <div className="mt-4 flex flex-wrap items-end gap-3 text-sm">
        <FilterSelect
          label="Tier"
          value={tierFilter}
          onChange={setTierFilter}
          options={TIERS}
        />
        <FilterSelect
          label="Channel"
          value={channelFilter}
          onChange={setChannelFilter}
          options={CHANNELS.map((c) => ({ label: c, value: c }))}
        />
        <FilterSelect
          label="Status"
          value={statusFilter}
          onChange={setStatusFilter}
          options={STATUSES.map((s) => ({ label: s, value: s }))}
        />
        <div className="ml-auto text-xs text-muted">
          {items.length} shown
        </div>
      </div>

      {err && (
        <div className="card mt-4 border-down/40 p-4 text-sm text-down">
          {err}
        </div>
      )}

      {/* Table */}
      <div className="card mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-border text-xs uppercase text-muted">
            <tr>
              <th className="px-3 py-2 text-left">#</th>
              <th className="px-3 py-2 text-left">When</th>
              <th className="px-3 py-2 text-left">Channel</th>
              <th className="px-3 py-2 text-left">From</th>
              <th className="px-3 py-2 text-left">Preview</th>
              <th className="px-3 py-2 text-center">Tier</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((m) => (
              <tr key={m.id} className="border-b border-border/30 hover:bg-panel/60">
                <td className="px-3 py-2 nums text-muted">{m.id}</td>
                <td className="px-3 py-2 text-xs text-muted nums">
                  {new Date(m.received_at).toLocaleString(undefined, {
                    month: "short", day: "numeric",
                    hour: "2-digit", minute: "2-digit",
                  })}
                </td>
                <td className="px-3 py-2 text-xs">{m.channel}</td>
                <td className="px-3 py-2 max-w-[140px] truncate">{m.author}</td>
                <td className="px-3 py-2 max-w-[420px] truncate text-muted">
                  {m.subject ? <strong className="text-fg">{m.subject}: </strong> : ""}
                  {m.body_preview}
                </td>
                <td className="px-3 py-2 text-center">
                  {m.tier !== null && <TierBadge tier={m.tier} />}
                </td>
                <td className="px-3 py-2">
                  <StatusBadge status={m.status} />
                </td>
                <td className="px-3 py-2 text-right">
                  {(m.status === "new" || m.status === "classified") && m.tier === 1 ? (
                    <button
                      onClick={() => openDetail(m.id)}
                      className="link text-xs"
                    >
                      Review →
                    </button>
                  ) : (
                    <button
                      onClick={() => openDetail(m.id)}
                      className="text-xs text-muted hover:text-fg"
                    >
                      View
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {items.length === 0 && !refreshing && (
              <tr>
                <td colSpan={8} className="px-3 py-12 text-center text-sm text-muted">
                  No inbound messages match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Detail modal */}
      {selected && (
        <div
          onClick={() => setSelected(null)}
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-6"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="card w-full max-w-3xl p-6"
          >
            <div className="flex items-baseline justify-between">
              <div>
                <h2 className="text-lg font-semibold">
                  #{selected.id} · {selected.channel}
                </h2>
                <p className="text-xs text-muted mt-0.5">
                  From <strong>{selected.author}</strong> ·{" "}
                  {new Date(selected.received_at).toLocaleString()}
                </p>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="text-muted hover:text-fg"
              >
                ✕
              </button>
            </div>

            {selected.subject && (
              <div className="mt-4 text-sm">
                <span className="text-xs text-muted uppercase">Subject</span>
                <div className="mt-1 font-medium">{selected.subject}</div>
              </div>
            )}

            <div className="mt-4 text-sm">
              <span className="text-xs text-muted uppercase">Body</span>
              <pre className="mt-1 whitespace-pre-wrap rounded bg-panel/50 p-3 text-sm leading-relaxed">
                {selected.body}
              </pre>
            </div>

            {selected.tier_reason && (
              <div className="mt-4 text-sm">
                <span className="text-xs text-muted uppercase">
                  Classifier reason
                </span>
                <div className="mt-1 italic text-muted">{selected.tier_reason}</div>
              </div>
            )}

            {(selected.status === "new" || selected.status === "classified") && (
              <>
                <div className="mt-6">
                  <span className="text-xs text-muted uppercase">
                    Draft reply
                  </span>
                  <textarea
                    value={editBody}
                    onChange={(e) => setEditBody(e.target.value)}
                    rows={6}
                    placeholder="No draft from the classifier — write your reply here…"
                    className="mt-1 w-full rounded border border-border bg-panel/30 p-3 text-sm leading-relaxed"
                  />
                </div>

                <div className="mt-4 flex gap-2 justify-end">
                  <button
                    onClick={() => reject(selected.id)}
                    className="btn btn-secondary text-sm"
                  >
                    Reject
                  </button>
                  <button
                    onClick={() => approve(selected.id, editBody)}
                    disabled={!editBody.trim()}
                    className="btn btn-primary text-sm"
                  >
                    Approve + send
                  </button>
                </div>
              </>
            )}

            {selected.status === "approved" && (
              <div className="mt-6 rounded bg-up/10 p-3 text-sm text-up">
                ✓ Approved — sent at{" "}
                {selected.handled_at &&
                  new Date(selected.handled_at).toLocaleString()}
                {selected.suggested_reply && (
                  <pre className="mt-3 whitespace-pre-wrap text-fg text-sm font-normal">
                    {selected.suggested_reply}
                  </pre>
                )}
              </div>
            )}

            {selected.status === "auto_replied" && (
              <div className="mt-6 rounded bg-accent/10 p-3 text-sm text-accent">
                ⚡ Auto-replied via Tier 2 template at{" "}
                {selected.handled_at &&
                  new Date(selected.handled_at).toLocaleString()}
                {selected.suggested_reply && (
                  <pre className="mt-3 whitespace-pre-wrap text-fg text-sm font-normal">
                    {selected.suggested_reply}
                  </pre>
                )}
              </div>
            )}

            {selected.status === "rejected" && (
              <div className="mt-6 rounded bg-down/10 p-3 text-sm text-down">
                Rejected at{" "}
                {selected.handled_at &&
                  new Date(selected.handled_at).toLocaleString()}{" "}
                — no reply sent.
              </div>
            )}

            {selected.status === "ignored" && (
              <div className="mt-6 rounded bg-panel p-3 text-sm text-muted">
                Tier 3 — classifier marked as spam/hostile, no reply sent.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { label: string; value: string }[];
}) {
  return (
    <label className="flex flex-col gap-1 text-xs uppercase text-muted">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-border bg-panel/30 px-2 py-1 text-sm normal-case text-fg"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function TierBadge({ tier }: { tier: number }) {
  const cls =
    tier === 1
      ? "bg-warn/20 text-warn"
      : tier === 2
        ? "bg-up/20 text-up"
        : "bg-panel text-muted";
  return (
    <span className={`rounded px-2 py-0.5 text-xs uppercase ${cls}`}>
      T{tier}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    new: "bg-accent/20 text-accent",
    classified: "bg-warn/20 text-warn",
    approved: "bg-up/20 text-up",
    auto_replied: "bg-up/20 text-up",
    rejected: "bg-down/20 text-down",
    ignored: "bg-panel text-muted",
  };
  return (
    <span
      className={`rounded px-2 py-0.5 text-xs uppercase ${colors[status] || "bg-panel text-muted"}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}
