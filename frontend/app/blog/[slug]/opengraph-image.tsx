/**
 * Dynamic OG for /blog/{slug}. Pulls title + excerpt from the same POSTS
 * manifest the blog route uses so adding a post auto-generates its card.
 */
import { ogResponse, ogSize } from "@/lib/og";
import { POSTS } from "../posts";

export const runtime = "edge";
export const size = ogSize;
export const contentType = "image/png";
export const alt = "Tapeline blog post";

export default async function OG({ params }: { params: { slug: string } }) {
  const post = POSTS.find((p) => p.slug === params.slug);
  if (!post) {
    return ogResponse({
      eyebrow: "BLOG",
      title: "Tapeline blog — methodology + market notes.",
      subtitle: "How the score works, what the data sources actually mean, why we built it this way.",
    });
  }
  return ogResponse({
    eyebrow: "BLOG",
    title: post.title,
    subtitle: post.excerpt,
  });
}
