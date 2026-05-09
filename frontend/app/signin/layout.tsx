import { pageMeta } from "@/lib/seo";

// signin/page.tsx is a client component, so metadata lives in this layout.
// We index this page (vs noindex) so brand queries like "tapeline signin"
// and "tapeline login" land users on the right URL.
export const metadata = pageMeta({
  title: "Sign In — Tapeline",
  description:
    "Sign in to your Tapeline account to access the live quantitative stock scanner, watchlists, and alerts.",
  path: "/signin",
});

export default function SignInLayout({ children }: { children: React.ReactNode }) {
  return children;
}
