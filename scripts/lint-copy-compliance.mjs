#!/usr/bin/env node
/**
 * Copy-compliance linter — mechanical enforcement of the financial-promotion
 * rules in docs/COMPLIANCE_COPY_RULES.md.
 *
 * WHY THIS EXISTS
 * ---------------
 * Tapeline publishes descriptive analytics about securities. Under the ASIC /
 * FTC framing in our legal review, the highest-risk failure mode is NOT a
 * deliberate misstatement — it is a well-intentioned growth edit that
 * reintroduces an evaluative adjective or a performance claim into a TEMPLATE.
 * One templated adjective ("a strong candidate") replicated across a
 * per-ticker route becomes thousands of implied recommendations, each of
 * which is arguably personal advice.
 *
 * Human memory does not survive a growth sprint. This linter does.
 *
 * DESIGN PRINCIPLE: PRECISION OVER RECALL
 * ---------------------------------------
 * A linter that cries wolf gets disabled, and a disabled linter protects
 * nobody. Every pattern below is written to fire on phrasings we would have
 * to defend to a regulator, not on every appearance of a loaded word.
 * Concretely:
 *   - Comments are stripped before scanning. Comments are not user-facing,
 *     and this codebase's comments discuss these very concepts at length.
 *   - Weak evaluative adjectives ("strong", "attractive") only fire when they
 *     land near a security noun or a ticker interpolation. "strong password"
 *     is not a securities recommendation.
 *   - Ambiguous commercial words are context-gated: "guaranteed" fires on
 *     "guaranteed returns", never on "30-day money-back guarantee".
 * When a legitimate use still trips a rule, it belongs in the allowlist file
 * (scripts/copy-compliance.allow.json) WITH A WRITTEN REASON — not in a
 * loosened pattern.
 *
 * USAGE
 *   node scripts/lint-copy-compliance.mjs             # lint the repo, exit 1 on findings
 *   node scripts/lint-copy-compliance.mjs --json      # machine-readable output
 *   node scripts/lint-copy-compliance.mjs path/to.tsx # lint specific files
 *
 * Exit code 0 = clean, 1 = findings, 2 = linter/config error.
 */

import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, relative, resolve, dirname, sep } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "..");
const ALLOW_FILE = join(HERE, "copy-compliance.allow.json");

/* ------------------------------------------------------------------ *
 * PRODUCT LEXICON — masked out before scanning.
 *
 * "STRONG SETUP" and "HIGH CONVICTION" are not adjectives here: they are the
 * names of two of the six score bands (70-84 and 85-100) in Tapeline's
 * published signal taxonomy, and they appear as enum values, CSS-class
 * switches, URL slugs and legend rows in ~50 files. Treating the band name as
 * an evaluative adjective would bury every real finding under a landslide of
 * noise, and a linter nobody can read is a linter someone deletes.
 *
 * The band vocabulary itself was reviewed separately (see changelog: the
 * labels were rewritten to descriptive language). If it is ever revisited,
 * revisit this mask with it — that is a copy decision, not a lint decision.
 * ------------------------------------------------------------------ */
const PRODUCT_LEXICON = [
  /\bstrong[-\s]setup\b/gi,
  /\bhigh[-\s]conviction\b/gi,
];

function maskProductLexicon(text) {
  let out = text;
  for (const re of PRODUCT_LEXICON) {
    out = out.replace(new RegExp(re.source, re.flags), (m) => "·".repeat(m.length));
  }
  return out;
}

/* ------------------------------------------------------------------ *
 * NEGATION GUARD
 *
 * The largest false-positive class in a compliance linter is the DISCLAIMER
 * itself: "no countdown", "≠ guaranteed return", "a score of 92 doesn't mean
 * you should buy", "we do not claim to beat the market". Naming a prohibited
 * claim in order to deny it is exactly what a compliant page does, and Rule 9
 * means those pages have to exist.
 *
 * So: a match is suppressed when a negator sits within 40 characters before
 * it with no sentence boundary in between. The trade-off is real — "we do not
 * think you should buy" is also suppressed — but affirmative claims are the
 * regulatory exposure, and precision is what keeps this check switched on.
 * ------------------------------------------------------------------ */
const NEGATOR =
  /(?:\bno\b|\bnot\b|\bnever\b|\bwithout\b|\bnor\b|\bisn'?t\b|\baren'?t\b|\bdon'?t\b|\bdoesn'?t\b|\bdidn'?t\b|\bwon'?t\b|\bcan'?t\b|\bcannot\b|\bnon-|\brather\s+than\b|\binstead\s+of\b|≠|!=)/i;

function isNegated(text, matchIndex) {
  const windowStart = Math.max(0, matchIndex - 40);
  const before = text.slice(windowStart, matchIndex);
  // A sentence boundary resets the scope of the negation.
  const lastBoundary = Math.max(before.lastIndexOf(". "), before.lastIndexOf("\n"));
  const scope = lastBoundary === -1 ? before : before.slice(lastBoundary);
  return NEGATOR.test(scope);
}

/* ------------------------------------------------------------------ *
 * Security nouns — the words that turn a vague adjective into a claim
 * about a financial product. Deliberately narrow: generic English nouns
 * ("candidate", "company", "play", "setup") are excluded because they
 * produced real false positives against copy about product features and
 * competitor tooling ("strong candidate for a future Tapeline factor").
 * ------------------------------------------------------------------ */
// NOTE the word-boundary placement: `\b` is applied to the word alternatives
// only. A leading `\b` in front of `${` never matches, because `$` is not a
// word character — which silently disabled every template-interpolation case,
// i.e. exactly the templated copy this rule exists to police.
const SECURITY_NOUN =
  "(?:\\b(?:stocks?|tickers?|shares?|equit(?:y|ies)|securit(?:y|ies)|symbols?|" +
  "picks?|names?|positions?|holdings?)\\b|\\$\\{[^}]*\\}|\\{\\{?[A-Za-z_]+\\}?\\})";

/**
 * Adjective within ~24 chars of a security noun, in either order.
 * Commas are excluded from the gap: a comma almost always separates list
 * items rather than binding an adjective to a noun, and allowing it matched
 * "strong portfolio analytics, equity research" as an evaluative claim.
 */
/**
 * A suitability-style term preceded (within ~28 chars) by a cue that we are
 * ASKING for it rather than disclaiming knowledge of it.
 */
function collectionCue(term) {
  return new RegExp(
    `\\b(?:what(?:'s| is| are)?|select|choose|enter|tell\\s+us|share|specify|` +
      `set|rate|pick|describe|your)\\s+(?:your|the|is\\s+your)?\\s*${term}\\s*\\??` +
      `(?=\\s*(?:\\?|:|<|"|'|\\{|$))`,
    "i",
  );
}

function nearSecurityNoun(adjective) {
  return new RegExp(
    `\\b${adjective}\\b[^.,<>\\n]{0,24}?${SECURITY_NOUN}` +
      `|${SECURITY_NOUN}[^.,<>\\n]{0,16}?\\bis\\s+(?:a\\s+|an\\s+|very\\s+)?${adjective}\\b`,
    "i",
  );
}

/* ------------------------------------------------------------------ *
 * RULES
 *
 * Each rule: { id, brief, patterns: [RegExp], message }
 * `brief` cites the numbered rule in docs/COMPLIANCE_COPY_RULES.md so a
 * failing build tells the author WHICH constraint they hit and why.
 * ------------------------------------------------------------------ */
/**
 * The trial length, read from the ONE place that defines it.
 *
 * Not a literal here. A linter that hardcodes the number it is policing stops
 * policing the moment the number moves, and would then have to be edited in
 * lockstep with the thing it exists to guard — which is the same failure it is
 * meant to catch.
 */
export const TRIAL_DAYS_IN_COPY = (() => {
  try {
    const src = readFileSync("frontend/lib/trial.ts", "utf8");
    const m = src.match(/export const TRIAL_DAYS\s*=\s*(\d+)/);
    return m ? Number(m[1]) : null;
  } catch {
    return null;
  }
})();

/**
 * Substitute the interpolated constants that appear inside user-facing copy,
 * so proximity rules measure rendered length.
 *
 * Deliberately a small, explicit table rather than a TS evaluator: the only
 * placeholders that appear inside compliance-relevant sentences are the trial
 * length and the price labels, and a real evaluator would be a much larger
 * surface for a much smaller gain. An unlisted placeholder is left alone,
 * which is the safe direction — it can only make a window LOOK longer than it
 * renders, never shorter.
 */
export function expandKnownConstants(text) {
  // Read from lib/trial.ts, NEVER written as a digit here. This table used to
  // hardcode "14-day", so when the trial moved to 30 days the linter expanded
  // every CORRECT `{TRIAL_LENGTH_LABEL}` into the OLD number and then flagged
  // the pages that were right — while pages carrying a literal "14-day" were
  // the ones actually wrong. A guard holding its own stale copy of the value
  // it guards is worse than no guard: it reports the truth as the error.
  const days = TRIAL_DAYS_IN_COPY == null ? "" : String(TRIAL_DAYS_IN_COPY);
  if (!days) return text;
  return text
    .replace(/\$\{TRIAL_LENGTH_LABEL\}/g, `${days}-day`)
    .replace(/\{TRIAL_LENGTH_LABEL\}/g, `${days}-day`)
    .replace(/\$\{TRIAL_DAYS\}/g, days)
    .replace(/\{TRIAL_DAYS\}/g, days);
}


export const RULES = [
  {
    id: "performance-claim",
    brief: "Rule 1 — descriptive only; never imply returns, profit or outperformance",
    message:
      "Reads as a claim that Tapeline produces returns or outperformance. " +
      "Describe what the product MEASURES, not what it will earn.",
    patterns: [
      // "beat the market" is the flagship banned phrase — unconditional.
      // NOTE: "beat SPY" is deliberately NOT here. Rule 3 expressly permits a
      // vs-SPY figure in a neutral data table, and "Beat SPY rate" is the
      // operational NAME of that column (share of picks whose next-day return
      // exceeded SPY's). Banning the metric's own definition would push the
      // scorecard toward vaguer, less auditable language — the opposite of
      // what the rule is for. What Rule 3 polices is WHERE that figure
      // appears, which the vs-spy-in-headline check below enforces.
      /\bbeat(?:s|ing|en)?\s+(?:the\s+)?(?:market|broader\s+market)\b/i,
      // "outperform" is context-gated. The word legitimately appears in the
      // academic definition of the Momentum factor ("stocks that have
      // outperformed tend to continue outperforming") and in critiques of
      // competitor marketing. What is prohibited is US claiming it.
      /\b(?:we|our|tapeline|users?|subscribers?|the\s+(?:scanner|score|scores|formula|picks?|signals?))\b[^.<>\n]{0,40}?\bout[-\s]?perform/i,
      /\b(?:will|can|helps?\s+you|designed\s+to|built\s+to|and)\s+out[-\s]?perform\s+(?:the\s+)?(?:market|s&p|spy)\b/i,
      /\bout[-\s]?performance\s+(?:guarantee|promise|of\s+our)\b/i,
      /\bwinning\s+(?:stocks?|picks?|trades?|tickers?|names?|positions?)\b/i,
      /\bbest\s+picks?\b/i,
      /\bstrong\s+buy\b/i,
      /\btop\s+performers?\s+to\s+buy\b/i,
      // "guaranteed" only when attached to an outcome — "money-back
      // guarantee" is a real, permitted refund term and must not fire.
      /\bguarantee(?:d|s)?\s+(?:you\s+)?(?:returns?|profits?|gains?|results?|performance|income|winners?)\b/i,
      /\b(?:returns?|profits?|gains?|results?)\s+(?:are\s+)?guaranteed\b/i,
      /\bproven\s+(?:returns?|results?|profits?|performance|track\s+record)\b/i,
      /\byou\s+should\s+(?:buy|sell|short|hold|own|invest|trade|add|exit)\b/i,
      /\bwe\s+recommend\s+(?:buying|selling|shorting|you\s+(?:buy|sell))\b/i,
      /\bmakes?\s+(?:you|our\s+users?)\s+money\b/i,
      // "edge" only in the performance-promise sense (Rule 1's wording).
      // "if your edge is reading charts" and "where Zacks has a real edge"
      // are about a workflow and a competitor's feature set respectively —
      // neither is a representation that Tapeline produces returns.
      /\b(?:unfair|proven|guaranteed|statistical)\s+edge\b/i,
      /\bgain(?:ing)?\s+an?\s+edge\b/i,
      /\bedge\s+over\s+the\s+(?:market|s&p|spy)\b/i,
      /\b(?:gives?|get|getting)\s+you\s+an?\s+edge\b/i,
      /\brisk[-\s]free\s+(?:returns?|profits?|trade|trading)\b/i,
      /\bcan'?t\s+lose\b/i,
      /\bprofit\s+from\s+(?:our|the)\s+(?:scores?|signals?|picks?)\b/i,
    ],
  },
  {
    id: "evaluative-adjective",
    brief: "Rule 2 — no evaluative adjectives on securities in templated copy",
    message:
      "An evaluative adjective applied to a security. In a template this " +
      "replicates into thousands of implied recommendations. State what the " +
      "factor measured instead (e.g. 'RSI is 71', not 'looks strong').",
    patterns: [
      // Unconditionally evaluative — these words carry a forward-looking
      // valuation judgment no matter what noun follows.
      /\bunder[-\s]?valued\b/i,
      /\bover[-\s]?valued\b/i,
      /\bpoised\s+(?:to|for)\b/i,
      /\bset\s+to\s+(?:soar|surge|rally|pop|run)\b/i,
      /\bready\s+to\s+(?:break\s?out|run|rip|pop)\b/i,
      /\bmust[-\s]own\b/i,
      // "breakout" is a scan CATEGORY and a chart-pattern name in a scanner
      // product ("Breakout Stocks", "breakout watch" ChartLists) — naming the
      // scan is not predicting the move. Only the predictive forms fire.
      /\bbreakout\s+candidates?\b/i,
      /\b(?:is|looks?\s+like|shaping\s+up\s+as)\s+an?\s+breakout\b/i,
      // Context-gated — only a problem when pointed at a security.
      nearSecurityNoun("strong"),
      nearSecurityNoun("promising"),
      nearSecurityNoun("attractive"),
      nearSecurityNoun("compelling"),
      nearSecurityNoun("undervalued"),
      nearSecurityNoun("bullish"),
    ],
  },
  {
    id: "derived-performance-stat",
    brief: "Rule 4 — no derived performance statistics",
    message:
      "Derived performance statistics (annualised return, Sharpe, hypothetical " +
      "P&L, backtests) turn a factual archive into a performance representation. " +
      "Publishing the raw record is fine; summarising it as a return is not.",
    patterns: [
      /\bannuali[sz]ed\s+(?:return|gain|performance|alpha)/i,
      /\bsharpe\s+ratio\b/i,
      /\bsortino\b/i,
      /\bcompound\s+annual\s+growth\b/i,
      /\bhypothetical\s+(?:p\s*&\s*l|pnl|profit|returns?|performance)\b/i,
      /\bif\s+you\s+had\s+(?:followed|bought|invested|held|traded)\b/i,
      /\bsimulated\s+(?:returns?|performance|results?|trading)\b/i,
      /\bmodel(?:led|ed)?\s+performance\b/i,
      // Rule 4 prohibits PUBLISHING a derived performance statistic, not
      // saying the word. "Backtesting depth" as a comparison-table row (where
      // our answer is "we don't") and a roadmap item named "Backtesting" are
      // descriptions of a capability, not a performance representation.
      /\bback[-\s]?test(?:ed|ing)?\s+(?:results?|returns?|performance|p\s*&\s*l|pnl|track\s+record)\b/i,
      /\bour\s+back[-\s]?test/i,
      // Rule 3 prohibits a cumulative "up and to the right" chart outright,
      // so the component name itself is a finding — `<EquityCurve/>` matches
      // as readily as the prose does.
      /\bequity[-\s]?curve\b/i,
      /\bcumulative\s+returns?\b/i,
    ],
  },
  {
    id: "card-free-trial",
    brief: "Rule 10 — never advertise the TRIAL as card-free",
    message:
      "Card-free TRIAL claim. The Premium trial is card-required ($0 that day, " +
      "first charge when it ends), so 'no credit card' next to 'trial' is false " +
      "advertising on a financial product. NARROWED 2026-08-30 (#683): the card " +
      "wall at first sign-in is gone, so a card-free claim about SIGNING UP or " +
      "about the FREE PLAN is now TRUE and no longer matches this rule — signing " +
      "up takes an email and a password. Saying the PUBLIC RECORD needs no card " +
      "is likewise still true. Two things stay banned everywhere: card-free " +
      "wording within ~40 characters of 'trial', and the marketing phrase 'no " +
      "credit card required', which is true of sign-up but false of the trial " +
      "and never says which — prefer plain wording like 'email and password, no " +
      "card'. For a dated historical entry (e.g. /changelog), use an inline " +
      "copy-compliance-allow with a reason.",
    patterns: [
      // "14-day trial ... no credit card" / "trial is no-card".
      // Two temperings, both for honest copy that names the constraint:
      //   (?<!\bno\s) / (?!\bno\b) — "no card, no trial" on the newsletter
      //     capture rules the trial OUT; it does not offer a card-free one.
      //   (?![-\s]free) -- "there is no card-free tier to sign up for" is the
      //     honest negation on /best-finviz-alternatives, not a claim.
      /(?<!\bno\s)\btrial\b(?:(?!\bno\b)[^.!?]){0,40}\bno[-\s]?(?:credit[-\s]?)?card\b(?![-\s]free)/i,
      // "no-credit-card trial". Since #683 this window is TRIAL-only:
      // "no card to sign up" and "free plan, no card" are true statements
      // about the ACCOUNT, and banning them would have the linter enforce
      // the opposite of what the product does. A sentence break still ends
      // the window, so "... no card. A card starts the trial." stays clean
      // and is the phrasing to reach for when both facts must sit together.
      /\bno[-\s]?(?:credit[-\s]?)?card\b(?![-\s]free)(?:(?!\bno\b)[^.!?]){0,40}\btrial\b/i,
      // "card-free trial" ("card-free account" is now true, so it is out).
      /(?<!\bno\s)\bcard[-\s]free\b[^.!?]{0,20}\btrial\b/i,
      // The marketing phrase itself, wherever it lands. Kept because it is
      // ambiguous between the account (true) and the trial (false).
      /\bno\s+credit\s+card\s+(?:required|needed|necessary)\b/i,
    ],
  },
  {
    id: "stale-trial-length",
    brief: "The stated trial length must match the trial we actually run",
    message:
      "This states a trial length that is NOT the one the product runs. The " +
      "trial length is a promise about when a customer's card gets charged, so " +
      "a stale number here is a false statement about money, not a typo. It " +
      "happened: moving the trial from 14 to 30 days left 165 claims of '14-day " +
      "Premium trial' and 'first charge on day 14' across 72 files, and " +
      "tapeline.io/signup advertised BOTH lengths on the same page. Read the " +
      "number from lib/trial.ts (TRIAL_DAYS / TRIAL_LENGTH_LABEL) rather than " +
      "writing a digit. For a dated historical entry (/changelog, /legal/refund " +
      "supersession) use an inline copy-compliance-allow with a reason.",
    patterns:
      TRIAL_DAYS_IN_COPY == null
        ? []
        : [
            // A trial LENGTH claim, not any sentence with a number near
            // "trial". "3 days left on your trial" and "your trial ends in 3
            // days" are correct copy about the pre-charge warning window, and
            // an earlier version of this rule flagged both - a rule that cries
            // wolf on true copy gets muted, and then it guards nothing.
            //
            // The leading \b is load-bearing: without it the engine can begin
            // matching INSIDE the number, on the "0" of "30", so the negative
            // lookahead trivially passes and correct copy gets flagged.
            //
            // Hyphenated form: "14-day Premium trial".
            new RegExp(
              String.raw`\b(?!${TRIAL_DAYS_IN_COPY}\b)\d{1,3}-days?\b[^.!?]{0,24}\btrial\b`,
              "i",
            ),
            // "the trial runs 14 days" / "trial lasts 14 days" / "trial is 14 days".
            new RegExp(
              String.raw`\btrial\b[^.!?]{0,12}\b(?:runs|lasts|is|of)\s+(?!${TRIAL_DAYS_IN_COPY}\b)\d{1,3}\s+days\b`,
              "i",
            ),
            // "Premium free for 14 days" / "free for 14 days".
            new RegExp(
              String.raw`\bfree for (?!${TRIAL_DAYS_IN_COPY}\b)\d{1,3}\s+days\b`,
              "i",
            ),
            // The same promise phrased as a date: "first charge on day 14".
            new RegExp(
              String.raw`\bfirst charge (?:is )?on day (?!${TRIAL_DAYS_IN_COPY}\b)\d{1,3}\b`,
              "i",
            ),
          ],
  },
  {
    id: "card-required-signup",
    brief: "Rule 10b — never claim a card is needed to SIGN UP",
    message:
      "Card-required SIGN-UP claim. This is the inverse of card-free-trial and " +
      "became false on 2026-08-30 (#683), which removed the card wall: signing " +
      "up takes an email and a password, and the scanner opens on the free " +
      "plan. #548 had made the opposite claim true for eight days and #686 " +
      "corrected 79 places when it stopped being — but only the card-FREE " +
      "direction was ever linted, so the card-REQUIRED direction kept " +
      "regenerating from paste-ready templates (the brand SERP kit, the Chrome " +
      "Web Store listing, newsletter outreach, the launch playbook) and from a " +
      "/compare FAQ answer that also ships as FAQPage JSON-LD to Google. " +
      "The trial IS card-required and saying so is correct — the banned shape " +
      "is attaching the card to the ACCOUNT or to SIGNING IN. Prefer the " +
      "three-layer wording used on /compare/finviz: the record needs no " +
      "account; signing up takes an email and a password; a card starts the " +
      "trial. For a DATED historical entry (/changelog, /legal/refund, " +
      "llms.txt), use an inline copy-compliance-allow with a reason.",
    patterns: [
      // "a new account adds a card at first sign-in" and its variants.
      /\bcard\b[^.!?]{0,30}\bat\s+first\s+sign[-\s]?in\b/i,
      /\b(?:new\s+)?accounts?\b[^.!?]{0,40}\badds?\s+(?:a\s+)?card\b/i,
      // "signing up takes a card" / "an account requires a card"
      // `(?<![\/\w])` keeps a URL PATH out of it: an href="/signup" sitting
      // near true trial copy ("starting it takes a card") is not a claim
      // about signing up. Caught on a blog draft before this shipped.
      /(?<![\/\w])sign(?:ing)?[-\s]?up\b[^.!?]{0,30}\b(?:takes|needs|requires)\s+(?:a\s+)?card\b/i,
      /\baccount\b[^.!?]{0,30}\b(?:takes|needs|requires)\s+(?:a\s+)?(?:credit\s+)?card\b/i,
      // The comparison-table row #548 introduced.
      /\bcard\s+to\s+sign\s+in\b/i,
    ],
  },
  {
    id: "urgency-scarcity",
    brief: "Rule 6 — no manufactured urgency or scarcity",
    message:
      "Manufactured urgency/scarcity. The ONLY permitted time statement is a " +
      "factual note about the user's own real trial expiry, styled calmly.",
    patterns: [
      /\bonly\s+\d+\s+(?:left|remaining|spots?|seats?|places?|licen[cs]es?)\b/i,
      /\b\d+\s+(?:spots?|seats?|places?)\s+(?:left|remaining)\b/i,
      /\bspots?\s+remaining\b/i,
      /\b(?:expires?|ends?|closes?)\s+in\s+\d+\s*(?:second|minute|hour|hr|min|sec)/i,
      /\bcountdown\b/i,
      /\blimited[-\s]time\s+(?:offer|deal|pricing|discount)\b/i,
      /\blast\s+chance\b/i,
      /\bact\s+(?:now|fast)\b/i,
      /\bhurry\b/i,
      /\bselling\s+fast\b/i,
      /\balmost\s+(?:gone|sold\s+out)\b/i,
      /\b\d+\s+(?:people|users|traders)\s+(?:subscribed|signed\s+up|joined|upgraded)\s+(?:today|in\s+the\s+last)\b/i,
      /\bprice\s+(?:goes\s+up|increases|rises)\s+(?:in|on|after)\b/i,
      /\bbefore\s+(?:the\s+)?price\s+goes\s+up\b/i,
      /\bdon'?t\s+miss\s+out\b/i,
    ],
  },
  {
    id: "testimonial-gains",
    brief: "Rule 5 — no testimonials about gains, profits or trades that worked",
    message:
      "A testimonial referencing gains/profit. Testimonials about outcomes are " +
      "prohibited in any form; testimonials about workflow are not a workaround " +
      "if they imply money made.",
    patterns: [
      /\b(?:made|earned|banked|pocketed)\s+(?:me\s+)?\$[\d,]+/i,
      /\bpaid\s+for\s+itself\b/i,
      /\bup\s+\d+%\s+(?:since|thanks\s+to|after)\b/i,
      /\bdoubled\s+my\s+(?:account|portfolio|money)\b/i,
      /\bmy\s+best\s+trade\b/i,
    ],
  },
  {
    id: "personalised-performance",
    brief: "Rule 7 — personalised messages report ACTIVITY only, never how holdings moved",
    message:
      "Telling a named user how THEIR self-selected securities performed is the " +
      "worst-case fact pattern for the personal-advice test. Report activity " +
      "(scans run, tickers added, exports taken) instead.",
    patterns: [
      /\byour\s+(?:watchlist|watched|saved|tracked)\s+(?:tickers?|stocks?|names?)\s+(?:are\s+)?(?:up|down|gained|lost|rose|fell|returned)\b/i,
      /\byour\s+(?:best|top|worst)\s+(?:performer|performing|pick)\b/i,
      /\bhow\s+your\s+(?:stocks?|tickers?|watchlist|picks?)\s+(?:did|performed)\b/i,
      /\byour\s+(?:portfolio|positions?)\s+(?:is|are|was|were)\s+(?:up|down)\b/i,
    ],
  },
  {
    id: "prohibited-data-collection",
    brief: "Rule 8 — never collect capital, holdings, risk tolerance, goals or experience",
    message:
      "Collecting suitability-style inputs (capital, holdings, risk tolerance, " +
      "goals, experience) is what converts general information into personal " +
      "advice. Do not ask for it in any form, survey or onboarding step.",
    // Rule 8 is about COLLECTING these inputs. Compliant pages have to be
    // able to say "whether to act depends on your portfolio, risk tolerance
    // and time horizon — things Tapeline does not know about you", which is
    // the single most common legitimate use of this vocabulary in the tree.
    // So the lexical patterns are gated on a collection cue, and a second
    // pattern catches the real hazard directly: a form field bound to one of
    // these concepts.
    patterns: [
      collectionCue("(?:portfolio|account)\\s+size"),
      collectionCue("investable\\s+assets"),
      collectionCue("net\\s+worth"),
      collectionCue("risk\\s+tolerance"),
      collectionCue("investment\\s+(?:goals?|objectives?|horizon)"),
      collectionCue("(?:trading|investing)\\s+experience"),
      collectionCue("experience\\s+level"),
      /\bhow\s+much\s+(?:capital|money)\s+(?:do|are|have)\s+you\b/i,
      // A direct question about capital/holdings/experience, in any phrasing.
      // Requiring a literal "?" keeps this precise while catching the forms
      // the cue-prefix patterns miss ("Roughly what size portfolio do you
      // run?"), which is how the live onboarding survey slipped through.
      /\b(?:what|which|how)\b[^?<>\n]{0,45}?\b(?:portfolio|capital|net\s+worth|risk\s+tolerance|investing\s+experience|trading\s+experience|experience\s+level)\b[^?<>\n]{0,30}?\?/i,
      // Form/input bindings — name=, id=, label=, placeholder=, htmlFor=.
      /\b(?:name|id|label|placeholder|htmlFor|aria-label)\s*=\s*["'{][^"'}\n]{0,40}?(?:risk[-_\s]?tolerance|portfolio[-_\s]?size|net[-_\s]?worth|investable[-_\s]?assets|investment[-_\s]?(?:goals?|objectives?|horizon)|experience[-_\s]?level)/i,
    ],
  },
  {
    id: "financial-state-targeting",
    brief:
      "Rule 9 — never assert or imply knowledge of the reader's financial situation",
    message:
      "Second-person financial-state copy (\"if your returns disappoint\", " +
      "\"struggling with debt?\") asserts something about the reader's money. " +
      "Qualify by WORKFLOW instead — \"if you screen 500 tickers by hand every " +
      "weekend\" targets the same person and is compliant.",
    /*
     * Why this is its own rule, and not a widening of 7 or 8.
     *
     * Rule 7 polices telling a KNOWN user how THEIR actual holdings moved —
     * an in-product personalisation hazard. Rule 8 polices COLLECTING
     * suitability inputs. This rule polices a third thing that both miss:
     * ACQUISITION copy, addressed to a stranger, that claims to know their
     * financial position. Nothing is collected and no holding is reported, so
     * neither existing rule fires — yet this is the class that actually gets
     * finance ads rejected, and the class that reads most like advice.
     *
     * It is the #1 documented Meta finance rejection trigger (their "personal
     * attributes" standard) — see docs/META_SAAS_ADS_PLAYBOOK.md §4.2 and
     * docs/PAID_ADS_METRICS_BIBLE.md §7.3, which flagged the gap. Ad copy is
     * the highest-risk surface for it AND the least protected: CI's include
     * globs do not cover docs/**, so the copy banks are hand-linted only.
     *
     * FALSE-POSITIVE BOUNDARY, deliberately drawn tight. "your" plus a money
     * word is NOT enough — the tree is full of legitimate second person:
     *   - "your watchlist", "your account", "your trial", "your card"
     *   - "It never tells you what to do" · "You still make every decision"
     *   - Rule 8's own required sentence: "whether to act depends on your
     *     portfolio, risk tolerance and time horizon — things Tapeline does
     *     not know about you"
     * So every pattern below needs a financial-state noun AND a
     * deficiency/desire cue. Describing what the reader DOES (screening,
     * scanning, reviewing) is always fine; describing what they HAVE, or
     * lack, is not.
     */
    patterns: [
      // "your returns disappoint", "your portfolio is underperforming"
      /\byour\s+(?:returns?|portfolio|savings|investments?|gains?|profits?|losses?|balance|nest\s+egg)\b[^.?!<>\n]{0,32}?\b(?:disappoint\w*|underperform\w*|lagging|lag|shrink\w*|dwindl\w*|stuck|flat|suffering|bleeding|losing|too\s+small|not\s+enough)\b/i,
      // "struggling with debt", "tired of losing money", "sick of bad trades".
      // The optional gerund slot is what catches "tired of LOSING money" —
      // the state noun is not always adjacent to the preposition.
      /\b(?:struggl\w+|worried|frustrated|tired|sick|fed\s+up|anxious)\s+(?:with|about|of)\s+(?:your\s+)?(?:\w+ing\s+)?(?:debt|savings|returns?|portfolio|losses|investments?|money|trades?|trading\s+results?)\b/i,
      // "want to grow your savings", "ready to double your money"
      /\b(?:want|ready|looking|hoping)\s+to\s+(?:grow|boost|double|triple|increase|improve|maximi[sz]e|build)\s+(?:your\s+)?(?:savings|returns?|portfolio|wealth|money|investments?|gains?|nest\s+egg)\b/i,
      // "are you losing money?", "is your portfolio down?"
      /\b(?:are|is)\s+(?:you|your\s+(?:portfolio|returns?|investments?|savings|trades?))\b[^.?<>\n]{0,28}?\b(?:losing|down|underperform\w*|behind|struggling|in\s+the\s+red)\b/i,
      // "not seeing the returns you want"
      /\bnot\s+(?:seeing|getting|making|earning)\s+the\s+(?:returns?|gains?|profits?|results?)\b/i,
      // "if your trades keep losing" / "when your picks go wrong"
      /\b(?:if|when|because)\s+your\s+(?:trades?|picks?|positions?|investments?|portfolio)\b[^.?!<>\n]{0,28}?\b(?:keep\s+)?(?:los\w+|fail\w*|go\s+wrong|tank\w*|crash\w*)\b/i,
    ],
  },
];

/* ------------------------------------------------------------------ *
 * Rule 3 — the vs-SPY presentation rule.
 *
 * This one is structural rather than lexical: the SAME number is permitted
 * in a neutral data table and prohibited in an H1 / <title> / meta
 * description / OG card / email subject. So we extract headline-shaped
 * strings and only test those.
 *
 * Built now, while the live number is unflattering (50.9% hit rate, n=269),
 * precisely so it survives a future good run — the temptation to hero-stat
 * the record arrives with the first good month, not today.
 * ------------------------------------------------------------------ */
const HEADLINE_EXTRACTORS = [
  // <h1 ...>…</h1> and raw <title>…</title>
  { kind: "h1", re: /<h1\b[^>]*>([\s\S]{0,500}?)<\/h1>/gi },
  { kind: "title", re: /<title\b[^>]*>([\s\S]{0,500}?)<\/title>/gi },
  // Metadata / OG / email-subject object keys, single- double- or backtick-quoted.
  {
    kind: "metadata",
    re: /\b(?:title|description|subject|ogTitle|ogDescription|headline)\s*[:=]\s*(`[\s\S]{0,500}?`|"[^"\n]{0,500}"|'[^'\n]{0,500}')/gi,
  },
];

/** A vs-SPY figure: a benchmark reference sitting next to a number. */
const BENCHMARK_REF = /\b(?:vs\.?\s*spy|versus\s+spy|\bspy\b|s\s*&\s*p\s*500|benchmark|hit\s*rate|alpha)\b/i;
// The figure may be interpolated rather than literal — `${rate}% vs SPY` in a
// template is the same representation as "50.9% vs SPY", and is likelier,
// since a headline built from live data is what a growth edit reaches for.
const NUMERIC_FIGURE =
  /(?:[-+]?\d+(?:\.\d+)?|\$\{[^}]*\}|\{\{?[A-Za-z_.]+\}?\})\s*(?:%|percent|bps)/i;

const HEADLINE_RULE = {
  id: "vs-spy-in-headline",
  brief: "Rule 3 — no vs-SPY figure in an H1, title, meta description, OG card or subject line",
  message:
    "A vs-SPY / hit-rate figure in a headline slot frames the record as a " +
    "success claim. The number is permitted in a neutral data table with n " +
    "disclosed and losing days styled identically — not in a headline.",
};

/* ------------------------------------------------------------------ *
 * Rule 10 — trading vocabulary that is banned in AD CREATIVE ONLY.
 *
 * WHY THIS IS PATH-SCOPED AND NOT A GLOBAL RULE
 * ---------------------------------------------
 * "picks" is legitimate, load-bearing product vocabulary on the site —
 * `/daily-picks` is a real public route, and the word appears across the
 * scanner, watchlist and about pages. Banning it repo-wide would be wrong
 * and would fail CI everywhere.
 *
 * In an AD UNIT it is different, and the ban is documented in
 * `docs/META_SAAS_ADS_PLAYBOOK.md`: *"no 'picks' token in ad copy — Meta's
 * finance classifier pattern-matches it to stock-tip services, so it is
 * 'score(s)' everywhere"*. That is an account-safety rule about how Meta's
 * classifier reads a paid financial ad, not a claim about the word's meaning.
 *
 * WHY IT EXISTS AT ALL
 * --------------------
 * Concept C of the 2026-08 burst shipped with "Every top-10 pick, logged
 * daily, measured against SPY" burned into all three of its images, and ran
 * live on an FPS account for three days. Two gaps let it through: the ban
 * lived only in prose, and the on-image strings live in the PowerShell
 * generators, which were never linted — only the primary text and headline
 * were. So "the ad copy passed the linter" was true and beside the point.
 * ------------------------------------------------------------------ */
const AD_CREATIVE_PATH = /(?:^|[\\/])docs[\\/]ads[\\/]/i;

/** Does this file contain words that get burned into, or submitted as, an ad? */
function isAdCreativePath(filePath) {
  return AD_CREATIVE_PATH.test(String(filePath).replace(/\\/g, "/"));
}

/* ------------------------------------------------------------------ *
 * AD MODE — `--ads`
 *
 * WHY THIS EXISTS, measured 2026-09-05
 * ------------------------------------
 * An external advertising team was handed this account. The natural
 * instruction — "run the linter before you ship copy" — was tested first, on
 * twelve lines a competent performance marketer writes reflexively. All
 * twelve are violations. The linter reported:
 *
 *     copy-compliance: OK — 1 user-facing source files scanned, 0 blocking findings.
 *
 * Two of the twelve are docs/COMPLIANCE_COPY_RULES.md's OWN flagship bad
 * examples ("Find the winners", "NVDA looks strong here"). That is not a bug
 * in the rules below — the site rules are tuned to stop a templated phrase
 * regressing across a 100k-line product codebase, where the surrounding words
 * are known. Ad copy is the opposite: short, written by strangers, and read
 * cold by someone with no product context.
 *
 * So `--ads` is a SECOND, stricter pass, not a re-tuning of the first:
 *
 *   1. It applies AD_VOCAB_RULE to any file given on the command line,
 *      instead of only to docs/ads/**. The path gate was the reason the one
 *      rule written for ad creative never ran in CI at all — CI's include
 *      globs do not cover docs/**, and CI passes no paths.
 *   2. It stops masking the score-band names. On the site "HIGH CONVICTION"
 *      is an enum value in ~50 files and masking is correct; in an ad, read
 *      by a stranger, a band name reads as a strength-of-recommendation
 *      scale — exactly the prescriptive frame those labels were renamed to
 *      escape.
 *   3. It adds AD_ONLY_RULES below, each one written against a line that
 *      currently passes.
 *
 * DELIBERATELY NOT DONE: these rules are not added to the default pass.
 * "score", "pick" and "signal" are legitimate product vocabulary on the site
 * (/daily-picks is a real route), and firing on them everywhere would produce
 * hundreds of false positives, which is how a linter gets ignored.
 * ------------------------------------------------------------------ */

/**
 * A bare ticker symbol: 1-5 capitals, standing alone.
 *
 * The site-wide evaluative-adjective rule keys off a list of security NOUNS
 * (stock, ticker, share, name, position…). That catches "AAPL is a strong
 * name" and misses "NVDA looks strong here" — the phrasing an ad actually
 * uses, and the compliance doc's own example. A symbol is the noun in ad copy.
 *
 * Excludes common English words and product vocabulary that happen to be
 * short and capitalised, so a sentence-initial "The" or an all-caps headline
 * cannot manufacture a ticker.
 */
const TICKER_STOPWORDS = new Set([
  "A", "I", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "IF", "IN", "IS", "IT",
  "MY", "NO", "OF", "ON", "OR", "SO", "TO", "UP", "US", "WE", "AND", "ARE",
  "BUT", "CAN", "FOR", "GET", "HAS", "HOW", "ITS", "NEW", "NOT", "NOW", "ONE",
  "OUR", "OUT", "SEE", "THE", "WHO", "WHY", "YOU", "ALL", "ANY", "DAY", "USD",
  "AUD", "API", "CSV", "ETF", "SPY", "CEO", "PRO", "FREE", "PLUS", "THIS",
  "THAT", "WITH", "FROM", "YOUR", "WHAT", "WHEN", "EVERY", "SCORE", "DAILY",
]);

const AD_EVAL_ADJECTIVES =
  "strong|promising|attractive|compelling|undervalued|overvalued|bullish|bearish|" +
  "hot|explosive|poised|primed|ready|due|cheap|expensive|solid|weak";

/**
 * Outcome nouns a performance claim hides behind when the security noun is
 * absent. "Find the winners before they run" contains no banned bigram —
 * the site rule needs "winning stocks" — but it is a promise about money.
 */
const AD_ONLY_RULES = [
  {
    id: "ad-outcome-promise",
    brief: "Ads — no promise about what the reader will earn",
    message:
      "This promises an outcome rather than describing what the product " +
      "measures. Tapeline holds no AFSL; its position is that it publishes " +
      "general descriptive information. Rewrite as a fact about the " +
      "mechanism: 'Six factors, one 0-100 score, one plain sentence per " +
      "ticker.'",
    patterns: [
      // "find/spot/catch the winners", "the next winner", "tomorrow's winners"
      /\b(?:find|finds|finding|spot|spots|catch|catches|uncover|uncovers|discover|discovers)\b[^.!?\n]{0,30}\b(?:the\s+|tomorrow'?s\s+|next\s+)?\bwinners?\b/i,
      /\b(?:the\s+next|tomorrow'?s|this\s+week'?s)\s+(?:big\s+)?(?:winner|mover|runner|breakout)s?\b/i,
      // "before they run/move/pop/take off"
      /\bbefore\s+(?:they|it|the\s+\w+)\s+(?:run|runs|move|moves|pop|pops|take\s+off|takes\s+off|rip|rips|breakout|break\s+out)\b/i,
      // "get ahead of the market", "stay ahead of the market"
      /\b(?:get|stay|keep)\s+ahead\s+of\s+the\s+(?:market|street|crowd|index)\b/i,
      // "make money", "grow your money/portfolio/account"
      /\b(?:make|makes|making)\s+(?:you\s+)?(?:more\s+)?money\b/i,
      /\bgrow\s+your\s+(?:money|portfolio|account|wealth|returns?)\b/i,
      // "your edge" as a possession
      /\b(?:your|the)\s+(?:unfair\s+|real\s+)?edge\b/i,
    ],
  },
  {
    id: "ad-free-trial",
    brief: "Ads — 'free' and 'trial' must never touch",
    message:
      "Signing up is genuinely card-free; the 14-day Premium trial is NOT — " +
      "it takes a card and bills in full on day 14. Merging them is false " +
      "advertising on a financial product. Say: 'Signing up takes an email " +
      "and a password. A card is only needed if you start the 14-day " +
      "Premium trial.'",
    patterns: [
      /\bfree\b[^.!?\n]{0,24}\btrial\b/i,
      /\btrial\b[^.!?\n]{0,24}\bfree\b/i,
      /\brisk[-\s]free\b/i,
      /\bno\s+(?:credit\s+)?card\s+(?:required|needed|necessary)\b/i,
      /\btry\b[^.!?\n]{0,30}\bfree\b/i,
    ],
  },
  {
    id: "ad-financial-state",
    brief: "Ads — never target by the reader's financial situation",
    message:
      "Asserting knowledge of the reader's finances is Meta's top finance " +
      "rejection trigger, and under Australian law it is what turns general " +
      "information into advice addressed to a person's circumstances. " +
      "Qualify by WORKFLOW instead: 'If you screen 500 tickers by hand every " +
      "weekend…'",
    patterns: [
      /\b(?:still\s+)?(?:losing|lost|lose)\b[^.!?\n]{0,24}\b(?:to\s+the\s+(?:index|market)|money|on\s+(?:bad|your))\b/i,
      /\b(?:tired|sick|frustrated)\s+of\b[^.!?\n]{0,40}\b(?:losing|lagging|missing|underperform\w*|your\s+(?:portfolio|returns?|account))\b/i,
      /\b(?:struggling|failing)\s+to\b[^.!?\n]{0,30}\b(?:keep\s+up|beat|match|grow)\b/i,
      /\b(?:is|are)\s+your\s+(?:portfolio|returns?|account|investments?)\b[^.!?\n]{0,30}\?/i,
      /\byour\s+(?:portfolio|account)\s+(?:lagging|behind|underperform\w*|shrinking)\b/i,
      /\b(?:small|tiny|modest)\s+account\b/i,
      // Collecting suitability information — the same failure, inbound.
      /\b(?:tell\s+us|what'?s|how\s+much)\b[^.!?\n]{0,40}\b(?:portfolio\s+size|risk\s+tolerance|investment\s+goals?|to\s+invest|you\s+have\s+to\s+invest)\b/i,
    ],
  },
  {
    id: "ad-social-proof",
    brief: "Ads — no user-count, testimonial or as-seen-in claims",
    message:
      "Tapeline has collected one invoice in its history. Any claim about " +
      "how many people use it is unverifiable at best and false at worst — " +
      "that is consumer-law exposure independent of the licensing question. " +
      "Point at the public record instead; it is the honest proof.",
    patterns: [
      /\bjoin\s+(?:thousands|hundreds|\d[\d,]*\+?)\b/i,
      /\b(?:thousands|hundreds|\d[\d,]{2,}\+?)\s+of\s+(?:traders|investors|users|subscribers|customers)\b/i,
      /\btrusted\s+by\b/i,
      /\bas\s+seen\s+(?:in|on)\b/i,
      /\b(?:loved|used)\s+by\s+(?:thousands|hundreds|\d)/i,
      /\b\d[\d,]*\+?\s+(?:happy\s+)?(?:traders|investors|users|subscribers)\b/i,
    ],
  },
  {
    id: "ad-urgency",
    brief: "Ads — no manufactured urgency or scarcity",
    message:
      "No countdowns, no seat counts, no 'prices go up'. Note the site rule " +
      "catches 'price goes up' and misses 'prices go up' — one character. " +
      "State the price and the refund terms and stop.",
    patterns: [
      /\bprices?\s+(?:go(?:es)?|going|will\s+go|are\s+going)\s+up\b/i,
      /\bprices?\s+(?:increase|increases|rise|rises|jump|jumps)\b/i,
      /\b(?:only|just)\s+\d+\s+(?:seats?|spots?|places?|licen[cs]es?)\s+(?:left|remaining|available)\b/i,
      /\b(?:limited|founding)\s+(?:seats?|spots?|places?|pricing|offer)\b/i,
      /\b(?:ends|closes|expires)\s+(?:soon|tonight|today|tomorrow|in\s+\d)/i,
      /\bdon'?t\s+miss\s+out\b/i,
      /\blast\s+chance\b/i,
    ],
  },
  {
    id: "ad-dm-invite",
    brief: "Ads — no direct-message or call-to-contact invitations",
    message:
      "Meta prohibits investment-product ads that invite direct messaging " +
      "with the advertiser (the anti-'pig-butchering' clause). It covers the " +
      "creative, the CTA, the destination AND comment replies on the ad " +
      "post. Send people to the pricing page.",
    patterns: [
      /\bDM\s+(?:us|me)\b/i,
      /\b(?:message|msg|inbox|whatsapp|telegram)\s+(?:us|me)\b/i,
      /\b(?:send|drop)\s+(?:us|me)\s+a\s+(?:message|dm|note)\b/i,
      /\breach\s+out\s+(?:to\s+us\s+)?(?:for|and)\b/i,
      /\bbook\s+a\s+call\b/i,
    ],
  },
  {
    id: "ad-detached-annual-price",
    brief: "Ads — an annual per-month price must carry 'billed annually'",
    message:
      "$8.25/mo and $16.58/mo are annual totals divided by twelve, charged " +
      "as one payment of $99 or $199. Detached, they misdescribe the charge. " +
      "Either write '$8.25/mo billed annually ($99/yr)' or use the " +
      "month-to-month price ($9.99 / $19.99).",
    patterns: [
      // The two live annual-equivalent figures, without the qualifier nearby.
      /\$\s?(?:8\.25|16\.58)\s*(?:\/|\s+(?:a|per)\s+)\s*(?:mo\b|month)(?![^.!?\n]{0,40}\b(?:billed\s+annually|annual|\/yr|per\s+year|a\s+year)\b)/i,
    ],
  },
];

/**
 * Score-band names, unmasked in ad mode.
 *
 * On the site these are enum values and the mask is right. Cold, in an ad,
 * "HIGH CONVICTION" reads as a strength-of-recommendation scale — the exact
 * prescriptive frame the labels were renamed to escape (they replaced
 * BUY NOW / STRONG ACCUMULATE / ACCUMULATE / HOLD / WATCH / AVOID).
 */
const AD_BAND_RULE = {
  id: "ad-score-band-name",
  brief: "Ads — no score-band names in cold copy",
  message:
    "A stranger reads a band name as a recommendation strength, which is " +
    "what these labels exist to avoid. Say '0-100 composite score with a " +
    "plain-English label' instead.",
  patterns: [
    /\bHIGH[-\s]CONVICTION\b/i,
    /\bSTRONG[-\s]SETUP\b/i,
    /\bCONSTRUCTIVE\b/,
    /\bCAUTION\b/,
  ],
};

/** Evaluative adjective sitting next to a bare ticker symbol. */
function findTickerAdjectiveViolations(code) {
  const out = [];
  const near = new RegExp(
    `\\b([A-Z]{1,5})\\b[^.!?<>\\n]{0,28}?\\b(?:${AD_EVAL_ADJECTIVES})\\b` +
      `|\\b(?:${AD_EVAL_ADJECTIVES})\\b[^.!?<>\\n]{0,28}?\\b([A-Z]{1,5})\\b`,
    "g",
  );
  let m;
  while ((m = near.exec(code)) !== null) {
    const symbol = m[1] || m[2] || "";
    if (!symbol || TICKER_STOPWORDS.has(symbol)) continue;
    out.push({ index: m.index, match: m[0] });
    if (m[0].length === 0) near.lastIndex += 1;
  }
  return out;
}

const AD_TICKER_ADJ_RULE = {
  id: "ad-ticker-adjective",
  brief: "Ads — no evaluative adjective attached to a ticker",
  message:
    "A forward-looking judgement about a named real security. State the " +
    "measured factor instead: \"NVDA's Relative Strength factor reads " +
    "82/100 — it has outpaced its sector over the trailing three months.\" " +
    "A fact about a past measurement is not a prediction.",
};

const AD_VOCAB_RULE = {
  id: "ad-trading-vocabulary",
  brief: "Playbook — no stock-tip vocabulary in ad creative (use 'score(s)')",
  message:
    "Meta's finance classifier pattern-matches this token to stock-tip " +
    "services, which risks rejection or silent suppression on a Special Ad " +
    "Category account. Say 'score(s)' or 'flagged ticker' instead. This rule " +
    "is scoped to ad creative — the word is fine on the site.",
};

const AD_VOCAB_PATTERNS = [
  /\bpicks?\b/gi,
  // "call" as a prediction ("our calls", "every call") is the same frame and
  // is equally prescriptive trading vocabulary.
  /\bcalls?\b/gi,
  /\bstock\s+tips?\b/gi,
  /\bhot\s+stocks?\b/gi,
  // "signal" was missing until 2026-09-05, and it is arguably the most
  // dangerous token of the set: Google's complex-speculative-products policy
  // names trading signals explicitly, and Meta's classifier reads it as a
  // stock-tip service. "Plain-English signals for busy traders" ran on Google
  // once and was pulled — then passed this very rule when re-tested.
  // Ad-mode only, so the product's own `signal` column and the /signals route
  // are untouched.
  /\bsignals?\b/gi,
];

/* ------------------------------------------------------------------ *
 * Comment stripping.
 *
 * Comments are not user-facing copy, and stripping them is the single
 * largest precision win available: this repo's comments discuss squeeze
 * setups, backtests and outperformance at length, and every one of those
 * would otherwise be a false positive.
 * ------------------------------------------------------------------ */

/**
 * Blank out comments while preserving line numbering and column offsets.
 * Handles //, /* … *\/ and JSX {/* … *\/} for JS/TS, and # for Python.
 *
 * Python triple-quoted strings are deliberately NOT stripped — our HTML
 * email bodies live in them, and those are exactly the copy we must lint.
 */
/**
 * Blank out Python docstrings — module-level, and the first statement of a
 * def/class — while preserving line numbers.
 *
 * Triple-quoted strings in general are NOT stripped: our HTML email bodies
 * live in them and are exactly the copy we need to lint. A docstring is
 * distinguishable structurally: the triple-quote is the first token on its
 * line, and it is either the head of the file or directly under a `def`/
 * `class` header. That distinction matters in practice — email.py's
 * docstrings describe the "hit rate vs SPY, avg alpha, best pick" data the
 * renderer consumes, and flagging a docstring for describing the feature it
 * implements is noise.
 */
function stripPythonDocstrings(text) {
  const lines = text.split("\n");
  const out = [...lines];
  let seenCode = false;
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (!trimmed) continue;
    const quote = trimmed.startsWith('"""') ? '"""' : trimmed.startsWith("'''") ? "'''" : null;
    if (!quote) {
      seenCode = true;
      continue;
    }
    // Preceding non-blank line — a docstring follows a def/class header.
    let prev = i - 1;
    while (prev >= 0 && !lines[prev].trim()) prev -= 1;
    const prevLine = prev >= 0 ? lines[prev].trim() : "";
    const isDocstring =
      !seenCode || /^(?:async\s+)?(?:def|class)\b/.test(prevLine.replace(/^@.*/, ""))
        ? !seenCode || prevLine.endsWith(":")
        : false;
    if (!isDocstring) {
      seenCode = true;
      continue;
    }
    // Blank through the closing quote.
    const rest = trimmed.slice(3);
    let end = i;
    if (!rest.includes(quote)) {
      end = i + 1;
      while (end < lines.length && !lines[end].includes(quote)) end += 1;
    }
    for (let j = i; j <= Math.min(end, lines.length - 1); j++) out[j] = " ".repeat(lines[j].length);
    i = end;
    seenCode = true;
  }
  return out.join("\n");
}

export function stripComments(text, lang) {
  if (lang === "py") {
    return stripPythonDocstrings(text)
      .split("\n")
      .map((line) => {
        // Only strip a # comment when it is not inside an obvious string.
        const idx = line.indexOf("#");
        if (idx === -1) return line;
        const before = line.slice(0, idx);
        const quotes = (before.match(/"/g) || []).length + (before.match(/'/g) || []).length;
        if (quotes % 2 === 1) return line; // # is inside a string literal
        return before + " ".repeat(line.length - idx);
      })
      .join("\n");
  }

  if (lang === "md") {
    // Markdown has no `//` or block comments - only HTML comments. Running
    // the JS state machine here is what let a `docs/**` glob in prose act as
    // an unterminated `/*` and blind every rule for the rest of the file.
    //
    // Fenced code blocks are deliberately still scanned. An unclosed fence
    // would reintroduce exactly the runaway-to-EOF failure being fixed, and
    // a false positive inside a fence is an allowlist entry with a written
    // reason - which is the documented process. Silence is not.
    return text.replace(/<!--[\s\S]*?-->/g, (m) => m.replace(/[^\n]/g, " "));
  }

  // JS/TS/JSX: single pass state machine.
  let out = "";
  let i = 0;
  let state = "code"; // code | line-comment | block-comment
  while (i < text.length) {
    const two = text.slice(i, i + 2);
    if (state === "code") {
      if (two === "//") {
        // Not a comment if it is part of a URL scheme (http://, //cdn…).
        const prev = text[i - 1];
        if (prev === ":") {
          out += two;
          i += 2;
          continue;
        }
        state = "line-comment";
        out += "  ";
        i += 2;
        continue;
      }
      if (two === "/*") {
        state = "block-comment";
        out += "  ";
        i += 2;
        continue;
      }
      out += text[i];
      i += 1;
      continue;
    }
    if (state === "line-comment") {
      if (text[i] === "\n") {
        state = "code";
        out += "\n";
        i += 1;
        continue;
      }
      out += " ";
      i += 1;
      continue;
    }
    // block-comment
    if (two === "*/") {
      state = "code";
      out += "  ";
      i += 2;
      continue;
    }
    out += text[i] === "\n" ? "\n" : " ";
    i += 1;
  }
  return out;
}

/* ------------------------------------------------------------------ *
 * Allowlist
 * ------------------------------------------------------------------ */

/**
 * Minimal glob matcher: supports `**` (any path segments), `*` (any chars
 * except `/`) and literal text. Enough for our include/exclude/allow paths
 * and avoids taking a dependency for a script that must run in bare CI.
 */
export function globMatch(pattern, path) {
  const rx = pattern
    .split("")
    .reduce((acc, ch, idx, arr) => {
      if (ch === "*" && arr[idx - 1] === "*") return acc; // consumed by the pair below
      if (ch === "*" && arr[idx + 1] === "*") return acc + "§§";
      if (ch === "*") return acc + "[^/]*";
      if (ch === "?") return acc + "[^/]";
      if ("\\^$.|+()[]{}".includes(ch)) return acc + "\\" + ch;
      return acc + ch;
    }, "")
    .replace(/§§\//g, "(?:.*/)?")
    .replace(/§§/g, ".*");
  return new RegExp(`^${rx}$`).test(path);
}

export function loadAllowlist(file = ALLOW_FILE) {
  if (!existsSync(file)) {
    return { include: [], exclude: [], allow: [] };
  }
  const raw = JSON.parse(readFileSync(file, "utf8"));
  for (const [idx, entry] of (raw.allow || []).entries()) {
    if (!entry.reason || !entry.reason.trim()) {
      throw new Error(
        `copy-compliance.allow.json: allow[${idx}] is missing a "reason". ` +
          `Every exemption must be justified in writing.`,
      );
    }
  }
  for (const [idx, entry] of (raw.knownViolations || []).entries()) {
    if (!entry.reason || !entry.reason.trim()) {
      throw new Error(
        `copy-compliance.allow.json: knownViolations[${idx}] is missing a "reason".`,
      );
    }
  }
  return {
    include: raw.include || [],
    exclude: raw.exclude || [],
    allow: raw.allow || [],
    knownViolations: raw.knownViolations || [],
  };
}

/**
 * Index of the first entry matching this finding, or -1.
 *
 * Returning the INDEX rather than a boolean is what makes stale-entry
 * detection possible: the caller can record which ledger entries actually
 * fired and report the ones that never did.
 */
export function matchingEntryIndex(finding, list) {
  return list.findIndex((entry) => {
    if (entry.file && !globMatch(entry.file, finding.file)) return false;
    if (entry.rule && entry.rule !== "*" && entry.rule !== finding.rule) return false;
    if (entry.phrase && !finding.match.toLowerCase().includes(entry.phrase.toLowerCase())) {
      return false;
    }
    return true;
  });
}

function isAllowed(finding, allow) {
  return matchingEntryIndex(finding, allow) !== -1;
}

/**
 * Inline escape hatch for a one-off legitimate use, e.g.
 *   {/* copy-compliance-allow evaluative-adjective -- quoting a user complaint *\/}
 * A reason after `--` is mandatory. Applies to the marker line and the line
 * immediately following it (comments usually sit above the code).
 */
const INLINE_ALLOW = /copy-compliance-allow\s+([\w-]+|\*)\s*--\s*\S/;

function inlineAllowedLines(rawText) {
  const allowed = new Map(); // lineNumber -> ruleId
  rawText.split("\n").forEach((line, idx) => {
    const m = line.match(INLINE_ALLOW);
    if (!m) return;
    allowed.set(idx + 1, m[1]);
    allowed.set(idx + 2, m[1]);
  });
  return allowed;
}

/* ------------------------------------------------------------------ *
 * Scanning
 * ------------------------------------------------------------------ */

function lineAndColOf(text, index) {
  const before = text.slice(0, index);
  const line = before.split("\n").length;
  const col = index - before.lastIndexOf("\n");
  return { line, col };
}

function excerpt(text, index, matchLength) {
  const start = text.lastIndexOf("\n", index) + 1;
  const end = text.indexOf("\n", index + matchLength);
  const raw = text.slice(start, end === -1 ? text.length : end).trim();
  return raw.length > 160 ? raw.slice(0, 157) + "…" : raw;
}

/**
 * Scan one file's source. Exported for tests.
 *
 * @param {string} text      raw file contents
 * @param {string} filePath  repo-relative path (used for allowlisting)
 * @param {object} options   { allow?: Array }
 * @returns {Array<{file,line,column,rule,brief,match,excerpt,message}>}
 */
export function scanSource(text, filePath = "<input>", options = {}) {
  const allow = options.allow || [];
  const known = options.knownViolations || [];
  // Ad mode: every file named on the command line is treated as ad creative,
  // the stricter AD_ONLY_RULES run, and the score-band mask comes off. See
  // the AD MODE block above for why this is a second pass and not a retune.
  const adsMode = options.ads === true || isAdCreativePath(filePath);
  // Markdown is NOT JavaScript. `docs/**` contains the two characters `/*`,
  // which the JS state machine reads as an unterminated block comment and
  // uses to blank the entire rest of the file - silently reporting success
  // on copy it never scanned. See stripComments' `md` branch.
  const lang = filePath.endsWith(".py")
    ? "py"
    : /\.mdx?$/i.test(filePath)
      ? "md"
      : "js";
  const stripped = stripComments(text, lang);
  const code = adsMode ? stripped : maskProductLexicon(stripped);
  const inlineAllowed = inlineAllowedLines(text);
  const findings = [];

  const push = (rule, index, matchText) => {
    const { line, col: column } = lineAndColOf(code, index);
    const inline = inlineAllowed.get(line);
    if (inline && (inline === "*" || inline === rule.id)) return;
    if (isNegated(code, index)) return;
    const finding = {
      file: filePath,
      line,
      column,
      rule: rule.id,
      brief: rule.brief,
      match: matchText,
      excerpt: excerpt(code, index, matchText.length),
      message: rule.message,
    };
    if (isAllowed(finding, allow)) return;
    // Pre-existing violations are reported as warnings rather than dropped,
    // so the debt stays visible instead of quietly becoming the new baseline.
    const knownIndex = matchingEntryIndex(finding, known);
    finding.known = knownIndex !== -1;
    if (finding.known) finding.knownIndex = knownIndex;
    findings.push(finding);
  };

  // Lexical rules.
  for (const rule of RULES) {
    for (const pattern of rule.patterns) {
      const re = new RegExp(pattern.source, pattern.flags.includes("g") ? pattern.flags : pattern.flags + "g");
      let m;
      while ((m = re.exec(code)) !== null) {
        push(rule, m.index, m[0]);
        if (m[0].length === 0) re.lastIndex += 1;
      }
    }
  }

  // Structural rule 3 — vs-SPY figures in headline slots only.
  for (const { kind, re } of HEADLINE_EXTRACTORS) {
    const rx = new RegExp(re.source, re.flags);
    let m;
    while ((m = rx.exec(code)) !== null) {
      const value = m[1] || "";
      if (BENCHMARK_REF.test(value) && NUMERIC_FIGURE.test(value)) {
        push(
          { ...HEADLINE_RULE, message: `${HEADLINE_RULE.message} (found in a ${kind} slot)` },
          m.index,
          value.trim().replace(/\s+/g, " ").slice(0, 120),
        );
      }
    }
  }

  // Rule 10 — stock-tip vocabulary, ad creative only. Scoped by path because
  // "picks" is legitimate site copy (/daily-picks) and only dangerous in a
  // paid financial ad unit. See AD_VOCAB_RULE above.
  if (adsMode) {
    for (const pattern of AD_VOCAB_PATTERNS) {
      const re = new RegExp(pattern.source, pattern.flags);
      let m;
      while ((m = re.exec(code)) !== null) {
        push(AD_VOCAB_RULE, m.index, m[0]);
        if (m[0].length === 0) re.lastIndex += 1;
      }
    }

    // The stricter ad-only ruleset. Each rule was written against a line that
    // passed the default pass — see the AD MODE block.
    for (const rule of [...AD_ONLY_RULES, AD_BAND_RULE]) {
      for (const pattern of rule.patterns) {
        const re = new RegExp(pattern.source, pattern.flags.includes("g") ? pattern.flags : pattern.flags + "g");
        let m;
        while ((m = re.exec(code)) !== null) {
          push(rule, m.index, m[0]);
          if (m[0].length === 0) re.lastIndex += 1;
        }
      }
    }

    for (const hit of findTickerAdjectiveViolations(code)) {
      push(AD_TICKER_ADJ_RULE, hit.index, hit.match);
    }
  }

  // Two patterns in the same rule can match the same span (e.g. a cue-prefix
  // pattern and the question-mark pattern both hitting one survey label).
  // Report the location once.
  const seen = new Set();
  return findings
    .filter((f) => {
      const key = `${f.rule}:${f.line}:${f.column}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort((a, b) => a.line - b.line || a.column - b.column);
}

/* ------------------------------------------------------------------ *
 * File walking + CLI
 * ------------------------------------------------------------------ */

function walk(dir, acc = []) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return acc;
  }
  for (const name of entries) {
    if (name === "node_modules" || name === ".git" || name === ".next" || name === "dist") continue;
    const full = join(dir, name);
    let st;
    try {
      st = statSync(full);
    } catch {
      continue;
    }
    if (st.isDirectory()) walk(full, acc);
    else acc.push(full);
  }
  return acc;
}

function toRepoRelative(p) {
  return relative(REPO_ROOT, resolve(p)).split(sep).join("/");
}

export function collectFiles(config, explicit = []) {
  if (explicit.length) return explicit.map(toRepoRelative);
  const all = walk(REPO_ROOT).map(toRepoRelative);
  return all
    .filter((f) => config.include.some((g) => globMatch(g, f)))
    .filter((f) => !config.exclude.some((g) => globMatch(g, f)))
    .sort();
}

function main(argv) {
  const asJson = argv.includes("--json");
  // `--ads` turns on the stricter pass for ad copy written outside this repo.
  // It only applies to files named explicitly, which is the normal way an
  // advertiser runs it: `node scripts/lint-copy-compliance.mjs --ads copy.md`
  const adsMode = argv.includes("--ads");
  const explicit = argv.filter((a) => !a.startsWith("--"));

  let config;
  try {
    config = loadAllowlist();
  } catch (err) {
    console.error(`copy-compliance: ${err.message}`);
    return 2;
  }

  const files = collectFiles(config, explicit);
  const findings = [];
  for (const file of files) {
    const abs = join(REPO_ROOT, file);
    let text;
    try {
      text = readFileSync(abs, "utf8");
    } catch {
      continue;
    }
    // Scan what the page RENDERS, not what the source spells.
    //
    // Several rules work on proximity — Rule 10 bans card-free wording within
    // ~40 characters of "trial" — and every one of them measures the SOURCE
    // string. A template placeholder is longer than the value it renders to,
    // so interpolated copy can sit inside the banned window on screen while
    // testing clean on disk.
    //
    // That was not hypothetical: four /signup sublines reading "Sign up with
    // no card; a card starts the ${TRIAL_LENGTH_LABEL} Premium trial" were
    // passing purely because the 18-character placeholder pushed "trial" past
    // the 40-character window that the 6-character "14-day" would have sat
    // inside. The copy happened to be honest. The linter had no way to know.
    text = expandKnownConstants(text);
    findings.push(
      ...scanSource(text, file, {
        allow: config.allow,
        knownViolations: config.knownViolations,
        ads: adsMode,
      }),
    );
  }

  const blocking = findings.filter((f) => !f.known);
  const carried = findings.filter((f) => f.known);

  /* ---------------------------------------------------------------- *
   * Stale ledger entries.
   *
   * An entry that no longer matches anything is not dead weight — it is a
   * live hole. knownViolations DOWNGRADES a match from blocking to warning,
   * so a stale entry silently re-arms: if someone reintroduces the copy that
   * was cleaned up, the ledger catches it and the build stays green. That is
   * precisely the regression this linter exists to stop.
   *
   * So a fixed violation must be pruned in the same PR that fixes it, and
   * that requirement is enforced here rather than left to a README.
   * Scoped to a full-repo run: an explicit-file run only scans a subset, so
   * an unmatched entry there means nothing.
   * ---------------------------------------------------------------- */
  const fullRun = explicit.length === 0;
  const used = new Set(carried.map((f) => f.knownIndex));
  const stale = fullRun
    ? (config.knownViolations || [])
        .map((entry, idx) => ({ entry, idx }))
        .filter(({ idx }) => !used.has(idx))
    : [];

  if (asJson) {
    console.log(
      JSON.stringify(
        {
          scanned: files.length,
          blocking,
          knownViolations: carried,
          staleKnownViolations: stale.map(({ entry }) => entry),
        },
        null,
        2,
      ),
    );
    return blocking.length || stale.length ? 1 : 0;
  }

  const report = (stream, list) => {
    const byRule = new Map();
    for (const f of list) {
      if (!byRule.has(f.rule)) byRule.set(f.rule, []);
      byRule.get(f.rule).push(f);
    }
    for (const [ruleId, group] of byRule) {
      stream(`── ${ruleId} — ${group[0].brief}`);
      stream(`   ${group[0].message}\n`);
      for (const f of group) {
        stream(`   ${f.file}:${f.line}:${f.column}`);
        stream(`     matched: "${f.match}"`);
        stream(`     line:    ${f.excerpt}`);
      }
      stream("");
    }
  };

  if (carried.length) {
    console.log(
      `copy-compliance: ${carried.length} pre-existing finding(s) carried in the ` +
        `known-violations ledger (scripts/copy-compliance.allow.json).\n` +
        `These do NOT fail the build, but they are real copy debt — see the ledger\n` +
        `for the per-entry reason and owner.\n`,
    );
    report((s) => console.log(s), carried);
  }

  if (stale.length) {
    console.error(
      `copy-compliance: ${stale.length} stale known-violation entr(y/ies) in ` +
        `scripts/copy-compliance.allow.json.\n` +
        `These no longer match any finding — the copy was fixed. Delete them.\n` +
        `A stale entry is not harmless: it would downgrade the SAME violation from\n` +
        `blocking to a warning if the copy were ever reintroduced.\n`,
    );
    for (const { entry, idx } of stale) {
      console.error(
        `   knownViolations[${idx}] — ${entry.file || "(any file)"} · ` +
          `${entry.rule || "(any rule)"}${entry.phrase ? ` · "${entry.phrase}"` : ""}`,
      );
    }
    console.error("");
  }

  if (!blocking.length && !stale.length) {
    console.log(
      `copy-compliance: OK — ${files.length} user-facing source files scanned, ` +
        `0 blocking findings.`,
    );
    return 0;
  }

  if (!blocking.length) return 1;

  console.error(
    `copy-compliance: ${blocking.length} blocking finding(s) across ${files.length} scanned file(s).\n`,
  );
  report((s) => console.error(s), blocking);
  console.error(
    "Fix the copy, or — if this is a defensible legitimate use — add an entry with a\n" +
      "written reason to scripts/copy-compliance.allow.json, or an inline\n" +
      "`copy-compliance-allow <rule> -- <reason>` comment.\n" +
      "See docs/COMPLIANCE_COPY_RULES.md. Note that a disclaimer does not cure\n" +
      "non-compliant copy (Rule 9) — fix the content, not the footnote.",
  );
  return 1;
}

const isDirectRun =
  process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
if (isDirectRun) {
  process.exit(main(process.argv.slice(2)));
}
