"use client";

/**
 * Inbox admin UI — Phase E of the inbox auto-handler bot.
 *
 * Founder-only surface for reviewing inbound messages classified by
 * the backend (Reddit / email / Telegram → Tier 1/2/3). Tier 2
 * messages are already auto-replied — the UI shows them as 'sent' /
 * 'auto_replied' for accountability. Tier 1 messages need explicit
 * approval (or edit, or reject) before a reply goes out.
 *
 * Hidden from the nav for non-admins — middleware doesn't gate it
 * (the backend does, returning 403), but the page renders a
 * friendly "not authorised" state instead of a raw error.
 */
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useUser } from "@/components/UserContext";

type InboxItem = {
  id: number;
  channel: string;
  author: string;
  subject: string | null;
  body_preview: string;
  received_at: string;
  tier: number | null;
  tier_reason: string | null;
  suggested_reply: string | null;
  status: string;
  handled_at: string | null;
};

type InboxStats = {
  today_spend_usd: number;
  today_classifications: number;
  cap_usd: number;
  cap_tripped: boolean;
  tier_counts_today: { "1": number; "2": number; "3": number; unclassified: number };
  tier_counts_last_7d: { "1": number; "2": number; "3": number; unclassified: number };
  channel_counts_today: Record<string, number>;
  status_counts_today: Record<string, number>;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  cache_hit_ratio: number;
  pending_count: number;
  bot_enabled: boolean;
  dry_run: boolean;
};

// Refresh cadence for the stats strip — fast enough that a cap trip is
// noticed within a tick, slow enough that the founder leaving the page
// open doesn't hammer the API.
const STATS_REFRESH_MS = 30_000;

const STATUS_FILTERS = [
  { key: "all",       label: "All",       value: "" },
  { key: "queue",     label: "Needs review", value: "classified" },
  { key: "auto",      label: "Auto-replied", value: "auto_replied,sent" },
  { key: "ignored",   label: "Ignored",   value: "ignored" },
];

const TIER_PILL: Record<number, { label: string; cls: string }> = {
  1: { label: "Tier 1 · founder voice", cls: "bg-warn/15 text-warn" },
  2: { label: "Tier 2 · auto-reply",    cls: "bg-up/15 text-up" },
  3: { label: "Tier 3 · ignored",       cls: "bg-down/15 text-down" },
};

const CHANNEL_LABEL: Record<string, string> = {
  email:           "Email",
  reddit_comment:  "Reddit comment",
  reddit_dm:       "Reddit DM",
  telegram:        "Telegram",
};


export default function InboxPage() {
  const { user, loading: userLoading } = useUser();
  const [items, setItems] = useState<InboxItem[]>([]);
  const [stats, setStats] = useState<InboxStats | null>(null);
  const [statusKey, setStatusKey] = useState("queue");
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  const load = useCallback(async () => {
    setError(null);
    const filter = STATUS_FILTERS.find((f) => f.key === statusKey);
    try {
      const r = await api.inboxList({
        status: filter?.value || undefined,
        limit: 100,
      });
      setItems(r.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load inbox");
      setItems([]);
    }
  }, [statusKey]);

  const loadStats = useCallback(async () => {
    try {
      const s = await api.inboxStats();
      setStats(s);
    } catch {
      // Stats failure shouldn't block the page — the strip just hides
      // when stats is null. Don't surface a banner; the list error
      // banner is the loud channel.
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Stats live independently of the list filter — load once on mount
  // and poll every 30s so the spend chip + cap warning are fresh.
  useEffect(() => {
    if (!user || !user.is_admin) return;
    loadStats();
    const id = setInterval(loadStats, STATS_REFRESH_MS);
    return () => clearInterval(id);
  }, [user, loadStats]);

  async function onApprove(id: number, editedText?: string) {
    setBusy(id);
    try {
      // The endpoint returns HTTP 200 with {ok:false,...} when the reply
      // couldn't actually be delivered (Reddit throttle, skipped email,
      // unsupported channel). Surface that instead of silently "succeeding"
      // — the row stays at status='approved' so re-approving retries.
      const res = await api.inboxApprove(id, editedText);
      if (res && res.ok === false) {
        const detail = res.reason ? `${res.error} (${res.reason})` : res.error;
        setError(`Couldn't send #${id}: ${detail ?? "unknown error"}`);
      } else {
        setEditingId(null);
        setEditText("");
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setBusy(null);
    }
  }

  async function onReject(id: number) {
    if (!confirm("Reject this message — no reply will be sent. Continue?")) return;
    setBusy(id);
    try {
      await api.inboxReject(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reject failed");
    } finally {
      setBusy(null);
    }
  }

  if (userLoading) return null;
  if (!user || !user.is_admin) {
    return (
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Inbox</h1>
        <div className="card mt-4 p-6 text-center text-sm text-muted">
          The inbox auto-handler is admin-only. If you should have access,
          contact support.
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Inbox</h1>
          <p className="mt-1 text-sm text-muted">
            Inbound messages across Reddit, email, and Telegram — auto-classified
            into Tier 1 (needs your eyes), Tier 2 (auto-replied), Tier 3 (ignored).
            Refresh manually after acting; live updates land in a future build.
          </p>
        </div>
      </div>

      {/* Stats strip — observability for spend / queue / latency / mode.
          Hidden until the stats fetch lands. Cap-tripped + bot-disabled
          + dry-run get loud chips up front. */}
      {stats && <StatsStrip stats={stats} />}

      {/* Status filter pills */}
      <div className="mt-5 flex flex-wrap items-center gap-2 text-xs">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setStatusKey(f.key)}
            className={`rounded-full px-3 py-1 font-medium transition ${
              statusKey === f.key
                ? "bg-accent/15 text-accent"
                : "bg-panel text-muted hover:text-fg"
            }`}
          >
            {f.label}
          </button>
        ))}
        <button
          type="button"
          onClick={load}
          className="ml-auto rounded-full bg-panel px-3 py-1 text-muted hover:text-fg"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="card mt-4 border border-down/30 p-4 text-sm">
          <p className="text-down">{error}</p>
        </div>
      )}

      {!error && items.length === 0 && (
        <div className="card mt-4 p-6 text-center text-sm text-muted">
          No messages match this filter.
        </div>
      )}

      <div className="mt-4 space-y-3">
        {items.map((m) => {
          const tier = m.tier ?? 0;
          const pill = TIER_PILL[tier];
          const channelLabel = CHANNEL_LABEL[m.channel] || m.channel;
          const isEditing = editingId === m.id;
          const isFinal = m.status === "sent" || m.status === "ignored";

          return (
            <div key={m.id} className="card p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <div className="flex flex-wrap items-baseline gap-2">
                  {pill && (
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${pill.cls}`}>
                      {pill.label}
                    </span>
                  )}
                  <span className="text-xs uppercase tracking-wider text-subtle">
                    {channelLabel}
                  </span>
                  <span className="text-sm font-medium">{m.author}</span>
                </div>
                <span className="text-[11px] text-subtle nums">
                  {new Date(m.received_at).toLocaleString()}
                </span>
              </div>

              {m.subject && (
                <p className="mt-2 text-sm font-medium">{m.subject}</p>
              )}

              <p className="mt-2 whitespace-pre-wrap text-sm text-muted">
                {m.body_preview}
              </p>

              {m.tier_reason && (
                <p className="mt-3 text-[11px] text-subtle">
                  <span className="font-semibold text-muted">Why this tier:</span>{" "}
                  {m.tier_reason}
                </p>
              )}

              {m.suggested_reply && !isEditing && (
                <div className="mt-3 rounded-md border border-border/60 bg-panel p-3">
                  <p className="text-[11px] uppercase tracking-wider text-subtle">
                    {tier === 2 ? "Auto-reply sent" : "Suggested reply"}
                  </p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">
                    {m.suggested_reply}
                  </p>
                </div>
              )}

              {isEditing && (
                <div className="mt-3">
                  <textarea
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    rows={5}
                    className="w-full rounded-md border border-border bg-panel p-3 text-sm focus:border-accent focus:outline-none"
                    placeholder="Edit the reply…"
                  />
                </div>
              )}

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className={`text-[11px] uppercase tracking-wider ${
                  m.status === "sent" ? "text-up"
                    : m.status === "ignored" ? "text-down"
                    : m.status === "classified" ? "text-warn"
                    : "text-muted"
                }`}>
                  {m.status}
                </span>

                {!isFinal && tier === 1 && (
                  <>
                    {isEditing ? (
                      <>
                        <button
                          type="button"
                          disabled={busy === m.id || editText.trim().length === 0}
                          onClick={() => onApprove(m.id, editText)}
                          className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
                        >
                          Send edited
                        </button>
                        <button
                          type="button"
                          disabled={busy === m.id}
                          onClick={() => { setEditingId(null); setEditText(""); }}
                          className="rounded-md border border-border px-3 py-1.5 text-xs hover:border-fg/40"
                        >
                          Cancel edit
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          disabled={busy === m.id || !m.suggested_reply}
                          onClick={() => onApprove(m.id)}
                          className="rounded-md bg-up/85 px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
                          title={m.suggested_reply ? "Send suggested reply as-is" : "No suggested reply on record"}
                        >
                          Approve & send
                        </button>
                        <button
                          type="button"
                          disabled={busy === m.id}
                          onClick={() => {
                            setEditingId(m.id);
                            setEditText(m.suggested_reply || "");
                          }}
                          className="rounded-md border border-border px-3 py-1.5 text-xs hover:border-fg/40"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          disabled={busy === m.id}
                          onClick={() => onReject(m.id)}
                          className="rounded-md border border-down/30 px-3 py-1.5 text-xs text-down hover:bg-down/10"
                        >
                          Reject
                        </button>
                      </>
                    )}
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}


/**
 * Stats strip — observability chips at the top of the inbox page.
 *
 * Prioritised by what the founder MUST see at a glance:
 *   1. Loud red banner if cap_tripped (Claude calls have stopped)
 *   2. Loud amber banner if dry_run (no real sends going out)
 *   3. Loud red banner if bot_enabled=false (master kill switch is on)
 *   4. Chip row: today's spend / pending queue / classifications today /
 *      tier mix / p95 latency / cache hit rate
 *
 * Cache-hit rate is informational — should sit near 0.95 on a warm
 * prompt cache. A drop near 0.0 means the cache_control header isn't
 * landing, which would balloon spend silently.
 */
function StatsStrip({ stats }: { stats: InboxStats }) {
  const banners: { tone: "warn" | "down"; label: string; detail: string }[] = [];
  if (!stats.bot_enabled) {
    banners.push({
      tone: "down",
      label: "Bot disabled",
      detail: "INBOX_BOT_ENABLED=false — no classification or sending happens.",
    });
  }
  if (stats.cap_tripped) {
    banners.push({
      tone: "down",
      label: "Daily cap tripped",
      detail: `Today's Claude spend ≥ $${stats.cap_usd.toFixed(2)}. Ambiguous messages default to Tier 1 manual review until UTC midnight.`,
    });
  }
  if (stats.dry_run) {
    banners.push({
      tone: "warn",
      label: "Dry-run mode",
      detail: "INBOX_DRY_RUN=true — classifier + pipeline run, but adapters log instead of sending. No real replies going out.",
    });
  }

  const spendPct = stats.cap_usd > 0
    ? Math.min(100, Math.round((stats.today_spend_usd / stats.cap_usd) * 100))
    : 0;
  const spendTone = stats.cap_tripped ? "text-down" : spendPct > 80 ? "text-warn" : "text-fg";

  const tier1 = stats.tier_counts_today["1"] || 0;
  const tier2 = stats.tier_counts_today["2"] || 0;
  const tier3 = stats.tier_counts_today["3"] || 0;
  const totalToday = tier1 + tier2 + tier3 + (stats.tier_counts_today.unclassified || 0);

  return (
    <div className="mt-4 space-y-2">
      {banners.map((b) => (
        <div
          key={b.label}
          className={`rounded-md border px-3 py-2 text-xs ${
            b.tone === "down"
              ? "border-down/40 bg-down/10 text-down"
              : "border-warn/40 bg-warn/10 text-warn"
          }`}
        >
          <span className="font-semibold">{b.label}.</span> <span className="text-muted">{b.detail}</span>
        </div>
      ))}

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Chip label="Today's spend">
          <span className={`font-semibold nums ${spendTone}`}>
            ${stats.today_spend_usd.toFixed(2)}
          </span>
          <span className="text-subtle"> / ${stats.cap_usd.toFixed(2)} cap</span>
        </Chip>
        <Chip label="Pending">
          <span className={`font-semibold nums ${stats.pending_count > 0 ? "text-warn" : "text-fg"}`}>
            {stats.pending_count}
          </span>
        </Chip>
        <Chip label="Classifications">
          <span className="font-semibold nums">{stats.today_classifications}</span>
          <span className="text-subtle"> today</span>
        </Chip>
        <Chip label="Tier mix">
          <span className="nums text-warn">T1 {tier1}</span>
          <span className="text-subtle"> · </span>
          <span className="nums text-up">T2 {tier2}</span>
          <span className="text-subtle"> · </span>
          <span className="nums text-down">T3 {tier3}</span>
          {totalToday > 0 && (
            <span className="text-subtle"> ({totalToday})</span>
          )}
        </Chip>
        {stats.latency_p95_ms !== null && (
          <Chip label="p95 latency">
            <span className={`font-semibold nums ${stats.latency_p95_ms > 4000 ? "text-warn" : "text-fg"}`}>
              {stats.latency_p95_ms}ms
            </span>
          </Chip>
        )}
        {stats.today_classifications > 0 && (
          <Chip label="Cache hit">
            <span className={`font-semibold nums ${stats.cache_hit_ratio < 0.5 ? "text-warn" : "text-up"}`}>
              {Math.round(stats.cache_hit_ratio * 100)}%
            </span>
          </Chip>
        )}
      </div>
    </div>
  );
}

function Chip({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-1.5 rounded-md bg-panel px-2.5 py-1">
      <span className="text-[10px] uppercase tracking-wider text-subtle">{label}</span>
      <span className="text-sm">{children}</span>
    </div>
  );
}
