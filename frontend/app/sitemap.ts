import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = process.env.NEXT_PUBLIC_APP_URL || "https://tapeline.io";
  const now = new Date();
  return [
    { url: `${base}/`,                          lastModified: now, priority: 1.0 },
    { url: `${base}/pricing`,                   lastModified: now, priority: 0.9 },
    { url: `${base}/how-it-works`,              lastModified: now, priority: 0.9 },
    { url: `${base}/scorecard`,                 lastModified: now, priority: 0.9 },
    { url: `${base}/changelog`,                 lastModified: now, priority: 0.6 },
    { url: `${base}/roadmap`,                   lastModified: now, priority: 0.6 },
    { url: `${base}/compare/finviz`,            lastModified: now, priority: 0.7 },
    { url: `${base}/compare/zacks`,             lastModified: now, priority: 0.7 },
    { url: `${base}/compare/wallstreetzen`,     lastModified: now, priority: 0.7 },
    { url: `${base}/signin`,                    lastModified: now, priority: 0.4 },
    { url: `${base}/signup`,                    lastModified: now, priority: 0.6 },
    { url: `${base}/legal/risk`,                lastModified: now, priority: 0.3 },
    { url: `${base}/legal/terms`,               lastModified: now, priority: 0.3 },
    { url: `${base}/legal/privacy`,             lastModified: now, priority: 0.3 },
  ];
}
