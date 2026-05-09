import { pageMeta } from "@/lib/seo";

// signup/page.tsx is a client component (Turnstile + form state), so the
// metadata lives here. Indexable — brand queries like "tapeline sign up"
// and "tapeline free trial" should land here directly.
export const metadata = pageMeta({
  title: "Start Your Free Tapeline Trial — 14-Day Premium, No Credit Card",
  description:
    "Create a free Tapeline account. 14-day Premium trial unlocks the full ~2,500-ticker live scanner, smart alerts, congressional trades, and elite 13F holdings. No credit card required, cancel in one click.",
  path: "/signup",
});

export default function SignUpLayout({ children }: { children: React.ReactNode }) {
  return children;
}
