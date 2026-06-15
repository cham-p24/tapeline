/**
 * JSON-LD builders for Schema.org structured data.
 *
 * Returns plain objects; pages JSON.stringify them into a
 * <script type="application/ld+json"> tag rendered in the body.
 * Google parses JSON-LD anywhere in the HTML, so body placement is fine
 * (and avoids the "head must be in head" hydration warnings Next throws
 * when you stuff <script> tags into the layout's <head>).
 */

/**
 * Founder Person schema — gated by env vars so disclosure is a one-touch
 * deployment switch in Vercel, not a code change.
 *
 * Activation requires all three:
 *   1. NEXT_PUBLIC_FOUNDER_DISCLOSED === "true"
 *   2. NEXT_PUBLIC_FOUNDER_NAME is non-empty
 *   3. At least one of NEXT_PUBLIC_FOUNDER_LINKEDIN / NEXT_PUBLIC_FOUNDER_X
 *      is set (a Person with no off-site profiles is weaker than no Person).
 *
 * If any condition fails, returns null and every downstream schema falls back
 * to the Organization-only graph. Trigger condition for flipping:
 *   n=100 scored + back-checked picks on /scorecard,
 *   launched alongside /blog/100-picks-in-public.
 * Full pre-flight checklist: C:\Tapeline\seo-tools\disclosure\README.md
 *
 * When this returns a Person:
 *   - aboutProfilePageJsonLd() upgrades AboutPage → ProfilePage with Person mainEntity
 *   - articleJsonLd() swaps Organization author for Person author (every blog post)
 *   - /about page renders an extra <script> with the Person itself
 */
export function founderPersonJsonLd() {
  const disclosed = process.env.NEXT_PUBLIC_FOUNDER_DISCLOSED === "true";
  const name = process.env.NEXT_PUBLIC_FOUNDER_NAME;
  if (!disclosed || !name) return null;
  const sameAs = [
    process.env.NEXT_PUBLIC_FOUNDER_LINKEDIN,
    process.env.NEXT_PUBLIC_FOUNDER_X,
    process.env.NEXT_PUBLIC_FOUNDER_GITHUB,
  ].filter((u): u is string => Boolean(u));
  if (sameAs.length === 0) return null;
  const image = process.env.NEXT_PUBLIC_FOUNDER_HEADSHOT_URL;
  return {
    "@context": "https://schema.org",
    "@type": "Person",
    "@id": "https://tapeline.io/about#founder",
    name,
    jobTitle: "Founder, Tapeline",
    url: "https://tapeline.io/about",
    ...(image ? { image } : {}),
    sameAs,
    knowsAbout: [
      "Quantitative equity scoring",
      "Six-factor scoring methodology",
      "Public-record back-testing",
      "Stock scanner product design",
      "Multi-factor models",
      "Retail trader workflow design",
    ],
    description:
      "Founder of Tapeline — the transparent six-factor stock scanner with a public scorecard. Builds Tapeline solo and runs the same scoring engine as a personal trading bot.",
    worksFor: {
      "@type": "Organization",
      "@id": "https://tapeline.io#org",
      name: "Tapeline",
      url: "https://tapeline.io",
    },
  } as const;
}

export type FaqItem = { q: string; a: string };

export function faqJsonLd(items: FaqItem[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((it) => ({
      "@type": "Question",
      name: it.q,
      acceptedAnswer: {
        "@type": "Answer",
        text: it.a,
      },
    })),
  };
}

export type BreadcrumbItem = { name: string; url: string };

export function breadcrumbJsonLd(items: BreadcrumbItem[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((it, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: it.name,
      item: it.url,
    })),
  };
}

export type TickerDatasetArgs = {
  symbol: string;
  name: string;
  url: string;
  /** 0-100 Tapeline score, or null if not scored. */
  score: number | null;
  /** Signal label e.g. "STRONG SETUP", or null if not scored. */
  signal: string | null;
  /** Plain-English why sentence; falls back to a default. */
  why: string | null;
};

/**
 * Schema.org Dataset for a per-ticker page.
 *
 * Deliberately NOT a Review/Rating of the security. A reviewRating on a stock
 * is wrong on two counts:
 *   1. Invalid structured data — Google does not accept FinancialProduct as an
 *      `itemReviewed` type, so the page is ineligible for rich results and GSC
 *      flags it ("Invalid object type for field itemReviewed").
 *   2. Prescriptive framing — a Review + reviewRating authored by Tapeline reads
 *      as "Tapeline rates this security N/100", which collides with the
 *      descriptive-not-prescriptive posture that protects the Australian
 *      publisher's exemption.
 * So we model the page honestly: a dataset of quantitative factor readings.
 * No rating semantics, no recommendation. The visible score stays on the page;
 * it just isn't dressed up as a star rating in JSON-LD.
 */
export function tickerDatasetJsonLd(a: TickerDatasetArgs) {
  const lead = a.why ? `${a.why.trim().replace(/\.$/, "")}. ` : "";
  const description =
    `${lead}Tapeline's six-factor quantitative readings for ${a.name} (${a.symbol}) — ` +
    `trend, relative strength, fundamentals, smart money, macro, and momentum, blended into a ` +
    `single 0-100 composite score. Descriptive market analytics, not financial advice.`;
  return {
    "@context": "https://schema.org",
    "@type": "Dataset",
    name: `Tapeline quantitative scan — ${a.name} (${a.symbol})`,
    description,
    url: a.url,
    isAccessibleForFree: true,
    creator: {
      "@type": "Organization",
      name: "Tapeline",
      url: "https://tapeline.io",
    },
    variableMeasured: [
      "Trend",
      "Relative strength",
      "Fundamentals",
      "Smart money",
      "Macro",
      "Momentum",
      "Composite score (0-100)",
    ],
    keywords: [a.symbol, a.name, "stock scanner", "quantitative score"],
  };
}

export type ArticleArgs = {
  title: string;
  description: string;
  url: string;
  publishedAt: string;       // ISO
  modifiedAt?: string;       // ISO
  author?: string;           // defaults to "Tapeline"
  imageUrl?: string;
};

export function articleJsonLd(a: ArticleArgs) {
  // Author auto-upgrades to Person once founder is disclosed via env flags
  // (see founderPersonJsonLd above). Until then, falls back to the existing
  // Organization-author shape which is what's deployed today.
  const founder = founderPersonJsonLd();
  const author = founder
    ? {
        "@type": "Person",
        "@id": "https://tapeline.io/about#founder",
        name: founder.name,
        url: "https://tapeline.io/about",
      }
    : {
        "@type": "Organization",
        name: a.author ?? "Tapeline",
        url: "https://tapeline.io",
      };
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: a.title,
    description: a.description,
    url: a.url,
    datePublished: a.publishedAt,
    dateModified: a.modifiedAt ?? a.publishedAt,
    author,
    publisher: {
      "@type": "Organization",
      name: "Tapeline",
      // `url` was previously absent — schema.org-validators flagged it as a
      // required field on Organization. Free fix; tightens publisher signal.
      url: "https://tapeline.io",
      logo: {
        "@type": "ImageObject",
        url: "https://tapeline.io/favicon.svg",
      },
    },
    ...(a.imageUrl ? { image: a.imageUrl } : {}),
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": a.url,
      // Schema.org allows WebPage to identify itself via @id alone, but
      // Google's rich-result validator prefers an explicit `url` too.
      url: a.url,
    },
  };
}

/**
 * Organization schema for the brand. Rendered in the root layout so it lands
 * in static HTML (Google + LinkedIn parse it for the Knowledge Panel).
 *
 * Heavy entity signal — legalName, slogan, knowsAbout, address country, and a
 * verified sameAs graph — to disambiguate "Tapeline = US stock scanner SaaS"
 * from the measuring-tool brands and a UK insurance broker that outrank us for
 * the bare brand query (per the 2026-05-19 Search Console audit).
 */
export function organizationJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Tapeline",
    legalName: "Tapeline",
    alternateName: "Tapeline.io",
    slogan: "Read the tape",
    description:
      "Tapeline is a transparent quantitative stock scanner for US equities and ETFs. Every actively-traded ticker gets one 0-100 composite score from a publicly-documented six-factor formula (trend, relative strength, fundamentals, smart money, macro, momentum), refreshed sub-60 seconds during US market hours. Every top-10 daily pick is logged to a public scorecard and back-checked against SPY the next session.",
    url: "https://tapeline.io",
    logo: "https://tapeline.io/favicon.svg",
    foundingDate: "2026",
    // Country-only address — full street suppressed per founder privacy.
    // Country signal alone is enough to help Google localise the brand entity
    // vs the UK/AU "tapeline" measuring-tool sellers.
    address: {
      "@type": "PostalAddress",
      addressCountry: "AU",
    },
    // knowsAbout teaches the Knowledge Graph what topics this entity is about
    // — strongest available signal for brand-query disambiguation.
    knowsAbout: [
      "Stock scanner",
      "Quantitative trading",
      "US equities",
      "Exchange-traded fund",
      "Technical analysis",
      "Fundamental analysis",
      "Market data",
      "Financial technology",
    ],
    // sameAs lists only profiles that actually resolve AND belong to Tapeline
    // (the stock scanner). A 404 is a negative trust signal; a 200 pointing at
    // a DIFFERENT entity is worse. See seo-tools/disclosure/profile_kits.md for
    // the canonical paste-ready copy when claiming each.
    sameAs: [
      "https://x.com/tapeline_io",
      "https://www.linkedin.com/company/tapeline-io",
      "https://github.com/cham-p24/tapeline",
      "https://www.reddit.com/user/tapeline_io",
    ],
    contactPoint: [
      {
        "@type": "ContactPoint",
        email: "support@tapeline.io",
        contactType: "customer support",
        availableLanguage: ["en"],
      },
      {
        "@type": "ContactPoint",
        email: "press@tapeline.io",
        contactType: "press inquiries",
        availableLanguage: ["en"],
      },
    ],
  };
}

/**
 * WebSite schema with SearchAction so Google can render a sitelinks search box
 * under our brand result. Rendered in the root layout (static HTML).
 */
export function websiteJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Tapeline",
    url: "https://tapeline.io",
    potentialAction: {
      "@type": "SearchAction",
      // SearchAction must point at a URL Googlebot can actually crawl with a
      // substituted query. /search accepts ?q=, validates as a ticker, and
      // redirects to /t/.
      target: {
        "@type": "EntryPoint",
        urlTemplate: "https://tapeline.io/search?q={search_term_string}",
      },
      "query-input": "required name=search_term_string",
    },
  };
}

/**
 * SoftwareApplication schema for the product, with four explicit offers
 * (monthly + annual for each tier) so SERPs can show the cheapest entry point
 * and the highest commit. Rendered in the root layout (static HTML).
 */
export function softwareApplicationJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Tapeline",
    applicationCategory: "FinanceApplication",
    applicationSubCategory: "Stock Scanner",
    operatingSystem: "Web",
    description:
      "Live quantitative market scanner for retail stock pickers. One 0-100 score and one plain-English sentence per US ticker, plus squeeze detection, market regime, congressional trades, and a public scorecard.",
    offers: [
      {
        "@type": "Offer",
        name: "Pro · monthly",
        price: "29.99",
        priceCurrency: "USD",
        priceSpecification: {
          "@type": "UnitPriceSpecification",
          price: "29.99",
          priceCurrency: "USD",
          unitText: "MONTH",
        },
        url: "https://tapeline.io/pricing",
      },
      {
        "@type": "Offer",
        name: "Pro · annual",
        price: "299.99",
        priceCurrency: "USD",
        priceSpecification: {
          "@type": "UnitPriceSpecification",
          price: "299.99",
          priceCurrency: "USD",
          unitText: "ANN",
        },
        url: "https://tapeline.io/pricing",
      },
      {
        "@type": "Offer",
        name: "Premium · monthly",
        price: "49.99",
        priceCurrency: "USD",
        priceSpecification: {
          "@type": "UnitPriceSpecification",
          price: "49.99",
          priceCurrency: "USD",
          unitText: "MONTH",
        },
        url: "https://tapeline.io/pricing",
      },
      {
        "@type": "Offer",
        name: "Premium · annual",
        price: "479.99",
        priceCurrency: "USD",
        priceSpecification: {
          "@type": "UnitPriceSpecification",
          price: "479.99",
          priceCurrency: "USD",
          unitText: "ANN",
        },
        url: "https://tapeline.io/pricing",
      },
    ],
    url: "https://tapeline.io",
  };
}

/**
 * Render helper: returns the props for a <script> tag.
 * Usage:
 *   <script {...jsonLdScript(faqJsonLd([...]))} />
 */
export function jsonLdScript(data: unknown) {
  return {
    type: "application/ld+json",
    dangerouslySetInnerHTML: { __html: JSON.stringify(data) },
  } as const;
}

/**
 * HowTo schema for instructional blog posts.
 *
 * Unlocks Google's step-by-step rich-result variant — the SERP card with
 * numbered steps surfaced above the fold under the post URL. Massive CTR
 * lift on educational queries when it triggers ("how to find momentum
 * stocks", "what is RSI", "best time to buy stocks").
 *
 * Apply with restraint: Google's quality classifier rejects HowTo schema
 * on pages where the body doesn't literally walk through ordered steps.
 * Only the genuinely instructional posts in posts.ts should pass
 * `howToSteps` — see the type comment on BlogPost.howToSteps for the
 * eligibility heuristic.
 *
 * `totalTime` is ISO 8601 duration (PT7M = 7 minutes). Conservative
 * defaults of 5-10 min suit the long-form educational posts we ship.
 */
export type HowToArgs = {
  name: string;
  description: string;
  url: string;
  imageUrl?: string;
  totalTime?: string; // ISO 8601 duration
  steps: { name: string; text: string }[];
};

export function howToJsonLd(a: HowToArgs) {
  return {
    "@context": "https://schema.org",
    "@type": "HowTo",
    name: a.name,
    description: a.description,
    ...(a.imageUrl ? { image: a.imageUrl } : {}),
    ...(a.totalTime ? { totalTime: a.totalTime } : {}),
    step: a.steps.map((s, i) => ({
      "@type": "HowToStep",
      position: i + 1,
      name: s.name,
      text: s.text,
      url: `${a.url}#step-${i + 1}`,
    })),
  };
}

/**
 * Schema.org Dataset for /scorecard.
 *
 * The public scorecard is Tapeline's flagship proprietary asset — a permanent,
 * append-only record of every top-10 daily pick with original score, signal,
 * and reasoning, back-checked vs SPY the next session. Modeling it as Dataset
 * makes it citable as a structured data source by AI systems and lets it
 * surface in Google Dataset Search. Live stats (days tracked, hit rate) are
 * deliberately omitted from the schema because the page fetches them client-
 * side; embedding stale numbers in SSR HTML is worse than omitting them.
 */
export function scorecardDatasetJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "Dataset",
    "@id": "https://tapeline.io/scorecard#dataset",
    name: "Tapeline Public Scorecard",
    alternateName: "Tapeline Top-10 Daily Picks Track Record",
    description:
      "Append-only public record of every top-10 daily pick produced by the Tapeline 6-factor scanner. Each entry preserves the original Tapeline Score, signal label, plain-English reasoning, and the realised next-session return benchmarked against SPY. No hindsight editing, no cherry-picking, no survivor bias.",
    url: "https://tapeline.io/scorecard",
    isAccessibleForFree: true,
    license: "https://tapeline.io/legal/terms",
    creator: {
      "@type": "Organization",
      name: "Tapeline",
      url: "https://tapeline.io",
    },
    publisher: {
      "@type": "Organization",
      name: "Tapeline",
      url: "https://tapeline.io",
    },
    spatialCoverage: {
      "@type": "Place",
      name: "United States equity markets (NYSE, NASDAQ, AMEX)",
    },
    keywords: [
      "stock scanner track record",
      "transparent quant scoring",
      "Tapeline Score",
      "six-factor model",
      "back-test vs SPY",
      "public scorecard",
      "stock picking accountability",
    ],
    variableMeasured: [
      { "@type": "PropertyValue", name: "Tapeline Score", description: "Composite 0–100 score from six published-weight factors", minValue: 0, maxValue: 100 },
      { "@type": "PropertyValue", name: "Signal label", description: "HIGH CONVICTION / STRONG SETUP / CONSTRUCTIVE / NEUTRAL / CAUTION / WEAK" },
      { "@type": "PropertyValue", name: "Trend factor (25%)", minValue: 0, maxValue: 100 },
      { "@type": "PropertyValue", name: "Relative Strength factor (20%)", minValue: 0, maxValue: 100 },
      { "@type": "PropertyValue", name: "Fundamentals factor (15%)", minValue: 0, maxValue: 100 },
      { "@type": "PropertyValue", name: "Smart Money factor (15%)", minValue: 0, maxValue: 100 },
      { "@type": "PropertyValue", name: "Macro factor (15%)", minValue: 0, maxValue: 100 },
      { "@type": "PropertyValue", name: "Momentum factor (10%)", minValue: 0, maxValue: 100 },
      { "@type": "PropertyValue", name: "Realised 1-day return vs SPY", description: "Pick performance one trading session forward, benchmarked against SPY", unitText: "percent" },
    ],
    distribution: [
      {
        "@type": "DataDownload",
        encodingFormat: "text/html",
        contentUrl: "https://tapeline.io/scorecard",
        name: "Web view (canonical)",
      },
    ],
    measurementTechnique:
      "Closing price comparison: pick scored at session N close, evaluated at session N+1 close, return delta vs SPY return delta.",
    sameAs: [
      "https://tapeline.io/blog/the-formula-is-public",
      "https://tapeline.io/how-it-works",
    ],
  };
}

export type BlogIndexArgs = {
  posts: { slug: string; title: string; excerpt: string; publishedAt: string; author: string }[];
};

/**
 * Schema.org Blog + ItemList for /blog.
 * Replaces the un-typed schema the audit caught on /blog.
 */
export function blogIndexJsonLd(a: BlogIndexArgs) {
  return [
    {
      "@context": "https://schema.org",
      "@type": "Blog",
      "@id": "https://tapeline.io/blog#blog",
      name: "Tapeline Blog",
      url: "https://tapeline.io/blog",
      description:
        "Methodology notes, factor design choices, and accountability writeups from Tapeline. Every post is anchored to public data — no opinion-only takes.",
      publisher: {
        "@type": "Organization",
        name: "Tapeline",
        url: "https://tapeline.io",
        logo: { "@type": "ImageObject", url: "https://tapeline.io/favicon.svg" },
      },
      inLanguage: "en",
      blogPost: a.posts.map((p) => ({
        "@type": "BlogPosting",
        headline: p.title,
        description: p.excerpt,
        url: `https://tapeline.io/blog/${p.slug}`,
        datePublished: p.publishedAt,
        author: { "@type": "Organization", name: p.author, url: "https://tapeline.io" },
      })),
    },
    {
      "@context": "https://schema.org",
      "@type": "ItemList",
      "@id": "https://tapeline.io/blog#itemlist",
      itemListOrder: "https://schema.org/ItemListOrderDescending",
      // Schema.org ListItem requires `item` — the URL/name shortcut isn't
      // sufficient on its own. Embed the BlogPosting as the item so Google
      // gets both the position and the post entity in one block.
      itemListElement: a.posts.map((p, i) => ({
        "@type": "ListItem",
        position: i + 1,
        url: `https://tapeline.io/blog/${p.slug}`,
        name: p.title,
        item: {
          "@type": "BlogPosting",
          "@id": `https://tapeline.io/blog/${p.slug}`,
          headline: p.title,
          url: `https://tapeline.io/blog/${p.slug}`,
          datePublished: p.publishedAt,
        },
      })),
    },
  ];
}

/**
 * Schema.org ContactPage + AboutPage for /press.
 * Currently /press only emits BreadcrumbList; this adds the contact +
 * publisher entity graph journalists' tools (e.g. Muck Rack, JustReachOut)
 * scrape for press-contact discovery.
 */
export function pressContactPageJsonLd() {
  return [
    {
      "@context": "https://schema.org",
      "@type": "ContactPage",
      "@id": "https://tapeline.io/press#contactpage",
      url: "https://tapeline.io/press",
      name: "Tapeline Press & Media",
      description:
        "Press kit, fact sheet, founder bio, brand assets, and direct press contact for Tapeline — the transparent quantitative stock scanner with a public scorecard.",
      isPartOf: { "@type": "WebSite", url: "https://tapeline.io", name: "Tapeline" },
      mainEntity: {
        "@type": "Organization",
        name: "Tapeline",
        url: "https://tapeline.io",
        logo: "https://tapeline.io/favicon.svg",
        foundingLocation: {
          "@type": "Place",
          address: {
            "@type": "PostalAddress",
            addressLocality: "Melbourne",
            addressRegion: "VIC",
            addressCountry: "AU",
          },
        },
        contactPoint: [
          {
            "@type": "ContactPoint",
            contactType: "press inquiries",
            email: "press@tapeline.io",
            availableLanguage: ["en"],
            areaServed: "Worldwide",
          },
          {
            "@type": "ContactPoint",
            contactType: "customer support",
            email: "support@tapeline.io",
            availableLanguage: ["en"],
          },
        ],
      },
    },
  ];
}

/**
 * Schema.org AboutPage (or ProfilePage when the founder is disclosed) for
 * /about. Until disclosure, mainEntity is the Tapeline Organization; once
 * `NEXT_PUBLIC_FOUNDER_DISCLOSED=true` + name + at least one same-as link
 * are set, mainEntity flips to the Person and the @type upgrades to
 * ProfilePage — the type Google explicitly looks for to attribute E-E-A-T
 * to a named human.
 */
export function aboutProfilePageJsonLd() {
  const founder = founderPersonJsonLd();
  return {
    "@context": "https://schema.org",
    "@type": founder ? "ProfilePage" : "AboutPage",
    "@id": "https://tapeline.io/about#aboutpage",
    url: "https://tapeline.io/about",
    name: founder ? `About ${founder.name} — Tapeline` : "About Tapeline",
    description:
      "Who's behind Tapeline, why we publish the formula and the scorecard, what we believe about transparency in retail finance tooling, and how to reach us.",
    isPartOf: { "@type": "WebSite", url: "https://tapeline.io", name: "Tapeline" },
    mainEntity: founder ?? {
      "@type": "Organization",
      "@id": "https://tapeline.io#org",
      name: "Tapeline",
      url: "https://tapeline.io",
      logo: "https://tapeline.io/favicon.svg",
      description:
        "Tapeline is a quantitative stock scanner that publishes its 6-factor scoring formula and back-checks every top-10 daily pick against the next-day SPY-relative move.",
      knowsAbout: [
        "Quantitative equity scoring",
        "Multi-factor models",
        "Public-record back-testing",
        "Stock scanner methodology",
        "Six-factor scoring",
        "Smart-money flow analysis",
        "Macro regime classification",
      ],
    },
  };
}

export type ItemListTickerArgs = {
  /** Page URL (e.g. https://tapeline.io/best-stocks-for/swing-traders). */
  pageUrl: string;
  /** Page name, e.g. "Best Stocks to Swing Trade". */
  name: string;
  description: string;
  /** Stocks in ranked order. score may be null if not yet scored. */
  items: Array<{ symbol: string; name: string; score: number | null }>;
};

/**
 * Schema.org ItemList for a ranked stock listicle (/best-stocks-for/*).
 *
 * Why: Google's quality filter rejects "thin/templated" programmatic pages
 * unless the page has unique, structured data per slug. Emitting an explicit
 * ItemList with the 30 actual ranked tickers per strategy (sourced live from
 * the scanner) gives Google an unambiguous "these are different lists, with
 * different items, each holding its own ranking" signal — the exact pattern
 * Google docs recommend for ranked content.
 */
export function tickerItemListJsonLd(a: ItemListTickerArgs) {
  return {
    "@context": "https://schema.org",
    "@type": "ItemList",
    "@id": `${a.pageUrl}#itemlist`,
    name: a.name,
    description: a.description,
    itemListOrder: "https://schema.org/ItemListOrderDescending",
    numberOfItems: a.items.length,
    url: a.pageUrl,
    itemListElement: a.items.map((it, i) => ({
      "@type": "ListItem",
      position: i + 1,
      url: `https://tapeline.io/t/${it.symbol}`,
      name: `${it.name} (${it.symbol})`,
      item: {
        "@type": "FinancialProduct",
        "@id": `https://tapeline.io/t/${it.symbol}`,
        name: `${it.name} (${it.symbol})`,
        category: "Stock",
        url: `https://tapeline.io/t/${it.symbol}`,
        ...(it.score != null
          ? {
              additionalProperty: {
                "@type": "PropertyValue",
                name: "Tapeline Score",
                value: it.score,
                minValue: 0,
                maxValue: 100,
              },
            }
          : {}),
      },
    })),
  };
}

export type CompareArgs = {
  competitorName: string;
  competitorUrl: string;
  competitorPriceMonthly?: number; // entry monthly tier price USD
  competitorAnnualNote?: string; // free-form e.g. "$249/yr (annual only)"
  pageUrl: string; // e.g. https://tapeline.io/compare/finviz
};

/**
 * Schema.org head-to-head pair for /compare/{competitor} pages. Emits:
 *   - WebPage referencing both as `about`
 *   - SoftwareApplication for Tapeline (canonical)
 *   - SoftwareApplication for the competitor (constructed from args)
 *
 * Pair this with the existing FAQPage schema each compare page already emits.
 * The visible head-to-head table is page-specific and intentionally NOT
 * mirrored in schema (would force every WIN row into ItemList noise).
 */
export function compareJsonLd(a: CompareArgs) {
  const competitorOffer = a.competitorPriceMonthly
    ? [
        {
          "@type": "Offer",
          price: String(a.competitorPriceMonthly),
          priceCurrency: "USD",
          priceSpecification: {
            "@type": "UnitPriceSpecification",
            price: String(a.competitorPriceMonthly),
            priceCurrency: "USD",
            unitText: "MONTH",
          },
          url: a.competitorUrl,
          ...(a.competitorAnnualNote ? { description: a.competitorAnnualNote } : {}),
        },
      ]
    : [];
  return [
    {
      "@context": "https://schema.org",
      "@type": "WebPage",
      url: a.pageUrl,
      isPartOf: { "@type": "WebSite", url: "https://tapeline.io", name: "Tapeline" },
      about: [
        { "@id": "https://tapeline.io#softwareapp" },
        { "@id": `${a.competitorUrl}#competitor` },
      ],
    },
    {
      "@context": "https://schema.org",
      "@type": "SoftwareApplication",
      "@id": "https://tapeline.io#softwareapp",
      name: "Tapeline",
      applicationCategory: "FinanceApplication",
      applicationSubCategory: "Stock Scanner",
      operatingSystem: "Web",
      url: "https://tapeline.io",
      description:
        "Live transparent six-factor scanner with published weights and a public daily scorecard back-checked vs SPY.",
      offers: [
        { "@type": "Offer", name: "Pro · monthly", price: "29.99", priceCurrency: "USD", url: "https://tapeline.io/pricing" },
        { "@type": "Offer", name: "Pro · annual", price: "299.99", priceCurrency: "USD", url: "https://tapeline.io/pricing" },
        { "@type": "Offer", name: "Premium · monthly", price: "49.99", priceCurrency: "USD", url: "https://tapeline.io/pricing" },
        { "@type": "Offer", name: "Premium · annual", price: "479", priceCurrency: "USD", url: "https://tapeline.io/pricing" },
      ],
      featureList: [
        "Six published-weight factors (Trend 25%, Relative Strength 20%, Fundamentals 15%, Smart Money 15%, Macro 15%, Momentum 10%)",
        "Public scorecard — every top-10 daily pick back-checked vs SPY next session",
        "Sub-60-second refresh during market hours",
        "Plain-English reasoning per ticker (free tier included)",
        "~2,500 actively scored from the full liquid US universe",
        "Squeeze + market-regime detection",
        "Congressional trades + recent insider buys via SEC Form 4 (Premium)",
      ],
    },
    {
      "@context": "https://schema.org",
      "@type": "SoftwareApplication",
      "@id": `${a.competitorUrl}#competitor`,
      name: a.competitorName,
      applicationCategory: "FinanceApplication",
      operatingSystem: "Web",
      url: a.competitorUrl,
      ...(competitorOffer.length ? { offers: competitorOffer } : {}),
    },
  ];
}
