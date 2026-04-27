import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";
import { UserProvider } from "@/components/UserContext";

const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "";

export const metadata: Metadata = {
  title: {
    default: "Tapeline — Live quantitative market scanner",
    template: "%s — Tapeline",
  },
  description: "Every US stock scored live. Squeeze detection, market regime, congressional trades — all synthesized into one verdict per ticker. $29/mo.",
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "https://tapeline.io"),
  openGraph: {
    title: "Tapeline — Read the tape. Live.",
    description: "Quantitative market scanner for retail traders. One composite score per ticker, refreshed live.",
    url: "https://tapeline.io",
    siteName: "Tapeline",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Tapeline — Read the tape. Live.",
    description: "Quantitative market scanner for retail traders.",
  },
  robots: { index: true, follow: true },
  icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
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
      </head>
      <body>
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
