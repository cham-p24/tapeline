import { pageMeta } from "@/lib/seo";

// status/page.tsx is a client component (live polling), so metadata is here.
export const metadata = pageMeta({
  title: "Tapeline System Status — Uptime + Data Feed Health",
  description:
    "Status of Tapeline systems: scanner engine, public API, upstream data feeds, and the worker pass. Checked from your browser every 30 seconds while the page is open.",
  path: "/status",
});

export default function StatusLayout({ children }: { children: React.ReactNode }) {
  return children;
}
