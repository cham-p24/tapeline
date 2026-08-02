import { notFound } from "next/navigation";
import { TrialWelcomePreview } from "./preview-client";

// Guarded verification route for the welcome card + trial nudge copy. Available
// on local dev and Vercel PREVIEW deployments only; 404s on any production
// build — Vercel prod (VERCEL_ENV === "production") and the Fly.io frontend
// prod (NODE_ENV === "production", no VERCEL_ENV) both fail the allow check.
export const dynamic = "force-static";

export default function Page() {
  const allowed =
    process.env.VERCEL_ENV === "preview" || process.env.NODE_ENV !== "production";
  if (!allowed) notFound();
  return <TrialWelcomePreview />;
}
