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
  const lang = filePath.endsWith(".py") ? "py" : "js";
  const code = maskProductLexicon(stripComments(text, lang));
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
    findings.push(
      ...scanSource(text, file, {
        allow: config.allow,
        knownViolations: config.knownViolations,
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
