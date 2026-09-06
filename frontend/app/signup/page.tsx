/**
 * /signup — the page every paid ad lands on.
 *
 * WHY THIS FILE IS A THIN SERVER COMPONENT
 * ----------------------------------------
 * The form lives in SignUpForm.tsx, a client component: it needs Turnstile,
 * form state and `useSearchParams()`. That last one is the reason this split
 * exists.
 *
 * Under STATIC prerendering, a client component that calls `useSearchParams()`
 * makes Next bail out of prerendering that subtree — it emits only the Suspense
 * fallback and renders the real content in the browser. So the HTML served for
 * /signup contained a heading and sub-line and **zero `<input>` elements**: 251
 * characters of visible text, with the form appearing only after eleven JS
 * chunks downloaded, parsed and executed.
 *
 * That is not a cosmetic problem, it is where the ad budget went. Every Meta ad
 * lands here, mostly on a phone inside the Facebook in-app browser. A visitor on
 * mobile data saw a blank page until hydration finished. Worse, the Meta pixel
 * loads `afterInteractive`, so the landing-page-view event ALSO waited on
 * hydration — which is the mechanical explanation for 27 recorded ad clicks
 * producing only 14 landing page views. Roughly half of what was paid for left
 * before the page existed, and Meta never learned they had arrived.
 *
 * `force-dynamic` renders the route per request. Search params are known at
 * that point, `useSearchParams()` resolves during SSR instead of suspending, and
 * the form ships in the first byte of HTML.
 *
 * The cost is that /signup is no longer statically cached. That is the right
 * trade for a form whose content already varies by `?from=`, `?plan=` and
 * `?ref=` — it was never meaningfully cacheable, it was just being prerendered
 * empty.
 *
 * Metadata stays in layout.tsx (a server component), which is why moving the
 * page's own body into a client file costs nothing there.
 *
 * Guarded by __tests__/signupFormIsServerRendered.test.tsx.
 */
import SignUpScreen from "./SignUpForm";

export const dynamic = "force-dynamic";

export default function SignUpPage() {
  return <SignUpScreen />;
}
