"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { authApi } from "@/lib/auth";
import { OAuthButtons } from "@/components/OAuthButtons";

const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "";

declare global {
  interface Window {
    onTapelineTurnstile?: (token: string) => void;
  }
}

export default function SignUpPage() {
  const router = useRouter();
  const qp = useSearchParams();
  const next = qp.get("next") || "/app/scanner";

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  // Honeypot — bots fill this, humans never see it. Submitted as `company`.
  const [honeypot, setHoneypot] = useState("");
  // Turnstile token — populated by Cloudflare's widget callback. Empty until solved.
  const [turnstileToken, setTurnstileToken] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const turnstileRef = useRef<HTMLDivElement | null>(null);

  // Bridge Cloudflare's data-callback into React state. The widget calls
  // window.onTapelineTurnstile(token) when the user solves the challenge.
  useEffect(() => {
    if (!TURNSTILE_SITE_KEY) return;
    window.onTapelineTurnstile = (token: string) => setTurnstileToken(token);
    return () => { delete window.onTapelineTurnstile; };
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (password.length < 8) { setErr("Password must be at least 8 characters."); return; }
    if (TURNSTILE_SITE_KEY && !turnstileToken) {
      setErr("Please complete the bot check above.");
      return;
    }
    setBusy(true);
    try {
      await authApi.signup(email, password, name, {
        company: honeypot,
        turnstile_token: turnstileToken || undefined,
      });
      router.push(next);
      router.refresh();
    } catch (e: any) {
      setErr(e.message || "Sign up failed");
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

          <h1 className="mt-10 text-3xl font-bold tracking-tight">Start 14-day Pro trial</h1>
          <p className="mt-2 text-sm text-muted">No credit card. Cancel anytime.</p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            {/* Honeypot field — offscreen, hidden from real users (and screen readers).
                Bots that auto-fill every input will populate it; if non-empty, the
                backend silently rejects the signup. */}
            <input
              type="text"
              name="company"
              value={honeypot}
              onChange={(e) => setHoneypot(e.target.value)}
              tabIndex={-1}
              autoComplete="off"
              aria-hidden="true"
              className="absolute left-[-9999px] top-[-9999px] h-0 w-0 opacity-0"
            />

            <Field label="Name" type="text" autoComplete="name" value={name} onChange={setName} />
            <Field label="Email" type="email" autoComplete="email" value={email} onChange={setEmail} required />
            <Field label="Password" type="password" autoComplete="new-password" value={password} onChange={setPassword} required minLength={8} hint="At least 8 characters" />

            {/* Cloudflare Turnstile widget — auto-rendered by the script tag in
                root layout. data-callback names a window function that receives
                the token. Hidden entirely if no site key is configured. */}
            {TURNSTILE_SITE_KEY && (
              <div
                ref={turnstileRef}
                className="cf-turnstile"
                data-sitekey={TURNSTILE_SITE_KEY}
                data-callback="onTapelineTurnstile"
                data-theme="dark"
              />
            )}

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
              {busy ? "Creating account…" : "Create account"}
            </button>

            <p className="text-xs text-subtle">
              By signing up you agree to our{" "}
              <Link href="/legal/terms" className="link">Terms</Link>{" "}and{" "}
              <Link href="/legal/privacy" className="link">Privacy Policy</Link>.
            </p>
          </form>

          <OAuthButtons />

          <p className="mt-8 text-center text-sm text-muted">
            Already have an account?{" "}
            <Link href={`/signin?next=${encodeURIComponent(next)}`} className="link">Sign in</Link>
          </p>
        </div>
      </div>
    </main>
  );
}

function Field({
  label, type, value, onChange, autoComplete, required, minLength, hint,
}: {
  label: string; type: string; value: string; onChange: (v: string) => void;
  autoComplete?: string; required?: boolean; minLength?: number; hint?: string;
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
        className="mt-1.5 block h-10 w-full rounded-md border border-border bg-panel px-3 text-sm transition-colors focus:border-accent focus:outline-none"
      />
      {hint && <span className="mt-1 block text-xs text-subtle">{hint}</span>}
    </label>
  );
}
