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

// Title template is "%s" so each page owns its full <title>. Putting the
// brand suffix in the template double-applies it on pages that already
// include " — Tapeline" in their own title (most of them do, for SEO).
// Default title is used only when a page omits its own.
export const metadata: Metadata = {
  title: {
    default: "Tapeline — One score per stock · Live transparent stock scanner",
    template: "%s",
  },
  description:
    "Live quantitative stock scanner. Every US ticker gets one 0-100 score and a plain-English sentence from a public 6-factor formula. Pro from $24.99/mo, Premium from $39.99/mo (annual). 14-day free trial, no credit card.",
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
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "Tapeline — A scanner that shows its work",
    description:
      "One score and one sentence per US ticker. Six-factor formula public. Track record back-checked vs SPY, daily. Pro from $24.99/mo, Premium from $39.99/mo.",
    url: "/",
    siteName: "Tapeline",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    site: "@tapeline_io",
    title: "Tapeline — A scanner that shows its work",
    description:
      "Live quantitative scanner. One score per US ticker. Public formula. Public scorecard.",
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
            results. Three graphs:
              - Organization for the brand
              - WebSite (with SearchAction) so Google can render a sitelinks
                search box under our brand result
              - SoftwareApplication for the product so price + description
                surface in SERPs */}
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
              sameAs: ["https://x.com/tapeline_io"],
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
          id="ld-website"
          type="application/ld+json"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "WebSite",
              name: "Tapeline",
              url: "https://tapeline.io",
              potentialAction: {
                "@type": "SearchAction",
                // Search box currently routes to ticker page; once a real
                // /search exists, swap target to /search?q={search_term_string}
                target: {
                  "@type": "EntryPoint",
                  urlTemplate: "https://tapeline.io/t/{search_term_string}",
                },
                "query-input": "required name=search_term_string",
              },
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
              applicationSubCategory: "Stock Scanner",
              operatingSystem: "Web",
              description:
                "Live quantitative market scanner for retail stock pickers. One 0-100 score and one plain-English sentence per US ticker, plus squeeze detection, market regime, congressional trades, and a public scorecard.",
              // Four explicit offers — monthly + annual for each tier — so
              // SERPs can show the cheapest entry point ($24.99 Pro annual)
              // and the highest commit ($479 Premium annual).
              offers: [
                {
                  "@type": "Offer",
                  name: "Pro · monthly",
                  price: "29",
                  priceCurrency: "USD",
                  priceSpecification: {
                    "@type": "UnitPriceSpecification",
                    price: "29",
                    priceCurrency: "USD",
                    unitText: "MONTH",
                  },
                  url: "https://tapeline.io/pricing",
                },
                {
                  "@type": "Offer",
                  name: "Pro · annual",
                  price: "299",
                  priceCurrency: "USD",
                  priceSpecification: {
                    "@type": "UnitPriceSpecification",
                    price: "299",
                    priceCurrency: "USD",
                    unitText: "ANN",
                  },
                  url: "https://tapeline.io/pricing",
                },
                {
                  "@type": "Offer",
                  name: "Premium · monthly",
                  price: "49",
                  priceCurrency: "USD",
                  priceSpecification: {
                    "@type": "UnitPriceSpecification",
                    price: "49",
                    priceCurrency: "USD",
                    unitText: "MONTH",
                  },
                  url: "https://tapeline.io/pricing",
                },
                {
                  "@type": "Offer",
                  name: "Premium · annual",
                  price: "479",
                  priceCurrency: "USD",
                  priceSpecification: {
                    "@type": "UnitPriceSpecification",
                    price: "479",
                    priceCurrency: "USD",
                    unitText: "ANN",
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
