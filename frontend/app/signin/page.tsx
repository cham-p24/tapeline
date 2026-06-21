"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { authApi } from "@/lib/auth";
import { errorMessage } from "@/lib/api";
import { safeNext } from "@/lib/safeNext";
import { OAuthButtons } from "@/components/OAuthButtons";
import { useUser } from "@/components/UserContext";

// Outer page wraps the form in Suspense so useSearchParams() doesn't break prerender.
export default function SignInPage() {
  return (
    <Suspense fallback={null}>
      <SignInForm />
    </Suspense>
  );
}

function SignInForm() {
  const router = useRouter();
  const qp = useSearchParams();
  // Sanitize at the source: `next` drives router navigation AND the
  // /signup?next=… link below, so guarding here covers both. Rejects
  // open-redirect payloads (//evil.com, https://evil.com) → safe default.
  const next = safeNext(qp.get("next"));

  const { user, loading: userLoading, refresh } = useUser();

  // 2026-05-20 — Back-button sign-out bug fix (part 2 of 2; the
  // UserContext side is the other half).
  //
  // If the user is already signed in (cookie still valid) and they land
  // on /signin — e.g. by hitting Back after signing in — bounce them to
  // `next` so they don't see the signin form acting as if they're
  // signed out. Without this redirect, the user could re-submit the
  // form and either get "already signed in" 4xx (bad UX) or end up with
  // stale session state.
  useEffect(() => {
    if (!userLoading && user) {
      router.replace(next);
    }
  }, [user, userLoading, next, router]);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // 2FA second step. When the account has TOTP enabled, the password submit
  // returns an mfa_token instead of a session; we then show the code prompt.
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");

  // Shared post-auth handoff: push the new session into UserContext BEFORE
  // navigating, so the destination page mounts already signed-in (and any
  // later back-navigation sees correct state) instead of flashing signed-out.
  async function finishSignin() {
    await refresh();
    router.push(next);
    router.refresh();
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const res = await authApi.signin(email, password);
      if ("mfa_required" in res) {
        // Password was correct but the account needs a 2FA code. Stash the
        // challenge token and switch to the code step; finally{} clears busy.
        setMfaToken(res.mfa_token);
        return;
      }
      await finishSignin();
    } catch (e: unknown) {
      setErr(errorMessage(e) || "Sign in failed");
    } finally {
      setBusy(false);
    }
  }

  async function submitCode(e: React.FormEvent) {
    e.preventDefault();
    if (!mfaToken) return;
    setErr(null);
    setBusy(true);
    try {
      await authApi.signin2fa(mfaToken, mfaCode.trim());
      await finishSignin();
    } catch (e: unknown) {
      setErr(errorMessage(e) || "Verification failed");
    } finally {
      setBusy(false);
    }
  }

  function cancelMfa() {
    setMfaToken(null);
    setMfaCode("");
    setErr(null);
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

          {mfaToken ? (
            <>
              <h1 className="mt-10 text-3xl font-bold tracking-tight">Two-step verification</h1>
              <p className="mt-2 text-sm text-muted">
                Enter the 6-digit code from your authenticator app — or a recovery code.
              </p>

              <form onSubmit={submitCode} className="mt-8 space-y-4">
                <label className="block">
                  <span className="text-xs font-medium text-muted">Authentication code</span>
                  <input
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    autoFocus
                    value={mfaCode}
                    onChange={(e) => setMfaCode(e.target.value)}
                    placeholder="123456"
                    required
                    className="mt-1.5 block h-11 w-full rounded-md border border-border bg-panel px-3 text-center text-lg tracking-[0.4em] nums transition-colors focus:border-accent focus:outline-none"
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
                  {busy ? "Verifying…" : "Verify"}
                </button>
              </form>

              <button
                type="button"
                onClick={cancelMfa}
                className="mt-6 text-sm text-muted underline-offset-4 hover:text-fg hover:underline"
              >
                &larr; Use a different account
              </button>
            </>
          ) : (
            <>
              <h1 className="mt-10 text-3xl font-bold tracking-tight">Welcome back</h1>
              <p className="mt-2 text-sm text-muted">Sign in to your Tapeline account.</p>

              <form onSubmit={submit} className="mt-8 space-y-4">
                <Field label="Email" type="email" autoComplete="email" value={email} onChange={setEmail} required />
                <Field label="Password" type="password" autoComplete="current-password" value={password} onChange={setPassword} required />

                <div className="flex justify-end">
                  <Link href="/forgot-password" className="text-xs text-muted underline-offset-4 hover:text-fg hover:underline">
                    Forgot password?
                  </Link>
                </div>

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
                  {busy ? "Signing in…" : "Sign in"}
                </button>
              </form>

              <OAuthButtons />

              <p className="mt-8 text-center text-sm text-muted">
                Don&rsquo;t have an account?{" "}
                <Link href={`/signup?next=${encodeURIComponent(next)}`} className="link">Sign up free</Link>
              </p>
            </>
          )}
        </div>
      </div>
    </main>
  );
}

function Field({
  label, type, value, onChange, autoComplete, required, minLength,
}: {
  label: string; type: string; value: string; onChange: (v: string) => void;
  autoComplete?: string; required?: boolean; minLength?: number;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-muted">{label}</span>
      <input
        type={type}
        autoComplete={autoComplete}
        required={required}
        minLength={minLength}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1.5 block h-11 w-full rounded-md border border-border bg-panel px-3 text-base transition-colors focus:border-accent focus:outline-none"
      />
    </label>
  );
}
