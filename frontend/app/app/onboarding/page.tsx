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
 *
 * Marketing-consent semantics (weekly digest): consent can now also be
 * granted on the /signup form, so this page must never destroy it.
 * The checkbox prefills from the user's CURRENT consent (best-effort
 * /api/me fetch), and the submit sends `marketing_opt_in: null` on Skip
 * or when the checkbox was never touched — the backend leaves the stored
 * value untouched for null. Only an explicit tick/untick changes consent.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { track } from "@vercel/analytics";
import { api, handle401 } from "@/lib/api";
import { trackEvent, trackEventOnce } from "@/lib/gtag";
import { SECTOR_SLUG_TO_CANONICAL } from "@/components/TodaysTape";
import { safeNext } from "@/lib/safeNext";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// Dedupe key: the OAuth signup/trial conversion pair must fire at most once
// per browser. New Google users land here at /app/onboarding?oauth=1.
const OAUTH_CONVERSION_FIRED_KEY = "tapeline_oauth_conversion_fired";

type Style = "day" | "swing" | "longterm" | "mixed";
type Source =
  | "twitter_x"
  | "reddit"
  | "youtube"
  | "podcast"
  | "friend"
  | "search"
  | "hacker_news"
  | "other";

const STYLES: { value: Style; label: string; hint: string }[] = [
  { value: "day", label: "Day trader", hint: "Intraday, flat by close" },
  { value: "swing", label: "Swing trader", hint: "Hold days to weeks" },
  { value: "longterm", label: "Long-term", hint: "Months to years" },
  { value: "mixed", label: "Mixed", hint: "Different bucket for different setups" },
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

  const [style, setStyle] = useState<Style | "">("");
  const [source, setSource] = useState<Source | "">("");
  const [sectors, setSectors] = useState<string[]>([]);
  const [marketingOptIn, setMarketingOptIn] = useState(false);
  // True once the user has interacted with the consent checkbox. Only a
  // touched checkbox submits a real true/false; untouched (and Skip) submit
  // null so the backend leaves any previously-granted consent alone.
  const marketingTouchedRef = useRef(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Prefill the consent checkbox from the user's CURRENT stored consent so
  // the UI tells the truth for users who already opted in on the signup form
  // (and so an explicit untick here is a real revocation). Best-effort: any
  // failure just leaves the default unchecked box, and the untouched-→-null
  // submit semantics mean we still can't destroy stored consent.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/me`, { credentials: "include" });
        if (!res.ok) return;
        const d = await res.json();
        if (
          !cancelled &&
          !marketingTouchedRef.current &&
          d?.profile?.marketing_opt_in === true
        ) {
          setMarketingOptIn(true);
        }
      } catch {
        // best-effort only — default unchecked stays.
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // OAuth signup conversion. The backend redirects NEW Google/OAuth users to
  // /app/onboarding?oauth=1, but OAuth signups never touch the /signup form
  // where `sign_up` / `start_trial` fire — so without this they're invisible
  // to GA4/Ads. Fire both once, deduped per browser (localStorage) with a ref
  // guard for React strict-mode double-mount.
  //
  // The localStorage flag is now written by trackEventOnce AFTER a confirmed
  // dispatch, never before. The old order set the flag first and then called
  // trackEvent, which silently no-opped whenever gtag.js hadn't finished
  // loading — and since gtag loads afterInteractive while this effect runs at
  // mount, that race permanently lost the OAuth signup conversion on this
  // browser. trackEvent also queues-and-retries now, so a slow load delays
  // the event instead of dropping it.
  const oauthFiredRef = useRef(false);
  useEffect(() => {
    if (qp.get("oauth") == null) return;
    if (oauthFiredRef.current) return;
    oauthFiredRef.current = true;
    // OAuth account creation === same conversion bucket as an email signup;
    // the 14-day trial auto-starts, so start_trial fires alongside it (mirrors
    // the email /signup flow). Both share one dedupe key: they are two halves
    // of the same moment, so they must never fire independently of each other.
    if (trackEventOnce(OAUTH_CONVERSION_FIRED_KEY, "sign_up", { method: "oauth" })) {
      trackEvent("start_trial", { method: "oauth" });
    }
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
      // Leave AT LEAST ONE free watchlist slot so the user's own first add —
      // the activation action — never hits the cap. The Free watchlist cap is
      // 5 (backend tier.FREE_WATCHLIST_TICKERS), so seed at most 4 here. The
      // server also enforces the cap with a 403, but capping the seed keeps a
      // slot open instead of relying on the user to delete a starter pick.
      const SECTOR_SEED_MAX = 4; // = FREE_WATCHLIST_TICKERS (5) - 1
      for (const p of picks.slice(0, SECTOR_SEED_MAX)) {
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
        trading_style: skipped ? null : style || null,
        referral_source: skipped ? null : source || null,
        // null = "no answer" — the backend leaves stored consent untouched.
        // Sent on Skip AND when the checkbox was never touched, so neither
        // path can destroy consent granted earlier (e.g. at signup). Only an
        // explicit tick/untick transmits true/false.
        marketing_opt_in:
          skipped || !marketingTouchedRef.current ? null : marketingOptIn,
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
        {/* Investing-experience and portfolio-size questions were REMOVED
            2026-07-18. Collecting experience level or capital/portfolio size
            is suitability data: under the personal-advice test it is one of
            the inputs that turns general information into personal financial
            advice. Do not reintroduce them, and do not add risk tolerance,
            holdings, or investment goals. Use-case questions (how you trade,
            which sectors interest you) are fine — they must never change
            which securities or factor weightings a user is shown.
            See docs/COMPLIANCE_COPY_RULES.md (Rule 8). */}

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
              onChange={(e) => {
                marketingTouchedRef.current = true;
                setMarketingOptIn(e.target.checked);
              }}
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
