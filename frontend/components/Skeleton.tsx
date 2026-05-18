export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-panel ${className}`} />;
}

export function TableSkeleton({ cols, rows = 6 }: { cols: number; rows?: number }) {
  return (
    <div className="divide-y divide-border">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3">
          {Array.from({ length: cols }).map((__, j) => (
            <Skeleton key={j} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Card-shaped placeholder used by single-card pages (regime / referrals / usage). */
export function CardSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="card mt-6 p-6 space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className={`h-4 ${i === 0 ? "w-1/3" : i % 2 ? "w-2/3" : "w-1/2"}`} />
      ))}
    </div>
  );
}
