/**
 * /signup and /signin must ship a real form in their HTML, not a skeleton.
 *
 * WHAT WENT WRONG
 * ---------------
 * Every paid Meta ad lands on /signup, mostly on a phone inside the Facebook
 * in-app browser. Measured on the live site on 2026-09-06:
 *
 *   curl https://tapeline.io/signup?from=trial  ->  24,718 bytes
 *     <form           0
 *     <input          0
 *     type="email"    0
 *     type="password" 0
 *     visible text    251 characters, all of it the theme-detection script
 *
 *   curl https://tapeline.io/signin | grep -c "<input"  ->  0
 *
 * The form existed only after eleven JS chunks downloaded, parsed and ran. The
 * cause was not the form: each `page.tsx` was a `"use client"` component whose
 * subtree called `useSearchParams()`, and under STATIC prerendering Next bails
 * out of any such subtree and emits only the Suspense fallback.
 *
 * On /signup this is where the ad budget went. The Meta pixel loads
 * `afterInteractive`, so the landing-page-view event also waited on hydration —
 * the mechanical explanation for 27 recorded ad clicks producing 14 landing
 * page views. Roughly half of what was paid for left before the page existed,
 * and Meta never learned they had arrived. A second consequence: the
 * `?from=trial` headline the ad promises verbatim never reached the HTML, so a
 * non-JS fetch saw the generic default instead of the ad's own words.
 *
 * On /signin the cost is different but worse in kind. The trial pre-charge
 * notice sends people to billing to cancel or continue, and a signed-out click
 * lands here. An apparently empty page between a customer and cancelling a
 * charge is a complaint, not a conversion problem.
 *
 * THE FIX THIS PINS
 * -----------------
 * Each `page.tsx` is now a SERVER component that re-exports its client form and
 * marks the route `dynamic = "force-dynamic"`. Rendered per request, search
 * params are known, `useSearchParams()` resolves during SSR, and the form is in
 * the first byte. Verified against a production build (`next build` +
 * `next start`): /signup visible text 251 -> 3,810 characters with a real
 * <form>, email and password inputs; /signin 0 -> 1 form.
 *
 * Either half is enough to reintroduce the bug, so both are asserted:
 *   - adding "use client" to page.tsx makes it a client component again
 *   - removing force-dynamic returns the route to static prerendering
 *
 * Source text is stripped of comments first. This file's own explanation
 * contains both `"use client"` and `force-dynamic`, and each page.tsx docstring
 * explains the same history — a naive grep would match the prose and pass while
 * the code was wrong, which is the failure mode this repo keeps hitting.
 */
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const APP = resolve(__dirname, "../app");

const ROUTES = [
  { route: "signup", form: "SignUpForm.tsx" },
  { route: "signin", form: "SignInForm.tsx" },
] as const;

/** Strip block comments, line comments and JSDoc continuations — code only. */
function codeOnly(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n")
    .map((line) => {
      const t = line.trimStart();
      if (t.startsWith("//") || t.startsWith("*")) return "";
      return line;
    })
    .join("\n");
}

const pageCode = (route: string) =>
  codeOnly(readFileSync(join(APP, route, "page.tsx"), "utf8"));
const formCode = (route: string, form: string) =>
  codeOnly(readFileSync(join(APP, route, form), "utf8"));

describe("auth routes ship a form, not a skeleton", () => {
  it("the comment stripper actually removes prose (guards this file's own method)", () => {
    const stripped = codeOnly(
      [
        '/* "use client" in a block comment */',
        '// "use client" in a line comment',
        "const real = 1;",
      ].join("\n"),
    );
    expect(stripped).not.toMatch(/use client/);
    expect(stripped).toMatch(/const real = 1;/);
  });

  for (const { route, form } of ROUTES) {
    it(`/${route} page.tsx is a server component — no 'use client'`, () => {
      expect(pageCode(route)).not.toMatch(/["']use client["']/);
    });

    it(`/${route} forces per-request rendering`, () => {
      expect(pageCode(route)).toMatch(
        /export\s+const\s+dynamic\s*=\s*["']force-dynamic["']/,
      );
    });

    it(`/${route} page.tsx delegates to its client form and uses no hooks`, () => {
      const code = pageCode(route);
      expect(code).toMatch(new RegExp(`from\\s+["']\\./${form.replace(".tsx", "")}["']`));
      // A server component cannot use hooks; if one appears the split is broken.
      expect(code).not.toMatch(/\buseState\(|\buseEffect\(|\buseRouter\(/);
    });

    it(`/${route} client form still carries the interactive parts`, () => {
      // If someone folds the form back into page.tsx the server component would
      // need "use client" and the first assertion catches it. This one asserts
      // the split is real rather than a file that got emptied.
      const code = formCode(route, form);
      expect(code).toMatch(/["']use client["']/);
      expect(code).toMatch(/useSearchParams\(\)/);
      expect(code).toMatch(/type="email"/);
      expect(code).toMatch(/type="password"/);
    });
  }
});
