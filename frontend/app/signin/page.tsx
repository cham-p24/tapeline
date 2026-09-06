/**
 * /signin — the route a returning customer lands on, including from the
 * pre-charge trial email.
 *
 * Same defect and same fix as /signup: the form lives in a client component
 * that calls `useSearchParams()`, and under STATIC prerendering Next bails out
 * of that subtree and ships only the Suspense fallback. Measured on the live
 * site 2026-09-06, `curl https://tapeline.io/signin | grep -c "<input"` = 0 —
 * a visitor on a slow phone saw a heading and no way to sign in.
 *
 * That matters beyond conversion. The trial pre-charge notice sends people to
 * the billing page to cancel or continue, and a signed-out click lands here. A
 * page that appears empty until ~200KB of JS executes is the wrong thing to put
 * between a customer and cancelling a charge.
 *
 * `force-dynamic` renders per request, so `useSearchParams()` resolves during
 * SSR and the form is in the first byte. Metadata stays in layout.tsx.
 *
 * Guarded by __tests__/signupFormIsServerRendered.test.tsx.
 */
import SignInScreen from "./SignInForm";

export const dynamic = "force-dynamic";

export default function SignInPage() {
  return <SignInScreen />;
}
