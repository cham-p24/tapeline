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

  useEffect(() => {
    if (loading) return;
    if (!user || !user.is_admin) {
      router.push("/signin?next=/app/admin/email-preview");
      return;
    }
    fetch(`${API_BASE}/api/admin/email-preview`, { credentials: "include" })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
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
      <main className="flex flex-1 flex-col gap-3 overflow-hidden">
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
            <a
              href={iframeSrc}
              target="_blank"
              rel="noreferrer"
              className="ml-auto text-xs text-muted underline-offset-4 hover:text-fg hover:underline"
            >
              Open in new tab ↗
            </a>
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
