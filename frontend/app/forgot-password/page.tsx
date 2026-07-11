"use client";

/**
 * Forgot-password initiation. User enters their email, we POST to
 * /api/auth/forgot-password which always returns 200 (no account
 * enumeration). UI says "if an account exists, a reset link is on its
 * way" — matches the security posture of the backend.
 */

import Link from "next/link";
import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const r = await fetch(`${API_BASE}/api/auth/forgot-password`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      setSubmitted(true);
    } catch (e: unknown) {
      setErr(String((e as Error)?.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main" className="relative min-h-screen">
      <div className="pointer-events-none absolute inset-0 bg-hero opacity-60" />
      <div className="relative flex min-h-screen items-center justify-center px-6 py-10">
        <div className="w-full max-w-sm">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-2 w-6 rounded-full bg-gradient-to-r from-accent to-accent2" />
            <span className="text-lg font-semibold tracking-tight">Tapeline</span>
          </Link>

          <h1 className="mt-10 text-3xl font-bold tracking-tight">
            Reset your password
          </h1>
          <p className="mt-2 text-sm text-muted">
            Enter your email — we&rsquo;ll send a reset link valid for 60 minutes.
          </p>

          {submitted ? (
            <div className="mt-8 rounded-lg border border-up/30 bg-up/5 p-5 text-sm">
              <p className="font-semibold text-up">Check your inbox.</p>
              <p className="mt-2 text-muted">
                If an account exists for <strong>{email}</strong>, a reset link is on the way. The link is good for 60 minutes; you can request another from this page if it expires.
              </p>
              <Link
                href="/signin"
                className="mt-4 inline-flex h-9 items-center text-sm font-medium text-accent underline-offset-4 hover:underline"
              >
                Back to sign in &rarr;
              </Link>
            </div>
          ) : (
            <form onSubmit={submit} className="mt-8 space-y-4">
              <label className="block">
                <span className="text-xs font-medium text-muted">Email</span>
                <input
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="mt-1.5 block h-10 w-full rounded-md border border-border bg-panel px-3 text-sm transition-colors focus:border-accent focus:outline-none"
                />
              </label>

              {err && (
                <div className="rounded-md border border-down/30 bg-down/5 p-3 text-sm text-down">
                  {err}
                </div>
              )}

              <button
                type="submit"
                disabled={busy}
                className="flex h-11 w-full items-center justify-center rounded-md bg-gradient-to-r from-accent to-accent2 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-50"
              >
                {busy ? "Sending…" : "Send reset link"}
              </button>

              <p className="text-center text-xs text-subtle">
                Remember your password?{" "}
                <Link href="/signin" className="link">
                  Sign in
                </Link>
              </p>
            </form>
          )}
        </div>
      </div>
    </main>
  );
}
