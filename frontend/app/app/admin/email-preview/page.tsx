"use client";

/**
 * Admin email-preview tool.
 *
 * Lists every renderer in app.services.email and embeds the selected one
 * in an iframe with light/dark/auto theme + desktop/mobile width toggles.
 * Lets the founder iterate on email design without sending themselves
 * test emails — paste a copy change in Python, refresh, see it.
 *
 * Admin-only — the backend endpoint enforces is_admin, and the page also
 * guards client-side so non-admins bounce to /signin.
 */

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@/components/UserContext";
import { handle401 } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

type PreviewItem = { name: string; description: string };

type Theme = "auto" | "light" | "dark";
type Width = "desktop" | "mobile";

export default function EmailPreviewPage() {
  const router = useRouter();
  const { user, loading } = useUser();
  const [items, setItems] = useState<PreviewItem[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>("auto");
  const [width, setWidth] = useState<Width>("desktop");
  const [err, setErr] = useState<string | null>(null);
  const [sendState, setSendState] = useState<"idle" | "sending" | "sent" | "skipped" | "error">("idle");
  const [sendMsg, setSendMsg] = useState<string | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.push("/signin?next=/app/admin/email-preview");
      return;
    }
    // Signed-in non-admins: bounce to a safe page (NOT /signin — that
    // would loop because the backend returns 401 for non-admins).
    if (!user.is_admin) {
      router.push("/app/scanner");
      return;
    }
    fetch(`${API_BASE}/api/admin/email-preview`, { credentials: "include" })
      .then((r) => {
        if (!r.ok) {
          handle401(r.status);
          throw new Error(`${r.status} ${r.statusText}`);
        }
        return r.json();
      })
      .then((data: { items: PreviewItem[] }) => {
        setItems(data.items);
        if (data.items.length > 0) setActive(data.items[0].name);
      })
      .catch((e: unknown) => setErr(String((e as Error)?.message || e)));
  }, [loading, user, router]);

  const iframeSrc = useMemo(() => {
    if (!active) return "";
    const qs = new URLSearchParams({ theme });
    return `${API_BASE}/api/admin/email-preview/${active}?${qs}`;
  }, [active, theme]);

  // Reset the send-to-me state when the user picks a different email so
  // a stale "✓ Sent" doesn't claim the new variant was already delivered.
  useEffect(() => {
    setSendState("idle");
    setSendMsg(null);
  }, [active]);

  if (loading) return <div className="p-8 text-sm text-muted">Loading…</div>;
  if (!user || !user.is_admin) return null;
  if (err)
    return (
      <div className="m-8 rounded-md border border-down/30 bg-down/5 p-4 text-sm text-down">
        Couldn&rsquo;t load previews: {err}
      </div>
    );

  return (
    <div className="flex h-[calc(100vh-3rem)] gap-4 p-4">
      {/* Sidebar — list of every email */}
      <aside className="w-72 flex-shrink-0 overflow-y-auto rounded-md border border-border bg-panel p-3">
        <div className="mb-3 px-2">
          <p className="eyebrow text-muted">Admin</p>
          <h1 className="mt-1 text-lg font-semibold tracking-tight">Email preview</h1>
          <p className="mt-1 text-xs text-muted">
            {items.length} renderer{items.length === 1 ? "" : "s"}
          </p>
        </div>
        <ul className="space-y-0.5">
          {items.map((it) => {
            const on = active === it.name;
            return (
              <li key={it.name}>
                <button
                  type="button"
                  onClick={() => setActive(it.name)}
                  className={`block w-full rounded px-2.5 py-2 text-left text-sm transition-colors ${
                    on
                      ? "bg-accent/10 text-accent"
                      : "text-fg hover:bg-fg/5"
                  }`}
                >
                  <div className={`font-medium ${on ? "text-accent" : "text-fg"}`}>
                    {it.description}
                  </div>
                  <div className="mt-0.5 font-mono text-[10px] uppercase tracking-wider text-subtle">
                    {it.name}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </aside>

      {/* Main pane — toolbar + iframe */}
      <main id="main" className="flex flex-1 flex-col gap-3 overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-panel px-3 py-2">
          <span className="text-xs font-medium text-muted">Theme</span>
          <Toggle
            options={[
              { value: "auto", label: "Auto" },
              { value: "light", label: "Light" },
              { value: "dark", label: "Dark" },
            ]}
            value={theme}
            onChange={(v) => setTheme(v as Theme)}
          />
          <span className="ml-4 text-xs font-medium text-muted">Width</span>
          <Toggle
            options={[
              { value: "desktop", label: "Desktop" },
              { value: "mobile", label: "Mobile" },
            ]}
            value={width}
            onChange={(v) => setWidth(v as Width)}
          />
          {active && (
            <div className="ml-auto flex items-center gap-3">
              <SendToMeButton
                name={active}
                state={sendState}
                msg={sendMsg}
                onClick={async () => {
                  setSendState("sending");
                  setSendMsg(null);
                  try {
                    const r = await fetch(
                      `${API_BASE}/api/admin/email-preview/${active}/send`,
                      { method: "POST", credentials: "include" },
                    );
                    if (!r.ok) {
                      handle401(r.status);
                      const txt = await r.text();
                      setSendState("error");
                      setSendMsg(txt || `${r.status} ${r.statusText}`);
                      return;
                    }
                    const body = await r.json();
                    if (body.status === "sent") {
                      setSendState("sent");
                      setSendMsg(`Delivered to ${body.to}`);
                    } else if (body.status === "skipped") {
                      setSendState("skipped");
                      setSendMsg("Resend not configured (local dev?)");
                    }
                  } catch (e: unknown) {
                    setSendState("error");
                    setSendMsg(String((e as Error)?.message || e));
                  }
                }}
              />
              <a
                href={iframeSrc}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-muted underline-offset-4 hover:text-fg hover:underline"
              >
                Open in new tab ↗
              </a>
            </div>
          )}
        </div>

        <div
          className={`flex-1 overflow-auto rounded-md border border-border ${
            theme === "dark" ? "bg-[#0a0a0a]" : "bg-white"
          }`}
        >
          {iframeSrc ? (
            <div
              className="mx-auto h-full"
              style={{ maxWidth: width === "mobile" ? 390 : "100%" }}
            >
              <iframe
                key={iframeSrc}
                src={iframeSrc}
                title="Email preview"
                className="h-full w-full border-0"
                sandbox="allow-same-origin"
              />
            </div>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted">
              Pick an email from the left.
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function SendToMeButton({
  name,
  state,
  msg,
  onClick,
}: {
  name: string;
  state: "idle" | "sending" | "sent" | "skipped" | "error";
  msg: string | null;
  onClick: () => void;
}) {
  const label =
    state === "sending" ? "Sending…" :
    state === "sent"    ? "✓ Sent" :
    state === "skipped" ? "⚠ Skipped" :
    state === "error"   ? "Retry" :
    "Send to my inbox";
  const className =
    state === "sent"
      ? "rounded-md bg-up/10 px-3 py-1 text-xs font-medium text-up"
      : state === "error"
      ? "rounded-md bg-down/10 px-3 py-1 text-xs font-medium text-down hover:bg-down/20"
      : state === "skipped"
      ? "rounded-md bg-warn/10 px-3 py-1 text-xs font-medium text-warn"
      : "rounded-md bg-accent/10 px-3 py-1 text-xs font-medium text-accent hover:bg-accent/20 disabled:opacity-50";
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={onClick}
        disabled={state === "sending"}
        className={className}
        title={`Deliver the rendered ${name} preview to your own email`}
      >
        {label}
      </button>
      {msg && (
        <span className="text-[11px] text-muted">{msg}</span>
      )}
    </div>
  );
}

function Toggle({
  options,
  value,
  onChange,
}: {
  options: { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="inline-flex rounded-md border border-border bg-bg p-0.5">
      {options.map((o) => {
        const on = value === o.value;
        return (
          <button
            type="button"
            key={o.value}
            onClick={() => onChange(o.value)}
            aria-pressed={on}
            className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
              on ? "bg-accent text-white" : "text-muted hover:text-fg"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
