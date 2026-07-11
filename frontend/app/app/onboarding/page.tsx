"use client";

/**
 * Post-signup onboarding.
 *
 * One page, five questions, all optional. Used to capture investor profile
 * + attribution + marketing-opt-in shortly after the user lands in /app/*.
 * Either button (Save or Skip) POSTs to /api/me/onboarding which stamps
 * `onboarding_completed_at` server-side, so the user is only ever prompted
 * once. The middleware-level redirect lives in lib/auth (callers check
 * `user.onboarding_completed_at` after signup/signin).
 *
 * Conversion-protective by design: questions are clearly optional, the
 * Skip button is equally prominent, and the trial is already running so
 * there's no urgency to interrupt them.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { track } from "@vercel/analytics";
import { api, handle401 } from "@/lib/api";
import { trackEvent } from "@/lib/gtag";
import { SECTOR_SLUG_TO_CANONICAL } from "@/components/TodaysTape";
import { safeNext } from "@/lib/safeNext";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// Dedupe key: the OAuth signup/trial conversion pair must fire at most once
// per browser. New Google users land here at /app/onboarding?oauth=1.
const OAUTH_CONVERSION_FIRED_KEY = "tapeline_oauth_conversion_fired";

type Experience = "beginner" | "intermediate" | "advanced";
type Style = "day" | "swing" | "longterm" | "mixed";
type Band =
  | "under_10k"
  | "10_50k"
  | "50_250k"
  | "250k_plus"
  | "prefer_not_to_say";
type Source =
  | "twitter_x"
  | "reddit"
  | "youtube"
  | "podcast"
  | "friend"
  | "search"
  | "hacker_news"
  | "other";

const EXPERIENCE: { value: Experience; label: string; hint: string }[] = [
  { value: "beginner", label: "Beginner", hint: "< 1 year, learning the ropes" },
  { value: "intermediate", label: "Intermediate", hint: "1–5 years, comfortable" },
  { value: "advanced", label: "Advanced", hint: "5+ years, set in your process" },
];

const STYLES: { value: Style; label: string; hint: string }[] = [
  { value: "day", label: "Day trader", hint: "Intraday, flat by close" },
  { value: "swing", label: "Swing trader", hint: "Hold days to weeks" },
  { value: "longterm", label: "Long-term", hint: "Months to years" },
  { value: "mixed", label: "Mixed", hint: "Different bucket for different setups" },
];

const BANDS: { value: Band; label: string }[] = [
  { value: "under_10k", label: "Under $10k" },
  { value: "10_50k", label: "$10k – $50k" },
  { value: "50_250k", label: "$50k – $250k" },
  { value: "250k_plus", label: "$250k+" },
  { value: "prefer_not_to_say", label: "Prefer not to say" },
];

const SOURCES: { value: Source; label: string }[] = [
  { value: "twitter_x", label: "Twitter / X" },
  { value: "reddit", label: "Reddit" },
  { value: "youtube", label: "YouTube" },
  { value: "podcast", label: "Podcast" },
  { value: "friend", label: "A friend" },
  { value: "search", label: "Search engine" },
  { value: "hacker_news", label: "Hacker News" },
  { value: "other", label: "Somewhere else" },
];

// Keep in sync with backend _ALLOWED_SECTORS in routers/me.py.
const SECTORS: { value: string; label: string }[] = [
  { value: "technology", label: "Technology" },
  { value: "healthcare", label: "Healthcare" },
  { value: "financials", label: "Financials" },
  { value: "energy", label: "Energy" },
  { value: "communications", label: "Communications" },
  { value: "consumer_discretionary", label: "Consumer Discretionary" },
  { value: "consumer_staples", label: "Consumer Staples" },
  { value: "industrials", label: "Industrials" },
  { value: "materials", label: "Materials" },
  { value: "real_estate", label: "Real Estate" },
  { value: "utilities", label: "Utilities" },
  { value: "commodities", label: "Commodities" },
  { value: "etfs", label: "Broad ETFs" },
];

export default function OnboardingPage() {
  return (
    <Suspense fallback={null}>
      <OnboardingForm />
    </Suspense>
  );
}

function OnboardingForm() {
  const router = useRouter();
  const qp = useSearchParams();
  // Guard the post-submit redirect against open-redirect payloads
  // (//evil.com, https://evil.com) forwarded from /signup?next=…
  const next = safeNext(qp.get("next"));

  const [experience, setExperience] = useState<Experience | "">("");
  const [style, setStyle] = useState<Style | "">("");
  const [band, setBand] = useState<Band | "">("");
  const [source, setSource] = useState<Source | "">("");
  const [sectors, setSectors] = useState<string[]>([]);
  const [marketingOptIn, setMarketingOptIn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // OAuth signup conversion. The backend redirects NEW Google/OAuth users to
  // /app/onboarding?oauth=1, but OAuth signups never touch the /signup form
  // where `sign_up` / `start_trial` fire — so without this they're invisible
  // to GA4/Ads. Fire both once, deduped per browser (localStorage) with a ref
  // guard for the storage-unavailable case + React strict-mode double-mount.
  const oauthFiredRef = useRef(false);
  useEffect(() => {
    if (qp.get("oauth") == null) return;
    if (oauthFiredRef.current) return;
    try {
      if (
        typeof window !== "undefined" &&
        window.localStorage.getItem(OAUTH_CONVERSION_FIRED_KEY) === "1"
      ) {
        oauthFiredRef.current = true;
        return;
      }
      window.localStorage.setItem(OAUTH_CONVERSION_FIRED_KEY, "1");
    } catch {
      // storage unavailable — the ref still dedupes within this mount.
    }
    oauthFiredRef.current = true;
    // OAuth account creation === same conversion bucket as an email signup;
    // the 14-day trial auto-starts, so start_trial fires alongside it (mirrors
    // the email /signup flow).
    trackEvent("sign_up", { method: "oauth" });
    trackEvent("start_trial", { method: "oauth" });
  }, [qp]);

  function toggleSector(slug: string) {
    setSectors((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug],
    );
  }

  // Best-effort watchlist seed from the user's selected sectors — this is the
  // "start your watchlist with the top-scored names" promise the sector-picker
  // copy makes. Fire-and-forget: never awaited by submit(), every failure is
  // swallowed, so it can never block or break navigation. The scanner `sector`
  // param takes a single canonical label, so we query per selected sector
  // (bounded), merge + rank by score, and add the best few names via the SAME
  // watchlist API the watchlist page uses (lands in the default list).
  async function seedWatchlistFromSectors(slugs: string[]) {
    const labels = slugs
      .map((s) => SECTOR_SLUG_TO_CANONICAL[s])
      .filter(Boolean)
      .slice(0, 3);
    if (labels.length === 0) return;
    try {
      const seen = new Set<string>();
      const picks: { symbol: string; score: number }[] = [];
      for (const label of labels) {
        try {
          const r = await api.scanner({
            sector: label,
            sort: "score",
            order: "desc",
            limit: 5,
          });
          for (const row of r.items) {
            if (row.symbol && !seen.has(row.symbol)) {
              seen.add(row.symbol);
              picks.push({ symbol: row.symbol, score: row.score ?? 0 });
            }
          }
        } catch {
          // Skip this sector — a partial seed is still useful.
        }
      }
      picks.sort((a, b) => b.score - a.score);
      for (const p of picks.slice(0, 5)) {
        try {
          await api.watchlistAdd(p.symbol);
        } catch {
          // Already present / tier-capped / transient — ignore per-add.
        }
      }
    } catch {
      // Never let the seed break onboarding.
    }
  }

  async function submit(skipped: boolean) {
    setBusy(true);
    setErr(null);
    try {
      const body = {
        experience_level: skipped ? null : experience || null,
        trading_style: skipped ? null : style || null,
        portfolio_band: skipped ? null : band || null,
        referral_source: skipped ? null : source || null,
        marketing_opt_in: skipped ? false : marketingOptIn,
        sectors_of_interest: skipped ? [] : sectors,
        skipped,
      };
      const res = await fetch(`${API_BASE}/api/me/onboarding`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        handle401(res.status);
        const t = await res.text();
        throw new Error(t || `${res.status} ${res.statusText}`);
      }
      track("onboarding_submitted", {
        skipped,
        sectors: sectors.length,
        marketing_opt_in: marketingOptIn,
      });
      // Seed the watchlist from whatever sectors the user picked — even on
      // Skip, since the picker copy promises it. Fire-and-forget (not awaited)
      // so navigation is instant; the fetches finish after the route change.
      if (sectors.length > 0) {
        void seedWatchlistFromSectors(sectors);
      }
      router.push(next);
      router.refresh();
    } catch (e: unknown) {
      setErr((e as Error)?.message || "Couldn't save — try again or skip for now.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main" className="mx-auto max-w-2xl px-4 py-10 sm:py-14">
      <p className="eyebrow text-muted">One quick step</p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight">
        Tell us a bit about you
      </h1>
      <p className="mt-2 text-sm text-muted">
        Every question is optional. We use these to tune your scanner defaults,
        the weekly digest, and what we build next. You can skip the whole thing
        — your 14-day Premium trial is already running.
      </p>

      <div className="mt-8 space-y-8">
        <Section label="What's your investing experience?">
          <ButtonRow
            options={EXPERIENCE.map((o) => ({
              value: o.value,
              label: o.label,
              hint: o.hint,
            }))}
            value={experience}
            onChange={(v) => setExperience(v as Experience)}
          />
        </Section>

        <Section label="How do you typically trade?">
          <ButtonRow
            options={STYLES.map((o) => ({
              value: o.value,
              label: o.label,
              hint: o.hint,
            }))}
            value={style}
            onChange={(v) => setStyle(v as Style)}
          />
        </Section>

        <Section label="Roughly what size portfolio do you run?">
          <ButtonRow
            options={BANDS.map((o) => ({ value: o.value, label: o.label }))}
            value={band}
            onChange={(v) => setBand(v as Band)}
          />
        </Section>

        <Section label="Which sectors are you most interested in?" hint="Pick any that apply — we'll pre-tune your scanner filters and start your watchlist with the top-scored names from your first pick (you can remove them anytime).">
          <div className="flex flex-wrap gap-2">
            {SECTORS.map((s) => {
              const on = sectors.includes(s.value);
              return (
                <button
                  type="button"
                  key={s.value}
                  onClick={() => toggleSector(s.value)}
                  aria-pressed={on}
                  className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                    on
                      ? "border-accent bg-accent/10 text-accent"
                      : "border-border bg-panel text-muted hover:border-fg/40 hover:text-fg"
                  }`}
                >
                  {s.label}
                </button>
              );
            })}
          </div>
        </Section>

        <Section label="How did you hear about Tapeline?">
          <ButtonRow
            options={SOURCES.map((o) => ({ value: o.value, label: o.label }))}
            value={source}
            onChange={(v) => setSource(v as Source)}
          />
        </Section>

        <Section label="Weekly market digest">
          <label className="flex cursor-pointer items-start gap-3 rounded-md border border-border bg-panel p-4 text-sm">
            <input
              type="checkbox"
              checked={marketingOptIn}
              onChange={(e) => setMarketingOptIn(e.target.checked)}
              className="mt-0.5 h-4 w-4 cursor-pointer accent-accent"
            />
            <span className="text-fg">
              Send me the weekly digest — top movers, regime, and what the
              public scorecard did this week.{" "}
              <span className="text-muted">
                One email a week, every Monday. Opt out anytime in{" "}
                <Link href="/app/settings/email" className="link">
                  email preferences
                </Link>
                .
              </span>
            </span>
          </label>
        </Section>
      </div>

      {err && (
        <div className="mt-6 rounded-md border border-down/30 bg-down/5 p-3 text-sm text-down">
          {err}
        </div>
      )}

      <div className="mt-10 flex flex-col-reverse items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
        <button
          type="button"
          onClick={() => submit(true)}
          disabled={busy}
          className="text-sm font-medium text-muted underline-offset-4 transition-colors hover:text-fg hover:underline disabled:opacity-50"
        >
          Skip for now
        </button>
        <button
          type="button"
          onClick={() => submit(false)}
          disabled={busy}
          className="flex h-11 items-center justify-center rounded-md bg-gradient-to-r from-accent to-accent2 px-6 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-50"
        >
          {busy ? "Saving…" : "Save and continue"}
        </button>
      </div>
    </main>
  );
}

function Section({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-sm font-medium text-fg">{label}</div>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
      <div className="mt-3">{children}</div>
    </div>
  );
}

function ButtonRow({
  options,
  value,
  onChange,
}: {
  options: { value: string; label: string; hint?: string }[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {options.map((o) => {
        const on = value === o.value;
        return (
          <button
            type="button"
            key={o.value}
            onClick={() => onChange(o.value)}
            aria-pressed={on}
            className={`flex flex-col items-start rounded-md border px-3 py-2.5 text-left text-sm transition-colors ${
              on
                ? "border-accent bg-accent/10"
                : "border-border bg-panel hover:border-fg/40"
            }`}
          >
            <span className={on ? "text-accent" : "text-fg"}>{o.label}</span>
            {o.hint && (
              <span className="mt-0.5 text-xs text-muted">{o.hint}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
