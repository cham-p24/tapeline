/**
 * Regression guard for React error #31 on FastAPI validation errors.
 *
 * Production Sentry showed:
 *   Minified React error #31; args[]=object with keys {type, loc, msg, input, ctx}
 *
 * That key set is exactly a Pydantic v2 validation error item. FastAPI returns
 * an ARRAY of them under `detail` on a 422, and several components did
 * `setError(body.detail || "fallback")` — putting an array of objects into
 * string-typed state and white-screening the page when React rendered it.
 *
 * The subtle part, and the reason the bug survived review: `||` does not help.
 * A non-empty array is truthy, so the fallback never runs. The guard must be
 * on the TYPE, which is what errorText does.
 */
import { describe, it, expect } from "vitest";
import { errorText } from "@/lib/errorText";

// The literal shape FastAPI sends for a 422, matching the Sentry payload.
const VALIDATION_422 = {
  detail: [
    {
      type: "value_error",
      loc: ["body", "email"],
      msg: "value is not a valid email address",
      input: "not-an-email",
      ctx: { reason: "An email address must have an @-sign." },
    },
    {
      type: "string_too_short",
      loc: ["body", "name"],
      msg: "String should have at least 1 character",
      input: "",
      ctx: { min_length: 1 },
    },
  ],
};

describe("errorText", () => {
  it("always returns a string, never an object or array", () => {
    for (const body of [
      VALIDATION_422,
      { detail: "a plain message" },
      { detail: { nested: "object" } },
      { detail: null },
      { detail: [] },
      {},
      null,
      undefined,
      "not an object at all",
    ]) {
      expect(typeof errorText(body, "fallback")).toBe("string");
    }
  });

  it("passes a plain string detail straight through", () => {
    expect(errorText({ detail: "Card was declined." }, "fallback")).toBe("Card was declined.");
  });

  it("renders a 422 array as readable field messages instead of crashing", () => {
    const out = errorText(VALIDATION_422, "Could not send.");
    expect(out).toContain("email: value is not a valid email address");
    expect(out).toContain("name: String should have at least 1 character");
    // The whole point: no "[object Object]" leaking into the UI.
    expect(out).not.toContain("[object Object]");
  });

  it("does not let a truthy-but-unrenderable detail beat the fallback", () => {
    // This is the exact case `body.detail || fallback` got wrong.
    expect(errorText({ detail: { type: "x" } }, "fallback")).toBe("fallback");
    expect(errorText({ detail: [{ no_msg: true }] }, "fallback")).toBe("fallback");
  });

  it("falls back on empty, blank, or missing detail", () => {
    expect(errorText({ detail: "" }, "fallback")).toBe("fallback");
    expect(errorText({ detail: "   " }, "fallback")).toBe("fallback");
    expect(errorText({ detail: [] }, "fallback")).toBe("fallback");
    expect(errorText({}, "fallback")).toBe("fallback");
    expect(errorText(null, "fallback")).toBe("fallback");
    expect(errorText(undefined, "fallback")).toBe("fallback");
  });

  it("survives a detail array of bare strings", () => {
    expect(errorText({ detail: ["first", "second"] }, "fallback")).toBe("first; second");
  });

  it("omits the 'body' prefix from the field path", () => {
    const out = errorText(VALIDATION_422, "fallback");
    expect(out).not.toContain("body:");
  });
});
