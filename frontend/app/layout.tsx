import type { Metadata } from "next";
import Script from "next/script";
import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/next";
import "./globals.css";
import { UserProvider } from "@/components/UserContext";
import { ThemeProvider, themeBootScript } from "@/components/ThemeProvider";
import { UtmCapture } from "@/components/UtmCapture";
import { PostHogProvider } from "@/components/PostHogProvider";
import { PRICING, usd } from "@/lib/pricing";

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

// Google Ads conversion tag (AW-XXXXXXXXXX). DISTINCT from GA4: this is what
// makes ad clicks -> signups countable as conversions in the Google Ads
// dashboard, which Smart Bidding / ROAS depend on. Without it a paid search
// campaign is flying blind. Defaults to the production conversion tag
// (AW-18169833652) now that the "Tapeline - Search Test (Jun 2026)" campaign +
// conversion action are live; override via NEXT_PUBLIC_GOOGLE_ADS_ID in Vercel
// (or set to empty string to disable on a preview/staging deploy). Shares the
// gtag.js loader with GA4 below; per-event send_to labels live in lib/gtag.ts
// (NEXT_PUBLIC_GOOGLE_ADS_*_LABEL — still unset until the conversion label is
// pulled from the Ads conversion action, at which point signups start counting).
const GOOGLE_ADS_ID = process.env.NEXT_PUBLIC_GOOGLE_ADS_ID ?? "AW-18169833652";

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
    `Tapeline.io is a transparent quantitative stock scanner: every US ticker gets one 0-100 score from a public 6-factor formula, and every top-10 pick is logged at /scorecard with the next-day return. Pro from ${usd(PRICING.pro.annualPerMonth)}/mo. 14-day Premium trial, no card.`,
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
      `Read the tape. One score per US ticker, public 6-factor formula, daily back-checked scorecard. Pro ${usd(PRICING.pro.annualPerMonth)}/mo, Premium ${usd(PRICING.premium.annualPerMonth)}/mo. 14-day Premium trial, no card.`,
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
        {/* RSS feed discovery — browsers + aggregators (Feedly, Inoreader,
            NewsBlur, etc.) look for this link tag to auto-detect the
            site's feed. Pointing at /feed.xml (RSS 2.0 of the daily
            Top 10) gets the scorecard into aggregator pipelines without
            anyone needing to know the URL. */}
        <link
          rel="alternate"
          type="application/rss+xml"
          title="Tapeline — Daily Top 10"
          href="/feed.xml"
        />
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
              // Entity disambiguation for brand-name SERP. Per Search Console
              // (2026-05-19 audit) the bare query "tapeline" returns us at
              // position 15.1 with 13 imp / 0 clicks over 90 days — the
              // measuring-tool brands and a UK insurance broker outrank us
              // for our own name. The fix is heavier entity signal: legalName,
              // explicit description, slogan, knowsAbout, and country so
              // Google's Knowledge Graph learns "Tapeline = US stock scanner
              // SaaS" rather than "Tapeline = generic word."
              legalName: "Tapeline",
              alternateName: "Tapeline.io",
              slogan: "Read the tape",
              description:
                "Tapeline is a transparent quantitative stock scanner for US equities and ETFs. Every actively-traded ticker gets one 0-100 composite score from a publicly-documented six-factor formula (trend, relative strength, fundamentals, smart money, macro, momentum), refreshed sub-60 seconds during US market hours. Every top-10 daily pick is logged to a public scorecard and back-checked against SPY the next session.",
              url: "https://tapeline.io",
              logo: "https://tapeline.io/favicon.svg",
              foundingDate: "2026",
              // Country-only address — full street suppressed per founder
              // privacy. Country signal alone is enough to help Google
              // localise the brand entity vs the UK/AU "tapeline" measuring-
              // tool sellers.
              address: {
                "@type": "PostalAddress",
                addressCountry: "AU",
              },
              // knowsAbout teaches the Knowledge Graph what topics this
              // entity is about — strongest available signal for brand-query
              // disambiguation. Each entry is a topic Google has its own
              // entity page for.
              knowsAbout: [
                "Stock scanner",
                "Quantitative trading",
                "US equities",
                "Exchange-traded fund",
                "Technical analysis",
                "Fundamental analysis",
                "Market data",
                "Financial technology",
              ],
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
              // 2026-05-12 → 2026-05-31: linkedin.com/company/tapeline is a
              //   European agroecology research project (different brand), so we
              //   claimed the unique slug /company/tapeline-io instead. Verified
              //   live + admin-owned (company id 118593983) on 2026-05-31 →
              //   RESTORED to sameAs below.
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
                "https://www.linkedin.com/company/tapeline-io",
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
              // Offers are derived from lib/pricing.ts (single source of truth)
              // so the rich-result price can never drift from the visible price.
              // AggregateOffer.lowPrice is the advertised headline — Pro billed
              // annually at $24.99/mo — so Google surfaces "From $24.99/mo"
              // instead of the $29.99 month-to-month rate (the prior bug: the
              // annual offers were priced as yearly totals in "ANN" units, so
              // the lowest per-offer price was the $29.99 monthly). Every offer
              // is a real per-month price for its billing term; the annual
              // yearly total is carried in the offer name.
              offers: {
                "@type": "AggregateOffer",
                priceCurrency: PRICING.currency,
                lowPrice: PRICING.pro.annualPerMonth.toFixed(2),
                highPrice: PRICING.premium.monthly.toFixed(2),
                offerCount: 4,
                offers: [
                  {
                    "@type": "Offer",
                    name: `Pro — billed annually (${usd(PRICING.pro.annual)}/yr)`,
                    priceCurrency: PRICING.currency,
                    price: PRICING.pro.annualPerMonth.toFixed(2),
                    priceSpecification: {
                      "@type": "UnitPriceSpecification",
                      price: PRICING.pro.annualPerMonth.toFixed(2),
                      priceCurrency: PRICING.currency,
                      unitText: "MONTH",
                    },
                    url: "https://tapeline.io/pricing",
                  },
                  {
                    "@type": "Offer",
                    name: "Pro — monthly",
                    priceCurrency: PRICING.currency,
                    price: PRICING.pro.monthly.toFixed(2),
                    priceSpecification: {
                      "@type": "UnitPriceSpecification",
                      price: PRICING.pro.monthly.toFixed(2),
                      priceCurrency: PRICING.currency,
                      unitText: "MONTH",
                    },
                    url: "https://tapeline.io/pricing",
                  },
                  {
                    "@type": "Offer",
                    name: `Premium — billed annually (${usd(PRICING.premium.annual)}/yr)`,
                    priceCurrency: PRICING.currency,
                    price: PRICING.premium.annualPerMonth.toFixed(2),
                    priceSpecification: {
                      "@type": "UnitPriceSpecification",
                      price: PRICING.premium.annualPerMonth.toFixed(2),
                      priceCurrency: PRICING.currency,
                      unitText: "MONTH",
                    },
                    url: "https://tapeline.io/pricing",
                  },
                  {
                    "@type": "Offer",
                    name: "Premium — monthly",
                    priceCurrency: PRICING.currency,
                    price: PRICING.premium.monthly.toFixed(2),
                    priceSpecification: {
                      "@type": "UnitPriceSpecification",
                      price: PRICING.premium.monthly.toFixed(2),
                      priceCurrency: PRICING.currency,
                      unitText: "MONTH",
                    },
                    url: "https://tapeline.io/pricing",
                  },
                ],
              },
              url: "https://tapeline.io",
            }),
          }}
        />
        <ThemeProvider>
          <UserProvider>
            <PostHogProvider>{children}</PostHogProvider>
          </UserProvider>
        </ThemeProvider>
        {/* First-touch UTM capture — runs once per page-load and writes
            ?utm_* query params to localStorage with a 30-day TTL. The
            signup page + newsletter capture component both read this
            back on submit so we attribute revenue to the original
            paid-channel landing, not the eventual direct-return signup. */}
        <UtmCapture />
        {/* Vercel Analytics + Speed Insights. Free tier on Vercel; no env
            config needed — auto-detects when deployed on Vercel and is a
            no-op in local dev. Page-view + custom-event tracking +
            Web Vitals (Core Web Vitals + custom metrics). Complementary
            to Plausible above (Plausible is the privacy-first aggregate
            view; Vercel adds per-route + Web Vitals). */}
        <Analytics />
        <SpeedInsights />
        {/* Google tag (gtag.js) — one loader, shared by GA4 (analytics + the
            GSC attribution loop) AND Google Ads (paid-search conversion
            tracking). Loaded after-interactive so it never blocks first paint.
            Fire events via the typed helper in lib/gtag.ts; conversion-worthy
            events (sign_up / start_trial / subscribe) auto-forward to Google
            Ads when NEXT_PUBLIC_GOOGLE_ADS_ID + the matching label are set.
            Cross-reference GA4 with Search Console under GSC -> Settings ->
            Associations so query data flows into Acquisition reports. */}
        {(GA4_ID || GOOGLE_ADS_ID) && (
          <>
            <Script
              id="gtag-loader"
              src={`https://www.googletagmanager.com/gtag/js?id=${GA4_ID || GOOGLE_ADS_ID}`}
              strategy="afterInteractive"
            />
            <Script
              id="gtag-config"
              strategy="afterInteractive"
              dangerouslySetInnerHTML={{
                __html: `
                  window.dataLayer = window.dataLayer || [];
                  function gtag(){dataLayer.push(arguments);}
                  gtag('js', new Date());
                  ${GA4_ID ? `gtag('config', '${GA4_ID}');` : ""}
                  ${GOOGLE_ADS_ID ? `gtag('config', '${GOOGLE_ADS_ID}');` : ""}
                `,
              }}
            />
          </>
        )}
        {/* Cloudflare Turnstile — only loaded when a site key is configured.
            The widget is rendered by the signup form (and any other gated form)
            via <div className="cf-turnstile">. The script self-discovers them.

            strategy="lazyOnload" (not afterInteractive) on purpose: api.js
            auto-injects an iframe into every SSR'd .cf-turnstile div the moment
            it runs. Under afterInteractive on a fast connection it fired BEFORE
            React finished hydrating the signup form's Suspense subtree, so React
            hit an extra DOM child that wasn't in its vdom -> "Hydration failed,
            tree regenerated on the client". lazyOnload defers the script to
            browser idle (strictly after hydration), so the div is hydrated empty
            -- matching the server -- and only then gets its widget. Same
            self-discovery mechanism, just no race. */}
        {TURNSTILE_SITE_KEY && (
          <Script
            src="https://challenges.cloudflare.com/turnstile/v0/api.js"
            strategy="lazyOnload"
            async
            defer
          />
        )}
      </body>
    </html>
  );
}
