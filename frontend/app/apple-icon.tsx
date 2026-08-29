/**
 * 180x180 apple-touch-icon, generated from the same mark as favicon.svg.
 *
 * iOS ignores manifest `icons` when drawing the Home Screen tile and uses
 * `apple-touch-icon` instead, so the manifest alone would install a web app
 * with a blurry screenshot for an icon. 180x180 is the size current iPhones
 * ask for.
 *
 * Padded more than app/icon.tsx because iOS applies its own corner mask and
 * crops toward the centre; the bar would otherwise touch the rounded edge.
 *
 * See app/icon.tsx for why raster icons exist at all when the favicon is SVG.
 */
import { ImageResponse } from "next/og";

export const runtime = "edge";
export const contentType = "image/png";
export const size = { width: 180, height: 180 };

export default function AppleIcon() {
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
        <div
          style={{
            width: 100,
            height: 20,
            borderRadius: 10,
            background: "#3b82f6",
          }}
        />
      </div>
    ),
    { ...size },
  );
}
