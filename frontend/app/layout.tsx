import type { Metadata } from "next";
import Script from "next/script";
import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/next";
import "./globals.css";
import { UserProvider } from "@/components/UserContext";
import { ThemeProvider, themeBootScript } from "@/components/ThemeProvider";
import { PostHogProvider } from "@/components/PostHogProvider";

const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "";
// Env-gated analytics — set NEXT_PUBLIC_PLAUSIBLE_DOMAIN to "tapeline.io"
// (or your custom Plausible host via NEXT_PUBLIC_PLAUSIBLE_SCRIPT) to flip
// on. No personal data, GDPR-friendly, ~1KB script.
const PLAUSIBLE_DOMAIN = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN || "";
const PLAUSIBLE_SCRIPT =
  process.env.NEXT_PUBLIC_PLAUSIBLE_SCRIPT || "https://plausible.io/js/script.js";

// Google Analytics 4 measurement ID. Defaults to the production property
// (G-YRK73W9NS9) so prod tracks without env config; override via
// NEXT_PUBLIC_GA4_ID for staging/preview deploys, or set to empty string
// to disable on a specific environment. GA4 powers the GSC ↔ signup
// attribution loop — Search Console shows what query brought a visitor,
// GA4 shows what they did after (event "sign_up" on the success page).
const GA4_ID = process.env.NEXT_PUBLIC_GA4_ID ?? "G-YRK73W9NS9";

// Title template is "%s" so each page owns its full <title>. Putting the
// brand suffix in the template double-applies it on pages that already
// include " — Tapeline" in their own title (most of them do, for SEO).
// Default title is used only when a page omits its own.
export const metadata: Metadata = {
  title: {
    // Brand-first title keeps the "Read the tape" tagline (recognisable to
    // existing audience on X/LinkedIn) while adding the explicit category +
    // public-formula differentiator that addresses the GSC brand-search audit
    // (the old "Live quantitative stock scanner" suffix wasn't winning brand
    // CTR — 11 imp / 0 clicks on "tapeline" over 3mo per GSC). Reads cleanly
    // in the 60-char SERP truncation window.
    default: "Tapeline — Read the tape · Stock scanner with public formula",
    template: "%s",
  },
  description:
    "Tapeline.io is a transparent quantitative stock scanner: every US ticker gets one 0-100 score from a public 6-factor formula, and every top-10 pick is logged at /scorecard with the next-day return. Pro from $24.99/mo. 14-day Premium trial, no card.",
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "https://tapeline.io"),
  applicationName: "Tapeline",
  authors: [{ name: "Tapeline", url: "https://tapeline.io" }],
  keywords: [
    "stock scanner",
    "quantitative scoring",
    "live market scanner",
    "squeeze detection",
    "congressional trades",
    "insider Form 4",
    "market regime",
    "retail trading",
  ],
  alternates: {
    canonical: "/",
  },
  openGraph: {
    // OG card is share-context — keep the punchy "Read the tape" line
    // (matches X/LinkedIn banner copy) rather than the SERP-loaded variant.
    title: "Tapeline — Read the tape",
    description:
      "Read the tape. One score per US ticker, public 6-factor formula, daily back-checked scorecard. Pro $24.99/mo, Premium $39.99/mo. 14-day Premium trial, no card.",
    url: "/",
    siteName: "Tapeline",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    site: "@tapeline_io",
    title: "Tapeline — Read the tape",
    description:
      "Read the tape. Public formula, public scorecard. → tapeline.io/scorecard",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1 },
  },
  icons: {
    // favicon.ico isn't shipped (we use SVG only). Referencing a non-existent
    // .ico made Google log a 404 against /favicon.ico in Search Console; SVG
    // alone is supported in every modern browser + Googlebot.
    icon: [{ url: "/favicon.svg", type: "image/svg+xml" }],
    shortcut: "/favicon.svg",
    apple: "/favicon.svg",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        {/* Theme boot — runs synchronously in <head> before React mounts so
            users with a saved "light" preference don't flash dark on first
            paint. Pulls from localStorage('tapeline_theme'). */}
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
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
              // sameAs is the canonical "this is the same entity" graph that
              // feeds Google's Knowledge Panel and Knowledge Graph. Each URL
              // here should be the actual public profile page on an
              // authoritative platform (no redirects, no short links).
              // Coverage checklist + submission instructions live in
              // docs/OFFSITE.md. Update entries when a profile is created;
              // remove if a profile is genuinely abandoned.
              // sameAs lists only profiles that actually resolve AND
              // belong to Tapeline (the stock scanner). A 404 is a negative
              // trust signal; a 200 pointing at a DIFFERENT entity is worse
              // — Google will learn the wrong Knowledge Graph link.
              //
              // Removed 2026-05-11: Substack, YouTube (HEAD-404).
              // Removed 2026-05-12: linkedin.com/company/tapeline (it's a
              //   European agroecology research project — different brand).
              //   Restore once we claim a unique slug like /company/tapeline-io.
              // Removed 2026-05-13: producthunt /products/tapeline (HTTP 404),
              //   capterra /p/tapeline (HTTP 404), stocktwits /tapeline
              //   (HTTP 404). Restore each entry as the profile is claimed.
              //   crunchbase / alternativeto / g2 also Cloudflare-blocked but
              //   per seo-tools/disclosure/profile_kits.md these are known-
              //   unclaimed; gating them behind verification too. Restore as
              //   each platform's profile is claimed and reachable.
              //
              // Only entries below have been confirmed to resolve AND belong
              // to Tapeline. See seo-tools/disclosure/profile_kits.md for the
              // canonical paste-ready copy when claiming each.
              sameAs: [
                "https://x.com/tapeline_io",
                "https://github.com/cham-p24/tapeline",
                "https://www.reddit.com/user/tapeline_io",
              ],
              contactPoint: [
                {
                  "@type": "ContactPoint",
                  email: "support@tapeline.io",
                  contactType: "customer support",
                  availableLanguage: ["en"],
                },
                {
                  "@type": "ContactPoint",
                  email: "press@tapeline.io",
                  contactType: "press inquiries",
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
                // SearchAction must point at a URL Googlebot can actually
                // crawl with a substituted query. /t/{search_term_string} was
                // logging a literal-placeholder 404 in Search Console because
                // Google was test-fetching the template URL itself. /search
                // accepts ?q=, validates as a ticker, and redirects to /t/.
                target: {
                  "@type": "EntryPoint",
                  urlTemplate: "https://tapeline.io/search?q={search_term_string}",
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
                  name: "Pro · annual",
                  price: "299.99",
                  priceCurrency: "USD",
                  priceSpecification: {
                    "@type": "UnitPriceSpecification",
                    price: "299.99",
                    priceCurrency: "USD",
                    unitText: "ANN",
                  },
                  url: "https://tapeline.io/pricing",
                },
                {
                  "@type": "Offer",
                  name: "Premium · monthly",
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
        <ThemeProvider>
          <UserProvider>
            <PostHogProvider>{children}</PostHogProvider>
          </UserProvider>
        </ThemeProvider>
        {/* Vercel Analytics + Speed Insights. Free tier on Vercel; no env
            config needed — auto-detects when deployed on Vercel and is a
            no-op in local dev. Page-view + custom-event tracking +
            Web Vitals (Core Web Vitals + custom metrics). Complementary
            to Plausible above (Plausible is the privacy-first aggregate
            view; Vercel adds per-route + Web Vitals). */}
        <Analytics />
        <SpeedInsights />
        {/* Google Analytics 4 — loaded after-interactive so it never blocks
            first paint or interactivity. Two scripts per Google docs: (1)
            the gtag loader; (2) the inline config. Once mounted, fire events
            with `gtag('event','sign_up')` from any client component (see
            lib/gtag.ts for the typed helper). Cross-references with Search
            Console under GSC → Settings → Associations so query data flows
            into GA4's Acquisition reports. */}
        {GA4_ID && (
          <>
            <Script
              id="ga4-loader"
              src={`https://www.googletagmanager.com/gtag/js?id=${GA4_ID}`}
              strategy="afterInteractive"
            />
            <Script
              id="ga4-config"
              strategy="afterInteractive"
              dangerouslySetInnerHTML={{
                __html: `
                  window.dataLayer = window.dataLayer || [];
                  function gtag(){dataLayer.push(arguments);}
                  gtag('js', new Date());
                  gtag('config', '${GA4_ID}');
                `,
              }}
            />
          </>
        )}
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
