/**
 * The pre-charge notice timing we PROMISE matches the one we SEND (T-09,
 * founder-approved 2026-09-14).
 *
 * The notice moved from Stripe's `trial_will_end` (about 3 days out) to our
 * own daily drip at about 7 days (Visa requires at least 7, Mastercard 3 to
 * 7). The copy kept saying "three days before". The number now lives in
 * lib/trial.ts (PRECHARGE_NOTICE_DAYS), pinned to the backend drip window by
 * backend/tests/test_precharge_notice_copy_matches_drip.py.
 *
 * /legal/refund is dated legal text, so its original sentence is kept as
 * published and superseded by a dated revision note rather than rewritten.
 */
import { describe, it, expect, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { render, screen } from "@testing-library/react";

vi.mock("@/components/MarketingNav", () => ({ MarketingNav: () => <nav /> }));
vi.mock("@/components/MarketingFooter", () => ({ MarketingFooter: () => <footer /> }));

import RefundPolicyPage from "@/app/legal/refund/page";
import { PRECHARGE_NOTICE_DAYS, PRECHARGE_NOTICE_PHRASE } from "@/lib/trial";

const ROOT = join(__dirname, "..");

describe("PRECHARGE_NOTICE_DAYS", () => {
  it("is 7 and the phrase interpolates it", () => {
    expect(PRECHARGE_NOTICE_DAYS).toBe(7);
    expect(PRECHARGE_NOTICE_PHRASE).toBe("about 7 days before");
  });
});

describe("/legal/refund", () => {
  it("carries a dated revision note that states the real timing", () => {
    render(<RefundPolicyPage />);
    const note = screen.getByTestId("refund-precharge-revision");
    const text = (note.textContent ?? "").replace(/\s+/g, " ");
    expect(text).toMatch(/^Updated 14 September 2026:/);
    expect(text).toContain(`goes out ${PRECHARGE_NOTICE_PHRASE} that charge, not three days before`);
    expect(text).toContain("a backup reminder goes out about three days before the charge instead");
    expect(text).not.toMatch(/second reminder/);
  });
});

describe("sell surfaces owned by this change", () => {
  // Rendered copy only (comments stripped). The refund page is excluded on
  // purpose: its original, dated sentence stays as published.
  const FILES = [
    "app/signup/SignUpForm.tsx",
    "app/app/start/page.tsx",
    "app/free-stock-scanner-no-credit-card/page.tsx",
    "public/llms.txt",
  ];
  it.each(FILES)("%s no longer promises a three-day notice", (rel) => {
    let src = readFileSync(join(ROOT, rel), "utf-8");
    if (!rel.endsWith(".txt")) {
      src = src.replace(/\/\*[\s\S]*?\*\//g, " ").replace(/^\s*\/\/.*$/gm, " ");
    }
    expect(src).not.toMatch(/three days (?:before|ahead)/i);
  });
});
