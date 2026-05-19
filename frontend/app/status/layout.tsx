import { pageMeta } from "@/lib/seo";

// status/page.tsx is a client component (live polling), so metadata is here.
export const metadata = pageMeta({
  title: "Tapeline System Status — Live Uptime + Data Feed Health",
  description:
    "Live status of Tapeline systems: scanner engine, public API, upstream data feeds, and live worker tick. Updated in real time.",
  path: "/status",
});

export default function StatusLayout({ children }: { children: React.ReactNode }) {
  return children;
}
