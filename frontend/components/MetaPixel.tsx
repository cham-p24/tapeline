"use client";

/**
 * Meta pixel — marketing pages only, never the logged-in product.
 *
 * WHY THIS IS SCOPED AND NOT JUST DROPPED IN THE ROOT LAYOUT
 * ----------------------------------------------------------
 * #538 put the base pixel straight in the root layout, which is the only
 * layout carrying <html>. That means it would have run on `/app/*` too — the
 * entire logged-in surface, including `/app/ticker/[symbol]`.
 *
 * That matters more here than on a normal SaaS. Meta's `fbevents.js` reports
 * the FULL current URL as the `dl` parameter on its `/tr/` beacon. `dl` is a
 * payload field, not the Referer header, so our
 * `Referrer-Policy: strict-origin-when-cross-origin` (next.config.js) does not
 * trim it. And because `/tr/` is on facebook.com, the browser attaches
 * whatever facebook.com cookies it already holds. Net effect, once the pixel
 * is switched on: **which specific tickers a user researches, linkable to
 * their real Facebook account.** For a financial product that is a serious
 * disclosure to make by accident.
 *
 * Nothing is lost by scoping it. The pixel's job is ad attribution, which
 * happens on acquisition pages. Every conversion — CompleteRegistration,
 * StartTrial, Purchase — is sent SERVER-SIDE by `services/meta_capi`, which
 * needs no browser at all and survives ad-blockers. So the logged-in surface
 * has nothing to contribute and everything to leak.
 *
 * HONEST LIMIT OF THIS CONTROL
 * ----------------------------
 * This prevents the script from ever being INSERTED on an `/app/*` page. It
 * does not unload it if the user client-side-navigates from a marketing page
 * into `/app` in the same tab — once `fbevents.js` is in the document it stays
 * there. No new PageView is sent (we only fire one at init, and the base pixel
 * does not auto-track SPA route changes), but the script is present. A hard
 * navigation or fresh load of any `/app/*` URL — the common case for a
 * logged-in user, who lands there by bookmark or redirect — gets no pixel at
 * all. Stated plainly rather than overclaimed, because the privacy policy
 * describes this behaviour and must not describe it as airtight.
 *
 * A SEPARATE RISK THIS FILE CANNOT CONTROL
 * ----------------------------------------
 * Meta's **Automatic Advanced Matching** is a per-pixel toggle in Events
 * Manager. Turning it on makes `fbevents.js` scrape visible form fields —
 * email, phone, name — and send hashed values, with no change to this repo.
 * We deliberately pass no advanced-matching object to `fbq('init', ...)`, but
 * that toggle overrides intent from the dashboard. Leave it OFF. See
 * `docs/META_GO_LIVE.md`.
 */

import Script from "next/script";
import { usePathname } from "next/navigation";

/** Route prefixes the pixel must never load on. */
const EXCLUDED_PREFIXES = ["/app"] as const;

export function isPixelAllowedPath(pathname: string | null): boolean {
  if (!pathname) return false;
  return !EXCLUDED_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );
}

export function MetaPixel({ pixelId }: { pixelId: string }) {
  const pathname = usePathname();

  // No id → the pixel does not exist at all. This is the production state
  // until the operator sets NEXT_PUBLIC_META_PIXEL_ID as a BUILD ARG (a Fly
  // secret of that name is a no-op — the value is inlined at build time).
  if (!pixelId) return null;
  if (!isPixelAllowedPath(pathname)) return null;

  return (
    <Script
      id="meta-pixel"
      strategy="afterInteractive"
      dangerouslySetInnerHTML={{
        __html: `
          !function(f,b,e,v,n,t,s)
          {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
          n.callMethod.apply(n,arguments):n.queue.push(arguments)};
          if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
          n.queue=[];t=b.createElement(e);t.async=!0;
          t.src=v;s=b.getElementsByTagName(e)[0];
          s.parentNode.insertBefore(t,s)}(window,document,'script',
          'https://connect.facebook.net/en_US/fbevents.js');
          fbq('init', '${pixelId}');
          fbq('track', 'PageView');
        `,
      }}
    />
  );
}
