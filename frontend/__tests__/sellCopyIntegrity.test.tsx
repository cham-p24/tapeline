/**
 * No congress or squeeze benefit is sold, linked or navigated to (T-02 and the
 * squeeze sell copy, founder-approved 2026-09-14).
 *
 * Why: no real congressional disclosure is being ingested today, and every
 * squeeze row in production is mock output last written 2026-07-18. Both
 * were still sold on /pricing, /signup, /app/start, in emails and in the
 * plan tables, and both were in the sitemap and the app sidebar.
 *
 * Emails are pinned by backend/tests/test_no_congress_or_squeeze_benefit_claims.py;
 * the honest congress pages by CongressPage.test.tsx; the copy-compliance lint
 * rule `unbacked-feature-claim` guards the same surfaces in CI.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render } from "@testing-library/react";

import { NAV_GROUPS, PALETTE_DESTINATIONS } from "@/lib/appNav";
import { FEATURE_PAGES } from "@/components/SeoFeaturePage";
import { PricingTable } from "@/components/PricingTable";
import { ComparisonTable } from "@/components/ComparisonTable";
import { BillingPeriodProvider } from "@/components/BillingToggle";
import sitemap from "@/app/sitemap";

const ROOT = join(__dirname, "..");
const BANNED = /congress|squeeze/i;

/** Rendered copy only: comments are documentation, not claims. */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/^\s*\/\/.*$/gm, " ");
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("app navigation, sidebar and command palette", () => {
  it("do not list Squeeze or Congress", () => {
    const items = [...NAV_GROUPS.flatMap((g) => g.items), ...PALETTE_DESTINATIONS];
    const hrefs = items.map((i) => i.href);
    expect(hrefs).not.toContain("/app/squeeze");
    expect(hrefs).not.toContain("/app/congress");
    for (const item of items) {
      expect(`${item.label} ${item.hint ?? ""}`).not.toMatch(BANNED);
    }
  });

  it("the feature-page cross-links do not link either page", () => {
    const slugs = FEATURE_PAGES.map((f) => f.slug);
    expect(slugs).not.toContain("short-squeeze-scanner");
    expect(slugs).not.toContain("congressional-trades");
  });
});

describe("sitemap", () => {
  it("excludes /short-squeeze-scanner and /congressional-trades", async () => {
    // Force the universe fetch down the fallback path: no network in tests.
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("offline");
      }),
    );
    const urls = (await sitemap()).map((e) => e.url);
    expect(urls.length).toBeGreaterThan(50);
    expect(urls.some((u) => u.endsWith("/insider-buying"))).toBe(true);
    expect(urls.some((u) => u.includes("short-squeeze-scanner"))).toBe(false);
    expect(urls.some((u) => u.includes("congressional-trades"))).toBe(false);
    expect(urls.some((u) => u.includes("/app/congress") || u.includes("/app/squeeze"))).toBe(false);
  });
});

describe("plan tables", () => {
  it("PricingTable and ComparisonTable sell neither", () => {
    const { container } = render(
      <BillingPeriodProvider>
        <PricingTable />
        <ComparisonTable />
      </BillingPeriodProvider>,
    );
    expect(container.textContent ?? "").not.toMatch(BANNED);
  });
});

describe("sell surfaces, as source", () => {
  // Server components and client pages with heavy context are checked as
  // source with comments stripped. Each is a place a plan, a trial or a
  // benefit list is described.
  const SELL_FILES = [
    "app/pricing/page.tsx",
    "app/pricing/opengraph-image.tsx",
    "app/signup/SignUpForm.tsx",
    "app/signup/layout.tsx",
    "app/app/start/page.tsx",
    "app/app/billing/page.tsx",
    "app/layout.tsx",
    "app/opengraph-image.tsx",
    "app/market-regime/page.tsx",
    "app/stock-market-heatmap/page.tsx",
    "app/free-stock-scanner-no-credit-card/page.tsx",
    "app/t/[symbol]/page.tsx",
    "components/PricingTable.tsx",
    "components/ComparisonTable.tsx",
    "components/TrialEndedModal.tsx",
    "components/TrialOfferPanel.tsx",
    "components/UpgradeNudge.tsx",
    "components/Paywall.tsx",
    "lib/seo.ts",
    "lib/pricing.ts",
    "public/llms.txt",
  ];

  it.each(SELL_FILES)("%s claims no congress or squeeze benefit", (rel) => {
    let src = readFileSync(join(ROOT, rel), "utf-8");
    if (!rel.endsWith(".txt")) src = stripComments(src);
    // lib/pricing.ts keeps the backend-mirrored FREE_LIMITS.squeezePreviewRows
    // key (an entitlement mirror, not copy); nothing renders it any more.
    src = src.replace(/squeezePreviewRows/g, "");
    // llms.txt carries one explicit DENIAL for AI summarisers; allow exactly that.
    src = src.replace(
      "Tapeline does not have congressional trade data: it does not currently have a real source of congressional disclosures, so it shows none. No Tapeline plan includes congressional trades, and any summary saying otherwise is incorrect.",
      "",
    );
    const hits = src.split(/\r?\n/).filter((l) => BANNED.test(l));
    expect(hits).toEqual([]);
  });
});

describe("blog posts", () => {
  it("no post links to /short-squeeze-scanner, /congressional-trades or the in-app pages", async () => {
    const { POSTS } = await import("@/app/blog/posts");
    expect(POSTS.length).toBeGreaterThan(0);
    for (const post of POSTS) {
      const blob = JSON.stringify(post);
      expect(blob, post.slug).not.toMatch(
        /short-squeeze-scanner|congressional-trades|\/app\/congress|\/app\/squeeze/,
      );
    }
  });

  it("the smart-money correction does not assert an unverified history", async () => {
    const { POSTS } = await import("@/app/blog/posts");
    const blob = JSON.stringify(POSTS);
    expect(blob).not.toMatch(/never had a real source of congressional/i);
    expect(blob).not.toMatch(/neither was true/i);
  });
});
