/**
 * Blog post manifest.
 *
 * Adding a post: append to POSTS with a unique slug + a body of HTML
 * fragments. Lightweight by design — when the corpus grows past 10-15
 * posts, swap to MDX or fetch from a CMS without changing the route
 * shape (slug-based).
 */
export type BlogPost = {
  slug: string;
  title: string;
  excerpt: string;
  publishedAt: string; // ISO 8601 date
  author: string;
  body: string; // Trusted HTML — keep this internal-only.
};

export const POSTS: BlogPost[] = [
  {
    slug: "the-formula-is-public",
    title: "The formula is public. Here's why that matters.",
    excerpt:
      "Every other prosumer score-per-ticker tool hides their methodology as IP. We publish the six factors and the exact weights — because the day the formula stops working, you should know to leave.",
    publishedAt: "2026-05-03",
    author: "Tapeline",
    body: `
      <p>If you ask Tipranks why a stock has a 7/10 Smart Score, you get
      "we aggregate analyst consensus, hedge fund moves, insider trades, and
      blogger sentiment." If you ask Zacks why a stock has a #1 rank, the answer
      is "earnings estimate revisions" but the cutoffs are proprietary. If you ask
      Kavout why their Kai Score moved, you get a black-box ML answer.</p>

      <p>Tapeline gives you the literal expression. It's on
      <a href="/how-it-works">/how-it-works</a> and reproduced here:</p>

      <pre style="background:#0a0a0a;border:1px solid #1f1f23;border-radius:8px;padding:18px;overflow-x:auto;font-family:'JetBrains Mono',ui-monospace,monospace;font-size:14px;line-height:1.5;">
score = 0.25 × trend
      + 0.20 × relative_strength
      + 0.15 × fundamentals
      + 0.15 × smart_money
      + 0.15 × macro
      + 0.10 × momentum</pre>

      <p>Why publish it?</p>
      <ul>
        <li><strong>Trust compounds when you can audit.</strong> If you find a
        ticker scoring 90 when its trend is clearly broken, you can call it out
        — and we'd rather you do that than churn silently.</li>
        <li><strong>The moat isn't the formula, it's the data spine.</strong>
        Plenty of competitors could copy the equation. None of them will
        publish their public scorecard back-checking every call against
        next-day prices the way we do.</li>
        <li><strong>If the formula stops working, you should leave.</strong>
        We'd rather you make that call honestly than discover via a slow drip
        of bad picks.</li>
      </ul>

      <p>The weights are versioned in our changelog. The day they change, you
      see why. That's the whole product, in one paragraph.</p>
    `,
  },
];

export function findPost(slug: string): BlogPost | null {
  return POSTS.find((p) => p.slug === slug) ?? null;
}
