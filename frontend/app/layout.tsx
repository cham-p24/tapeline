import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import Script from "next/script";
import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/next";
import "./globals.css";
import { UserProvider } from "@/components/UserContext";
import { ThemeProvider, themeBootScript } from "@/components/ThemeProvider";
import { UtmCapture } from "@/components/UtmCapture";
import { PostHogProvider } from "@/components/PostHogProvider";
import { PRICING, usd } from "@/lib/pricing";
import {
  jsonLdScript,
  organizationJsonLd,
  websiteJsonLd,
  softwareApplicationJsonLd,
} from "@/lib/jsonld";

// Self-hosted via next/font — Next downloads + subsets the fonts at build
// time and serves them from our origin (no render-blocking request to
// fonts.googleapis.com, no FOUT). Variables wire into tailwind.config's
// sans/mono stacks.
const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "600", "700"],
  variable: "--font-inter",
});
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "600"],
  variable: "--font-jetbrains-mono",
});

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
    `Stock scanner with a public 6-factor formula: one 0-100 score per US ticker, every top-10 pick logged with next-day return. Pro from ${usd(PRICING.pro.annualPerMonth)}/mo.`,
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
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <head>
        {/* Theme boot — runs synchronously in <head> before React mounts so
            users with a saved "light" preference don't flash dark on first
            paint. Pulls from localStorage('tapeline_theme'). */}
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
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
        {/* Skip-to-content link (WCAG 2.4.1). First focusable element in the
            body so keyboard / screen-reader users can bypass the nav straight
            to <main id="main">. Visually hidden until focused (.skip-link in
            globals.css). */}
        <a href="#main" className="skip-link">
          Skip to main content
        </a>
        {/* SEO structured data — Google + LinkedIn parse this for rich
            results. Three graphs, built in lib/jsonld.ts and rendered as
            plain <script> tags so the JSON-LD ships in the SSR HTML (fully
            crawlable) instead of being client-injected:
              - Organization for the brand
              - WebSite (with SearchAction) so Google can render a sitelinks
                search box under our brand result
              - SoftwareApplication for the product so price + description
                surface in SERPs */}
        <script {...jsonLdScript(organizationJsonLd())} />
        <script {...jsonLdScript(websiteJsonLd())} />
        <script {...jsonLdScript(softwareApplicationJsonLd())} />
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
        {/* Vercel Analytics + Speed Insights. Gated behind NEXT_PUBLIC_VERCEL
            (Vercel sets this to "1" on its builds) so they only mount on
            Vercel-hosted deploys — off-Vercel the beacons 404 against
            /_vercel/insights/*, so we skip rendering them entirely. Page-view
            + custom-event tracking + Web Vitals (Core Web Vitals + custom
            metrics). Complementary to Plausible above (Plausible is the
            privacy-first aggregate view; Vercel adds per-route + Web Vitals). */}
        {process.env.NEXT_PUBLIC_VERCEL === "1" && (
          <>
            <Analytics />
            <SpeedInsights />
          </>
        )}
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
