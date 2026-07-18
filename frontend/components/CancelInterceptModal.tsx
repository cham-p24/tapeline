"use client";

import { useEffect, useState } from "react";
import { track } from "@vercel/analytics";
import { userLocale } from "@/lib/datetime";
import { handle401, errorMessage } from "@/lib/api";
import { FREE_LIMITS } from "@/lib/pricing";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/**
 * Cancel-intercept modal — shown when a paid user clicks "Cancel subscription"
 * on /app/billing.
 *
 * TRUE ONE-CLICK CANCEL (founder decision): the FIRST screen carries a
 * clearly visible "Just cancel my subscription" button that performs the
 * cancel immediately — no survey gate, no second confirm. The save offer and
 * pause options stay on that same screen for anyone who wants them, but they
 * never stand between the user and cancelling. This is what makes the
 * "cancel in one click" claim across the site literally true.
 *
 * Flow:
 *   1. menu — save offer + pause AND the direct cancel button, all on one
 *             screen. Direct cancel calls POST /api/billing/cancel with an
 *             empty body and jumps straight to the done screen.
 *   2. done — terminal confirmation. For a cancellation it confirms the
 *             end-of-period date from the API response and offers the exit
 *             survey as a clearly OPTIONAL afterthought ("Mind telling us
 *             why? (optional)") — submitting it is a second POST /cancel
 *             that the backend treats as survey-capture only (no second
 *             Stripe call, no second email).
 *
 * State is read live from GET /api/billing/retention-options so the modal
 * reflects an in-flight pause or an already-scheduled cancellation instead
 * of blindly re-offering. Every state-changing action calls onChanged() so
 * the parent billing page can refresh the user/session.
 */

type RetentionOptions = {
  has_subscription: boolean;
  tier: string;
  save_offer_available: boolean;
  paused_until: string | null;
  canceled_at: string | null;
};

type DoneKind = "saved" | "paused" | "resumed" | "canceled";

const REASONS: { code: string; label: string }[] = [
  { code: "too_expensive", label: "Too expensive" },
  { code: "not_using", label: "Not using it enough" },
  { code: "missing_feature", label: "Missing a feature I need" },
  { code: "found_alternative", label: "Found an alternative" },
  { code: "trial_only", label: "Was just trying it out" },
  { code: "technical_issues", label: "Technical issues or bugs" },
  { code: "other", label: "Something else" },
];

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) return "";
  return d.toLocaleDateString(userLocale(), {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function CancelInterceptModal({
  open,
  onClose,
  onChanged,
  tier,
}: {
  open: boolean;
  onClose: () => void;
  onChanged?: () => void;
  tier: string;
}) {
  const [step, setStep] = useState<"menu" | "done">("menu");
  const [opts, setOpts] = useState<RetentionOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ kind: DoneKind; detail?: string | null } | null>(null);
  // Post-cancel exit survey (optional). No preselected reason — a default
  // radio would fabricate churn data from people who never chose anything.
  const [reason, setReason] = useState<string | null>(null);
  const [feedback, setFeedback] = useState("");
  const [surveySent, setSurveySent] = useState(false);

  const tierLabel = (tier || "your").replace(/^\w/, (c) => c.toUpperCase());

  // Reset to a clean state + fetch live retention options every time the
  // modal opens. Fetching on open (not mount) means a pause/cancel done in
  // a prior open is always reflected.
  useEffect(() => {
    if (!open) return;
    setStep("menu");
    setDone(null);
    setError(null);
    setBusy(null);
    setReason(null);
    setFeedback("");
    setSurveySent(false);
    setLoading(true);
    track("cancel_intercept_shown", { tier });
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/billing/retention-options`, {
          credentials: "include",
          cache: "no-store",
        });
        if (res.status === 401) {
          handle401(res.status);
          return;
        }
        const body = await res.json();
        if (res.ok) setOpts(body as RetentionOptions);
        else setError(body.detail || "Couldn't load your plan options.");
      } catch (e: unknown) {
        setError(errorMessage(e));
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;

  async function action(
    path: string,
    body: unknown,
    onOk: (data: { resumes_at?: string; period_end?: string }) => void,
    tag: string,
  ) {
    setBusy(tag);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body ?? {}),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        onOk(data);
        onChanged?.();
      } else if (res.status === 401) {
        handle401(res.status);
      } else {
        setError(data.detail || `Something went wrong (${res.status}).`);
      }
    } catch (e: unknown) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  const acceptSave = () =>
    action("/api/billing/save-offer", {}, () => {
      track("save_offer_accepted", { tier });
      setDone({ kind: "saved" });
      setStep("done");
    }, "save");

  const pause = (months: number) =>
    action("/api/billing/pause", { months }, (d) => {
      track("subscription_paused", { tier, months });
      setDone({ kind: "paused", detail: d.resumes_at });
      setStep("done");
    }, `pause${months}`);

  const resume = () =>
    action("/api/billing/resume", {}, () => {
      track("subscription_resumed", { tier });
      setDone({ kind: "resumed" });
      setStep("done");
    }, "resume");

  /** THE one-click cancel: fires from the first screen, empty body (the
   *  survey comes after, optionally), straight to the confirmation. */
  const directCancel = () =>
    action("/api/billing/cancel", {}, (d) => {
      track("subscription_canceled", { tier, via: "one_click" });
      setDone({ kind: "canceled", detail: d.period_end });
      setStep("done");
    }, "cancel");

  /** Optional post-cancel survey. The backend treats a POST /cancel while a
   *  cancellation is already scheduled as survey-capture only. */
  const submitSurvey = () =>
    action("/api/billing/cancel", { reason, feedback: feedback.trim() || null }, () => {
      track("cancel_survey_submitted", { tier, reason: reason ?? "other" });
      setSurveySent(true);
    }, "survey");

  const pausedActive =
    opts?.paused_until && new Date(opts.paused_until).getTime() > Date.now();

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 py-8 backdrop-blur-sm overflow-y-auto"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-2xl border border-border bg-panel p-6 shadow-2xl sm:p-7"
        onClick={(e) => e.stopPropagation()}
      >
        {loading ? (
          <div className="py-10 text-center text-sm text-muted">Loading your plan…</div>
        ) : step === "done" && done ? (
          done.kind === "canceled" ? (
            /* Cancelled — descriptive confirmation with the real end-of-period
               date from the API, then the OPTIONAL exit survey. Never a gate:
               Close works at any point, survey or no survey. */
            <div>
              <div className="text-xs font-medium uppercase tracking-wider text-muted">
                Cancellation scheduled
              </div>
              <h2 className="mt-2 text-2xl font-bold tracking-tight">Cancelled.</h2>
              <p className="mt-3 text-sm text-muted">
                {done.detail
                  ? `You'll keep full access until ${fmtDate(done.detail)}, then drop to Free. No further charges.`
                  : "You'll keep access until the end of your billing period, then drop to Free. No further charges."}
              </p>

              {error && <ErrorNote text={error} />}

              {surveySent ? (
                <p className="mt-5 text-sm text-up">Thanks — noted.</p>
              ) : (
                <div className="mt-6 rounded-xl border border-border bg-panel p-4">
                  <div className="text-sm font-semibold">Mind telling us why? (optional)</div>
                  <div className="mt-3 space-y-1.5">
                    {REASONS.map((r) => (
                      <label
                        key={r.code}
                        className={`flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 text-sm transition-colors ${
                          reason === r.code ? "border-accent bg-accent/5" : "border-border hover:border-muted"
                        }`}
                      >
                        <input
                          type="radio"
                          name="cancel_reason"
                          value={r.code}
                          checked={reason === r.code}
                          onChange={() => setReason(r.code)}
                          className="accent-accent"
                        />
                        <span>{r.label}</span>
                      </label>
                    ))}
                  </div>
                  <textarea
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value.slice(0, 1000))}
                    placeholder="Anything else? (optional)"
                    rows={3}
                    className="mt-3 block w-full rounded-md border border-border bg-panel px-3 py-2 text-sm focus:border-accent focus:outline-none"
                  />
                  <button
                    onClick={submitSurvey}
                    disabled={busy !== null || reason === null}
                    className="mt-3 rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-panel-hover disabled:opacity-50"
                  >
                    {busy === "survey" ? "Sending…" : "Send feedback"}
                  </button>
                </div>
              )}

              <div className="mt-6 flex justify-end">
                <button
                  onClick={onClose}
                  className="flex h-10 items-center justify-center rounded-md border border-border px-5 text-sm font-medium hover:bg-panel-hover"
                >
                  Close
                </button>
              </div>
            </div>
          ) : (
            <DonePanel done={done} onClose={onClose} />
          )
        ) : pausedActive ? (
          /* Already paused — reflect it, offer immediate resume. */
          <div>
            <div className="text-xs font-medium uppercase tracking-wider text-muted">Subscription paused</div>
            <h2 className="mt-2 text-2xl font-bold tracking-tight">
              Your plan is paused until {fmtDate(opts!.paused_until)}.
            </h2>
            <p className="mt-3 text-sm text-muted">
              Billing is on hold and resumes automatically on that date — your watchlist, scans and
              alerts are all still here. Want it back sooner?
            </p>
            {error && <ErrorNote text={error} />}
            <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-end">
              <button onClick={onClose} className="rounded-md border border-border px-4 py-2 text-sm text-muted hover:bg-panel-hover">
                Keep it paused
              </button>
              <button
                onClick={resume}
                disabled={busy !== null}
                className="flex h-10 items-center justify-center rounded-md bg-gradient-to-r from-accent to-accent2 px-5 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-50"
              >
                {busy === "resume" ? "Resuming…" : "Resume now →"}
              </button>
            </div>
          </div>
        ) : (
          /* menu — offers AND the direct cancel, all on one screen */
          <div>
            <div className="text-xs font-medium uppercase tracking-wider text-muted">
              {opts?.canceled_at ? "Scheduled to cancel" : "Cancel subscription"}
            </div>
            <h2 className="mt-2 text-2xl font-bold tracking-tight">
              {opts?.canceled_at
                ? `Your ${tierLabel} plan is set to cancel.`
                : "Cancel now, or stay for less?"}
            </h2>
            <p className="mt-3 text-sm text-muted">
              {opts?.canceled_at
                ? "You'll keep full access until the end of your billing period. Changed your mind? Here's a reason to stay."
                : // Downgrade description derives from FREE_LIMITS (mirrors
                  // backend tier.py) — never overstate what cancelling costs.
                  `Cancelling means moving to Free: live scores for the top ${FREE_LIMITS.scannerRows} scanner rows, ${FREE_LIMITS.dailyLookups} look-ups a day, a ${FREE_LIMITS.watchlistTickers}-ticker watchlist, ${FREE_LIMITS.webPushAlerts} browser push alerts — no email or Telegram alerts. Cancel below, or take one of these instead.`}
            </p>

            {error && <ErrorNote text={error} />}

            {/* Save offer — visible but never a gate. */}
            {opts?.save_offer_available && (
              <div className="mt-5 rounded-xl border border-accent/40 bg-accent/5 p-4">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-accent">
                  One-time offer
                </div>
                <div className="mt-1 text-base font-semibold">50% off your next 3 months</div>
                <p className="mt-1 text-xs text-muted">
                  Same plan, half the price — applied automatically to your next three invoices.
                </p>
                <button
                  onClick={acceptSave}
                  disabled={busy !== null}
                  className="mt-3 flex h-10 w-full items-center justify-center rounded-md bg-gradient-to-r from-accent to-accent2 text-sm font-medium text-white transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-50"
                >
                  {busy === "save" ? "Applying…" : "Claim 50% off — keep my plan"}
                </button>
              </div>
            )}

            {/* Pause — only offered when not already scheduled to cancel. A
                pause is a softer alternative to outright cancellation. */}
            {!opts?.canceled_at && (
              <div className="mt-4 rounded-xl border border-border bg-panel p-4">
                <div className="text-base font-semibold">Or pause instead of cancelling</div>
                <p className="mt-1 text-xs text-muted">
                  Freeze billing for a month or three. We keep everything; you're not charged until it resumes.
                </p>
                <div className="mt-3 grid grid-cols-3 gap-2">
                  {[1, 2, 3].map((m) => (
                    <button
                      key={m}
                      onClick={() => pause(m)}
                      disabled={busy !== null}
                      className="rounded-md border border-border px-3 py-2 text-sm font-medium hover:border-accent hover:text-accent disabled:opacity-50"
                    >
                      {busy === `pause${m}` ? "…" : `${m} mo`}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {opts?.canceled_at ? (
              /* Already scheduled — nothing left to cancel; just close. */
              <div className="mt-6 flex justify-end">
                <button
                  onClick={onClose}
                  className="rounded-md border border-border px-4 py-2 text-sm text-muted hover:bg-panel-hover"
                >
                  Close
                </button>
              </div>
            ) : (
              /* THE one-click cancel — a real, clearly visible button on the
                 first screen that cancels immediately. No survey, no second
                 confirm. This is what makes "cancel in one click" true. */
              <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <button
                  onClick={directCancel}
                  disabled={busy !== null}
                  className="flex h-10 items-center justify-center rounded-md border border-down/50 bg-down/10 px-5 text-sm font-medium text-down transition-all hover:bg-down/20 active:scale-[0.98] disabled:opacity-50"
                >
                  {busy === "cancel" ? "Cancelling…" : "Just cancel my subscription"}
                </button>
                <button
                  onClick={onClose}
                  disabled={busy !== null}
                  className="rounded-md border border-border px-4 py-2 text-sm text-muted hover:bg-panel-hover disabled:opacity-50"
                >
                  Never mind, stay on {tierLabel}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function DonePanel({ done, onClose }: { done: { kind: DoneKind; detail?: string | null }; onClose: () => void }) {
  const copy: Record<Exclude<DoneKind, "canceled">, { title: string; body: string }> = {
    saved: {
      title: "Done — you're staying.",
      body: "Your next 3 months are 50% off, applied automatically. Same plan, half the price.",
    },
    paused: {
      title: "Plan paused.",
      body: done.detail
        ? `Billing is on hold until ${fmtDate(done.detail)} and resumes automatically. Everything's saved.`
        : "Billing is on hold and resumes automatically. Everything's saved.",
    },
    resumed: {
      title: "Welcome back.",
      body: "Billing has resumed and your plan is fully active again.",
    },
  };
  const c = copy[done.kind as Exclude<DoneKind, "canceled">];
  if (!c) return null;
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wider text-up">All set</div>
      <h2 className="mt-2 text-2xl font-bold tracking-tight">{c.title}</h2>
      <p className="mt-3 text-sm text-muted">{c.body}</p>
      <div className="mt-6 flex justify-end">
        <button
          onClick={onClose}
          className="flex h-10 items-center justify-center rounded-md border border-border px-5 text-sm font-medium hover:bg-panel-hover"
        >
          Close
        </button>
      </div>
    </div>
  );
}

function ErrorNote({ text }: { text: string }) {
  return (
    <div className="mt-4 rounded-md border border-down/30 bg-down/5 p-3 text-sm text-down">{text}</div>
  );
}
