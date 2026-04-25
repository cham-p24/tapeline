import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = process.env.NEXT_PUBLIC_APP_URL || "https://tapeline.io";
  const now = new Date();
  return [
    { url: `${base}/`, lastModified: now, priority: 1 },
    { url: `${base}/scorecard`, lastModified: now, priority: 0.9 },
    { url: `${base}/legal/risk`, lastModified: now, priority: 0.3 },
    { url: `${base}/legal/terms`, lastModified: now, priority: 0.3 },
    { url: `${base}/legal/privacy`, lastModified: now, priority: 0.3 },
  ];
}
