"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/**
 * Public-record proof block for /pricing — the same pattern the signup
 * page renders at the moment of account decision, re-implemented locally
 * (the signup version is inlined in that page's form component, so there
 * is nothing importable without dragging in Turnstile et al.).
 *
 * What it shows and why: the one thing that is unambiguously true and
 * on-brand at the moment of purchase decision — the SIZE and DISCIPLINE
 * of the public record (days tracked, same-day, no edits). Deliberately
 * NOT the hit-rate / alpha headline numbers: over a short single-regime
 * sample those are weak, and anchoring the buy on them would be neither
 * honest nor effective. The full record — winners and losers — is one
 * click away on /scorecard for anyone who wants to audit.
 *
 * `days_tracked` is tier-invariant so anonymous visitors get it; the
 * block renders nothing until the back-check has logged at least one day
 * (a broken or empty proof block is worse than none).
 */
export function PricingProof() {
  const [proof, setProof] = useState<{ days: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .scorecard(30)
      .then((d) => {
        if (cancelled) return;
        const s = d.summary;
        if (typeof s.days_tracked === "number" && s.days_tracked > 0) {
          setProof({ days: s.days_tracked });
        }
      })
      .catch(() => {
        /* silent — no proof block is better than a broken one */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!proof) return null;

  return (
    <Link
      href="/scorecard"
      className="block rounded-md border border-accent/20 bg-accent/5 p-4 transition-colors hover:border-accent/40 hover:bg-accent/10"
    >
      <div className="flex items-center justify-between gap-3 text-[11px] uppercase tracking-wider text-muted">
        <span>Public track record</span>
        <span className="text-subtle">audit &rarr;</span>
      </div>
      <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1 nums">
        <span className="text-fg">
          <span className="text-base font-semibold">{proof.days}</span>
          <span className="ml-1 text-xs text-muted">days on the record</span>
        </span>
        <span className="text-fg">
          <span className="text-base font-semibold">every pick</span>
          <span className="ml-1 text-xs text-muted">logged same-day, never edited</span>
        </span>
      </div>
      <div className="mt-2 text-xs text-muted">
        See every call and how it did vs SPY &mdash; winners and losers &rarr;
      </div>
    </Link>
  );
}
