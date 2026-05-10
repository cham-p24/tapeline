import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";
import { UserProvider } from "@/components/UserContext";

const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "";
// Env-gated analytics — set NEXT_PUBLIC_PLAUSIBLE_DOMAIN to "tapeline.io"
// (or your custom Plausible host via NEXT_PUBLIC_PLAUSIBLE_SCRIPT) to flip
// on. No personal data, GDPR-friendly, ~1KB script.
const PLAUSIBLE_DOMAIN = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN || "";
const PLAUSIBLE_SCRIPT =
  process.env.NEXT_PUBLIC_PLAUSIBLE_SCRIPT || "https://plausible.io/js/script.js";

export const metadata: Metadata = {
  title: {
    default: "Tapeline — One score per stock. Live, transparent, public scorecard.",
    template: "%s — Tapeline",
  },
  description:
    "Live quantitative scanner: every US ticker gets one 0-100 score and one plain-English sentence. Six-factor formula is public. Track record updates daily. Pro $29.99/mo, Premium $49.99/mo (USD).",
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "https://tapeline.io"),
  applicationName: "Tapeline",
  authors: [{ name: "Tapeline", url: "https://tapeline.io" }],
  keywords: [
    "stock scanner",
    "quantitative scoring",
    "live market scanner",
    "squeeze detection",
    "congressional trades",
    "13F holdings",
    "market regime",
    "retail trading",
  ],
  openGraph: {
    title: "Tapeline — Read the tape. Live.",
    description:
      "One score and one sentence per US ticker. Squeeze detection, market regime, congressional trades, 13F holdings — synthesized live. Public scorecard from day 1.",
    url: "https://tapeline.io",
    siteName: "Tapeline",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "Tapeline — Read the tape. Live.",
    description:
      "Live quantitative scanner. One score per ticker. Public formula. Public scorecard.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1 },
  },
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon.ico", sizes: "any" },
    ],
    shortcut: "/favicon.svg",
    apple: "/favicon.svg",
  },
  // Future: replace with verified handles when accounts are created.
  // twitter: { ..., creator: "@tapelineio", site: "@tapelineio" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
        {/* Plausible analytics — env-gated, lazy, no cookies. */}
        {PLAUSIBLE_DOMAIN && (
          <script
            defer
            data-domain={PLAUSIBLE_DOMAIN}
            src={PLAUSIBLE_SCRIPT}
          />
        )}
      </head>
      <body>
        {/* SEO structured data — Google + LinkedIn parse this for rich
            results. Two graphs: Organization for the brand, SoftwareApplication
            for the product so price + description + ratings can surface. */}
        <Script
          id="ld-org"
          type="application/ld+json"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "Organization",
              name: "Tapeline",
              url: "https://tapeline.io",
              logo: "https://tapeline.io/favicon.svg",
              sameAs: [],
              contactPoint: [
                {
                  "@type": "ContactPoint",
                  email: "support@tapeline.io",
                  contactType: "customer support",
                  availableLanguage: ["en"],
                },
              ],
            }),
          }}
        />
        <Script
          id="ld-product"
          type="application/ld+json"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "SoftwareApplication",
              name: "Tapeline",
              applicationCategory: "FinanceApplication",
              operatingSystem: "Web",
              description:
                "Live quantitative market scanner for retail stock pickers. One 0-100 score and one plain-English sentence per US ticker, plus squeeze detection, market regime, congressional trades, and a public scorecard.",
              offers: [
                {
                  "@type": "Offer",
                  name: "Pro",
                  price: "29.99",
                  priceCurrency: "USD",
                  priceSpecification: {
                    "@type": "UnitPriceSpecification",
                    price: "29.99",
                    priceCurrency: "USD",
                    unitText: "MONTH",
                  },
                  url: "https://tapeline.io/pricing",
                },
                {
                  "@type": "Offer",
                  name: "Premium",
                  price: "49.99",
                  priceCurrency: "USD",
                  priceSpecification: {
                    "@type": "UnitPriceSpecification",
                    price: "49.99",
                    priceCurrency: "USD",
                    unitText: "MONTH",
                  },
                  url: "https://tapeline.io/pricing",
                },
              ],
              url: "https://tapeline.io",
            }),
          }}
        />
        <UserProvider>{children}</UserProvider>
        {/* Cloudflare Turnstile — only loaded when a site key is configured.
            The widget is rendered by the signup form (and any other gated form)
            via <div className="cf-turnstile">. The script self-discovers them. */}
        {TURNSTILE_SITE_KEY && (
          <Script
            src="https://challenges.cloudflare.com/turnstile/v0/api.js"
            strategy="afterInteractive"
            async
            defer
          />
        )}
      </body>
    </html>
  );
}
