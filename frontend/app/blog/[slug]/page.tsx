import Link from "next/link";
import { notFound } from "next/navigation";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { findPost, POSTS } from "../posts";
import { pageMeta } from "@/lib/seo";
import { articleJsonLd, breadcrumbJsonLd, howToJsonLd, jsonLdScript } from "@/lib/jsonld";

export async function generateStaticParams() {
  return POSTS.map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = findPost(slug);
  if (!post) {
    return pageMeta({
      title: "Post not found — Tapeline",
      description: "This post no longer exists or has moved. Browse the latest at /blog.",
      path: `/blog/${slug}`,
    });
  }
  return pageMeta({
    title: post.title,
    description: post.excerpt,
    path: `/blog/${post.slug}`,
    ogType: "article",
    publishedTime: post.publishedAt,
  });
}

export default async function BlogPost({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = findPost(slug);
  if (!post) notFound();

  return (
    <main className="min-h-screen">
      {/* Article schema — gives Google an explicit headline, datePublished
          and author for rich-result eligibility. BreadcrumbList helps Google
          render the site-hierarchy path under the SERP result.
          imageUrl points at the Next.js-generated dynamic OG image for this
          slug (frontend/app/blog/[slug]/opengraph-image.tsx). Google's
          Article rich-result eligibility requires an absolute image URL at
          1200×630+ which the OG handler emits. Without this, the SERP card
          renders text-only; with it, the post can win the image-thumbnail
          variant that materially lifts CTR. */}
      <script
        {...jsonLdScript(
          articleJsonLd({
            title: post.title,
            description: post.excerpt,
            url: `https://tapeline.io/blog/${post.slug}`,
            publishedAt: post.publishedAt,
            author: post.author,
            imageUrl: `https://tapeline.io/blog/${post.slug}/opengraph-image`,
          }),
        )}
      />
      <script
        {...jsonLdScript(
          breadcrumbJsonLd([
            { name: "Tapeline", url: "https://tapeline.io/" },
            { name: "Blog", url: "https://tapeline.io/blog" },
            { name: post.title, url: `https://tapeline.io/blog/${post.slug}` },
          ]),
        )}
      />
      {/* HowTo schema — only emitted for posts that opted in via howToSteps
          in the manifest (currently the 3 long-form educational posts:
          what-is-rsi, how-to-find-momentum-stocks, best-time-to-buy-stocks).
          Unlocks Google's step-by-step rich result which sits high on the
          SERP and lifts CTR significantly on instructional queries. */}
      {post.howToSteps && post.howToSteps.length > 0 && (
        <script
          {...jsonLdScript(
            howToJsonLd({
              name: post.title,
              description: post.excerpt,
              url: `https://tapeline.io/blog/${post.slug}`,
              imageUrl: `https://tapeline.io/blog/${post.slug}/opengraph-image`,
              totalTime: post.howToTime,
              steps: post.howToSteps,
            }),
          )}
        />
      )}
      <MarketingNav />

      <article className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
        <Link href="/blog" className="text-sm text-muted hover:text-fg">
          &larr; All posts
        </Link>

        <header className="mt-6">
          <div className="text-xs uppercase tracking-wider text-subtle">
            {new Date(post.publishedAt).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}
            {" · "}
            {post.author}
          </div>
          <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
            {post.title}
          </h1>
          <p className="mt-4 text-lg text-muted leading-relaxed">{post.excerpt}</p>
        </header>

        {/* Body — content is internal trusted HTML, not user input. */}
        <div
          className="prose prose-invert mt-10 max-w-none text-base leading-relaxed text-fg [&_a]:text-accent [&_a:hover]:underline [&_h2]:mt-8 [&_h2]:text-xl [&_h2]:font-semibold [&_p]:mb-4 [&_ul]:my-4 [&_ul]:list-disc [&_ul]:pl-6 [&_li]:mb-1.5"
          dangerouslySetInnerHTML={{ __html: post.body }}
        />

        <div className="mt-16 rounded-2xl border border-accent/30 bg-gradient-to-br from-accent/5 via-panel to-panel p-8">
          <h2 className="text-xl font-semibold tracking-tight">See it live.</h2>
          <p className="mt-2 text-sm text-muted">
            14-day Premium trial. No credit card. The scoring formula above runs
            on every US ticker every minute.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link href="/signup" className="btn-accent">
              Try Premium free &rarr;
            </Link>
            <Link href="/scorecard" className="btn-ghost">
              See the public scorecard
            </Link>
          </div>
        </div>
      </article>

      <MarketingFooter />
    </main>
  );
}
