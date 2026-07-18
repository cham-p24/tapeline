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
  title:
    "Tapeline Public Scorecard — Every Daily Top-10, Frozen at the Close and Checked Against SPY",
  description:
    "The append-only archive of every daily top-10 ranking Tapeline has published: frozen at the session close it printed, checked against the next session's SPY move, losing days kept. Raw CSV and JSON published so you can re-run the arithmetic yourself.",
  path: "/scorecard",
});

export default function ScorecardLayout({ children }: { children: React.ReactNode }) {
  return children;
}
