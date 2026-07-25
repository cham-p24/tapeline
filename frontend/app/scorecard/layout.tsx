import { pageMeta } from "@/lib/seo";

// scorecard/page.tsx is a client component, so its metadata has to live
// in this route-segment layout instead of being exported from the page.
//
// COMPLIANCE — Rule 3 (the vs-SPY presentation rule). The title and the
// description describe the MECHANISM (what is recorded, when it is frozen,
// what it is checked against, that losing days stay) and never the OUTCOME.
// No hit rate, no alpha figure, no percentage of any kind appears here.
//
// This is deliberately built while the live number is unflattering — a
// coin-flip hit rate on a small sample — precisely so it survives a future
// good run. The temptation to put the number in the title arrives with the
// first good month, not today, and by then the rule needs to already exist.
// scripts/lint-copy-compliance.mjs enforces the same constraint in CI.
export const metadata = pageMeta({
  // Title trimmed to <60 chars so it renders in full in the SERP (the prior
  // ~91-char title truncated mid-phrase). Still describes the MECHANISM, never
  // the outcome — no hit rate, no alpha, no vs-SPY figure (Rule 3).
  title: "Tapeline Public Scorecard — Daily Top-10 Track Record",
  // Front-loaded and tightened to ~155 chars so the differentiator (raw
  // downloadable record) survives SERP truncation. Descriptive only.
  description:
    "The append-only public record of every daily top-10 Tapeline ranks — frozen at the close, checked against SPY the next session, losing days kept. Raw CSV and JSON to verify it yourself.",
  path: "/scorecard",
});

export default function ScorecardLayout({ children }: { children: React.ReactNode }) {
  return children;
}
