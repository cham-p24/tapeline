"use client";

import { useEffect, useState } from "react";
import { formatRelativeOrAbsolute } from "@/lib/datetime";
import { quoteTimeNote } from "@/lib/freshness";
import { AUTO_REFRESH_WINDOW_MS, type LiveStatus } from "@/lib/useLiveStream";

/**
 * Connection and freshness badge for the in-app pages.
 *
 * It never says "Live" and never pulses. The prices behind every page are the
 * vendor's ~15-minute-delayed prices, and until 14 Sep 2026 this badge showed
 * a pulsing "Live" driven by heartbeat pings while no update event ever
 * reached the browser (0 update events in a 300s capture during the US
 * session). It now states only what the page is doing:
 *
 *   auto        "Auto-refreshing · updated HH:MM"  (time the last update arrived)
 *   connected   "Updated HH:MM"                     (time the data last loaded successfully)
 *               "Connected"                         (before the first successful load)
 *   connecting  "Updated HH:MM" once data has loaded, else "Connecting…"
 *   offline     "Offline · updated HH:MM", or "Offline" before any load
 *
 * "Auto-refreshing" appears only while update events really arrive, which is
 * only during the US extended session (the API's live bridge does not forward
 * the worker's off-hours writes) and only on pages that leave auto-refresh on.
 *
 * The delay disclosure ("prices delayed about 15 minutes") belongs to page
 * copy, not to this badge — EXCEPT that "Updated HH:MM" beside a single price
 * reads as the price's time, which it is not (it is when this page last
 * loaded). A page that shows one price passes `quoteAt`, the vendor's own time
 * for it (backend Ticker.quote_at), and the badge adds " · Quote as of 15m ago"
 * (an AGE or a date, never a bare clock time: a Friday or day-old crypto close
 * printed "10:00" reads as today's), or the no-time note from lib/freshness
 * when the vendor gave none. `crypto` switches both to the crypto wording.
 * Pages that do not pass `quoteAt` are unchanged.
 */

type BadgeStatus = LiveStatus;

export function formatBadgeTime(d: Date): string {
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function badgeLabel(
  status: BadgeStatus,
  lastUpdate: Date | null,
  now: number = Date.now(),
  quoteAt?: string | null,
  crypto: boolean = false,
): { text: string; tone: "auto" | "connected" | "connecting" | "offline" } {
  const base = baseLabel(status, lastUpdate, now);
  // `undefined` = the page did not say (unchanged badge); null = the vendor
  // gave no time for this price, so state the no-time note, never a time.
  if (quoteAt === undefined) return base;
  const note = quoteTimeNote(quoteAt, (d) => formatRelativeOrAbsolute(d), { crypto });
  return { ...base, text: `${base.text} · ${note}` };
}

function baseLabel(
  status: BadgeStatus,
  lastUpdate: Date | null,
  now: number,
): { text: string; tone: "auto" | "connected" | "connecting" | "offline" } {
  const time = lastUpdate ? formatBadgeTime(lastUpdate) : null;
  // Defensive: "auto" is only honest while updates are recent. The hook
  // already downgrades, but the badge must not outlive a stale prop either.
  const autoIsFresh =
    status === "auto" &&
    lastUpdate !== null &&
    now - lastUpdate.getTime() <= AUTO_REFRESH_WINDOW_MS;

  if (autoIsFresh && time) {
    return { text: `Auto-refreshing · updated ${time}`, tone: "auto" };
  }
  if (status === "offline") {
    return { text: time ? `Offline · updated ${time}` : "Offline", tone: "offline" };
  }
  if (status === "connecting") {
    return { text: time ? `Updated ${time}` : "Connecting…", tone: "connecting" };
  }
  return { text: time ? `Updated ${time}` : "Connected", tone: "connected" };
}

const DOT: Record<ReturnType<typeof badgeLabel>["tone"], string> = {
  auto: "bg-up",
  connected: "bg-muted",
  connecting: "bg-warn",
  offline: "bg-down",
};

const TITLE: Record<ReturnType<typeof badgeLabel>["tone"], string> = {
  auto: "New data loads on this page by itself after each update.",
  connected: "Reload to check for newer numbers.",
  connecting: "Connecting to the update stream.",
  offline: "Connection lost. Reconnecting.",
};

export function LiveBadge({
  status,
  lastUpdate,
  quoteAt,
  crypto = false,
}: {
  status: BadgeStatus;
  lastUpdate: Date | null;
  /** The vendor's time for the one price this page shows; see badgeLabel. */
  quoteAt?: string | null;
  /** The price is a crypto pair's daily close; see badgeLabel. */
  crypto?: boolean;
}) {
  // Re-render periodically so a stale "auto" prop cannot linger on screen.
  const [now, setNow] = useState<number>(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 15_000);
    return () => clearInterval(t);
  }, []);

  const { text, tone } = badgeLabel(status, lastUpdate, now, quoteAt, crypto);
  return (
    <span
      data-testid="live-badge"
      data-tone={tone}
      title={TITLE[tone]}
      className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 text-xs text-muted"
    >
      <span aria-hidden="true" className={`h-2 w-2 rounded-full ${DOT[tone]}`} />
      {text}
    </span>
  );
}
