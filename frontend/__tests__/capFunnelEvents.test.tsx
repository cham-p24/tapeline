/**
 * Free→paid micro-funnel events (lib/gtag.ts).
 *
 * The four helpers (trackCapHit / trackGateEncountered / trackUpgradePromptShown
 * / trackUpgradePromptClicked) must:
 *   1. dispatch the right GA4 event name with the right params, and
 *   2. stay GA4-only — never forward to Google Ads (they're on-site conversion
 *      diagnostics, not acquisition conversions), even when an Ads id is set.
 *
 * If the event name or params drift, the funnel roll-up in GA4 silently breaks
 * and the free-tier-tightening decision loses its data — worth a guard.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

type GtagSpy = ReturnType<typeof vi.fn>;

function installGtag(): GtagSpy {
  const spy = vi.fn();
  (window as unknown as { gtag?: GtagSpy }).gtag = spy;
  return spy;
}

describe("free→paid micro-funnel events", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    // Pin an Ads id so the "GA4-only, no Ads forwarding" assertions are
    // meaningful — the events must NOT forward even with an id present.
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_ADS_ID", "AW-123456789");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    delete (window as unknown as { gtag?: GtagSpy }).gtag;
  });

  it("trackCapHit dispatches cap_hit with {cap, surface}", async () => {
    const gtag = installGtag();
    const { trackCapHit } = await import("@/lib/gtag");

    trackCapHit("daily_lookups", "ticker");

    expect(gtag).toHaveBeenCalledWith("event", "cap_hit", {
      cap: "daily_lookups",
      surface: "ticker",
    });
    // GA4-only: no Google Ads conversion mirror.
    expect(gtag).not.toHaveBeenCalledWith("event", "conversion", expect.anything());
  });

  it("trackGateEncountered dispatches gate_encountered with {feature, surface}", async () => {
    const gtag = installGtag();
    const { trackGateEncountered } = await import("@/lib/gtag");

    trackGateEncountered("squeeze", "paywall");

    expect(gtag).toHaveBeenCalledWith("event", "gate_encountered", {
      feature: "squeeze",
      surface: "paywall",
    });
    expect(gtag).not.toHaveBeenCalledWith("event", "conversion", expect.anything());
  });

  it("trackUpgradePromptShown dispatches upgrade_prompt_shown with {surface, feature}", async () => {
    const gtag = installGtag();
    const { trackUpgradePromptShown } = await import("@/lib/gtag");

    trackUpgradePromptShown("paywall", "watchlist");

    expect(gtag).toHaveBeenCalledWith("event", "upgrade_prompt_shown", {
      surface: "paywall",
      feature: "watchlist",
    });
    expect(gtag).not.toHaveBeenCalledWith("event", "conversion", expect.anything());
  });

  it("trackUpgradePromptShown omits feature when not provided", async () => {
    const gtag = installGtag();
    const { trackUpgradePromptShown } = await import("@/lib/gtag");

    trackUpgradePromptShown("scanner");

    expect(gtag).toHaveBeenCalledWith("event", "upgrade_prompt_shown", {
      surface: "scanner",
    });
  });

  it("trackUpgradePromptClicked dispatches upgrade_prompt_clicked with {surface, feature}", async () => {
    const gtag = installGtag();
    const { trackUpgradePromptClicked } = await import("@/lib/gtag");

    trackUpgradePromptClicked("paywall", "watchlist");

    expect(gtag).toHaveBeenCalledWith("event", "upgrade_prompt_clicked", {
      surface: "paywall",
      feature: "watchlist",
    });
    expect(gtag).not.toHaveBeenCalledWith("event", "conversion", expect.anything());
  });

  it("never throws when gtag has not loaded (ad blocker / SSR-hydration race)", async () => {
    // intentionally do NOT install window.gtag
    const { trackCapHit, trackUpgradePromptShown } = await import("@/lib/gtag");
    expect(() => trackCapHit("scanner_rows", "scanner")).not.toThrow();
    expect(() => trackUpgradePromptShown("paywall")).not.toThrow();
  });
});
