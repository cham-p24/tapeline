/**
 * Auto-link `$TICKER` mentions in blog HTML to /t/{TICKER}.
 *
 * Why: every blog post mentions tickers but they're written as plain
 * `$NVDA` / `$AAPL` strings. Hand-wrapping each one in an <a> is toil
 * and rots fast (new posts add unlinked mentions). This util walks the
 * HTML and turns `$TICKER` → `<a href="/t/TICKER">$TICKER</a>` server-
 * side at render time.
 *
 * Compounding effect: every existing + future blog post becomes an
 * internal-link hub pointing at /t/{TICKER} pages. Helps:
 *   - SEO crawl graph density (tickers get inbound links from
 *     editorial content, not just programmatic neighbours)
 *   - User flow (reader clicks a ticker, lands on the live score)
 *   - Per-ticker indexing (the 'Discovered, not indexed' bucket
 *     shrinks faster when ticker pages are linked from editorial)
 *
 * Safety:
 *   - Skips text inside existing <a>...</a>, <code>...</code>, and
 *     <pre>...</pre> blocks so we don't double-link or corrupt code
 *     snippets that happen to mention `$ROOT` or similar.
 *   - Skips $ followed by anything other than 1-5 uppercase letters
 *     so currency ($5, $1000), variables ($var), and shell prompts
 *     don't get clobbered.
 *   - Idempotent: running the result through the function again is
 *     a no-op because all $TICKER occurrences are now inside <a> tags
 *     and the mask step skips them.
 *
 * Not aware of which tickers actually exist in our universe — links
 * to /t/UNKNOWN gracefully render Next.js notFound() via the page
 * route. Hardcoding an allowlist would defeat the auto-update goal.
 */

// Same regex used by Next.js's slug allowlist for ticker pages. 1-5
// uppercase letters captures the conventional US-equity range
// (1 letter = preferred stock or BRK.A; 5 letters = common; rare 6+
// are international ADRs we mostly don't cover anyway).
const TICKER_RE = /\$([A-Z]{1,5})\b/g;

// HTML segments we MUST NOT substitute inside. Each pattern catches an
// open-to-close run that should stay verbatim.
const MASK_RE = /<a\b[^>]*>[\s\S]*?<\/a>|<code\b[^>]*>[\s\S]*?<\/code>|<pre\b[^>]*>[\s\S]*?<\/pre>/gi;

// Sentinels around mask indices — use a control char that's
// vanishingly unlikely to appear in editorial HTML so we can restore
// safely afterward.
const MASK_OPEN = "MASK_";
const MASK_CLOSE = "";

export function autoLinkTickers(html: string): string {
  if (!html) return html;

  // Pass 1: mask out anchor / code / pre segments so the substitution
  // never touches them.
  const masks: string[] = [];
  const masked = html.replace(MASK_RE, (match) => {
    const i = masks.length;
    masks.push(match);
    return `${MASK_OPEN}${i}${MASK_CLOSE}`;
  });

  // Pass 2: substitute $TICKER → linked variant.
  const substituted = masked.replace(TICKER_RE, (_, ticker: string) => {
    // The class list matches the blog `[&_a]` prose styling already
    // configured on the article container — keeps the link visually
    // consistent without having to override per-post.
    return `<a href="/t/${ticker}" class="text-accent hover:underline" data-auto-ticker="${ticker}">$${ticker}</a>`;
  });

  // Pass 3: restore the masks.
  const restored = substituted.replace(
    /MASK_(\d+)/g,
    (_, i) => masks[Number(i)] ?? "",
  );

  return restored;
}
