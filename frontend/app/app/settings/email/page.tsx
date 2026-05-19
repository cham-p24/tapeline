"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type EmailPrefKey, type EmailPrefsResponse } from "@/lib/api";

/**
 * Per-user email preferences.
 *
 * Lets the user toggle which non-transactional email categories they
 * receive. Categories + descriptions come from the API so the backend
 * stays the source of truth for the list — no UI/backend drift.
 *
 * Transactional emails (welcome, payment-failed, referral confirmations)
 * aren't shown here because they're not user-suppressable; we mention
 * that in the footer copy so the user isn't surprised.
 */
export default function EmailSettingsPage() {
  const [state, setState] = useState<EmailPrefsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<EmailPrefKey | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  useEffect(() => {
    api
      .emailPrefsGet()
      .then(setState)
      .catch((e: unknown) => {
        const m = String((e as Error)?.message || e);
        if (m.includes("401")) {
          window.location.href = `/signin?next=${encodeURIComponent("/app/settings/email")}`;
          return;
        }
        setError(m);
      });
  }, []);

  async function toggle(key: EmailPrefKey, next: boolean) {
    if (!state) return;
    setPending(key);
    setError(null);
    // Optimistic: update local state immediately so the UI feels snappy.
    // Revert if the request fails.
    const prev = { ...state.prefs };
    setState({ ...state, prefs: { ...state.prefs, [key]: next } });
    try {
      const res = await api.emailPrefsPatch({ [key]: next });
      setState({ ...state, prefs: res.prefs });
      setSavedAt(Date.now());
    } catch (e: unknown) {
      const m = String((e as Error)?.message || e);
      if (m.includes("401")) {
        window.location.href = `/signin?next=${encodeURIComponent("/app/settings/email")}`;
        return;
      }
      // Roll back
      setState({ ...state, prefs: prev });
      setError(m);
    } finally {
      setPending(null);
    }
  }

  if (error && !state)
    return (
      <div className="card p-6 text-sm text-down">
        Couldn&rsquo;t load your email preferences: {error}
      </div>
    );
  if (!state)
    return <div className="card p-6 text-sm text-muted">Loading…</div>;

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <p className="eyebrow text-muted">Settings</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Email preferences</h1>
        <p className="mt-2 text-sm text-muted">
          Granular control over which non-transactional emails you get. Toggles
          save automatically. You can also reach this page from the &ldquo;Manage
          email prefs&rdquo; link in any Tapeline email.
        </p>
      </div>

      <div className="card divide-y divide-border">
        {state.categories.map((cat) => {
          const checked = state.prefs[cat.key] ?? true;
          const isPending = pending === cat.key;
          return (
            <div key={cat.key} className="flex items-start justify-between gap-4 p-5">
              <div className="min-w-0">
                <div className="font-semibold">{cat.label}</div>
                <p className="mt-1 text-sm text-muted">{cat.description}</p>
              </div>
              <button
                onClick={() => toggle(cat.key, !checked)}
                disabled={isPending}
                role="switch"
                aria-checked={checked}
                aria-label={`Toggle ${cat.label}`}
                className={`relative h-6 w-11 flex-shrink-0 rounded-full transition-colors ${
                  checked ? "bg-accent" : "bg-border"
                } ${isPending ? "opacity-50" : ""}`}
              >
                <span
                  className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${
                    checked ? "translate-x-5" : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>
          );
        })}
      </div>

      {savedAt && (
        <p className="mt-3 text-xs text-up">✓ Saved.</p>
      )}
      {error && (
        <p className="mt-3 text-xs text-down">Couldn&rsquo;t save: {error}</p>
      )}

      <div className="mt-8 rounded-md border border-border bg-panel p-4 text-sm text-muted">
        <strong className="text-fg">A note on transactional emails.</strong>{" "}
        Three types of email don&rsquo;t appear above and aren&rsquo;t
        opt-out-able: the <strong>welcome email</strong> when you sign up, the
        <strong> payment-failed notice</strong> if a card charge fails, and any{" "}
        <strong>referral credit confirmations</strong>. These are account-state
        notifications, not marketing — you&rsquo;d need them to know your
        account is working.
      </div>

      <div className="mt-6 text-sm">
        <Link href="/app/account" className="link">&larr; Back to account</Link>
      </div>
    </div>
  );
}
