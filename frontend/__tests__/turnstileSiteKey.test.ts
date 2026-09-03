/**
 * The Turnstile site key must never be blank while the backend enforces it.
 *
 * This guards a production outage that ran for months undetected, because each
 * half of it looks correct in isolation and no test spanned the two:
 *
 *   1. `services/bot_protection.verify_turnstile()` returns True — a dev
 *      pass-through — only while CLOUDFLARE_TURNSTILE_SECRET_KEY is unset.
 *      The moment that Fly secret exists, Turnstile is ENFORCED, and a request
 *      arriving with no token gets `return False`.
 *   2. `app/signup/page.tsx` renders the widget only under
 *      `{TURNSTILE_SITE_KEY && ...}`. With NEXT_PUBLIC_TURNSTILE_SITE_KEY blank
 *      no widget ships at all, so the browser can never mint a token.
 *
 * Together: `routers/auth.py` raises 400 "Bot challenge failed" on EVERY
 * email/password signup. Not hypothetical — it was live. 32 accounts existed
 * and only the seeded owner had a password; every real user arrived through
 * Google OAuth, which bypasses /api/auth/signup and was the only working door.
 *
 * The asymmetry is why this is asserted here rather than trusted: the backend
 * cannot see whether the frontend has a key, and the frontend cannot see
 * whether the backend has a secret. CI can see one of them, so it checks that
 * one. If Turnstile is ever genuinely retired, unset the Fly secret first and
 * then delete this test — in that order.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/** `frontend/fly.toml` with `#` comments stripped, per the house rule. */
function flyTomlArgs(): string {
  const src = readFileSync(resolve(__dirname, "../fly.toml"), "utf8");
  return src.replace(/#.*$/gm, "");
}

function siteKey(): string {
  const m = flyTomlArgs().match(
    /NEXT_PUBLIC_TURNSTILE_SITE_KEY\s*=\s*"([^"]*)"/,
  );
  if (!m) {
    throw new Error(
      "NEXT_PUBLIC_TURNSTILE_SITE_KEY assignment not found in frontend/fly.toml. " +
        "It must be a [build.args] entry — NEXT_PUBLIC_* is inlined at build " +
        "time, so a Fly secret of the same name is a no-op.",
    );
  }
  return m[1];
}

function signupSource(): string {
  return readFileSync(resolve(__dirname, "../app/signup/page.tsx"), "utf8");
}

describe("Turnstile site key", () => {
  it("is set in frontend/fly.toml build args", () => {
    expect(siteKey()).not.toBe("");
  });

  it("looks like a real Cloudflare Turnstile site key", () => {
    // Cloudflare issues site keys as `0x` followed by base62. The shape check
    // catches a placeholder like "TODO" or a secret key pasted by mistake
    // (those start `0x4AAAAAA...` too but are far longer and must never ship
    // to the browser).
    expect(siteKey()).toMatch(/^0x[A-Za-z0-9_-]{10,40}$/);
  });

  it("is the key the signup page actually reads", () => {
    // If the page stopped reading this env var the build arg would be inert
    // and this whole suite would be guarding nothing.
    expect(signupSource()).toContain(
      "process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY",
    );
  });

  it("still gates the widget render on that key", () => {
    // This is the half that makes a blank key fatal rather than merely
    // permissive. If the render ever becomes unconditional, a blank key would
    // be survivable and the first assertion could be relaxed.
    expect(signupSource()).toMatch(/TURNSTILE_SITE_KEY\s*&&/);
  });

  it("still submits the token the backend demands", () => {
    expect(signupSource()).toContain("turnstile_token");
  });
});
