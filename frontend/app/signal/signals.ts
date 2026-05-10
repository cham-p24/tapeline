/**
 * Signal-label taxonomy used by /signal/[signal]/page.tsx and the sitemap.
 *
 * Lives outside the page file because Next.js page modules can only export
 * the default component, generateMetadata, generateStaticParams, and a fixed
 * list of metadata-related fields.
 *
 * The `display` value is the literal label stored in the DB (UPPERCASE,
 * spaces between words). The slug is the URL fragment.
 */
export const SIGNALS = [
  {
    slug: "high-conviction",
    display: "HIGH CONVICTION",
    range: "85-100",
    blurb: "All six factors aligned positive — rare.",
    longDesc:
      "All six factors — trend, relative strength, fundamentals, smart money, macro, and momentum — aligned positive at high sub-score values. The strongest tier in the Tapeline scoring system; usually only a handful of names hold this label at any given time.",
  },
  {
    slug: "strong-setup",
    display: "STRONG SETUP",
    range: "70-84",
    blurb: "Most factors favourable — the workhorse tier.",
    longDesc:
      "Four to five of six factors favourable. The tier most top-10 daily picks come from. Strong but not perfect — typically a clean trend + RS combination with one or two factors slightly behind.",
  },
  {
    slug: "constructive",
    display: "CONSTRUCTIVE",
    range: "55-69",
    blurb: "Net positive with meaningful tradeoffs.",
    longDesc:
      "Net positive but with at least one factor pulling against the others. Often a great fundamentals story with a weak trend, or a hot trend with stretched valuation.",
  },
  {
    slug: "neutral",
    display: "NEUTRAL",
    range: "40-54",
    blurb: "Factors cancel — the data isn't telling you to do anything.",
    longDesc:
      "Sub-scores roughly cancel out. The data is genuinely neutral — useful for filtering names that don't have a clear directional thesis either way.",
  },
  {
    slug: "caution",
    display: "CAUTION",
    range: "25-39",
    blurb: "More factors negative than positive.",
    longDesc:
      "Most factors negative. Usually a deteriorating trend confirmed by RS lagging and smart-money distribution. The descriptive complement to STRONG SETUP.",
  },
  {
    slug: "weak",
    display: "WEAK",
    range: "0-24",
    blurb: "Broadly negative — the descriptive complement to HIGH CONVICTION.",
    longDesc:
      "Almost always reflects a clear downtrend confirmed by deteriorating fundamentals, smart money distribution, and weak relative strength. The strongest negative tier.",
  },
] as const;

export type Signal = (typeof SIGNALS)[number];
