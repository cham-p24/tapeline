import { pageMeta } from "@/lib/seo";
import { TRIAL_LENGTH_LABEL } from "@/lib/trial";

// signup/page.tsx is a client component (Turnstile + form state), so the
// metadata lives here. Indexable — brand queries like "tapeline sign up"
// should land here directly.
//
// SAY WHAT THIS FORM DOES, AND NOTHING IT DOES NOT (2026-09-14).
// The title used to read "Create Your Tapeline Account — 30-Day Premium Trial"
// and the description "Create a Tapeline account and start a 30-day Premium
// trial: $0 today, first charge on day 30". Creating an account starts no
// trial and schedules no charge: the row is written tier="free",
// trial_ends_at=None (backend/app/routers/auth.py), and the Premium trial is a
// separate, card-required Stripe Checkout the visitor may choose later. So the
// snippet Google shows and the card a shared link unfurls were both describing
// a step this page never takes.
//
// Kept at or under SERP_DESCRIPTION_MAX so the search snippet and the social
// card carry the same sentence; pageMeta would otherwise clamp only the
// snippet, and a clamp can cut the trial sentence in half. The trial length is
// read from lib/trial.ts, never typed. Guarded by
// __tests__/signupCopyTruth.test.tsx.
export const metadata = pageMeta({
  title: "Create Your Tapeline Account — Free Plan, No Card",
  description: `Sign up with an email and a password, no card, and run the scanner on the free plan. The ${TRIAL_LENGTH_LABEL} Premium trial is a separate step that takes a card.`,
  path: "/signup",
});

export default function SignUpLayout({ children }: { children: React.ReactNode }) {
  return children;
}
