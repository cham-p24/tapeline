"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { authApi } from "@/lib/auth";
import { OAuthButtons } from "@/components/OAuthButtons";

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
  const next = qp.get("next") || "/app/scanner";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await authApi.signin(email, password);
      router.push(next);
      router.refresh();
    } catch (e: any) {
      setErr(e.message || "Sign in failed");
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

          <h1 className="mt-10 text-3xl font-bold tracking-tight">Welcome back</h1>
          <p className="mt-2 text-sm text-muted">Sign in to your Tapeline account.</p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            <Field label="Email" type="email" autoComplete="email" value={email} onChange={setEmail} required />
            <Field label="Password" type="password" autoComplete="current-password" value={password} onChange={setPassword} required />

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
        className="mt-1.5 block h-10 w-full rounded-md border border-border bg-panel px-3 text-sm transition-colors focus:border-accent focus:outline-none"
      />
    </label>
  );
}
