"use client";

import { useCallback, useEffect, useState } from "react";
import { useUser } from "@/components/UserContext";
import { getWebPushStatus, subscribeToWebPush, testWebPush } from "@/lib/webPush";
import { api } from "@/lib/api";
import { trackEvent } from "@/lib/gtag";

const DISMISS_KEY = "tapeline_arm_alerts_dismissed";

/**
 * Alerts activation moment.
 *
 * Alerts are the #1 thing traders pay for, yet the usage data showed ZERO users
 * had ever set one — so the single most pay-worthy feature was never felt. This
 * card turns "arm an alert" into a one-click first-session action and delivers
 * an INSTANT sample push (via /api/me/push/test) so the value lands now, not
 * days later when a score happens to move. It also creates a real score rule on
 * a watched ticker so a live alert follows the sample.
 *
 * Free users get the web-push "taste" (a 2-rule allowance); hitting that small
 * cap is the high-intent free→paid moment the whole conversion plan hinges on.
 * Only shown when notification permission is still "default" (never asked) — a
 * "granted" user has already armed alerts; "denied"/"unsupported" can't be
 * resolved from here.
 */
export function ArmAlerts({ surface = "scanner" }: { surface?: "scanner" | "watchlist" } = {}) {
  const { user } = useUser();
  const [show, setShow] = useState(false);
  const [phase, setPhase] = useState<"idle" | "working" | "done" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [ticker, setTicker] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      if (!user) return;
      try {
        if (localStorage.getItem(DISMISS_KEY)) {
          trackEvent("alert_prompt_suppressed", { surface, reason: "dismissed" });
          return;
        }
      } catch {
        /* private mode — treat as not dismissed */
      }
      const status = await getWebPushStatus();
      if (status !== "default") {
        // Covers desktop Safari, iOS Safari outside an installed PWA, and
        // anyone who previously granted or denied. Silent until now, which is
        // why a zero armed-alert count was impossible to interpret.
        trackEvent("alert_prompt_suppressed", { surface, reason: `push_${status}` });
        return;
      }
      try {
        const wl = await api.watchlist(null);
        if (alive && wl.items.length > 0) setTicker(wl.items[0].symbol);
      } catch {
        /* no watchlist yet — still offer, with generic copy */
      }
      if (alive) {
        setShow(true);
        trackEvent("alert_prompt_shown", { surface });
      }
    })();
    return () => {
      alive = false;
    };
  }, [user]);

  const arm = useCallback(async () => {
    setPhase("working");
    setError(null);
    const sub = await subscribeToWebPush();
    if (!sub.ok) {
      setPhase("error");
      setError(sub.reason);
      trackEvent("alert_arm_failed", { surface, reason: sub.reason });
      return;
    }
    // Create a real score alert on a watched ticker so a LIVE alert follows the
    // sample. Best-effort: a duplicate or a cap-hit must not block the aha.
    let ruleCreated = false;
    if (ticker) {
      try {
        await api.alertRuleCreate({
          name: `${ticker} score move`,
          rule_type: "score",
          symbol: ticker,
          threshold: 5,
          channel: "web_push",
        });
        ruleCreated = true;
      } catch {
        /* rule already exists or the free web-push cap was reached */
        trackEvent("alert_arm_failed", { surface, reason: "rule_create_failed" });
      }
    } else {
      // No watched ticker, so no rule was even attempted. The old code still
      // reported `alert_armed` here, which is how an "armed alerts" number
      // could exceed the number of alert rules that exist.
      trackEvent("alert_arm_failed", { surface, reason: "no_ticker" });
    }
    // The aha: feel a sample alert land right now.
    await testWebPush().catch(() => {
      /* subscription is registered; the sample is best-effort */
    });
    // Only claim activation when a rule genuinely exists. This event used to
    // fire unconditionally — after a swallow-everything catch, and even when
    // `ticker` was null — so it counted successes that never happened while the
    // UI said "Alerts are on."
    if (ruleCreated) {
      trackEvent("alert_armed", { surface, symbol: ticker as string });
    }
    setPhase("done");
  }, [ticker, surface]);

  const dismiss = useCallback(() => {
    try {
      localStorage.setItem(DISMISS_KEY, "1");
    } catch {
      /* ignore */
    }
    setShow(false);
  }, []);

  if (!show) return null;

  if (phase === "done") {
    return (
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-accent/30 bg-accent/5 px-4 py-2.5 text-sm">
        <span className="text-fg">
          <strong className="font-medium">Alerts are on.</strong>{" "}
          {ticker ? (
            <>
              That sample is exactly what you&rsquo;ll get when <strong>{ticker}</strong>&rsquo;s score
              moves 5+ points.
            </>
          ) : (
            <>Add a ticker to your watchlist and we&rsquo;ll ping you when its score moves.</>
          )}
        </span>
        <button
          onClick={dismiss}
          className="shrink-0 rounded-md border border-accent/40 bg-accent/10 px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent/20"
        >
          Got it
        </button>
      </div>
    );
  }

  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-accent/30 bg-accent/5 px-4 py-2.5 text-sm">
      <span className="text-fg">
        <strong className="font-medium">Get pinged when a score moves.</strong>{" "}
        Turn on alerts and feel a sample land right now
        {ticker ? (
          <>
            {" "}
            — we&rsquo;ll watch <strong>{ticker}</strong> for you.
          </>
        ) : (
          <>.</>
        )}
        {phase === "error" && error && <span className="ml-2 text-down">{error}</span>}
      </span>
      <span className="flex shrink-0 items-center gap-2">
        <button
          onClick={arm}
          disabled={phase === "working"}
          className="rounded-md border border-accent/40 bg-accent/10 px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent/20 disabled:opacity-60"
        >
          {phase === "working" ? "Turning on…" : "Turn on alerts →"}
        </button>
        <button onClick={dismiss} className="text-xs text-muted hover:text-fg">
          Not now
        </button>
      </span>
    </div>
  );
}
