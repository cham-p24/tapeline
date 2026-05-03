import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { POSTS } from "./posts";

export const metadata = {
  title: "Blog — Tapeline",
  description:
    "Notes from building Tapeline. Methodology, market commentary, and the occasional rant about scanner pricing.",
  alternates: {
    canonical: "https://tapeline.io/blog",
    types: { "application/rss+xml": "https://tapeline.io/blog/rss.xml" },
  },
};

export default function BlogIndex() {
  // Newest first.
  const sorted = [...POSTS].sort(
    (a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime()
  );

  return (
    <main className="min-h-screen">
      <MarketingNav />

      <section className="mx-auto max-w-3xl px-4 sm:px-6 py-16">
        <p className="eyebrow">Blog</p>
        <h1 className="mt-3 text-5xl font-bold tracking-tight">Notes from building.</h1>
        <p className="mt-4 text-lg text-muted">
          Methodology, market commentary, and occasional rants about scanner pricing.
          Posts are short. Newest first. <a href="/blog/rss.xml" className="text-accent hover:underline">RSS</a>.
        </p>

        <div className="mt-12 divide-y divide-border border-y border-border">
          {sorted.map((p) => (
            <article key={p.slug} className="py-6">
              <Link href={`/blog/${p.slug}`} className="group block">
                <div className="text-xs uppercase tracking-wider text-subtle">
                  {new Date(p.publishedAt).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}
                  {" · "}
                  {p.author}
                </div>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight group-hover:text-accent transition-colors">
                  {p.title}
                </h2>
                <p className="mt-2 text-sm text-muted leading-relaxed">{p.excerpt}</p>
                <span className="mt-3 inline-block text-sm text-accent group-hover:underline">
                  Read &rarr;
                </span>
              </Link>
            </article>
          ))}
        </div>

        {sorted.length === 0 && (
          <div className="mt-12 rounded-xl border border-border bg-panel p-8 text-center text-muted">
            No posts yet. Subscribe-by-RSS coming once the corpus is bigger.
          </div>
        )}
      </section>

      <MarketingFooter />
    </main>
  );
}
