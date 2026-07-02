"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

type Providers = { google: boolean; microsoft: boolean; apple: boolean };
const NONE: Providers = { google: false, microsoft: false, apple: false };

type Position = "top" | "bottom";

export function OAuthButtons({
  position = "bottom",
  dividerLabel,
  postAuthNext,
}: {
  position?: Position;
  dividerLabel?: string;
  /**
   * Post-auth intent (same shape as the email flow's `postAuthNext` in
   * signup/page.tsx — an internal path like "/app/billing?intent=premium").
   * Appended to the /start URL as `?next=`; the backend validates it as a
   * same-origin relative path (mirroring lib/safeNext.ts), stashes it in a
   * short-lived cookie across the provider round-trip, and redirects there
   * after auth. Without this, plan intent from /pricing died at the OAuth
   * buttons while surviving the email form.
   */
  postAuthNext?: string;
} = {}) {
  const [providers, setProviders] = useState<Providers | null>(null);

  const startHref = (provider: "google" | "microsoft" | "apple") =>
    `${API_BASE}/api/auth/oauth/${provider}/start` +
    (postAuthNext ? `?next=${encodeURIComponent(postAuthNext)}` : "");

  useEffect(() => {
    fetch(`${API_BASE}/api/auth/oauth/providers`, { credentials: "include", cache: "no-store" })
      .then((r) => r.ok ? r.json() : NONE)
      .then((p) => setProviders({ google: !!p.google, microsoft: !!p.microsoft, apple: !!p.apple }))
      .catch(() => setProviders(NONE));
  }, []);

  if (!providers) return null;
  if (!providers.google && !providers.microsoft && !providers.apple) return null;

  // When rendered above the email form ("top"), the divider sits below the
  // OAuth buttons and reads "or sign up with email" by default. When rendered
  // below ("bottom" — the signin flow), the divider sits above and reads
  // "or continue with".
  const divider = (
    <div className="my-6 flex items-center gap-3 text-xs text-muted">
      <div className="h-px flex-1 bg-border" />
      <span>{dividerLabel ?? (position === "top" ? "or sign up with email" : "or continue with")}</span>
      <div className="h-px flex-1 bg-border" />
    </div>
  );

  const buttons = (
    <div className="grid gap-2">
      {providers.google && (
        <a
          href={startHref("google")}
          className="flex items-center justify-center gap-3 rounded-md border border-border bg-panel px-4 py-2 text-sm font-medium hover:bg-panel-hover"
        >
          <GoogleGlyph /> Continue with Google
        </a>
      )}
      {providers.microsoft && (
        <a
          href={startHref("microsoft")}
          className="flex items-center justify-center gap-3 rounded-md border border-border bg-panel px-4 py-2 text-sm font-medium hover:bg-panel-hover"
        >
          <MicrosoftGlyph /> Continue with Microsoft
        </a>
      )}
      {providers.apple && (
        <a
          href={startHref("apple")}
          className="flex items-center justify-center gap-3 rounded-md border border-border bg-black px-4 py-2 text-sm font-medium text-white hover:bg-black/80"
        >
          <AppleGlyph /> Continue with Apple
        </a>
      )}
    </div>
  );

  return position === "top" ? (
    <>
      {buttons}
      {divider}
    </>
  ) : (
    <>
      {divider}
      {buttons}
    </>
  );
}

function GoogleGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.7 1.22 9.2 3.6l6.9-6.9C35.9 2.38 30.48 0 24 0 14.62 0 6.51 5.38 2.56 13.22l8.04 6.24C12.51 13.72 17.74 9.5 24 9.5z"/>
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
      <path fill="#FBBC05" d="M10.6 28.55c-.4-1.2-.62-2.47-.62-3.78s.22-2.58.62-3.78l-8.04-6.24C1.05 18.1 0 20.93 0 24.77s1.05 6.66 2.56 10.02l8.04-6.24z"/>
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.14 15.9-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.17 2.3-6.26 0-11.49-4.22-13.38-9.96l-8.04 6.24C6.51 42.62 14.62 48 24 48z"/>
    </svg>
  );
}

function MicrosoftGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 23 23" aria-hidden="true">
      <rect x="1" y="1" width="10" height="10" fill="#f25022"/>
      <rect x="12" y="1" width="10" height="10" fill="#7fba00"/>
      <rect x="1" y="12" width="10" height="10" fill="#00a4ef"/>
      <rect x="12" y="12" width="10" height="10" fill="#ffb900"/>
    </svg>
  );
}

function AppleGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09l.01-.01zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z"/>
    </svg>
  );
}
