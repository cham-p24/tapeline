"use client";

/**
 * Reset-password completion. Token comes from ?token=... in the URL
 * (mailed to the user via render_password_reset_email). User picks a
 * new password, we POST it + the token to /api/auth/reset-password.
 *
 * Five backend outcomes are mapped to plain-English UI states.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}

function ResetPasswordForm() {
  const router = useRouter();
  const qp = useSearchParams();
  const token = qp.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (password.length < 8) {
      setErr("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setErr("Passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      const r = await fetch(`${API_BASE}/api/auth/reset-password`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password }),
      });
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail || `${r.status} ${r.statusText}`);
      switch (body.status) {
        case "reset":
          setDone(true);
          break;
        case "expired":
          setErr("This reset link has expired. Request a fresh one.");
          break;
        case "already_used":
          setErr("This reset link has already been used. Request a fresh one.");
          break;
        case "invalid":
          setErr("This reset link is invalid. Request a fresh one.");
          break;
        case "weak_password":
          setErr("Password didn't pass the strength check. Try a longer one.");
          break;
        default:
          setErr("Couldn't reset — try again or request a new link.");
      }
    } catch (e: unknown) {
      setErr(String((e as Error)?.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative min-h-screen">
      <div className="pointer-events-none absolute inset-0 bg-hero opacity-60" />
      <div className="relative flex min-h-screen items-center justify-center px-6 py-10">
        <div className="w-full max-w-sm">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-2 w-6 rounded-full bg-gradient-to-r from-accent to-accent2" />
            <span className="text-lg font-semibold tracking-tight">Tapeline</span>
          </Link>

          {done ? (
            <div className="mt-10">
              <h1 className="text-3xl font-bold tracking-tight text-up">
                Password updated.
              </h1>
              <p className="mt-2 text-sm text-muted">
                You can sign in with your new password now.
              </p>
              <button
                onClick={() => router.push("/signin?next=/app/scanner")}
                className="mt-6 flex h-11 w-full items-center justify-center rounded-md bg-gradient-to-r from-accent to-accent2 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98]"
              >
                Sign in
              </button>
            </div>
          ) : !token ? (
            <div className="mt-10 rounded-lg border border-down/30 bg-down/5 p-5 text-sm">
              <p className="font-semibold text-down">Missing token.</p>
              <p className="mt-2 text-muted">
                This page needs a token in the URL. Use the link in your reset email, or{" "}
                <Link href="/forgot-password" className="link">
                  request a new one
                </Link>
                .
              </p>
            </div>
          ) : (
            <>
              <h1 className="mt-10 text-3xl font-bold tracking-tight">
                Choose a new password
              </h1>
              <p className="mt-2 text-sm text-muted">
                At least 8 characters. You&rsquo;ll be signed out everywhere after the reset.
              </p>

              <form onSubmit={submit} className="mt-8 space-y-4">
                <label className="block">
                  <span className="text-xs font-medium text-muted">New password</span>
                  <input
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="mt-1.5 block h-10 w-full rounded-md border border-border bg-panel px-3 text-sm transition-colors focus:border-accent focus:outline-none"
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-medium text-muted">Confirm password</span>
                  <input
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={8}
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
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
                  {busy ? "Updating…" : "Update password"}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
