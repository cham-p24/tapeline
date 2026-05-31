"use client";

/**
 * Persistent banner shown at the top of every /app/* page when the
 * signed-in user's `email_verified_at` is null. Provides a one-click
 * "Resend verification" button hitting POST /api/auth/resend-verification.
 *
 * Why this matters: we send a verification email at signup, but if the
 * user misses it or the link expires (24h TTL), there's no in-app
 * affordance to recover. Without this banner the only path was emailing
 * support. With it, recovery is two clicks.
 *
 * Hidden states (returns null):
 *   - no user logged in (the layout's other banners handle anonymous nav)
 *   - user already verified
 *   - user is an OAuth-only account (always auto-verified — defensive guard)
 *   - user dismissed it this session (sessionStorage flag)
 *
 * Dismissing is per-session, not per-user-persistent. That's intentional:
 * if a user dismisses the nudge, we don't want to lose them forever, but
 * we also don't want to spam them every page load.
 */

import { useEffect, useState } from "react";
import { useUser } from "@/components/UserContext";
import { handle401 } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
const DISMISS_KEY = "tapeline_verify_banner_dismissed";

type ResendState = "idle" | "sending" | "sent" | "already_verified" | "error";

export function EmailVerificationBanner() {
  const { user, loading, refresh } = useUser();
  const [dismissed, setDismissed] = useState(false);
  const [state, setState] = useState<ResendState>("idle");

  // Read the dismiss flag once after mount — sessionStorage isn't available
  // during SSR.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      setDismissed(sessionStorage.getItem(DISMISS_KEY) === "1");
    } catch {
      // sessionStorage can throw in privacy mode — treat as not dismissed.
    }
  }, []);

  if (loading || !user) return null;
  if (user.email_verified_at) return null;
  if (dismissed) return null;

  async function resend() {
    setState("sending");
    try {
      const r = await fetch(`${API_BASE}/api/auth/resend-verification`, {
        method: "POST",
        credentials: "include",
      });
      if (!r.ok) {
        handle401(r.status);
        throw new Error(`${r.status} ${r.statusText}`);
      }
      const body = await r.json();
      if (body.status === "already_verified") {
        setState("already_verified");
        await refresh();
      } else {
        setState("sent");
      }
    } catch {
      setState("error");
    }
  }

  function dismiss() {
    setDismissed(true);
    try {
      sessionStorage.setItem(DISMISS_KEY, "1");
    } catch {
      // best-effort
    }
  }

  // Compose the right-hand action text based on resend state. We keep the
  // banner in place after success so the user has visible confirmation —
  // they can dismiss when they're ready.
  let actionNode: React.ReactNode;
  if (state === "sent") {
    actionNode = (
      <span className="text-xs text-up">
        ✓ Sent — check {user.email}
      </span>
    );
  } else if (state === "already_verified") {
    actionNode = <span className="text-xs text-up">✓ You&rsquo;re already verified.</span>;
  } else if (state === "error") {
    actionNode = (
      <button
        onClick={resend}
        className="rounded-md bg-down/10 px-3 py-1 text-xs font-medium text-down hover:bg-down/20"
      >
        Try again
      </button>
    );
  } else {
    actionNode = (
      <button
        onClick={resend}
        disabled={state === "sending"}
        className="rounded-md bg-accent/10 px-3 py-1 text-xs font-medium text-accent hover:bg-accent/20 disabled:opacity-50"
      >
        {state === "sending" ? "Sending…" : "Resend verification"}
      </button>
    );
  }

  return (
    <div
      role="status"
      className="mb-4 flex items-center justify-between gap-3 rounded-md border border-accent/30 bg-accent/5 px-4 py-2.5 text-sm"
    >
      <div className="flex min-w-0 items-center gap-2 text-fg">
        <span aria-hidden="true">📬</span>
        <span className="truncate">
          <strong className="font-semibold">Verify your email.</strong>{" "}
          <span className="text-muted">
            We sent a confirmation link to <span className="font-medium text-fg">{user.email}</span>.
            Click it to secure your account.
          </span>
        </span>
      </div>
      <div className="flex flex-shrink-0 items-center gap-2">
        {actionNode}
        <button
          onClick={dismiss}
          aria-label="Dismiss"
          className="rounded p-1 text-muted hover:bg-fg/5 hover:text-fg"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
            <path
              d="M3 3l8 8M11 3l-8 8"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
