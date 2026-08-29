/**
 * PNG app icon, generated at request time from the same marks as favicon.svg.
 *
 * WHY A PNG WHEN WE DELIBERATELY SHIP SVG-ONLY FAVICONS
 * -----------------------------------------------------
 * The favicon story is unchanged: `layout.tsx` still points browsers at
 * /favicon.svg, and this file does not alter that.
 *
 * This exists for the WEB APP MANIFEST. Manifest `icons` must be raster —
 * Android's install prompt and iOS's Home Screen both rasterise from PNG and
 * neither will install a web app whose only icon is an SVG. Without an
 * installable web app there is no iOS web push at all (16.4+ requires a Home
 * Screen web app), which the billing page already promises customers:
 * "Lock-screen notifications on desktop and Android. iOS requires the PWA to
 * be installed." That promise was unfulfillable before this file existed.
 *
 * Design deliberately matches public/favicon.svg — dark rounded square, blue
 * bar across the middle ("the tape") — so the installed icon is recognisably
 * the same mark as the tab favicon.
 */
import { ImageResponse } from "next/og";

export const runtime = "edge";
export const contentType = "image/png";

//: Both sizes the manifest declares. 192 is Android's minimum for an install
//: prompt; 512 is what the splash screen and app-drawer icon are scaled from.
export const size = { width: 512, height: 512 };

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0a0a0a",
        }}
      >
        {/* The tape: same 20/32 width, 4/32 height proportions as favicon.svg,
            scaled to 512. Kept as a plain div rather than an <svg> because
            Satori (which backs ImageResponse) supports only a subset of SVG. */}
        <div
          style={{
            width: 320,
            height: 64,
            borderRadius: 32,
            background: "#3b82f6",
          }}
        />
      </div>
    ),
    { ...size },
  );
}
