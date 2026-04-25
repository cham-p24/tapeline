"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Subscribe to the backend SSE stream and fire a callback whenever the
 * server publishes an "update" event. Returns a connection status badge.
 */
export function useLiveStream(onUpdate: () => void): {
  status: "connecting" | "live" | "offline";
  lastUpdate: Date | null;
} {
  const [status, setStatus] = useState<"connecting" | "live" | "offline">("connecting");
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const cb = useRef(onUpdate);
  cb.current = onUpdate;

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL || "";
    const url = `${base}/api/stream/live`;
    let es: EventSource | null = new EventSource(url);

    es.addEventListener("hello", () => setStatus("live"));
    es.addEventListener("update", () => {
      setLastUpdate(new Date());
      cb.current();
    });
    es.addEventListener("ping", () => setStatus("live"));
    es.onerror = () => setStatus("offline");

    return () => {
      es?.close();
      es = null;
    };
  }, []);

  return { status, lastUpdate };
}
