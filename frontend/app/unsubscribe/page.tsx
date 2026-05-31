"use client";

/**
 * Public unsubscribe confirmation page.
 *
 * Reached two ways:
 *   1. User clicks the "Unsubscribe" link inside an email footer (GET)
 *   2. Gmail / Outlook one-click POSTs to /api/unsubscribe directly,
 *      then redirects the user here — same UX either way
 *
 * On mount we hit the API with the token from the URL and render the
 * outcome. Friendly + brief — no hard sell to come back.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

type Status = "loading" | "ok" | "invalid";
type Body = { status: string; changed?: boolean; category?: string };

const CATEGORY_LABEL: Record<string, string> = {
  all: "all Tapeline emails",
  trial_drip: "trial reminder emails",
  re_engagement: "the come-back email",
  daily_digest: "the end-of-day digest",
  alert_emails: "alert emails",
  weekly_newsletter: "the weekly market digest",
};

export default function UnsubscribePage() {
  return (
    <Suspense fallback={null}>
      <UnsubscribeInner />
    </Suspense>
  );
}

function UnsubscribeInner() {
  const qp = useSearchParams();
  const token = qp.get("token") || "";
  const [status, setStatus] = useState<Status>("loading");
  const [body, setBody] = useState<Body | null>(null);

  useEffect(() => {
    if (!token) {
      setStatus("invalid");
      return;
    }
    fetch(`${API_BASE}/api/unsubscribe?token=${encodeURIComponent(token)}`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (r) => {
        const b = await r.json();
        setBody(b);
        setStatus(b.status === "ok" ? "ok" : "invalid");
      })
      .catch(() => setStatus("invalid"));
  }, [token]);

  const label = body?.category ? CATEGORY_LABEL[body.category] || body.category : "this email";

  return (
    <main className="relative min-h-screen">
      <div className="pointer-events-none absolute inset-0 bg-hero opacity-60" />
      <div className="relative flex min-h-screen items-center justify-center px-6 py-10">
        <div className="w-full max-w-md">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-2 w-6 rounded-full bg-gradient-to-r from-accent to-accent2" />
            <span className="text-lg font-semibold tracking-tight">Tapeline</span>
          </Link>

          <div className="mt-10 rounded-lg border border-border bg-panel p-6">
            {status === "loading" && (
              <>
                <h1 className="text-xl font-semibold tracking-tight">Unsubscribing…</h1>
                <p className="mt-2 text-sm text-muted">One moment.</p>
              </>
            )}

            {status === "ok" && (
              <>
                <h1 className="text-xl font-semibold tracking-tight text-up">
                  You&rsquo;re unsubscribed.
                </h1>
                <p className="mt-2 text-sm text-muted">
                  We&rsquo;ve {body?.changed ? "removed you from" : "confirmed you&rsquo;re not on"} {label}. Account-state emails (sign-up confirmation, payment receipts) still go through — those aren&rsquo;t marketing.
                </p>
                <p className="mt-4 text-sm text-muted">
                  Change your mind?{" "}
                  <Link href="/app/settings/email" className="link">
                    Email preferences
                  </Link>{" "}
                  has every toggle.
                </p>
              </>
            )}

            {status === "invalid" && (
              <>
                <h1 className="text-xl font-semibold tracking-tight text-down">
                  Couldn&rsquo;t process that link.
                </h1>
                <p className="mt-2 text-sm text-muted">
                  The token is missing or invalid. If you&rsquo;re trying to unsubscribe, sign in and use{" "}
                  <Link href="/app/settings/email" className="link">
                    Email preferences
                  </Link>{" "}
                  instead — or email{" "}
                  <a href="mailto:support@tapeline.io" className="link">
                    support@tapeline.io
                  </a>
                  .
                </p>
              </>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
