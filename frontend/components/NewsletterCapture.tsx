"use client";

import { useState } from "react";
import { track } from "@vercel/analytics";
import { trackEvent } from "@/lib/gtag";
import { getStoredUtm } from "@/lib/utm";

/**
 * Lead-magnet email capture. Lower-commitment funnel step than /signup —
 * visitor gives us an email to get the daily Top 10 digest without
 * needing a card or even an account. Once they're in the
 * `newsletter_subscribers` table the daily send + an in-email upgrade
 * CTA do the conversion lift.
 *
 * Posts to `/api/newsletter/subscribe` with:
 *   - email
 *   - source (passed via props — 'homepage' / 'scorecard' / 'pricing')
 *   - utm_* from the persisted localStorage capture (lib/utm.ts) so we
 *     attribute the eventual conversion to the channel that brought
 *     them.
 *
 * On success fires `newsletter_subscribed` to Vercel Analytics +
 * `sign_up` (with method='newsletter') to GA4 — same conversion bucket
 * as account signup so we can compare list-growth velocity in the same
 * GA4 funnel report.
 */
type Props = {
  /** Where on the site this instance is rendered. Logged to the row's
   * `source` column so we know which surface converts the email.
   * 'feature' — SEO feature landing pages (squeeze, congress, etc.)
   * 'signals' — the /signals public universe page
   * 'strategy' — /best-stocks-for/[strategy] listicle pages
   * 'compare' — /compare/* head-to-head pages
   */
  source: "homepage" | "scorecard" | "pricing" | "blog" | "footer" | "feature" | "signals" | "strategy" | "compare";
  /** Optional headline override; defaults to "Get the daily Top 10 picks". */
  heading?: string;
  /** Optional sub-line override. */
  sub?: string;
  /** Layout density — inline (single-row) or stacked (form below copy). */
  variant?: "inline" | "stacked";
};

export function NewsletterCapture({
  source,
  heading = "Get the daily Top 10 picks",
  sub = "One email each market morning. The 10 highest-scoring US tickers from our public 6-factor composite. No card, no trial — unsubscribe in one click.",
  variant = "inline",
}: Props) {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  // 'idle' | 'success' | 'already' — drives the post-submit UI swap.
  const [status, setStatus] = useState<"idle" | "success" | "already">("idle");
  // Honeypot field — invisible to humans, bots fill it. Server returns a
  // fake-success when this is non-empty so spammers can't probe.
  const [website, setWebsite] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      setErr("Enter a valid email address.");
      return;
    }
    setBusy(true);
    try {
      const utm = getStoredUtm();
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
      const res = await fetch(`${apiBase}/api/newsletter/subscribe`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          source,
          website,
          ...utm,
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(body.detail || `Failed (${res.status})`);
      }
      const body = (await res.json()) as { status?: string };
      if (body.status === "already_subscribed") {
        setStatus("already");
      } else {
        setStatus("success");
        // Conversion events — only fire on a truly new signup so list
        // growth in GA4 isn't inflated by re-submits. `method='newsletter'`
        // lets us distinguish from the trial-signup `sign_up` event.
        track("newsletter_subscribed", { source });
        trackEvent("sign_up", { method: "newsletter" });
      }
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Sign up failed";
      setErr(message);
    } finally {
      setBusy(false);
    }
  }

  if (status === "success" || status === "already") {
    return (
      <div
        className="rounded-lg border border-up/30 bg-up/[0.06] px-4 py-3 text-sm text-fg"
        role="status"
      >
        {status === "success" ? (
          <>
            <span className="font-semibold text-up">You&rsquo;re in.</span>{" "}
            Check your inbox for the welcome email — first daily digest hits the
            next US market morning.
          </>
        ) : (
          <>
            <span className="font-semibold text-up">Already subscribed.</span>{" "}
            You&rsquo;ll keep getting the daily digest every market morning. No
            action needed.
          </>
        )}
      </div>
    );
  }

  const isStacked = variant === "stacked";

  return (
    <form
      onSubmit={submit}
      className={
        isStacked
          ? "flex flex-col gap-3"
          : "flex flex-col gap-3 sm:flex-row sm:items-stretch"
      }
      aria-label="Newsletter signup"
    >
      {/* Honeypot — visually hidden, bots populate every input. Style is
          inline so a stylesheet error can't unhide it. */}
      <label
        aria-hidden="true"
        style={{
          position: "absolute",
          left: "-9999px",
          width: 1,
          height: 1,
          overflow: "hidden",
        }}
      >
        Don&rsquo;t fill this in
        <input
          tabIndex={-1}
          autoComplete="off"
          type="text"
          name="website"
          value={website}
          onChange={(e) => setWebsite(e.target.value)}
        />
      </label>

      {heading || sub ? (
        <div className={isStacked ? "" : "sr-only"}>
          {heading && (
            <h3 className="text-base font-semibold text-fg">{heading}</h3>
          )}
          {sub && <p className="mt-1 text-sm text-muted leading-relaxed">{sub}</p>}
        </div>
      ) : null}

      <label className="sr-only" htmlFor={`nl-email-${source}`}>
        Email address
      </label>
      <input
        id={`nl-email-${source}`}
        type="email"
        autoComplete="email"
        required
        placeholder="you@example.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="flex-1 rounded-md border border-border bg-panel px-3 py-2 text-sm text-fg placeholder:text-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        disabled={busy}
      />
      <button
        type="submit"
        disabled={busy}
        className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-bg hover:opacity-90 disabled:opacity-50"
      >
        {busy ? "Subscribing…" : "Get free daily picks"}
      </button>
      {err && (
        <p className="text-sm text-down" role="alert">
          {err}
        </p>
      )}
    </form>
  );
}
