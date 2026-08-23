/**
 * The privacy policy must describe the build it is part of — in BOTH states.
 *
 * The failure this prevents: setting NEXT_PUBLIC_META_PIXEL_ID switches on a
 * third-party advertising tracker AND, if the policy prose were hand-written,
 * silently makes a legal page false — in the same deploy, with nothing to
 * catch it. A privacy policy that says "nothing has ever been sent to Meta"
 * while the pixel is live is the kind of error that matters.
 *
 * So the page renders its status clauses from lib/trackers, the same constants
 * that gate the scripts. These tests run the page under both configurations
 * and assert the claims flip.
 *
 * Note on mechanism: lib/trackers reads process.env at MODULE LOAD, because
 * NEXT_PUBLIC_* is compile-time-inlined in a real build. So each case sets the
 * env and re-imports with a reset module registry, rather than mutating a
 * value that is already frozen.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render } from "@testing-library/react";

vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => null }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => null }));

const ORIGINAL = { ...process.env };

beforeEach(() => {
  vi.resetModules();
});

afterEach(() => {
  process.env = { ...ORIGINAL };
});

async function renderPolicyWith(env: Record<string, string | undefined>) {
  for (const [k, v] of Object.entries(env)) {
    if (v === undefined) delete process.env[k];
    else process.env[k] = v;
  }
  const mod = await import("@/app/legal/privacy/page");
  const Page = mod.default;
  const { container } = render(<Page />);
  return (container.textContent ?? "").replace(/\s+/g, " ");
}

describe("privacy policy — Meta disclosure tracks the build", () => {
  it("says Meta is NOT enabled when the pixel id is unset", async () => {
    const text = await renderPolicyWith({ NEXT_PUBLIC_META_PIXEL_ID: undefined });

    expect(text).toMatch(/Meta \(Facebook & Instagram\)/);
    expect(text).toMatch(/nothing has ever been sent to Meta/i);
    expect(text).not.toMatch(/Meta \(Facebook & Instagram\)[^.]*Currently enabled/i);
  });

  it("says Meta IS enabled when the pixel id is set", async () => {
    const text = await renderPolicyWith({ NEXT_PUBLIC_META_PIXEL_ID: "123456789" });

    // The stale claim must be gone — this is the whole point of the file.
    expect(text).not.toMatch(/nothing has ever been sent to Meta/i);
    expect(text).toMatch(/Currently enabled/i);
    // And the tense flips from conditional to present.
    expect(text).not.toMatch(/If we enable Meta advertising/i);
    expect(text).toMatch(/Our servers also send Meta a hashed version/i);
  });

  it("discloses the cookies and the hashing caveat in BOTH states", async () => {
    for (const id of [undefined, "123456789"]) {
      vi.resetModules();
      const text = await renderPolicyWith({ NEXT_PUBLIC_META_PIXEL_ID: id });
      expect(text).toMatch(/_fbp/);
      expect(text).toMatch(/_fbc/);
      expect(text).toMatch(/hashing is not anonymisation/i);
      // The scoping promise is load-bearing: it is why the policy can say Meta
      // cannot see which tickers you look at.
      expect(text).toMatch(/never on the signed-in app/i);
    }
  });
});

describe("privacy policy — the other trackers too", () => {
  it("flips PostHog, Clarity and Plausible independently", async () => {
    const off = await renderPolicyWith({
      NEXT_PUBLIC_POSTHOG_KEY: undefined,
      NEXT_PUBLIC_CLARITY_PROJECT_ID: undefined,
      NEXT_PUBLIC_PLAUSIBLE_DOMAIN: undefined,
      NEXT_PUBLIC_META_PIXEL_ID: undefined,
    });
    expect(off).toMatch(/none of them is currently enabled/i);

    vi.resetModules();
    const on = await renderPolicyWith({
      NEXT_PUBLIC_CLARITY_PROJECT_ID: "abc123",
      NEXT_PUBLIC_POSTHOG_KEY: undefined,
      NEXT_PUBLIC_PLAUSIBLE_DOMAIN: undefined,
      NEXT_PUBLIC_META_PIXEL_ID: undefined,
    });
    expect(on).not.toMatch(/none of them is currently enabled/i);
    // Assert the CLARITY BULLET specifically, not a bare /currently enabled/,
    // which would also match inside the sentence "none of them is currently
    // enabled" and pass for the wrong reason.
    expect(on).toMatch(/Microsoft Clarity — session replay and heatmaps\. Currently enabled\./);
    // The two that are still off must still say so.
    expect(on).toMatch(/PostHog — product analytics\. Not currently enabled\./);
    expect(on).toMatch(/Plausible — privacy-focused traffic analytics\. Not currently enabled\./);
  });

  it("always names Google Analytics and Google Ads as active — they have hardcoded defaults", async () => {
    const text = await renderPolicyWith({});
    expect(text).toMatch(/Google Analytics 4 and Google Ads are active/i);
  });
});

describe("lib/trackers — every tracker is disclosed", () => {
  it("has no tracker key that the policy fails to mention", async () => {
    const { trackerEnabled } = await import("@/lib/trackers");
    const text = await renderPolicyWith({});

    // Human-readable name each key must appear under in the policy. Adding a
    // tracker to lib/trackers without disclosing it should fail here.
    const disclosureFor: Record<string, RegExp> = {
      ga4: /Google \(Analytics 4/i,
      googleAds: /Google Ads/i,
      meta: /Meta \(Facebook & Instagram\)/,
      clarity: /Microsoft Clarity/,
      plausible: /Plausible/,
      posthog: /PostHog/,
    };

    for (const key of Object.keys(trackerEnabled)) {
      expect(
        disclosureFor[key],
        `lib/trackers has "${key}" but privacyPolicyTruth.test.tsx has no disclosure pattern for it — add the tracker to the privacy policy, then add its pattern here`,
      ).toBeDefined();
      expect(text, `privacy policy does not disclose tracker "${key}"`).toMatch(
        disclosureFor[key],
      );
    }
  });
});
