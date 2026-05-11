"use client";

import { useState } from "react";

type Status = "idle" | "submitting" | "sent" | "error";

export function ContactForm() {
  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus("submitting");
    setErrorMsg(null);

    const fd = new FormData(e.currentTarget);
    const payload = {
      name: String(fd.get("name") || "").trim(),
      email: String(fd.get("email") || "").trim(),
      subject: String(fd.get("subject") || "").trim() || null,
      message: String(fd.get("message") || "").trim(),
      // Honeypot — hidden field, real users leave it blank.
      website: String(fd.get("website") || ""),
    };

    if (payload.message.length < 8) {
      setStatus("error");
      setErrorMsg("Message is too short — give me at least a sentence.");
      return;
    }

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
      const r = await fetch(`${apiBase}/api/contact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        setStatus("error");
        setErrorMsg(body.detail || `Could not send (HTTP ${r.status}).`);
        return;
      }
      setStatus("sent");
      (e.target as HTMLFormElement).reset();
    } catch {
      setStatus("error");
      setErrorMsg("Network error — try again or email support@tapeline.io directly.");
    }
  }

  if (status === "sent") {
    return (
      <div className="rounded-lg border border-border bg-bg-soft p-6 text-center">
        <div className="text-2xl">✉️</div>
        <p className="mt-2 font-medium">Message sent.</p>
        <p className="mt-1 text-sm text-muted">
          Reply usually within 24 hours, Melbourne time. Check your spam folder if it&apos;s been longer.
        </p>
        <button
          type="button"
          onClick={() => setStatus("idle")}
          className="mt-4 text-sm text-accent hover:underline"
        >
          Send another
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Your name" name="name" required autoComplete="name" />
        <Field label="Your email" name="email" type="email" required autoComplete="email" />
      </div>
      <Field label="Subject" name="subject" autoComplete="off" />
      <div>
        <label htmlFor="message" className="block text-xs font-medium text-muted mb-1">
          Message <span className="text-fg">*</span>
        </label>
        <textarea
          id="message"
          name="message"
          required
          minLength={8}
          maxLength={5000}
          rows={6}
          className="w-full rounded-md border border-border bg-bg px-3 py-2 text-sm focus:border-accent focus:outline-none"
          placeholder="What's up? Bug report, feature idea, billing question — anything."
        />
      </div>

      {/* Honeypot — visually hidden, off-screen, tab-skipped. */}
      <div aria-hidden="true" style={{ position: "absolute", left: "-10000px", width: 1, height: 1, overflow: "hidden" }}>
        <label htmlFor="website">If you can see this, leave it blank.</label>
        <input id="website" name="website" type="text" tabIndex={-1} autoComplete="off" />
      </div>

      {status === "error" && errorMsg && (
        <p className="text-sm text-down" role="alert">{errorMsg}</p>
      )}

      <button
        type="submit"
        disabled={status === "submitting"}
        className="btn-primary inline-flex items-center gap-2 disabled:opacity-60"
      >
        {status === "submitting" ? "Sending…" : "Send message"}
      </button>
      <p className="text-[11px] text-subtle">
        We&apos;ll only use your email to reply. No marketing, no list, no resale.
      </p>
    </form>
  );
}

function Field({
  label,
  name,
  type = "text",
  required,
  autoComplete,
}: {
  label: string;
  name: string;
  type?: string;
  required?: boolean;
  autoComplete?: string;
}) {
  return (
    <div>
      <label htmlFor={name} className="block text-xs font-medium text-muted mb-1">
        {label} {required && <span className="text-fg">*</span>}
      </label>
      <input
        id={name}
        name={name}
        type={type}
        required={required}
        autoComplete={autoComplete}
        maxLength={type === "email" ? 200 : 200}
        className="w-full rounded-md border border-border bg-bg px-3 py-2 text-sm focus:border-accent focus:outline-none"
      />
    </div>
  );
}
