import type { Metadata } from "next";

const SITE = process.env.NEXT_PUBLIC_SITE_URL || "https://tapeline.io";

export async function generateMetadata({ params }: { params: { symbol: string } }): Promise<Metadata> {
  const sym = (params.symbol ?? "").toUpperCase();
  const title = `${sym} scorecard track record · Tapeline`;
  const description = `Every time ${sym} has been a Tapeline top-10 daily pick — full public record of next-day return vs SPY. No cherry-picking, no survivor bias.`;
  const url = `${SITE}/scorecard/${encodeURIComponent(sym)}`;
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      title,
      description,
      url,
      type: "article",
      siteName: "Tapeline",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
    },
  };
}

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
