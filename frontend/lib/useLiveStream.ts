"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Subscribe to the backend SSE stream and refetch the page's data when the
 * server says new data was written.
 *
 * What the server sends (backend/app/routers/stream.py):
 *   - `hello` once on connect, `ping` after 25s of quiet. Neither says any
 *     data changed. They only prove the connection is open.
 *   - `update` when the API's live bridge (backend/app/services/live_bridge.py)
 *     sees a new database write, about once per worker pass (~70-80s apart
 *     during US market hours). Before that bridge existed the worker's
 *     publishes never reached the API, and a 300s capture on 14 Sep 2026
 *     received 0 update events while this hook reported "live" off pings.
 *
 * Status is therefore driven by what actually happened, not by the socket:
 *   - "auto"       an update event arrived within AUTO_REFRESH_WINDOW_MS, so
 *                  the page really is refetching on its own.
 *   - "connected"  the stream is open but no update has arrived recently (or
 *                  ever): outside market hours, or updates are not flowing.
 *   - "connecting" before the first hello.
 *   - "offline"    the connection dropped; we are reconnecting.
 *
 * `lastUpdate` is the time the badge should print:
 *   - in "auto", when the last update event arrived;
 *   - otherwise, when this page's data was last loaded, as far as the hook
 *     knows: mount time, then each update-triggered refetch (when the callback
 *     returns a promise, the time it resolved). A page that also refetches on
 *     filter changes can call `markLoaded()` after those loads.
 *
 * Refetch pacing: one worker pass produces one event, but events are still
 * coalesced so a page never refetches more than once per MIN_REFETCH_GAP_MS.
 * An event inside that gap schedules one trailing refetch at the end of it,
 * so a newer pass is never dropped. Both constants are pinned to the bridge's
 * cadence by backend/tests/test_live_bridge.py.
 *
 * Reconnect strategy (unchanged):
 *   - EventSource auto-reconnects on transient drops, but on a permanent close
 *     `onerror` fires with readyState CLOSED and it never reopens by itself.
 *   - On error, mark "offline" and retry with exponential backoff capped at
 *     30s. Reset the backoff after any hello, update or ping.
 *   - On unmount, clear timers and close the EventSource.
 */

export type LiveStatus = "connecting" | "auto" | "connected" | "offline";

/** An update within this long keeps the badge in "auto". ~2 passes. */
export const AUTO_REFRESH_WINDOW_MS = 180_000;
/** Minimum spacing between update-triggered refetches. */
export const MIN_REFETCH_GAP_MS = 40_000;
/** Short wait so events that arrive together cause a single refetch. */
export const COALESCE_MS = 1_000;
/** How often the hook re-checks whether "auto" has gone stale. */
const RECHECK_MS = 15_000;

type Connection = "connecting" | "open" | "offline";

export function deriveLiveStatus(
  connection: Connection,
  lastEventAt: Date | null,
  now: number,
): LiveStatus {
  if (connection === "connecting") return "connecting";
  if (connection === "offline") return "offline";
  if (lastEventAt && now - lastEventAt.getTime() <= AUTO_REFRESH_WINDOW_MS) return "auto";
  return "connected";
}

export function useLiveStream(onUpdate: () => void | Promise<unknown>): {
  status: LiveStatus;
  lastUpdate: Date | null;
  markLoaded: () => void;
} {
  const [connection, setConnection] = useState<Connection>("connecting");
  const [lastEventAt, setLastEventAt] = useState<Date | null>(null);
  const [loadedAt, setLoadedAt] = useState<Date | null>(null);
  const [now, setNow] = useState<number>(0);
  const cb = useRef(onUpdate);
  // Keep the ref pointing at the latest callback without writing during
  // render (react-hooks/refs).
  useEffect(() => {
    cb.current = onUpdate;
  });

  const markLoaded = useCallback(() => {
    setLoadedAt(new Date());
  }, []);

  useEffect(() => {
    // Set after mount (not in initial state) so server and client render the
    // same markup. The page's own mount fetch starts at the same moment.
    setLoadedAt(new Date());
    setNow(Date.now());
    const recheck = setInterval(() => setNow(Date.now()), RECHECK_MS);
    return () => clearInterval(recheck);
  }, []);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL || "";
    const url = `${base}/api/stream/live`;

    let es: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let refetchTimer: ReturnType<typeof setTimeout> | null = null;
    let lastRefetchAt: number | null = null;
    let cancelled = false;
    let backoffMs = 1000;
    const MAX_BACKOFF_MS = 30_000;

    function runRefetch() {
      refetchTimer = null;
      if (cancelled) return;
      lastRefetchAt = Date.now();
      let result: void | Promise<unknown>;
      try {
        result = cb.current();
      } catch {
        return;
      }
      if (result && typeof (result as Promise<unknown>).then === "function") {
        (result as Promise<unknown>).then(
          () => {
            if (!cancelled) setLoadedAt(new Date());
          },
          () => {
            /* the page owns its error state; keep the previous load time */
          },
        );
      } else {
        setLoadedAt(new Date());
      }
    }

    function scheduleRefetch() {
      if (refetchTimer) return; // one pending refetch absorbs further events
      const sinceLast = lastRefetchAt === null ? Infinity : Date.now() - lastRefetchAt;
      const wait = Math.max(COALESCE_MS, MIN_REFETCH_GAP_MS - sinceLast);
      refetchTimer = setTimeout(runRefetch, wait);
    }

    function connect() {
      if (cancelled) return;
      try {
        es?.close();
      } catch {
        /* ignore */
      }
      es = new EventSource(url);

      es.addEventListener("hello", () => {
        backoffMs = 1000;
        setConnection("open");
      });
      es.addEventListener("update", () => {
        backoffMs = 1000;
        const at = new Date();
        setLastEventAt(at);
        setNow(at.getTime());
        setConnection("open");
        scheduleRefetch();
      });
      es.addEventListener("ping", () => {
        // A heartbeat proves the socket is open. It says nothing about data,
        // so it never moves the badge into "auto".
        backoffMs = 1000;
        setConnection("open");
      });
      es.onerror = () => {
        setConnection("offline");
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
      if (refetchTimer) clearTimeout(refetchTimer);
      try {
        es?.close();
      } catch {
        /* ignore */
      }
      es = null;
    };
  }, []);

  const status = deriveLiveStatus(connection, lastEventAt, now);
  const lastUpdate = status === "auto" ? lastEventAt : loadedAt;
  return { status, lastUpdate, markLoaded };
}
