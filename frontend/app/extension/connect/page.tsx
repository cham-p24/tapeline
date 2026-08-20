import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { pageMeta } from "@/lib/seo";

import ConnectClient from "./ConnectClient";

/**
 * /extension/connect — where the browser extension gets its credential.
 *
 * The extension cannot use the session cookie: `tapeline_session` is
 * SameSite=Lax, and while tapeline.io and api.tapeline.io are same-site (shared
 * registrable domain), a chrome-extension:// origin is not. This page runs on
 * tapeline.io, so it CAN use the cookie — it mints a connect token on the
 * user's behalf and hands it over for pasting.
 *
 * Signed-out visitors are sent to /signup rather than /signin. Requiring an
 * account is the point of the flow, and someone arriving here from the
 * extension has not necessarily got one yet.
 */
export const metadata = pageMeta({
  title: "Connect the Tapeline extension",
  description:
    "Sign in and copy your connect code to link the Tapeline browser extension to your account.",
  path: "/extension/connect",
});

// Not a discovery surface — it only makes sense mid-flow from the extension.
export const robots = { index: false, follow: false };

export default function ExtensionConnectPage() {
  return (
    <main>
      <MarketingNav />
      <div className="mx-auto max-w-xl px-4 py-14 sm:px-6">
        <div className="font-mono text-xs font-medium uppercase tracking-wider text-accent">
          Browser extension
        </div>
        <h1 className="mt-3 text-3xl font-bold tracking-tight text-balance sm:text-4xl">
          Connect the extension
        </h1>
        <p className="mt-4 leading-relaxed text-muted">
          The extension works with a Tapeline account. Copy the code below and paste it into
          the extension&rsquo;s popup — you only do this once per browser.
        </p>

        <ConnectClient />

        <p className="mt-10 text-sm leading-relaxed text-subtle">
          The code links the extension to your account. It expires after 180 days, and signing
          out of every device revokes it immediately. What the extension reads is set out in the{" "}
          <a className="text-accent" href="/legal/extension-privacy">
            extension privacy notice
          </a>
          .
        </p>
      </div>
      <MarketingFooter />
    </main>
  );
}
