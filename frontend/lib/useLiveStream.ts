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
 *     sees a new database write, about once per worker pass (~70-80s apart).
 *     The worker writes around the clock (it does not pause when the market
 *     is closed), but the bridge forwards writes only during the US extended
 *     session, 04:00-20:00 ET on trading days, because off-hours passes carry
 *     no new prices. Before that bridge existed the worker's publishes never
 *     reached the API, and a 300s capture on 14 Sep 2026 received 0 update
 *     events while this hook reported "live" off pings.
 *
 * Status is therefore driven by what actually happened, not by the socket:
 *   - "auto"       an update event arrived within AUTO_REFRESH_WINDOW_MS, so
 *                  the page really is refetching on its own.
 *   - "connected"  the stream is open but no update arrived within
 *                  AUTO_REFRESH_WINDOW_MS: just connected, a deploy gap,
 *                  outside the US extended session (the bridge does not
 *                  forward off-hours writes), the bridge is not publishing,
 *                  or the page turned auto-refresh off (`enabled: false`).
 *   - "connecting" before the first hello.
 *   - "offline"    the connection dropped; we are reconnecting.
 *
 * `lastUpdate` is the time the badge should print:
 *   - in "auto", when the last update event arrived;
 *   - otherwise, when this page's data last loaded SUCCESSFULLY, as far as
 *     the hook knows: the page calls `markLoaded()` after its own loads
 *     succeed (mount, filter changes), and the hook stamps each
 *     update-triggered refetch that succeeds. A refetch counts as failed when
 *     the callback throws, rejects, or returns/resolves to `false`; pages whose
 *     `load` swallows its own errors return `false` from the catch. Until the
 *     first successful load `lastUpdate` is null, and the badge says
 *     "Connected" rather than a time for data that never arrived.
 *
 * `enabled` (default true). Pass `enabled: false` where a refetch costs the
 * user something or records something: the squeeze preview (a free-tier cap
 * hit per call), or the ticker page when the API gave it no receipt to prove
 * the refetch is not a new look-up. While disabled the hook never schedules a
 * refetch (on an update or on a reconnect hello), never
 * reports "auto", and drops any refetch already pending. The stream stays
 * open so the badge can still show "Offline".
 *
 * `subscribe` (default true). Pass `subscribe: false` while the page shows a
 * cap wall instead of data (the ticker page's LookupWall): no EventSource is
 * opened, and one already open is closed with its timers. Nothing on a wall
 * refreshes and no badge is shown, so an open connection there would only be
 * a way for a later change to start spending the user's limits again. When it
 * turns true the stream connects fresh; the page loads its own data, so that
 * first hello does not refetch.
 *
 * Reconnects refetch. A `hello` after the first one on this subscription means
 * the connection dropped and came back (EventSource's own retry, or the
 * backoff below). Any update sent while it was down was missed, so that hello
 * schedules one refetch, paced like an update. It does not move the badge into
 * "auto": no update arrived.
 *
 * Refetch pacing: a normal worker pass produces one event, but events are still
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

export type LiveStreamOptions = {
  /** False turns auto-refresh off for this page. Default true. */
  enabled?: boolean;
  /** False opens no stream at all (a cap wall is shown). Default true. */
  subscribe?: boolean;
};

/** A refetch that returns `false` (or a promise resolving to it) failed. */
export type LiveRefetch = () => void | boolean | Promise<unknown>;

export function useLiveStream(
  onUpdate: LiveRefetch,
  options: LiveStreamOptions = {},
): {
  status: LiveStatus;
  lastUpdate: Date | null;
  markLoaded: () => void;
} {
  const enabled = options.enabled ?? true;
  const subscribe = options.subscribe ?? true;
  const [connection, setConnection] = useState<Connection>("connecting");
  const [lastEventAt, setLastEventAt] = useState<Date | null>(null);
  const [loadedAt, setLoadedAt] = useState<Date | null>(null);
  const [now, setNow] = useState<number>(0);
  const cb = useRef(onUpdate);
  const enabledRef = useRef(enabled);
  const cancelPendingRefetch = useRef<() => void>(() => {});
  // Keep the refs pointing at the latest values without writing during
  // render (react-hooks/refs).
  useEffect(() => {
    cb.current = onUpdate;
  });
  useEffect(() => {
    enabledRef.current = enabled;
    // Turning auto-refresh off drops a pending refetch. The status below
    // already ignores update events while disabled.
    if (!enabled) cancelPendingRefetch.current();
  }, [enabled]);

  const markLoaded = useCallback(() => {
    setLoadedAt(new Date());
  }, []);

  useEffect(() => {
    // Set after mount (not in initial state) so server and client render the
    // same markup. No load stamp here: the page's own fetch has not succeeded
    // yet, and may not.
    setNow(Date.now());
    const recheck = setInterval(() => setNow(Date.now()), RECHECK_MS);
    return () => clearInterval(recheck);
  }, []);

  useEffect(() => {
    if (!subscribe) {
      // A wall is shown: no connection, no timers. The previous run's cleanup
      // (if any) already closed its stream and cleared its pending refetch.
      cancelPendingRefetch.current = () => {};
      return;
    }
    const base = process.env.NEXT_PUBLIC_API_URL || "";
    const url = `${base}/api/stream/live`;

    let es: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let refetchTimer: ReturnType<typeof setTimeout> | null = null;
    let lastRefetchAt: number | null = null;
    let cancelled = false;
    // hellos seen on this subscription; any after the first is a reconnect.
    let hellos = 0;
    let backoffMs = 1000;
    const MAX_BACKOFF_MS = 30_000;

    function runRefetch() {
      refetchTimer = null;
      if (cancelled || !enabledRef.current) return;
      lastRefetchAt = Date.now();
      let result: void | boolean | Promise<unknown>;
      try {
        result = cb.current();
      } catch {
        return;
      }
      if (result && typeof (result as Promise<unknown>).then === "function") {
        (result as Promise<unknown>).then(
          (value) => {
            // `false` = the page caught its own error: keep the previous time.
            if (!cancelled && value !== false) setLoadedAt(new Date());
          },
          () => {
            /* the page owns its error state; keep the previous load time */
          },
        );
      } else if (result !== false) {
        setLoadedAt(new Date());
      }
    }

    cancelPendingRefetch.current = () => {
      if (refetchTimer) clearTimeout(refetchTimer);
      refetchTimer = null;
    };

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
        hellos += 1;
        // Back after a drop: updates sent while offline were missed.
        if (hellos > 1 && enabledRef.current) scheduleRefetch();
      });
      es.addEventListener("update", () => {
        backoffMs = 1000;
        setConnection("open");
        // Auto-refresh turned off by the page: the event proves the socket is
        // open and nothing else. No refetch, no "auto".
        if (!enabledRef.current) return;
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
  }, [subscribe]);

  const status = deriveLiveStatus(connection, enabled ? lastEventAt : null, now);
  const lastUpdate = status === "auto" ? lastEventAt : loadedAt;
  return { status, lastUpdate, markLoaded };
}
