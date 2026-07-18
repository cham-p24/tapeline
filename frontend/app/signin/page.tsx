"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { authApi } from "@/lib/auth";
import { errorMessage } from "@/lib/api";
import { safeNext } from "@/lib/safeNext";
import { OAuthButtons } from "@/components/OAuthButtons";
import { useUser } from "@/components/UserContext";
import {
  FormAlert,
  FormField,
  validateAuthCode,
  validateCurrentPassword,
  validateEmail,
  type FieldError,
} from "@/components/FormField";

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

  // Per-field errors keyed by input id — set on BLUR and on a failed submit,
  // cleared (never raised) while the user types. See components/FormField.tsx.
  const [fieldErrors, setFieldErrors] = useState<Record<string, FieldError>>({});
  const setFieldError = (id: string, msg: FieldError) =>
    setFieldErrors((prev) => ({ ...prev, [id]: msg }));

  // 2FA second step. When the account has TOTP enabled, the password submit
  // returns an mfa_token instead of a session; we then show the code prompt.
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");

  // OAuth → 2FA handoff. Signing in through a provider used to skip TOTP
  // entirely: the callback minted a full session regardless of mfa_enabled,
  // so anyone holding the victim's Google account walked straight past their
  // authenticator. routers/oauth.py now mints NO session for an MFA-enabled
  // account — it redirects here with ?mfa=1 and leaves the 5-minute challenge
  // in a readable `tapeline_mfa_challenge` cookie (kept out of the URL so the
  // token never lands in browser history, Referer headers or CDN logs).
  // Pick it up and drop into the same code step the password flow uses.
  const mfaHandoff = qp.get("mfa") === "1";
  useEffect(() => {
    if (!mfaHandoff) return;
    const hit = document.cookie
      .split("; ")
      .find((c) => c.startsWith("tapeline_mfa_challenge="));
    if (!hit) {
      // Cookie already expired, or blocked. Don't strand them on a form that
      // looks like the provider button silently failed — say what happened.
      setErr(
        "That sign-in took too long to confirm. Sign in again to get a new code prompt.",
      );
      return;
    }
    setMfaToken(decodeURIComponent(hit.split("=").slice(1).join("=")));
    // Burn it — a challenge shouldn't outlive the handoff. Cleared against
    // both the host and the registrable domain, because the cookie is set
    // with a domain so it spans the apex and the api subdomain in prod.
    const host = window.location.hostname;
    const parts = host.split(".");
    const registrable = parts.length > 2 ? parts.slice(-2).join(".") : host;
    document.cookie = "tapeline_mfa_challenge=; Max-Age=0; path=/";
    document.cookie = `tapeline_mfa_challenge=; Max-Age=0; path=/; domain=.${registrable}`;
  }, [mfaHandoff]);

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

    // Catch the empty/malformed cases here rather than spending a round-trip
    // to have the backend answer "incorrect email or password" — which would
    // wrongly imply the credentials were wrong when the email was simply
    // mistyped. Neither branch clears the inputs.
    const nextErrors: Record<string, FieldError> = {
      "signin-email": validateEmail(email),
      "signin-password": validateCurrentPassword(password),
    };
    setFieldErrors(nextErrors);
    const invalid = Object.keys(nextErrors).filter((id) => nextErrors[id]);
    if (invalid.length > 0) {
      setErr(
        invalid.length === 1
          ? "One field needs fixing before we can sign you in — the details are next to it below."
          : `${invalid.length} fields need fixing before we can sign you in — the details are next to each one below.`,
      );
      document.getElementById(invalid[0])?.focus();
      return;
    }

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
    const codeErr = validateAuthCode(mfaCode);
    if (codeErr) {
      setFieldError("signin-mfa-code", codeErr);
      document.getElementById("signin-mfa-code")?.focus();
      return;
    }
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
    setFieldErrors({});
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

          {mfaToken ? (
            <>
              <h1 className="mt-10 text-3xl font-bold tracking-tight">Two-step verification</h1>
              <p className="mt-2 text-sm text-muted">
                Enter the 6-digit code from your authenticator app — or a recovery code.
              </p>

              <form onSubmit={submitCode} noValidate className="mt-8 space-y-4">
                <FormField
                  id="signin-mfa-code"
                  label="Authentication code"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  autoFocus
                  value={mfaCode}
                  onChange={(v) => { setMfaCode(v); setFieldError("signin-mfa-code", null); }}
                  onBlur={() => setFieldError("signin-mfa-code", validateAuthCode(mfaCode))}
                  error={fieldErrors["signin-mfa-code"]}
                  placeholder="123456"
                  required
                  inputClassName="text-center text-lg tracking-[0.4em] nums"
                />

                <FormAlert message={err} />

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

              {/* PRIMARY sign-in path: Google-first, above the email form — the
                  same prominence flip as /signup. Most returning visitors are
                  already logged into Google, so one click beats retyping a
                  password. OAuthButtons feature-detects providers and renders
                  nothing when none are enabled; when that happens this block
                  collapses and the email form below becomes primary with no
                  orphaned divider. next carries the post-auth destination so a
                  visitor mid-flow (e.g. from a /pricing plan CTA) keeps context
                  through Google sign-in. */}
              <div className="mt-6">
                <OAuthButtons
                  position="top"
                  variant="primary"
                  dividerLabel="or sign in with email"
                  postAuthNext={next}
                />
              </div>

              {/* noValidate — see the same note on /signup: we own the
                  messages, so the browser's generic constraint bubbles must
                  not preempt them. */}
              <form onSubmit={submit} noValidate className="mt-6 space-y-4">
                <FormField
                  id="signin-email"
                  label="Email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(v) => { setEmail(v); setFieldError("signin-email", null); }}
                  onBlur={() => setFieldError("signin-email", validateEmail(email))}
                  error={fieldErrors["signin-email"]}
                  required
                />
                <FormField
                  id="signin-password"
                  label="Password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(v) => { setPassword(v); setFieldError("signin-password", null); }}
                  onBlur={() => setFieldError("signin-password", validateCurrentPassword(password))}
                  error={fieldErrors["signin-password"]}
                  required
                />

                <div className="flex justify-end">
                  <Link href="/forgot-password" className="text-xs text-muted underline-offset-4 hover:text-fg hover:underline">
                    Forgot password?
                  </Link>
                </div>

                <FormAlert message={err} />

                <button
                  type="submit"
                  disabled={busy}
                  className="flex h-11 w-full items-center justify-center rounded-md bg-gradient-to-r from-accent to-accent2 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-50"
                >
                  {busy ? "Signing in…" : "Sign in"}
                </button>
              </form>

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
