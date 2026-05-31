"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, errorMessage } from "@/lib/api";
import { CardSkeleton } from "@/components/Skeleton";

/**
 * Account security — two-factor authentication (TOTP).
 *
 * Three sub-flows in one page:
 *   1. Status load            → enabled? show "on" + Disable; else show Enable.
 *   2. Enable (3 steps)       → setup (QR + secret) → verify code → recovery
 *                               codes shown once.
 *   3. Disable                → re-auth with password, then clear.
 *
 * QR is rendered server-side as inline SVG (services/mfa.qr_svg) so we don't
 * pull a QR library into the bundle — injected via dangerouslySetInnerHTML.
 * Recovery codes are shown exactly once at enable time; we never store or
 * re-serve the plaintext.
 */

type Setup = { secret: string; otpauth_uri: string; qr_svg: string };

export default function SecuritySettingsPage() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Enable flow
  const [setup, setSetup] = useState<Setup | null>(null);
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);

  // Disable flow
  const [showDisable, setShowDisable] = useState(false);
  const [disablePassword, setDisablePassword] = useState("");

  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const r = await api.twoFAStatus();
      setEnabled(r.enabled);
    } catch (e: unknown) {
      const m = errorMessage(e);
      if (m.includes("401")) {
        window.location.href = `/signin?next=${encodeURIComponent("/app/settings/security")}`;
        return;
      }
      setLoadError(m);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  async function beginSetup() {
    setBusy(true);
    setErr(null);
    try {
      const s = await api.twoFASetup();
      setSetup(s);
    } catch (e: unknown) {
      setErr(errorMessage(e) || "Couldn't start setup");
    } finally {
      setBusy(false);
    }
  }

  async function confirmEnable(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await api.twoFAEnable(code.trim());
      setRecoveryCodes(r.recovery_codes);
      setEnabled(true);
      setSetup(null);
      setCode("");
    } catch (e: unknown) {
      setErr(errorMessage(e) || "Couldn't enable 2FA");
    } finally {
      setBusy(false);
    }
  }

  function cancelSetup() {
    setSetup(null);
    setCode("");
    setErr(null);
  }

  async function doDisable(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.twoFADisable(disablePassword);
      setEnabled(false);
      setShowDisable(false);
      setDisablePassword("");
      setRecoveryCodes(null);
    } catch (e: unknown) {
      setErr(errorMessage(e) || "Couldn't disable 2FA");
    } finally {
      setBusy(false);
    }
  }

  function copyCodes() {
    if (recoveryCodes) navigator.clipboard?.writeText(recoveryCodes.join("\n"));
  }

  function downloadCodes() {
    if (!recoveryCodes) return;
    const blob = new Blob(
      [
        "Tapeline two-factor recovery codes\n",
        "Each code works once. Store them somewhere safe.\n\n",
        recoveryCodes.join("\n"),
        "\n",
      ],
      { type: "text/plain" },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tapeline-recovery-codes.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  if (loadError && enabled === null)
    return (
      <div className="card p-6 text-sm text-down">
        Couldn&rsquo;t load your security settings: {loadError}
      </div>
    );
  if (enabled === null) return <CardSkeleton rows={4} />;

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6">
        <p className="eyebrow text-muted">Settings</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Security</h1>
        <p className="mt-2 text-sm text-muted">
          Two-factor authentication adds a second step at sign-in: your password
          plus a one-time code from an authenticator app (Google Authenticator,
          1Password, Authy, etc.).
        </p>
      </div>

      {/* Recovery codes — shown once, right after enabling */}
      {recoveryCodes && (
        <div className="card mb-6 border-accent/40 p-5">
          <h2 className="text-lg font-semibold">Save your recovery codes</h2>
          <p className="mt-1 text-sm text-muted">
            Each code works <strong>once</strong>. If you lose your authenticator,
            a recovery code is the only way back in. We can&rsquo;t show these
            again.
          </p>
          <div className="mt-4 grid grid-cols-2 gap-2 rounded-md border border-border bg-panel p-4 font-mono text-sm nums">
            {recoveryCodes.map((c) => (
              <div key={c}>{c}</div>
            ))}
          </div>
          <div className="mt-4 flex gap-3">
            <button onClick={copyCodes} className="btn border border-border text-fg hover:bg-panel">Copy</button>
            <button onClick={downloadCodes} className="btn border border-border text-fg hover:bg-panel">Download .txt</button>
            <button onClick={() => setRecoveryCodes(null)} className="btn-primary ml-auto text-sm">
              I&rsquo;ve saved them
            </button>
          </div>
        </div>
      )}

      {/* Main status card */}
      <div className="card p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold">Authenticator app</span>
              <span
                className={`rounded px-2 py-0.5 text-xs font-semibold uppercase ${
                  enabled ? "bg-up/20 text-up" : "bg-muted/20 text-muted"
                }`}
              >
                {enabled ? "On" : "Off"}
              </span>
            </div>
            <p className="mt-1 text-sm text-muted">
              {enabled
                ? "Sign-in requires a code from your authenticator app."
                : "Protect your account with time-based one-time codes."}
            </p>
          </div>

          {!setup && enabled === false && (
            <button onClick={beginSetup} disabled={busy} className="btn-primary text-sm">
              {busy ? "…" : "Enable"}
            </button>
          )}
          {enabled === true && !showDisable && (
            <button onClick={() => setShowDisable(true)} className="btn border border-border text-fg hover:bg-panel">
              Disable
            </button>
          )}
        </div>

        {/* Enable — setup step (QR + manual key + verify) */}
        {setup && (
          <form onSubmit={confirmEnable} className="mt-6 border-t border-border pt-6">
            <ol className="space-y-5 text-sm">
              <li>
                <div className="font-medium">1. Scan this QR code</div>
                <p className="mt-1 text-muted">In your authenticator app, add a new account.</p>
                <div className="mt-3 inline-block rounded-lg bg-white p-3">
                  <div
                    className="h-40 w-40 [&>svg]:h-full [&>svg]:w-full"
                    // QR markup is generated server-side by segno (services/mfa.qr_svg);
                    // no user-controlled content, safe to inline.
                    dangerouslySetInnerHTML={{ __html: setup.qr_svg }}
                  />
                </div>
              </li>
              <li>
                <div className="font-medium">Can&rsquo;t scan? Enter this key manually</div>
                <code className="mt-2 block break-all rounded-md border border-border bg-panel p-2 font-mono text-xs">
                  {setup.secret}
                </code>
              </li>
              <li>
                <div className="font-medium">2. Enter the 6-digit code it shows</div>
                <input
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="123456"
                  required
                  className="mt-2 block h-11 w-40 rounded-md border border-border bg-panel px-3 text-center text-lg tracking-[0.3em] nums focus:border-accent focus:outline-none"
                />
              </li>
            </ol>

            {err && <p className="mt-4 text-sm text-down">{err}</p>}

            <div className="mt-5 flex gap-3">
              <button type="submit" disabled={busy} className="btn-primary text-sm">
                {busy ? "Verifying…" : "Verify & turn on"}
              </button>
              <button type="button" onClick={cancelSetup} className="btn border border-border text-fg hover:bg-panel">
                Cancel
              </button>
            </div>
          </form>
        )}

        {/* Disable — password re-auth */}
        {showDisable && (
          <form onSubmit={doDisable} className="mt-6 border-t border-border pt-6">
            <div className="font-medium text-sm">Confirm your password to turn off 2FA</div>
            <input
              type="password"
              autoComplete="current-password"
              value={disablePassword}
              onChange={(e) => setDisablePassword(e.target.value)}
              placeholder="Your account password"
              required
              className="mt-2 block h-11 w-full max-w-xs rounded-md border border-border bg-panel px-3 text-base focus:border-accent focus:outline-none"
            />
            {err && <p className="mt-4 text-sm text-down">{err}</p>}
            <div className="mt-5 flex gap-3">
              <button type="submit" disabled={busy} className="btn bg-down text-white hover:opacity-90 disabled:opacity-50">
                {busy ? "Disabling…" : "Disable 2FA"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowDisable(false);
                  setDisablePassword("");
                  setErr(null);
                }}
                className="btn border border-border text-fg hover:bg-panel"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {/* Idle-state error (enable button failure with no open sub-form) */}
        {err && !setup && !showDisable && (
          <p className="mt-4 text-sm text-down">{err}</p>
        )}
      </div>

      <div className="mt-6 text-sm">
        <Link href="/app/account" className="link">&larr; Back to account</Link>
      </div>
    </div>
  );
}
