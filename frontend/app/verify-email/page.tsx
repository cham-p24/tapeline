"use client";

/**
 * Public landing page that the email-verification + "this wasn't me"
 * links in our verification email point at.
 *
 * On mount, parses ?token=... and ?action=verify|cancel from the URL,
 * POSTs to /api/auth/verify-email, and renders one of five outcome
 * states (verified / cancelled / already_verified / expired / invalid).
 * No auth required — the token IS the proof of ownership.
 *
 * UX is intentionally calm: this is a routine confirmation, not a
 * marketing surface. Single CTA per outcome state.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

type Status =
  | "loading"
  | "verified"
  | "cancelled"
  | "already_verified"
  | "expired"
  | "invalid"
  | "error";

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailInner />
    </Suspense>
  );
}

function VerifyEmailInner() {
  const router = useRouter();
  const qp = useSearchParams();
  const token = qp.get("token") || "";
  const action = (qp.get("action") || "verify") as "verify" | "cancel";
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    if (!token) {
      setStatus("invalid");
      return;
    }
    fetch(`${API_BASE}/api/auth/verify-email`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, action }),
    })
      .then(async (r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        const body = await r.json();
        setStatus((body.status as Status) || "error");
      })
      .catch(() => setStatus("error"));
  }, [token, action]);

  return (
    <main id="main" className="relative min-h-screen">
      <div className="pointer-events-none absolute inset-0 bg-hero opacity-60" />
      <div className="relative flex min-h-screen items-center justify-center px-6 py-10">
        <div className="w-full max-w-md">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-2 w-6 rounded-full bg-gradient-to-r from-accent to-accent2" />
            <span className="text-lg font-semibold tracking-tight">Tapeline</span>
          </Link>

          <div className="mt-10 rounded-lg border border-border bg-panel p-6">
            <Outcome status={status} action={action} router={router} />
          </div>

          <p className="mt-6 text-center text-xs text-subtle">
            Need help? Email{" "}
            <a href="mailto:support@tapeline.io" className="link">
              support@tapeline.io
            </a>
            .
          </p>
        </div>
      </div>
    </main>
  );
}

function Outcome({
  status,
  action,
  router,
}: {
  status: Status;
  action: "verify" | "cancel";
  router: ReturnType<typeof useRouter>;
}) {
  if (status === "loading") {
    return (
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Checking your link…</h1>
        <p className="mt-2 text-sm text-muted">One moment.</p>
      </div>
    );
  }

  if (status === "verified") {
    return (
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-up">
          Email confirmed.
        </h1>
        <p className="mt-2 text-sm text-muted">
          Thanks — your Tapeline account is now verified. You can head straight to the scanner.
        </p>
        <button
          onClick={() => router.push("/app/scanner")}
          className="mt-6 flex h-10 w-full items-center justify-center rounded-md bg-gradient-to-r from-accent to-accent2 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98]"
        >
          Open the scanner
        </button>
      </div>
    );
  }

  if (status === "already_verified") {
    return (
      <div>
        <h1 className="text-xl font-semibold tracking-tight">
          Already verified.
        </h1>
        <p className="mt-2 text-sm text-muted">
          This link has already been used. Your account is confirmed — nothing more to do.
        </p>
        <button
          onClick={() => router.push("/app/scanner")}
          className="mt-6 flex h-10 w-full items-center justify-center rounded-md bg-gradient-to-r from-accent to-accent2 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98]"
        >
          Open the scanner
        </button>
      </div>
    );
  }

  if (status === "cancelled") {
    return (
      <div>
        <h1 className="text-xl font-semibold tracking-tight">
          Account removed.
        </h1>
        <p className="mt-2 text-sm text-muted">
          Sorry about that — someone tried to sign up for Tapeline with your email by mistake. The account has been deleted and you won&rsquo;t hear from us again unless you sign up yourself.
        </p>
        <Link
          href="/"
          className="mt-6 flex h-10 w-full items-center justify-center rounded-md border border-border bg-bg text-sm font-medium text-muted transition-colors hover:text-fg"
        >
          Back to tapeline.io
        </Link>
      </div>
    );
  }

  if (status === "expired") {
    return (
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Link expired.</h1>
        <p className="mt-2 text-sm text-muted">
          Verification links are good for 24 hours. Sign in and we&rsquo;ll send you a fresh one from the &ldquo;Resend verification&rdquo; button.
        </p>
        <button
          onClick={() => router.push("/signin?next=/app/scanner")}
          className="mt-6 flex h-10 w-full items-center justify-center rounded-md bg-gradient-to-r from-accent to-accent2 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98]"
        >
          Sign in
        </button>
      </div>
    );
  }

  // invalid OR error
  return (
    <div>
      <h1 className="text-xl font-semibold tracking-tight text-down">
        We couldn&rsquo;t process that link.
      </h1>
      <p className="mt-2 text-sm text-muted">
        The token is missing, malformed, or has been removed. If you&rsquo;ve already signed up, sign in and resend the verification email.
      </p>
      <button
        onClick={() => router.push("/signin?next=/app/scanner")}
        className="mt-6 flex h-10 w-full items-center justify-center rounded-md bg-gradient-to-r from-accent to-accent2 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98]"
      >
        Sign in
      </button>
      {action === "cancel" && (
        <p className="mt-4 text-xs text-subtle">
          If you were trying to report that this wasn&rsquo;t you, please email{" "}
          <a href="mailto:support@tapeline.io" className="link">
            support@tapeline.io
          </a>{" "}
          and we&rsquo;ll handle it manually.
        </p>
      )}
    </div>
  );
}
