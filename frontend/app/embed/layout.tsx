/**
 * Minimal layout for /embed/* routes.
 *
 * Strips the global MarketingNav + MarketingFooter that the root layout
 * doesn't add directly but that every page-level component opts into.
 * Renders just the children inside a transparent, scroll-locked body so
 * the embedded card sits flush inside its iframe — no chrome, no fonts
 * other than the inherited Inter, no scrollbars.
 *
 * Why a separate layout: iframes that include the marketing nav waste
 * 80px of vertical space and look unprofessional embedded in someone
 * else's content. Embed views need to be visually contained to exactly
 * the iframe size.
 *
 * Robots: every /embed/* page is `noindex, follow` — we want the embeds
 * to drive backlinks to /t/{TICKER} and /, not for the embed page
 * itself to compete with /t/{TICKER} in SERPs. Follow=true so link
 * equity from "powered by Tapeline" footer still flows.
 */
import type { Metadata } from "next";

export const metadata: Metadata = {
  robots: {
    index: false,
    follow: true,
    googleBot: { index: false, follow: true },
  },
};

export default function EmbedLayout({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        background: "transparent",
        margin: 0,
        padding: 0,
        // Inherit Inter from the root layout's <body> font stack.
        fontFamily:
          "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
      }}
    >
      {children}
    </div>
  );
}
