import type { ReactNode } from "react";

/**
 * Shared page header for the in-app (/app/*) pages.
 *
 * Renders one consistent header block so every app page's title/subtitle
 * typography stays in lockstep instead of drifting per-page:
 *   - optional breadcrumb row above the title (text-xs text-muted)
 *   - the <h1> title (text-2xl md:text-3xl font-bold tracking-tight)
 *   - an optional subtitle line under the title (text-sm text-muted)
 *   - an optional right-aligned actions slot (e.g. a primary button, a
 *     LiveBadge) that sits opposite the title on the same row
 *
 * Purely presentational — no hooks, no client-only APIs — so it can be
 * dropped into either server or client pages. Additive: pages keep their
 * own body; this only replaces the ad-hoc heading block at the top.
 */
export function PageHeader({
  title,
  subtitle,
  breadcrumb,
  actions,
}: {
  title: string;
  subtitle?: ReactNode;
  breadcrumb?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div>
      {breadcrumb && (
        <div className="mb-2 flex items-center gap-2 text-xs text-muted">
          {breadcrumb}
        </div>
      )}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
        </div>
        {actions && (
          <div className="flex flex-shrink-0 items-center gap-3">{actions}</div>
        )}
      </div>
    </div>
  );
}
