import { pageMeta } from "@/lib/seo";

// scorecard/page.tsx is a client component, so its metadata has to live
// in this route-segment layout instead of being exported from the page.
export const metadata = pageMeta({
  title: "Tapeline Public Scorecard — Every Top-10 Pick Back-Checked vs SPY",
  description:
    "Public stock scanner track record. Every Tapeline top-10 daily pick auto-published with next-day return vs SPY. 30-day rolling hit rate, average alpha, transparent and immutable. The scoreboard nobody else publishes.",
  path: "/scorecard",
});

export default function ScorecardLayout({ children }: { children: React.ReactNode }) {
  return children;
}
