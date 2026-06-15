"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/**
 * Shared earnings-calendar lookup.
 *
 * Fetches the upcoming earnings calendar once and reduces it to a
 * `symbol → next-report-date (YYYY-MM-DD)` map. Rows come back from
 * /api/earnings ordered by report_date ascending and pre-filtered to
 * report_date >= today (see calendar_routes.list_earnings), so the FIRST
 * occurrence per symbol is the soonest upcoming report — exactly what the
 * row-level "earnings this week" pill needs.
 *
 * Used by the scanner + ticker pages so neither has to re-implement the
 * fetch or the dedupe. Failure is non-fatal: the map stays empty and the
 * pill simply doesn't render — earnings is supplementary context, never a
 * reason to break the surrounding table.
 *
 * `days` defaults to 14 to match the earnings page; callers wanting a
 * tighter "this week" window can still call daysUntilEarnings() with the
 * returned date and decide their own threshold.
 */
export function useEarningsCalendar(days = 14): Map<string, string> {
  const [map, setMap] = useState<Map<string, string>>(new Map());

  useEffect(() => {
    let cancelled = false;
    api
      .earnings({ days })
      .then((r) => {
        if (cancelled) return;
        const next = new Map<string, string>();
        for (const e of r.items) {
          // First write wins — items are date-ascending so this keeps the
          // soonest report per symbol.
          if (!next.has(e.symbol)) next.set(e.symbol, e.report_date);
        }
        setMap(next);
      })
      .catch(() => {
        /* non-fatal — leave the map empty, pills just don't show */
      });
    return () => {
      cancelled = true;
    };
  }, [days]);

  return map;
}

/**
 * Whole calendar-days from today (local) until `reportDate` (YYYY-MM-DD).
 * 0 = reports today, 1 = tomorrow, negative = already past (shouldn't
 * happen given the backend filter, but guarded anyway). Returns null for
 * an unparseable / missing date.
 */
export function daysUntilEarnings(reportDate: string | null | undefined): number | null {
  if (!reportDate) return null;
  // Parse as a local date at midnight so the diff is in whole calendar days
  // regardless of the current time-of-day.
  const parts = reportDate.split("-").map(Number);
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return null;
  const [y, m, d] = parts;
  const target = new Date(y, m - 1, d);
  if (Number.isNaN(target.getTime())) return null;
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const diffMs = target.getTime() - today.getTime();
  return Math.round(diffMs / 86_400_000);
}
