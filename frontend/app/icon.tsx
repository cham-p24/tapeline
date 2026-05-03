/**
 * Site favicon. Next.js 14 auto-routes this at /icon (and serves it as
 * the document <link rel="icon">), which means modern browsers find it
 * without us hand-rolling /favicon.ico.
 *
 * Brand mark: dark bg + the same green→teal gradient stripe used in the
 * MarketingNav. Edge-rendered so we get a small fast PNG without
 * shipping a static binary.
 */
import { ImageResponse } from "next/og";

export const runtime = "edge";
export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: "#0a0a0a",
          borderRadius: "6px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            width: "20px",
            height: "5px",
            background: "linear-gradient(90deg, #22c55e 0%, #14b8a6 100%)",
            borderRadius: "999px",
            display: "flex",
          }}
        />
      </div>
    ),
    { ...size }
  );
}
