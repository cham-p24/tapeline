import { pageMeta } from "@/lib/seo";

// signup/page.tsx is a client component (Turnstile + form state), so the
// metadata lives here. Indexable — brand queries like "tapeline sign up"
// and "tapeline free trial" should land here directly.
export const metadata = pageMeta({
  title: "Create Your Tapeline Account — 14-Day Premium Trial",
  description:
    "Create a Tapeline account and start a 14-day Premium trial: $0 today, first charge on day 14, cancel in one click. Unlocks the full ~2,500-ticker live scanner, smart alerts, congressional trades, and recent insider buys (SEC Form 4). The published record stays free to read with no account.",
  path: "/signup",
});

export default function SignUpLayout({ children }: { children: React.ReactNode }) {
  return children;
}
