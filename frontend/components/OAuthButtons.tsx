"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export function OAuthButtons() {
  const [providers, setProviders] = useState<{ google: boolean; microsoft: boolean } | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/auth/oauth/providers`, { credentials: "include", cache: "no-store" })
      .then((r) => r.ok ? r.json() : { google: false, microsoft: false })
      .then(setProviders)
      .catch(() => setProviders({ google: false, microsoft: false }));
  }, []);

  if (!providers) return null;
  if (!providers.google && !providers.microsoft) return null;

  return (
    <>
      <div className="my-6 flex items-center gap-3 text-xs text-muted">
        <div className="h-px flex-1 bg-border" />
        <span>or continue with</span>
        <div className="h-px flex-1 bg-border" />
      </div>
      <div className="grid gap-2">
        {providers.google && (
          <a
            href={`${API_BASE}/api/auth/oauth/google/start`}
            className="flex items-center justify-center gap-3 rounded-md border border-border bg-panel px-4 py-2 text-sm font-medium hover:bg-black/30"
          >
            <GoogleGlyph /> Continue with Google
          </a>
        )}
        {providers.microsoft && (
          <a
            href={`${API_BASE}/api/auth/oauth/microsoft/start`}
            className="flex items-center justify-center gap-3 rounded-md border border-border bg-panel px-4 py-2 text-sm font-medium hover:bg-black/30"
          >
            <MicrosoftGlyph /> Continue with Microsoft
          </a>
        )}
      </div>
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
