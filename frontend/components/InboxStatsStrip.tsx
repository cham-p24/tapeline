/**
 * Stats strip — observability chips at the top of the admin inbox page.
 *
 * Extracted from app/app/inbox/page.tsx (#296 follow-up): the App Router
 * discourages non-reserved named exports from page files, and the strip is
 * independently tested (__tests__/InboxStatsStrip.test.tsx), so it lives as
 * its own presentational module. No hooks, no client state — it renders
 * whatever InboxStats the page hands it.
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
import type { ReactNode } from "react";

export type InboxStats = {
  today_spend_usd: number;
  today_classifications: number;
  cap_usd: number;
  cap_tripped: boolean;
  // LLM health (PR #292) — non-zero llm_errors_24h means classifier calls are
  // failing and the bot has silently degraded to manual-review-everything.
  llm_errors_24h: number;
  llm_attempts_24h: number;
  llm_error_rate: number;
  last_error_at: string | null;
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

export function StatsStrip({ stats }: { stats: InboxStats }) {
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
  // Silent-classifier-degradation guard. Non-zero llm_errors_24h means
  // Anthropic calls are failing (dead key, timeout, parse error) and every
  // ambiguous message is falling back to Tier 1 manual review while tier
  // counts keep moving — the bot LOOKS up but isn't classifying. Surface it
  // loudly so the operator catches it within a stats tick.
  if (stats.llm_errors_24h > 0) {
    const lastAt = stats.last_error_at ? formatErrorTime(stats.last_error_at) : null;
    const ratePct = Math.round(stats.llm_error_rate * 100);
    banners.push({
      tone: "down",
      label: `LLM errors: ${stats.llm_errors_24h}${lastAt ? ` (last ${lastAt})` : ""}`,
      detail: `${stats.llm_errors_24h} of ${stats.llm_attempts_24h} classifier call${stats.llm_attempts_24h === 1 ? "" : "s"} failed in the last 24h (${ratePct}% error rate). Ambiguous messages are defaulting to Tier 1 manual review — check the Anthropic key and logs.`,
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
        {/* LLM errors chip — always shown when any classifier calls were
            attempted, so a healthy 0/N reads as an explicit "all good".
            A red dot + count flags silent classifier degradation. */}
        {stats.llm_attempts_24h > 0 && (
          <Chip label="LLM errors">
            {stats.llm_errors_24h > 0 ? (
              <span className="inline-flex items-center gap-1.5">
                <span
                  className="inline-block h-1.5 w-1.5 rounded-full bg-down"
                  aria-hidden="true"
                />
                <span className="font-semibold nums text-down">
                  {stats.llm_errors_24h}
                </span>
                {stats.last_error_at && (
                  <span className="text-subtle">
                    (last {formatErrorTime(stats.last_error_at)})
                  </span>
                )}
              </span>
            ) : (
              <span className="font-semibold nums text-up">0</span>
            )}
            <span className="text-subtle"> / {stats.llm_attempts_24h}</span>
          </Chip>
        )}
      </div>
    </div>
  );
}

// Short local-time HH:MM for the "last error" hint. Falls back to the raw
// string if the timestamp doesn't parse so we never render "Invalid Date".
function formatErrorTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function Chip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline gap-1.5 rounded-md bg-panel px-2.5 py-1">
      <span className="text-[10px] uppercase tracking-wider text-subtle">{label}</span>
      <span className="text-sm">{children}</span>
    </div>
  );
}
