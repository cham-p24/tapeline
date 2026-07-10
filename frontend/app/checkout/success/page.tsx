import type { Metadata } from "next";
import { CheckoutSuccessClient } from "./CheckoutSuccessClient";

/**
 * PUBLIC post-payment landing for the one-click email checkout flow.
 *
 * The email flow's whole premise is a user with no session (they forgot
 * their password — that's why the email links straight into Stripe). The
 * authed flow returns to /app/billing, but that sits behind the login-wall
 * middleware, which would dump a PAYING customer on the sign-in page and
 * silently drop the ?checkout=success params the conversion analytics need.
 * This page is the public equivalent: confirm the payment, fire the same
 * trial_converted + subscribe events, and hand them a sign-in path.
 *
 * Server wrapper so we can export metadata (noindex — a payment
 * confirmation page has no business in search results).
 */
export const metadata: Metadata = {
  title: "Payment received — Tapeline",
  robots: { index: false, follow: false },
};

export default function CheckoutSuccessPage() {
  return <CheckoutSuccessClient />;
}
