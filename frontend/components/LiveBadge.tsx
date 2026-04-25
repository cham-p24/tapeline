"use client";

export function LiveBadge({
  status,
  lastUpdate,
}: {
  status: "connecting" | "live" | "offline";
  lastUpdate: Date | null;
}) {
  const color =
    status === "live" ? "bg-up" : status === "connecting" ? "bg-yellow-500" : "bg-down";
  const label =
    status === "live"
      ? `Live${lastUpdate ? ` · updated ${lastUpdate.toLocaleTimeString()}` : ""}`
      : status === "connecting"
      ? "Connecting…"
      : "Offline";
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 text-xs text-muted">
      <span className={`h-2 w-2 rounded-full ${color} ${status === "live" ? "animate-pulse" : ""}`} />
      {label}
    </span>
  );
}
