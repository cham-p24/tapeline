"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Subscribe to the backend SSE stream and fire `onUpdate` when the server
 * publishes an "update" event.
 *
 * Reconnect strategy:
 *   - The browser's EventSource auto-reconnects on transient TCP drops.
 *   - But on a permanent close (HTTP 5xx, deploy, network policy change),
 *     `onerror` fires and the connection enters CLOSED state forever
 *     unless the page is reloaded. Without manual reconnect logic,
 *     paying users see LiveBadge stuck on "offline" while the data
 *     they're staring at silently goes stale.
 *
 * Manual reconnect path:
 *   - On error, mark status "offline", schedule a retry with exponential
 *     backoff capped at 30s.
 *   - Reset the backoff to its base after a successful "hello" or "update"
 *     event, so a quick blip doesn't propagate as long delays in a later
 *     incident.
 *   - On unmount, clear timers + close the EventSource.
 */
export function useLiveStream(onUpdate: () => void): {
  status: "connecting" | "live" | "offline";
  lastUpdate: Date | null;
} {
  const [status, setStatus] = useState<"connecting" | "live" | "offline">("connecting");
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const cb = useRef(onUpdate);
  // Keep the ref pointing at the latest callback without writing during
  // render (react-hooks/refs). A deps-less effect runs after every commit,
  // so the SSE "update" handler below always invokes the freshest callback.
  useEffect(() => {
    cb.current = onUpdate;
  });

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL || "";
    const url = `${base}/api/stream/live`;

    let es: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;
    let backoffMs = 1000; // base backoff
    const MAX_BACKOFF_MS = 30_000;

    function connect() {
      if (cancelled) return;
      // Tear down any prior dead instance before opening a new one.
      try {
        es?.close();
      } catch {
        /* ignore */
      }
      es = new EventSource(url);

      es.addEventListener("hello", () => {
        backoffMs = 1000; // reset on successful handshake
        setStatus("live");
      });
      es.addEventListener("update", () => {
        backoffMs = 1000;
        setLastUpdate(new Date());
        setStatus("live");
        cb.current();
      });
      es.addEventListener("ping", () => {
        backoffMs = 1000;
        setStatus("live");
      });
      es.onerror = () => {
        // EventSource has its own retry, but if it transitions to CLOSED
        // we have to reopen it ourselves. Even when it stays in CONNECTING,
        // surfacing "offline" while we're between attempts is the honest
        // signal to show the user.
        setStatus("offline");
        if (es && es.readyState === EventSource.CLOSED) {
          try {
            es.close();
          } catch {
            /* ignore */
          }
          es = null;
          if (!cancelled) {
            const wait = Math.min(backoffMs, MAX_BACKOFF_MS);
            retryTimer = setTimeout(connect, wait);
            backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF_MS);
          }
        }
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
      try {
        es?.close();
      } catch {
        /* ignore */
      }
      es = null;
    };
  }, []);

  return { status, lastUpdate };
}
