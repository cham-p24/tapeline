/**
 * safeNext — the open-redirect guard on the `?next=` post-auth redirect.
 *
 * It must return `next` ONLY for an internal same-origin path. The subtle
 * case these tests pin: the WHATWG URL parser strips TAB/LF/CR from a URL
 * before parsing, so a value like `/\t//evil.com` passes a naive `//` prefix
 * check (index 1 is TAB, not `/`) yet resolves to `https://evil.com`. That is
 * a post-auth open redirect — the guard must strip those control chars first
 * and validate the cleaned value.
 */
import { describe, it, expect } from "vitest";
import { safeNext } from "@/lib/safeNext";

const FALLBACK = "/app/scanner";

describe("safeNext", () => {
  it("passes ordinary internal paths through", () => {
    expect(safeNext("/app/billing?intent=premium")).toBe("/app/billing?intent=premium");
    expect(safeNext("/scorecard")).toBe("/scorecard");
    expect(safeNext("/")).toBe("/");
  });

  it("rejects protocol-relative and scheme redirects", () => {
    expect(safeNext("//evil.com")).toBe(FALLBACK);
    expect(safeNext("/\\evil.com")).toBe(FALLBACK);
    expect(safeNext("https://evil.com")).toBe(FALLBACK);
    expect(safeNext("http://evil.com")).toBe(FALLBACK);
  });

  it("rejects control-char smuggling that the URL parser would strip", () => {
    // TAB, LF, CR at index 1 — each resolves to //evil.com once the browser
    // strips the control char. Pre-fix these returned the raw string.
    expect(safeNext("/\t//evil.com")).toBe(FALLBACK);
    expect(safeNext("/\n//evil.com")).toBe(FALLBACK);
    expect(safeNext("/\r//evil.com")).toBe(FALLBACK);
    // Control char splitting the `\` backslash variant too.
    expect(safeNext("/\t/\\evil.com")).toBe(FALLBACK);
  });

  it("falls back for empty / nullish input", () => {
    expect(safeNext(null)).toBe(FALLBACK);
    expect(safeNext(undefined)).toBe(FALLBACK);
    expect(safeNext("")).toBe(FALLBACK);
    expect(safeNext("relative/path")).toBe(FALLBACK);
  });

  it("honours a custom fallback", () => {
    expect(safeNext("//evil.com", "/home")).toBe("/home");
  });
});
