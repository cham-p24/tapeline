/**
 * Blog post manifest.
 *
 * Adding a post: append to POSTS with a unique slug + a body of HTML
 * fragments. Lightweight by design — when the corpus grows past 10-15
 * posts, swap to MDX or fetch from a CMS without changing the route
 * shape (slug-based).
 */
/**
 * Optional HowTo-style step list for posts that are genuinely instructional.
 * When present, the /blog/[slug] route emits HowTo JSON-LD alongside the
 * Article schema — this unlocks Google's step-by-step rich-result variant
 * (numbered cards with the post URL above the fold). Only set this for
 * posts where the title pattern is "how to X" / "what is X" / "best X" and
 * the body literally walks through ordered steps; misapplied HowTo schema
 * gets rejected as spam by Google's quality classifier.
 */
export type HowToStep = {
  name: string;       // ≤ 60 chars; shown as the step header in SERP
  text: string;       // ≤ 280 chars; the body of the step
};

export type BlogPost = {
  slug: string;
  /** The article headline, as rendered on the page and in the blog index. */
  title: string;
  /**
   * Optional SERP-only title, used when `title` is too long for a search
   * result.
   *
   * These are two different jobs. The on-page headline can afford a
   * parenthetical aside — "(and why it's not what you think)" — because the
   * reader is already there. A search result gets ~60 characters before
   * Google cuts it, and seven posts were running 66-90 (audited 2026-08-29),
   * so the aside was all the reader ever saw truncated.
   *
   * Set this ONLY to shorten; never to say something the headline doesn't.
   * Falls back to `title` when absent, which is the case for most posts.
   */
  metaTitle?: string;
  excerpt: string;
  publishedAt: string; // ISO 8601 date
  author: string;
  body: string; // Trusted HTML — keep this internal-only.
  /** Optional HowTo schema — only on instructional posts. */
  howToSteps?: HowToStep[];
  /** Total time (ISO 8601 duration) needed to complete the steps. */
  howToTime?: string;
};

export const POSTS: BlogPost[] = [
  {
    slug: "how-to-read-a-stock-chart",
    title: "How to Read a Stock Chart: Price, Volume, Trend, Support",
    excerpt: "A stock chart is a compressed record of every transaction ever made in one stock — not a prediction of the next one. This guide breaks down the four things every chart actually shows: price, volume, trend, and the support, resistance, and moving-average lines traders draw on top. Each is taught honestly — including where it quietly lies — and connected to how Tapeline's Trend factor reads the same structure.",
    publishedAt: "2026-07-29",
    author: "Tapeline",
    body: `<p>A stock chart looks like a line wandering up and down. It is actually a compressed record of every decision thousands of buyers and sellers made about one company — each price a moment where someone was willing to trade and someone else was willing to take the other side. Learning to read a chart is not learning to predict the future. It is learning to read that record clearly, so the story the tape is telling stops sounding like noise.</p>

<p>Here is how the four building blocks — price, volume, trend, and the lines traders draw on top of them — actually work, and where each one quietly lies to you.</p>

<h2>Price and volume: the two dimensions of every chart</h2>
<p>Every chart has two axes doing two different jobs. Price, on the vertical, tells you where the market settled. Volume, the bars along the bottom, tells you how much conviction was behind getting there. They are only meaningful together.</p>
<p>A 4% up-day on twice the average volume means real demand showed up — a lot of shares changed hands to move the price that far. A 4% up-day on half the average volume means a thin market drifted higher on almost nothing, and it can drift back just as easily. The same price move describes two completely different situations depending on the volume underneath it. Reading price without volume is reading half the sentence.</p>

<h2>Trend: direction is the first thing to establish</h2>
<p>Before any pattern, the first question is direction. An uptrend is a sequence of higher highs and higher lows — each rally peaks above the last, each pullback bottoms above the previous one. A downtrend is the mirror: lower highs and lower lows. When highs and lows overlap sideways, there is no trend, just a range.</p>
<p>This matters because most chart signals mean opposite things depending on the trend they sit inside. A sharp pullback in a healthy uptrend and the same pullback inside a downtrend can look identical on the day and resolve in opposite directions. Establishing the trend first is what keeps a single candle from being read in a vacuum.</p>

<h2>Support and resistance: memory, not magic</h2>
<p>Support is a price level where buying has repeatedly shown up and stopped a decline. Resistance is a level where selling has repeatedly capped a rally. They work because they are memory: traders who bought at a level remember it, traders who missed a move remember the price they wish they had taken, and those memories cluster into real activity when price returns to the level.</p>
<p>The honest caveat is that these are approximate zones, not exact prices, and they break. A level that held three times can fail on the fourth, and broken support often flips into resistance on the way back up. Treating a round number as a guarantee is exactly how the level stops being useful.</p>

<h2>Moving averages: the trend, smoothed</h2>
<p>A moving average plots the average closing price over a window — 50 days, 200 days — as a single line, smoothing out daily noise so the underlying direction is visible. The 50-day and the 200-day are the two most-watched. Price above a rising 200-day line is the textbook shape of a long-term uptrend; price below a falling one is the opposite.</p>
<p>Because so many traders watch the same averages, they can become self-fulfilling support and resistance. But a moving average is built entirely from past prices — it is a lagging line by construction. It confirms a trend that already exists; it never announces one early. Anyone selling a moving-average crossover as a crystal ball is selling yesterday's news.</p>

<h2>How Tapeline's Trend factor reads the same chart</h2>
<p>The <a href="/how-it-works">Trend factor</a> is one of the six inputs in the Tapeline composite, and it reads price structure mechanically rather than by eye. It measures how far price has moved over a multi-month window and where the latest price sits inside the ticker's own 52-week range — not moving-average crossovers — then compresses that into one 0–100 sub-score so a chart's direction becomes a single comparable number across every US ticker. It is deliberately descriptive: the score reports what the tape is currently doing, not what it will do next. You can see how Trend combines with the other five factors on the public <a href="/scorecard">scorecard</a> — which, in the interest of transparency, currently trails a plain SPY buy-and-hold. The Trend read also shows up pre-computed on lists like <a href="/best-stocks-for/swing-traders">the swing-trading board</a>.</p>

<h2>The honest limit</h2>
<p>Every chart is a picture of the past. It records what has already happened with total accuracy and says nothing certain about tomorrow. Patterns fail, trends reverse without warning, and the cleanest setup can be undone by a single event the chart could never contain:</p>
<ul>
<li>A chart cannot show tomorrow's earnings surprise, only the market's positioning ahead of it.</li>
<li>It cannot show a macro shock — a rate decision, a geopolitical headline — until price has already reacted to it.</li>
<li>It cannot tell you whether the volume behind a move was one large holder repositioning or broad demand from many.</li>
</ul>
<p>A chart is a way to organize a read of risk, not a way to remove it. The <a href="/legal/risk">risk disclosure</a> covers what a chart, by its nature, leaves out.</p>`,
    howToSteps: [
      { name: "Match the chart's timeframe to your horizon", text: "A 1-minute chart and a daily chart tell different stories about the same stock. Pick the timeframe that matches how long a position would be held — intraday, days, or months — before reading anything into the pattern." },
      { name: "Establish the trend before anything else", text: "Look for higher highs and higher lows (uptrend), lower highs and lower lows (downtrend), or overlapping swings (a range). Direction changes what every later signal means, so it comes first." },
      { name: "Read every price move against its volume", text: "Check the volume bars under each move. A rise on above-average volume shows real demand; the same rise on thin volume shows a drifting, easily-reversed market. Price and volume are only meaningful together." },
      { name: "Mark support and resistance as zones", text: "Find levels where declines have repeatedly stalled (support) and rallies have repeatedly capped (resistance). Treat them as approximate zones, not exact prices — they break, and broken support often becomes resistance." },
      { name: "Add the 50- and 200-day moving averages", text: "Overlay the two most-watched averages to see the smoothed trend. Price above a rising 200-day line is a textbook uptrend shape. Remember the line lags — it confirms direction, it never announces it early." },
      { name: "Cross-check the chart against other factors", text: "A chart shows price behaviour only. Read it alongside fundamentals, relative strength, and macro context so one clean-looking pattern isn't carrying the whole decision on its own." },
    ],
    howToTime: "PT7M",
  },
  {
    slug: "how-to-use-macd",
    title: "How to Use MACD: The Indicator Explained (Line, Signal, Histogram)",
    metaTitle: "How to Use MACD: Line, Signal, Histogram Explained",
    excerpt: "MACD is the most-screenshotted indicator in trading and the most misread. Here's how the MACD indicator is actually built — the line, signal, and histogram — what crossovers and divergence mean, and where it whipsaws in choppy markets. Then, honestly, how Tapeline reads the same trend and momentum ideas underneath it as two separate factors.",
    publishedAt: "2026-07-29",
    author: "Tapeline",
    body: `<p>MACD is the most-screenshotted indicator in retail trading — and probably the most misread. Every charting app ships it, every YouTube thumbnail circles a crossover on it, and almost nobody stops to explain what the three squiggles are actually made of. This post does the boring, useful thing: it explains how MACD is built, what each part is conventionally read to mean, where it misleads, and how the same two ideas underneath it — trend and momentum — show up as two separate factors inside the Tapeline score.</p>

<h2>What MACD actually is</h2>
<p>MACD stands for Moving Average Convergence Divergence. Despite the intimidating name, it is just the distance between two moving averages, plotted over time. There are three pieces:</p>
<ul>
<li><strong>The MACD line</strong> — the 12-period exponential moving average (EMA) minus the 26-period EMA. When the fast average is above the slow one, the line is positive; when it's below, negative. It's a running measure of how far short-term price has pulled away from longer-term price.</li>
<li><strong>The signal line</strong> — a 9-period EMA of the MACD line itself. It's a smoothed, slower version of the MACD line, used as a reference to compare against.</li>
<li><strong>The histogram</strong> — the MACD line minus the signal line, drawn as bars. When the two lines converge the bars shrink toward zero; when they spread apart the bars grow.</li>
</ul>
<p>The 12/26/9 settings are the defaults Gerald Appel chose in the 1970s. They are conventions, not laws of nature — and it's worth remembering that nothing about those particular numbers is tuned to any specific stock or timeframe.</p>

<h2>Reading crossovers and the zero line</h2>
<p>Two events get the most attention. The first is the signal-line crossover: when the MACD line crosses above its signal line, momentum is conventionally read as turning up; when it crosses below, turning down. The second is the zero-line crossover: the MACD line moving above zero means the 12-EMA has overtaken the 26-EMA (shorter-term strength), and below zero the reverse.</p>
<p>The histogram is the early-warning version of the same information. Because it measures the gap between the two lines, it starts shrinking before they actually cross. The bars flipping from growing to shrinking is often read as a hint that a crossover may be coming — momentum decelerating even while price is still rising.</p>

<h2>Divergence — the part worth learning</h2>
<p>The most information-dense pattern on MACD is divergence. Price makes a higher high, but MACD makes a lower high: the move is still going, but with less momentum behind each push. That's bearish divergence. The mirror case — price making a lower low while MACD makes a higher low — is bullish divergence. Divergence doesn't time anything; it describes a loss of conviction underneath the surface of the price. Sometimes that resolves in a reversal; often it just resolves in more of the same.</p>

<h2>Where MACD misleads</h2>
<p>Here is the honest part most tutorials skip. MACD is built entirely from moving averages, so it is a lagging indicator by construction — it confirms moves after they've begun, it never predicts them. And in a sideways, choppy market it whipsaws mercilessly: the MACD and signal lines coil around each other near zero, generating crossover after crossover with no follow-through. Every one of those looks like a signal on a screenshot and none of them means much. The single biggest error with MACD is reading crossovers in a range the same way one would read them in a clean trend.</p>
<p>This is why MACD works best as a description of an existing trend's health rather than a standalone trigger, and why it pairs naturally with something that tells you whether a real trend is even present.</p>

<h2>How Tapeline reads the same two ideas</h2>
<p>MACD quietly fuses two different things: trend (are the moving averages stacked in one direction?) and momentum (how fast is price accelerating away from its own average?). Tapeline keeps those as two of its six named factors rather than blending them into a single line. The <a href="/best-stocks-for/momentum">Momentum factor</a> reads the rate and persistence of price change — the same acceleration MACD's histogram is gesturing at. The Trend factor reads price structure directly — a multi-month price change, and where price sits inside its own 52-week range — rather than the moving-average stack MACD is built from.</p>
<p>Keeping them apart is deliberate. A stock can have strong momentum inside a weak trend (a sharp bounce in a downtrend) or a solid trend with fading momentum (exactly the divergence case above). A single MACD line collapses those two states together; two separate factors let the scanner show which one is on screen. How the six factors rank by weight — most toward Trend and Relative Strength, least toward Momentum — is written up in <a href="/how-it-works">how the score works</a>.</p>

<h2>The caveat that matters</h2>
<p>MACD is a lens, not an oracle. It is arithmetic on past prices, and no arrangement of past prices guarantees anything about the next bar. Tapeline treats indicators like this as descriptive inputs, never predictions — and we publish a <a href="/scorecard">public scorecard</a> that currently trails the S&amp;P 500, precisely so nobody mistakes a tidy factor model for a promise. Read MACD for what it is: a compact, lagging summary of trend and momentum that is genuinely informative when a trend exists and genuinely misleading when one doesn't. The <a href="/legal/risk">risk disclosure</a> has the full picture.</p>`,
    howToSteps: [
      { name: "Identify the three components", text: "On the MACD panel, locate the MACD line (12-EMA minus 26-EMA), the signal line (a 9-EMA of the MACD line), and the histogram (the gap between the two, drawn as bars)." },
      { name: "Check the zero line", text: "Note whether the MACD line sits above or below zero. Above zero means the faster average has overtaken the slower one; below zero is the reverse. This frames whether shorter-term strength or weakness is in control." },
      { name: "Watch the signal-line crossover", text: "See where the MACD line sits relative to its signal line. A cross above the signal is conventionally read as momentum turning up; a cross below, turning down. In choppy ranges these crossovers repeat with little follow-through." },
      { name: "Read the histogram", text: "Track whether the bars are growing or shrinking. Shrinking bars mean the two lines are converging — momentum decelerating — and often precede a crossover, even while price is still moving in the same direction." },
      { name: "Look for divergence against price", text: "Compare the MACD peaks and troughs with price. Price making a higher high while MACD makes a lower high (or the mirror on the downside) signals momentum fading beneath the surface. It describes conviction, not timing." },
      { name: "Confirm the trend context", text: "Ask whether a real trend is present before trusting any MACD event. The indicator is lagging and built from moving averages, so its signals are informative in a trend and unreliable in a sideways range." },
    ],
    howToTime: "PT6M",
  },
  {
    slug: "best-technical-indicators-swing-trading",
    title: "Best Technical Indicators for Swing Trading: An Honest Read",
    excerpt: "\"Best technical indicators for swing trading\" is the wrong question — no indicator predicts, they only describe. Here's an honest walk through RSI, moving averages, relative strength, and volume: what each actually measures, where it goes quiet, and how Tapeline folds the trend and relative-strength reads into named factors instead of a single line on a chart.",
    publishedAt: "2026-07-29",
    author: "Tapeline",
    body: `<p>Type "best technical indicators for swing trading" into any search box and you'll get a hundred listicles ranking RSI against MACD against Bollinger Bands as if one of them were a secret. The honest version is duller and more useful: no indicator is <em>best</em>, because indicators don't predict — they describe. Each one is a different compression of the same price and volume data. The skill isn't picking the winner. It's knowing what each one actually measures, and where it goes quiet.</p>

<p>This is a walk through the handful that matter over a multi-day, multi-session holding period — the swing-trading horizon — with an honest note on what each does and doesn't tell you.</p>

<h2>RSI: a momentum gauge, not a bottom-caller</h2>
<p>The Relative Strength Index (confusingly named — more on that below) measures the speed of recent gains against recent losses on a 0–100 scale. The folklore is "below 30 is oversold, above 70 is overbought." The reality: in a strong trend, RSI can pin above 70 for weeks while a stock keeps climbing, or sit below 30 the whole way down. It's a rate-of-change gauge, not a reversal signal. Where it earns its keep for a swing horizon is divergence — price making a new high while RSI makes a lower one, which describes momentum thinning out under the surface. Descriptive, not a trigger.</p>

<h2>Moving averages: the trend, made visible</h2>
<p>A moving average is just the average close over the last N sessions, redrawn each day. Its whole job is to strip intraday noise so the direction underneath is legible. The 50-day and 200-day are the conventional swing anchors; their slope and their order — is the 50 above the 200, or below? — is a compact description of whether the multi-week trend is constructive or deteriorating. The catch is baked in: moving averages lag. They confirm a trend that has already turned. They never call the turn itself. Anyone selling a moving-average "cross signal" as prediction is selling a rear-view mirror.</p>

<h2>Relative strength: the one most retail traders skip</h2>
<p>This is the important one, and it's not the RSI above. True relative strength compares a stock's return to a benchmark — usually the S&P 500 and the stock's own sector. A name grinding higher while the index chops sideways is showing relative strength; a name rising less than the index on an up day is quietly lagging. Over a multi-day holding period this is often the most information-dense read on the chart, because it filters out moves that are really just the whole market moving. It describes leadership, not destiny.</p>

<h2>Volume: the confirmation layer</h2>
<p>Volume is participation. A breakout on heavy volume describes broad agreement; the same move on thin volume describes a handful of orders and a lot of empty tape. Volume doesn't stand alone — it's the corroboration check on everything above. A trend, a relative-strength breakout, an RSI reading: each reads stronger when volume confirms it, and weaker when it doesn't.</p>

<h2>How Tapeline reads these — as factors, not signals</h2>
<p>Tapeline doesn't hand you a single indicator; it folds these reads into named factors inside a six-factor composite (<a href="/how-it-works">the full methodology is here</a>). Several of the six cover the same ground as the indicators above. The <a href="/how-it-works/trend">Trend factor</a> reads a multi-month price change and where price sits inside its own 52-week range, scored 0–100 instead of eyeballed — it does not read moving-average crossovers. The <a href="/how-it-works/relative-strength">Relative Strength factor</a> compares each name's change with the broad-market benchmark's over the same periods, the leadership read that pure price charts hide. Short-horizon rate of change sits in the Momentum factor. The point of naming them is that you can see which read is carrying a score and which is conspicuously silent, instead of trusting one line on one chart.</p>

<p>If you want that composite pre-sorted for a multi-day horizon, the <a href="/best-stocks-for/swing-traders">best swing trade stocks list</a> ranks the US universe by the composite and shows the per-factor breakdown on every row — Trend and Relative Strength included — so you can read where the confluence sits before you do your own chart work.</p>

<h2>The honest caveat</h2>
<p>Every indicator here is lagging by construction. They summarise what price and volume have already done; none of them forecast, and stacking five of them doesn't turn description into prediction. Tapeline's composite is the same kind of summary — a structured read, not a crystal ball. Its daily top picks are back-checked in public at <a href="/scorecard">the scorecard</a>, unedited, and it currently trails SPY. Treat indicators, factors, and composites as ways to read the tape more carefully, never as a substitute for your own judgement and risk limits — see the <a href="/legal/risk">risk disclosure</a>.</p>`,
    howToSteps: [
      { name: "Read the trend with moving averages", text: "Start with the 50- and 200-day moving averages. Their slope and order describe whether the multi-week trend is constructive or deteriorating. Moving averages lag — they confirm a trend, they never call the turn." },
      { name: "Check relative strength vs the benchmark", text: "Compare the stock's move to the S&P 500 and its sector. A name outperforming the index shows leadership; one lagging on an up day is quietly weak. Over a multi-day horizon this is often the densest read on the chart." },
      { name: "Confirm with volume", text: "Read volume as participation. A move on heavy volume describes broad agreement; the same move on thin volume is a few orders and empty tape. Volume corroborates the trend and relative-strength reads rather than standing alone." },
      { name: "Sanity-check momentum with RSI", text: "Use RSI as a rate-of-change gauge, not a reversal trigger. In a strong trend it can stay 'overbought' or 'oversold' for weeks. Its useful read is divergence — price and RSI disagreeing — which describes momentum thinning, not a timed signal." },
    ],
    howToTime: "PT6M",
  },
  {
    slug: "bollinger-band-squeeze",
    title: "Bollinger Band Squeeze: How to Find a Volatility Contraction",
    excerpt: "A Bollinger Band squeeze is when a stock's volatility bands pinch tight — the classic sign that a large move may be loading. But a squeeze tells you when something might happen, never which way, and the fakeouts are brutal. Here's how to spot a genuine volatility contraction, why it fires false signals, and how Tapeline reads the directional context around it — descriptively, with no dedicated \"squeeze\" score.",
    publishedAt: "2026-07-29",
    author: "Tapeline",
    body: `<p>The Bollinger Band squeeze is one of the most-searched setups in technical analysis, and one of the most misread. The idea is seductive: the bands pinch tight, volatility drains out of a stock, and a big move is "loading." Traders screenshot the narrow bands and call the direction before anything has actually happened. That last part is where most squeeze analysis quietly goes wrong.</p>

<p>This post walks through what a squeeze actually is, why it fires false signals as often as real ones, and how Tapeline reads the surrounding context descriptively — without pretending to know which way a coiled stock will break.</p>

<h2>What a Bollinger Band squeeze actually is</h2>
<p>Bollinger Bands, developed by John Bollinger, are three lines: a 20-period moving average in the middle, and an upper and lower band set two standard deviations away from it. Standard deviation is a volatility measure, so the bands breathe — they widen when a stock is moving violently and contract when it goes quiet.</p>

<p>A squeeze is simply that contraction taken to an extreme: the bands pull in close to the moving average because realized volatility has fallen to a local low. Bollinger built a companion indicator, BandWidth, to measure exactly this — it tracks the distance between the upper and lower band as a percentage of the middle line. When BandWidth drops to a multi-month low, you have a squeeze.</p>

<p>The logic behind watching for it is genuinely sound, not mystical: volatility is <em>mean-reverting</em>. Quiet periods tend to be followed by active ones, and active periods by quiet ones. A squeeze is a stock coiling — narrowing price range, thinning volume, indecision — and that state historically doesn't last forever. Something usually gives.</p>

<h2>The part nobody screenshots: a squeeze has no direction</h2>
<p>Here is the honest limitation. A squeeze tells you a volatility <em>expansion</em> is more likely than usual. It tells you nothing about which way. The bands narrow identically whether a stock is about to break out or break down — contraction is a statement about range, not about direction.</p>

<p>That is the source of the classic false signals:</p>
<ul>
<li><strong>The fakeout.</strong> Price pokes above the upper band, every breakout scanner lights up, and then it reverses straight back through the range. Low-volatility bases are exactly where stop-runs and liquidity grabs tend to happen.</li>
<li><strong>The squeeze that stays squeezed.</strong> There is no rule that a contraction must resolve on your timeframe. Bands can stay tight for weeks. "It has to move soon" is a feeling, not a signal.</li>
<li><strong>The whipsaw.</strong> Expansion often means a violent move in <em>both</em> directions before a trend establishes — the band-touch that looks like confirmation is frequently the high or low of a shakeout.</li>
</ul>

<p>None of this makes the squeeze useless. It makes it a <em>timing</em> observation, not a <em>direction</em> one. Treating "the bands are tight" as a reason to expect a specific outcome is the mistake.</p>

<h2>Squeeze is not the same as short squeeze</h2>
<p>Worth clearing up, because the words collide: a Bollinger Band squeeze is a volatility-contraction pattern on the chart. A <em>short</em> squeeze is a completely different thing — a crowded short position forced to cover, mechanically driving price up. They can occur together, but they are measured from entirely different data. Tapeline's <a href="/short-squeeze-scanner">short-squeeze scanner</a> reads short interest, float, and crowding, not band width. Don't conflate the two.</p>

<h2>How Tapeline reads the context around a squeeze</h2>
<p>Tapeline does <strong>not</strong> have a dedicated "squeeze" score, and this post isn't going to invent one. What the scanner provides is the directional context a squeeze itself can't: a 0–100 composite built from <a href="/how-it-works">six named factors</a> — Trend, Relative Strength, Fundamentals, Smart Money, Macro, and Momentum.</p>

<p>Two of those speak most directly to a coiled chart. <a href="/how-it-works/trend">Trend</a> reads whether the quiet base is sitting inside an established uptrend, a downtrend, or genuine indecision. <a href="/how-it-works/momentum">Momentum</a> reads the rate-of-change and where the recent tape is leaning as the range tightens. Neither predicts the break — but together they describe which way the underlying data is tilted while price is still flat.</p>

<p>When several factors line up, the composite lands in the <a href="/signal/strong-setup">STRONG SETUP</a> band (Tapeline Score 70–84): four to five of the six factors favourable, usually a clean trend-plus-relative-strength read with a factor or two lagging. That label is descriptive — it says the factor data is in a particular state, not that a squeeze is about to resolve upward. A tight base under a STRONG SETUP score simply carries more constructive context than the same base under a CAUTION score. The chart pattern and the factor read are two independent lenses: the squeeze is one, the score is the other.</p>

<p>You can check whether that framing has held up over time on the public <a href="/scorecard">scorecard</a>, which back-checks every top-10 daily pick against the next session versus SPY. It's honest about where the model is trailing, not only where it lands.</p>

<h2>The genuine caveat</h2>
<p>A Bollinger Band squeeze is a description of volatility, not a forecast. Most tight bases resolve into noise rather than clean trends, and no factor score changes the fact that direction is unknown until price actually moves. Read the squeeze as a <em>when might</em>, never a <em>which way</em>, and treat any tool — Tapeline included — as one input into your own judgement rather than an answer. Nothing here is a recommendation to trade anything; see the <a href="/legal/risk">risk disclosure</a> for the full picture.</p>`,
    howToSteps: [
      { name: "Plot the bands", text: "Apply Bollinger Bands with the standard settings — a 20-period simple moving average with the upper and lower bands two standard deviations away. This is the default on almost every charting platform, so no configuration is usually needed." },
      { name: "Track BandWidth", text: "Add Bollinger's BandWidth indicator, which measures the gap between the upper and lower band as a percentage of the middle line. It turns 'the bands look tight' into a number you can compare across time rather than eyeball." },
      { name: "Find the contraction", text: "A squeeze is present when BandWidth falls to a multi-month low — for example its lowest reading in roughly six months. That marks realized volatility bottoming out, which is the coil that squeeze-watchers are looking for." },
      { name: "Confirm the quiet", text: "Check that the low-volatility state has persisted across several bars, not a single quiet candle. Thinning volume and a visibly narrowing price range alongside the low BandWidth reading make the contraction more credible." },
      { name: "Read direction separately", text: "The squeeze indicates a move is more likely, not which way. Read directional context — trend, relative strength, momentum — as a separate lens, and accept that the break stays unknown until price actually leaves the range." },
    ],
    howToTime: "PT7M",
  },
  {
    slug: "descriptive-vs-prescriptive-ratings",
    title: "Stock Rating Systems: Descriptive vs Prescriptive Labels",
    excerpt: "A stock rating can tell you what to do, or it can tell you what's true — and those are very different products. This post breaks down descriptive rating systems versus prescriptive buy/sell verdicts: the cognitive traps a verdict hides, the legal line it crosses, and why Tapeline's labels describe a state instead of issuing a command.",
    publishedAt: "2026-07-29",
    author: "Tapeline",
    body: `<p>Every stock "rating" answers one of two very different questions. A prescriptive rating answers <em>what should I do?</em> — Buy, Sell, Hold, Strong Buy, target $180. A descriptive rating answers <em>what is currently true?</em> — the trend is intact, relative strength is lagging, insiders are accumulating. On a screen the two look almost identical. They are not the same object, and the gap between them is wider than most rating systems admit.</p>

<p>Most of the retail world runs on the prescriptive kind. Analyst desks publish Buy/Hold/Sell. Aggregators average those into a "Strong Buy." The format is comforting because it collapses a messy pile of evidence into a single instruction. That is also exactly the problem.</p>

<h2>What a prescriptive rating hides</h2>

<p>A verdict is lossy. When a system compresses trend, valuation, momentum, and flow into the word "Buy," everything that made the picture interesting disappears. You can no longer see that the fundamentals are excellent while the chart is broken, or that momentum is screaming while relative strength quietly lags. The label has already decided the tradeoff and discarded the components that would let a reader disagree.</p>

<p>It also invites a specific cognitive trap: anchoring. Once a verdict is on the screen, the mind treats it as the reference point and reasons backward from it. "Strong Buy, target $180" doesn't start a thought process — it ends one. The reader stops asking what the evidence says and starts asking whether $180 is close.</p>

<p>And a verdict is almost impossible to check. "Buy" carries no timeframe, no confidence interval, no falsifiable claim. If the stock falls, the call was "long-term." If it rises, the call was right. Prescriptive labels are structurally unaccountable, which is convenient for whoever is issuing them.</p>

<h2>The legal line most tools walk past</h2>

<p>There is a second reason to avoid verdicts, and it isn't cosmetic. In the United States, telling a specific person to buy or sell a specific security — for compensation, as a business — is regulated activity. That is the territory of registered investment advisers, with the fiduciary duties, disclosures, and licensing that come attached. A tool that prints "Buy AAPL" is, arguably, doing exactly that: issuing individualized investment advice.</p>

<p>Tapeline is a data and scanning tool, not a licensed advisor, and it does not pretend otherwise. Describing what the data shows is analysis. Instructing a reader to act is advice. Keeping those two things clearly separated isn't legal theater — it is an honest statement of what the product is allowed to do and what it isn't. The full version of that boundary lives on the <a href="/legal/risk">risk and disclosures page</a>.</p>

<h2>How Tapeline labels stay descriptive</h2>

<p>The six-factor score — trend, relative strength, fundamentals, smart money, macro, and momentum, documented on <a href="/how-it-works">how it works</a> — rolls up into a single label. Those labels are deliberately descriptions of a <em>state</em>, not commands:</p>

<ul>
  <li><a href="/signal/high-conviction">HIGH CONVICTION</a> — all six factors aligned positive at high sub-score values; a rare configuration.</li>
  <li>STRONG SETUP — most factors favourable, usually a clean trend-and-strength combination with one or two lagging behind.</li>
  <li>CONSTRUCTIVE — net positive, but with at least one factor pulling meaningfully against the others.</li>
  <li>NEUTRAL, CAUTION, and WEAK — the same descriptive vocabulary applied to the flat and negative side of the spectrum.</li>
</ul>

<p>Notice what none of those words do: none of them tell anyone to act. "HIGH CONVICTION" is a statement about factor alignment, not an instruction to buy. The decision stays with the reader — their timeframe, their risk tolerance, their portfolio context — because those things live with the reader, not inside a scanner. A descriptive label hands over the observation and stops there, on purpose.</p>

<p>That design is also what makes the system checkable. Because a label is a concrete claim about a measurable state, it can be logged and compared against what actually happened next. The <a href="/scorecard">public scorecard</a> does precisely that — it back-checks each day's top-ranked names against the following session, in the open, whether the result flatters the model or not. A verdict you cannot audit isn't transparency; a description you can is.</p>

<h2>The honest tradeoff</h2>

<p>Descriptive labels ask more of the reader. A "Strong Buy" requires no thought; "CONSTRUCTIVE — strong fundamentals, weak trend" requires weighing two things that point in opposite directions and reaching an independent conclusion. That friction is the feature, not a bug — but it is real, and it isn't for everyone. Some people genuinely want to be told what to do, and a descriptive scanner will always feel like it is withholding the last step.</p>

<p>It is withholding it because the last step isn't ours to take. A label is a starting observation about a noisy, uncertain market — not a forecast, and not a recommendation. It can be accurate about the state of the data and still be followed by a move in either direction. That is why the labels read as descriptions rather than instructions, and why the <a href="/legal/risk">risk disclosures</a> belong to the methodology rather than the fine print.</p>`,
  },
  {
    slug: "case-against-ai-stock-scanners",
    title: "AI Stock Scanner: The Case for Seeing the Method and the Losses",
    excerpt: "\"AI stock scanner\" has become a marketing label, not a disclosure — most tools that wear it will show you the winners and name nothing about how the number is built. This is the honest case for the opposite: a published methodology and a public scorecard that includes the trades it got wrong. Transparency isn't an edge, but opacity should be a red flag.",
    publishedAt: "2026-07-29",
    author: "Tapeline",
    body: `<p>Search "AI stock scanner" or "best AI stock picker" today and you get a wall of tools that all promise the same thing in the same font: an algorithm, a neural network, a proprietary model that finds the moves before you do. The word "AI" is doing a lot of work in those headlines — and almost none of it is disclosure. It's persuasion. "AI" has quietly become the modern version of "secret formula": a phrase designed to make you stop asking how the thing actually works.</p>

<p>The problem was never artificial intelligence. Plenty of honest tools use machine learning in the pipeline, and there's nothing wrong with a model. The problem is <strong>opacity</strong>, and "AI" is just the most fashionable wrapper for it. When a scanner hides behind the word, it's usually hiding two specific things: what it is actually measuring, and the record of how that process has actually done.</p>

<h2>The two things an opaque scanner won't show you</h2>

<p>The first is the method. If a tool ranks the entire market and hands you a verdict, the only question that matters is: <em>what is it weighing, and why?</em> A scanner that can't answer that is asking you to trust an output with no way to audit the input. "Our AI analyzes thousands of data points" is not an answer. It's a way of not answering. You can't disagree with a weighting you're not allowed to see, and you can't tell noise from signal when the whole thing is a black box.</p>

<p>The second is the track record — and this is where "AI stock signals" marketing gets genuinely misleading. Look closely at how these tools present results. It's almost always a gallery of winners: a screenshot of the ticker that ran 40%, a testimonial, a green arrow. What's missing is the denominator. How many signals fired that week? How many went nowhere? How many were flatly wrong? A highlight reel of hits with every miss cropped out isn't a track record — it's survivorship bias with a marketing budget. Any process that only publishes its wins is telling you it doesn't want you to keep score.</p>

<p>"AI" makes both problems worse because complexity becomes the excuse. A simple weighted score is at least legible; you could, in principle, ask what each factor contributes. Once a vendor says "deep learning," the honesty bar somehow drops to zero, as if the math being complicated relieves them of the duty to show it to you. It doesn't. The more a model influences what you look at, the <em>more</em> you're owed an explanation, not less.</p>

<h2>The opposite approach: name the factors</h2>

<p>Tapeline's answer to all of this is deliberately boring: name what goes in. The score is a composite of six named factors — Trend, Relative Strength, Fundamentals, Smart Money, Macro, and Momentum — and each one is documented, including what data feeds it and where its lags are. The published methodology also states which factors carry the most weight: most toward Trend and Relative Strength, least toward Momentum. The exact numeric weights stay in-house. Smart Money, for example, reads SEC Form 4 filings: the disclosures corporate insiders are legally required to file when they trade their own company's stock. Not a mysterious "institutional signal," not hedge-fund tea leaves — a specific, public filing you can go read yourself. You can walk through every factor's methodology on <a href="/how-it-works">how it works</a>. There is no hidden layer where the "real" model lives — the six factors on that page are the whole input list.</p>

<p>The harder half is the losses. Tapeline runs a <a href="/scorecard">public scorecard</a> that tracks how the highest-scoring names actually performed afterward — and it publishes that record whether it's flattering or not. Right now it isn't especially flattering: over its tracked window the scorecard trails a simple S&P 500 index fund. That's stated plainly, on the page, because a scorecard that only shows good stretches would be exactly the survivorship theatre this whole post is complaining about. The honest reason to keep score isn't to prove the process wins. It's so you can see, in the open, whether it does.</p>

<h2>What to actually look for</h2>

<p>None of this requires taking a side on any particular competitor. It's a lens for reading all of them. When you evaluate any "AI" scanner — Trade Ideas, Tapeline, or the next one — the questions are the same: Can I see what it measures, or just the output? Can I see the losses, or just the highlight reel? Is there a denominator anywhere? Our own side-by-side on <a href="/compare/trade-ideas">Tapeline vs Trade Ideas</a> is written to make those exact differences legible rather than to declare a winner. If a tool makes it hard to answer those three questions, that difficulty is itself the answer.</p>

<h2>The honest caveat</h2>

<p>Transparency is not the same thing as edge. A fully documented method can still be wrong, and Tapeline's currently underperforms a plain index — being able to read the methodology doesn't make the methodology correct. A visible track record describes the past; it does not forecast the next quarter, and past scores carry no promise about future ones. Nothing here is a recommendation to buy or sell anything, and none of it is investment advice — see the <a href="/legal/risk">risk disclosure</a> for the full version. The only claim being made is a modest one: a tool that names what it measures and shows you its losses has given you enough to judge it. A tool that hides both is asking you to judge nothing — and calling that "AI."</p>`,
  },
  {
    slug: "sector-rotation-2026-q3",
    title: "Sector Rotation Strategy: How to Read What's Leading (Q3 2026)",
    excerpt: "Sector rotation sounds like a strategy but is really an observation — which of the eleven GICS sectors the market has been favouring, and which it has left behind. Heading through Q3 2026, here is how to read sector leadership honestly: regime first, then Relative Strength by sector, without pretending anyone can forecast the next rotation. It connects that read to Tapeline's Macro factor and per-sector pages.",
    publishedAt: "2026-07-29",
    author: "Tapeline",
    body: `<p>"Sector rotation" is one of those phrases that sounds like a strategy and is really a description. Money does not march through the eleven equity sectors on a schedule you can set your watch to. But over weeks and months, leadership does shift — energy leads one stretch, technology another, utilities and staples take over when the market turns defensive. Reading which sectors are carrying the market, and which are lagging, is one of the oldest ways to understand what kind of market you are actually in.</p>

<p>Heading through the third quarter of 2026, the question "what sectors are leading?" is being asked again, as it always is. This post is about how to read that honestly — without pretending anyone can forecast the next rotation. That distinction runs through everything below.</p>

<h2>What sector rotation actually is</h2>
<p>The US equity market is divided into eleven broad sectors under the GICS taxonomy: Information Technology, Health Care, Financials, Consumer Discretionary, Consumer Staples, Communication Services, Industrials, Energy, Utilities, Real Estate and Materials. Every listed company sits in exactly one. Sector rotation is simply the observation that, at any given time, relative performance concentrates in some of those buckets more than others — and that the concentration moves.</p>

<p>The textbook version ties rotation to the business cycle: cyclicals and financials early, energy and materials late, staples and utilities and health care when growth slows. It is a useful vocabulary. As a timing tool it is unreliable — cycles are only obvious in hindsight, the labels blur, and every cycle insists it is different. Treat the framework as a way to describe what already happened, not a calendar for what happens next.</p>

<h2>Regime first, sectors second</h2>
<p>Before asking which sector leads, it helps to ask what kind of market is doing the leading. A rotation into defensives during a falling market means something different from a rotation into those same sectors during a broad advance. That is why Tapeline treats the market backdrop as its own input rather than burying it inside every ticker.</p>

<p>That input is the <a href="/how-it-works/macro">Macro factor</a>, one of the six factors in the Tapeline Score. Macro reads a single market-wide regime classification and resolves it into one of three broad families — a rising or positive backdrop, a sideways or neutral one, and a falling or negative one. It is deliberately the same number for every ticker on a given tick: it describes the room, not the individual name. It is also strictly backward-looking, identifying a regime only once one is already under way, and it makes no forecast of when the regime will change. Read it as context, never as a prediction.</p>

<h2>How to read which sectors are leading</h2>
<p>Tapeline does not publish a "buy this sector" verdict, and it never will. What it does is score every name in the liquid universe on the same six factors, then let you slice that scored universe by sector. Each sector page shows how the names in one bucket are reading now — most usefully through Relative Strength, the factor that measures a ticker's price change against the broad-market benchmark over several horizons.</p>

<ul>
  <li>Start with the backdrop above: note which Macro regime family is in force, because the same leadership reads differently in a rising versus a falling market.</li>
  <li>Open a sector page — for example <a href="/sector/information-technology">Information Technology</a>, <a href="/sector/energy">Energy</a> or <a href="/sector/utilities">Utilities</a> — and look at the spread of Relative Strength readings across the names inside it.</li>
  <li>Compare that spread against other sectors. A sector where many names carry high Relative Strength is one the market has been favouring; a sector where most names lag is one it has been leaving behind. That comparison is the whole of what "leading" and "lagging" honestly mean.</li>
</ul>

<p>None of this tells you what a sector will do next. It tells you, in plain and checkable terms, what it has already done and how broadly. That is the honest ceiling of any rotation read, and it is where Tapeline deliberately stops.</p>

<h2>What this cannot tell you</h2>
<p>Sector leadership is a lagging description built on price that has already printed. Relative Strength is a difference between two returns, so a sector can "lead" over a stretch in which every name in it fell — because the benchmark fell further. Sector membership itself is coarse: a diversified conglomerate and a single-product company can share one bucket. And the Macro regime that frames all of it is a discrete label imposed on a continuous world, revised after the fact. You can see how each factor is built, and where each one fails, across the <a href="/how-it-works">methodology pages</a>; the live <a href="/scorecard">public scorecard</a> shows how the whole scored approach has actually done, including where it has trailed the market. Sector rotation is a lens for understanding the market you are in — not a signal for the one you are about to be in.</p>`,
    howToSteps: [
      { name: "Read the market regime first", text: "Start with the backdrop. Tapeline's Macro factor resolves the market-wide regime into a rising, sideways or falling family. The same sector leadership reads differently depending on which family is in force. It is context, not a forecast." },
      { name: "Open the sector pages", text: "Open a sector page such as Information Technology, Energy or Utilities and look at the spread of Relative Strength readings across the names inside that GICS bucket." },
      { name: "Compare leading versus lagging sectors", text: "Set one sector's spread of readings against the others. A sector where many names carry high Relative Strength is one the market has been favouring; a sector where most lag has been left behind. That comparison is all 'leading' honestly means." },
      { name: "Note what the read cannot tell you", text: "Sector leadership is backward-looking, built on price that already printed. Relative Strength is a difference, so a sector can lead while its own names fell. Treat the read as description of the past, never a prediction of the next rotation." },
    ],
    howToTime: "PT5M",
  },
  {
    slug: "what-smart-money-actually-means",
    title: "What 'Smart Money' actually means in the Tapeline Score (and why it's not what you think).",
    metaTitle: "What 'Smart Money' actually means in the Tapeline Score",
    excerpt:
      "'Smart money' is the most misused phrase in retail finance. It's not influencer alpha, not the latest hedge-fund headline, not yesterday's CNBC clip. Here's what Tapeline's Smart Money factor — one of the six — actually measures, what the data sources are, and where the lags lie.",
    publishedAt: "2026-05-13",
    author: "Tapeline",
    body: `
      <p>"Smart money" is the most misused phrase in retail finance. Open
      any trading subreddit, scroll any finance TikTok, look at any
      newsletter sales page — somebody is selling you "what the smart
      money is doing." Almost always, what they mean is "what one
      famous person on CNBC said in a clip yesterday." That's not smart
      money. That's TV.</p>

      <p>Tapeline's Smart Money factor is one of the six named factors in the
      composite score (<a href="/how-it-works">see the methodology</a>). It's a real
      number, sourced from real filings, with real lags. This post is
      the deep dive on what it actually measures and where the
      limitations are — because a named factor in our scoring engine
      deserves a paragraph more than "trust us, we're tracking the
      smart money."</p>

      <h2>The data sources behind the factor</h2>
      <p>Smart Money sums to a 0–100 sub-score from two independent
      data streams, each with its own lag and signal-to-noise
      characteristics:</p>
      <ol>
        <li><strong>Congressional disclosures</strong> — required by the
        STOCK Act (Stop Trading on Congressional Knowledge Act, 2012).
        US House and Senate members must disclose trades over $1,000
        within 30–45 days. The signal: when multiple members on relevant
        committees buy or sell the same name, that's information they
        plausibly had access to that the market didn't.</li>
        <li><strong>Insider Form 4 filings</strong> — required by the
        SEC within 2 business days of any insider transaction
        (executives, directors, 10%+ owners). The signal: insiders are
        the only buyers who know more about the company than the
        market, by definition. Clusters of buying — multiple insiders
        in the same window — are a stronger signal than single-buyer
        events.</li>
      </ol>

      <h2>What "smart money buying" actually predicts</h2>
      <p>Each data source has a different predictive horizon. Let me
      walk through the cases that matter:</p>

      <p><strong>Congressional buying</strong> works best on names
      where committee members have informational access — defense
      contractors near a relevant Armed Services committee member, healthcare names near
      a Finance committee member, regulatory beneficiaries before a
      relevant ruling. The base rate of edge is small but non-zero;
      academic studies (Ziobrowski et al., Belmont & Sayers) have
      shown weak positive alpha on a portfolio basis.</p>

      <p><strong>Insider Form 4 filings</strong> have the shortest lag
      (1–3 business days) and the highest signal-to-noise for cluster
      events. Single-insider buys are weak — executives buy for
      compensation reasons, exercising options is mechanical, charity
      donations get filed too. Multi-insider buys in the same window,
      where the executives have no scheduled compensation event, are the
      higher-signal case. Selling clusters are harder to read (they
      can mean tax planning, diversification, or genuine signal — hard
      to disambiguate).</p>

      <h2>Why Smart Money isn't one of the biggest factors</h2>
      <p>A natural retail-trader question: if Smart Money is so
      signal-rich, why isn't it the heaviest factor in the composite? Three
      reasons:</p>

      <p><strong>The lags compound.</strong> Insider Form 4 filings
      arrive 1–3 days after the trade. Congressional STOCK Act filings
      can be 30–45 days late and include trades that have already been
      unwound. By the time the data is clean and public, much of the
      move has happened.</p>

      <p><strong>It's a confirmation factor, not a leading one.</strong>
      Smart money flow is most useful in confluence with the other
      factors — when Trend, Relative Strength, and Smart Money all
      agree, that's the highest-conviction setup. Smart Money alone is
      late information; combined with leading factors it becomes
      directional certainty.</p>

      <p><strong>Survivorship and crowding.</strong> The fund managers
      most retail tools point at — Buffett, Burry, Tepper — are also
      the most-watched in the world. Their moves are crowded trades by
      the time any 13F filing publishes. Buffett buying Apple in 2016
      was signal; Buffett buying Apple in 2024 was a market price-anchor,
      not new information. This is one reason Tapeline doesn't fold 13F
      filings into the Smart Money sub-score directly — by the time a
      filing is public, the edge is largely priced.</p>

      <h2>How the Tapeline score uses it differently from competitors</h2>
      <p>Most "smart money" scoring in retail tools is broken in one of
      two ways: either it's a single-source (just hedge fund holdings,
      or just Congressional) which misses the confluence signal, or
      it's opaque (Tipranks' Hedge Fund Sentiment is a Smart Score
      input but the weighting and the underlying fund list are not
      published). Tapeline:</p>
      <ul>
        <li>Combines Congressional STOCK Act disclosures and SEC Form 4
        insider transactions into a single 0-100 sub-score with
        published methodology.</li>
        <li>Weights the sub-score as a mid-tier factor — high enough
        to matter, low enough not to drown out the leading factors when
        smart money is late or noisy.</li>
        <li>Surfaces the actual data feeds: the Premium tier exposes
        the underlying Congressional trades feed at /app/congress and
        the recent insider buys at /app/holdings — not just the
        aggregated score.</li>
      </ul>

      <h2>What to actually do with this</h2>
      <p>Don't treat Smart Money as a trigger on its own. Treat it as
      a confluence multiplier:</p>
      <ul>
        <li>A 90 Smart Money sub-score on a 40 composite is a value
        signal — institutions are positioning before the market has
        rerated it. Worth a watchlist add.</li>
        <li>A 90 Smart Money sub-score on a 75 composite is confirmation
        — the smart money is in a setup that's already showing up in
        Trend, RS, and Momentum. Standard signal-of-signals.</li>
        <li>A 30 Smart Money sub-score on a 75 composite is a yellow
        flag — strong setup, but institutions and insiders aren't
        confirming. Worth understanding why before sizing up.</li>
        <li>A 90 Smart Money sub-score with no other factor confirming
        is curious but not actionable. Maybe insiders are buying for a
        reason the market hasn't seen yet; maybe they're wrong.</li>
      </ul>

      <p>The point of breaking out the sub-score is exactly this kind
      of nuance. The composite gives you a summary; the breakdown lets
      you read where the conviction actually lives, and where it's
      conspicuously absent.</p>

      <p>You can see live Smart Money sub-scores on any ticker page —
      e.g. <a href="/t/NVDA">/t/NVDA</a>, <a href="/t/AAPL">/t/AAPL</a>
      — or filter by it on the live scanner. The full Congressional
      trades feed and recent insider buys are Premium features at
      /app/congress and /app/holdings; the Smart Money sub-score itself
      is shown on the ticker pages linked above.</p>
    `,
  },
  {
    slug: "stock-screener-vs-stock-scanner",
    // 2026-07-11: retitled to exact-match the definitional query (GSC: 318
    // impressions incl. "finviz alternative" 136, pos ~23). Question form,
    // <60 chars, no trailing period. Deliberately omits "Finviz" from the
    // title so it doesn't cannibalize /best-finviz-alternatives; the excerpt
    // keeps "Finviz" for the leaked finviz-alternative impressions.
    title: "Stock Screener vs Stock Scanner: What's the Difference?",
    excerpt:
      "'Screener' and 'scanner' aren't synonyms — one gives filters, the other a verdict. Which you need, and where Finviz fits, decides which tool you keep.",
    publishedAt: "2026-05-13",
    author: "Tapeline",
    body: `
      <p>Two of the most common Google queries in active retail trading
      are "stock screener" and "stock scanner". Most people treat them as
      synonyms. Most tools position themselves as both. They are not the
      same thing, and conflating them is how traders end up with $30/mo
      subscriptions they never open.</p>

      <p>The difference, in one sentence: <strong>a screener gives you
      filters; a scanner gives you a verdict.</strong> Both can be useful.
      Only one of them earns daily reuse.</p>

      <h2>What a screener actually does</h2>
      <p>A screener is a multi-field filter. You pick fields (price, P/E,
      RSI, market cap, sector, 20DMA distance, IV rank, insider ownership
      …) and set thresholds. The screener returns the rows that match.
      That's it. The output is a list of tickers; the synthesis — what
      each row actually means — is on you.</p>

      <p>Canonical example: Finviz. You can build a screen for "small-cap
      tech, P/E under 15, RSI below 30, above the 200DMA, insider buying
      last 6 months" and get a list back. The tool has done a database
      query for you. It hasn't formed an opinion.</p>

      <p>This is genuinely useful for a particular workflow: when you
      already know what you're looking for and you need a fast database
      query against the whole market. Anyone who's run a value-investing
      checklist or scanned for option-IV outliers has used screeners well.</p>

      <p>It is <em>not</em> what most retail traders actually need most
      mornings. Most mornings, what a retail trader wants is "what
      changed overnight that I should care about." Screening doesn't
      answer that — you have to know in advance what filter to set.</p>

      <h2>What a scanner actually does</h2>
      <p>A scanner is opinionated. It runs a model — anything from a
      simple weighted score to a deep-learning ensemble — and produces a
      ranked list with a verdict per row. The output is a recommendation
      shape: <em>this</em> is the top of the distribution today,
      <em>here's</em> why, <em>here's</em> how the signal label maps to
      the underlying score.</p>

      <p>The point of a scanner isn't the filters. It's the synthesis.
      The tool has decided what matters, weighted it, and surfaced the
      conclusion. You can disagree with the weighting — but you can't
      avoid <em>seeing</em> the conclusion.</p>

      <p>This matters because the binding constraint on most retail
      traders isn't data access. It's attention. The market has 2,500
      liquid US tickers; nobody reads all of them. A screener helps you
      find what you're looking for. A scanner helps you find what you
      didn't know to look for.</p>

      <h2>Why the distinction predicts six-month retention</h2>
      <p>If you've subscribed to multiple finance tools, you've seen this
      pattern: a screener gets daily use for the first week, then weekly
      use, then monthly, then never. A good scanner gets daily use
      indefinitely. The difference isn't the data behind them — most
      tools use overlapping data feeds. The difference is the cognitive
      load per session.</p>

      <p>Screeners require you to bring the question. Scanners hand you
      the question already formed. When you have 10 minutes before
      market open and three personal-life things on your mind, the
      cognitive cost of "construct a useful screen this morning"
      outweighs the cost of opening the app at all. So you don't open it.</p>

      <p>This isn't a problem with the user. It's a structural property
      of the tool category. The scanner format has lower activation
      energy and therefore higher retention.</p>

      <h2>The "scanner that gives you a screener" trap</h2>
      <p>Many tools position as both. TradingView calls itself a scanner;
      the actual product is a charting platform with filter overlays.
      Trade Ideas has Holly AI (scanner-shaped) AND a flexible filter
      builder (screener-shaped). The marketing fudges the line.</p>

      <p>That's fine as positioning. It does mean you need to look at
      what the tool actually defaults to when you open it. If the
      default view is a blank filter panel waiting for you to build
      something, you have a screener. If the default view is a ranked
      list with a verdict per row, you have a scanner.</p>

      <p>By that test, Tipranks, Zacks, and WallStreetZen are scanners
      (they default to a ranking with a per-row verdict — a Smart Score,
      a Zacks Rank, a Zen Rating). Finviz, in spite of its premium tier,
      is a screener (the default is a filterable table where you bring
      the criteria). Most "AI stock scanners" in 2025/26 are also
      scanners by this test — though many won't say what goes into that
      verdict, which is its own problem
      (<a href="/blog/the-formula-is-public">our methodology is public</a>
      goes deep on that).</p>

      <h2>Which one Tapeline is</h2>
      <p>Tapeline is a scanner. The default view at
      <a href="/app/scanner">/app/scanner</a> is a ranked list of every
      liquid US ticker with a 0–100 composite score and a plain-English
      sentence per row. The
      <a href="/how-it-works">six-factor methodology</a> is public — every
      factor named, and which ones carry the most weight; the
      <a href="/scorecard">scorecard</a> back-checks every top-10 daily
      pick against the next session vs SPY.</p>

      <p>You can also filter — by sector, by signal label, by minimum
      score, etc. — and the score breakdown lets you reproduce screener-
      shaped queries when you want to. But the default is the verdict.
      That's the design choice, and it's deliberate. Five minutes a
      morning, ranked list, one sentence per row. Click the names you
      care about; ignore the rest.</p>

      <h2>How to decide which you need</h2>
      <p>Pick the screener if:</p>
      <ul>
        <li>You already have a defined strategy (value, momentum,
        options-IV outliers, post-earnings drift) and you need to surface
        candidates that fit it.</li>
        <li>You enjoy designing filters and tuning them over time.</li>
        <li>You're willing to do the synthesis work yourself.</li>
      </ul>
      <p>Pick the scanner if:</p>
      <ul>
        <li>You want a daily ranked starting point you didn't have to
        build.</li>
        <li>You want the tool to do the synthesis work and you'll bring
        the discretion.</li>
        <li>You want accountability — a scanner with a public scorecard
        is the only way to tell whether the model is actually working
        over time.</li>
      </ul>

      <p>Both can be useful. Don't pay for two if you only use one.
      Don't subscribe to either if you can't tell which kind you have.</p>

      <p>If you're not sure where to start, the
      <a href="/compare/finviz">Tapeline vs Finviz comparison</a> goes
      into the screener-vs-scanner question head-to-head with a real
      $8.25/mo entry tier. Both products do useful work; they don't do
      the same work.</p>
    `,
  },
  {
    slug: "reading-a-tapeline-score",
    title: "Reading a Tapeline Score: a 10-minute walkthrough on $NVDA.",
    excerpt:
      "Most scanner scores are a number with no instructions. This is the opposite: a worked example on NVIDIA showing what each of the six factors is saying, how to read the radar, and when the composite is telling you the trade is harder than it looks.",
    publishedAt: "2026-05-12",
    author: "Tapeline",
    body: `
      <p>Most stock scanners give you a score and call it done. The score is
      the easy part — the hard part is knowing what it's actually telling you.
      Two stocks can both score 58, and one is a textbook setup while the
      other is a fundamentally strong name that the market hasn't priced in
      yet. The composite hides the difference; the factor breakdown shows it.</p>

      <p>So here's the walkthrough I wish every scanner gave you: a real
      ticker, a real score, and what each of the six numbers underneath is
      telling you. We'll do <a href="/t/NVDA"><strong>NVDA</strong></a> — at
      the time of writing, it's sitting at a composite of <strong>57.9</strong>
      with the signal <strong>CONSTRUCTIVE</strong>. That's a 58 with three
      different stories inside it, and reading them all is the difference
      between an action and a watch.</p>

      <h2>Step 1 — Don't start with the composite</h2>
      <p>The composite is a summary. It's where most traders stop. It's where
      every other scanner stops too. The composite tells you "the data is
      roughly net-positive on this name" — and that's about it. Same number
      can come from a sleepy large-cap with strong fundamentals and a weak
      chart, or from a momentum name where the trend is on fire but the
      balance sheet is questionable. Same 58, two opposite trades.</p>

      <p>So we ignore the headline for a minute and look at the six factors.
      The Tapeline radar shows them as a hexagon — six axes, each one a
      sub-score from 0–100, all blended into the composite. The factors are
      listed here in descending weight order (Trend heaviest through Momentum
      lightest), the same ordering documented on
      <a href="/how-it-works">/how-it-works</a>:</p>

      <pre style="background:#0a0a0a;border:1px solid #1f1f23;border-radius:8px;padding:18px;overflow-x:auto;font-family:'JetBrains Mono',ui-monospace,monospace;font-size:13px;line-height:1.5;">
NVDA — composite 57.9 (CONSTRUCTIVE)

  Trend                41
  Relative Strength    32
  Fundamentals         55
  Smart Money          97
  Macro                65
  Momentum             87</pre>

      <p>That's where the actual signal lives. Now we read it.</p>

      <h2>Step 2 — Look for the contradictions</h2>
      <p>Most scores tell a single story. Strong trend, strong RS, strong
      fundamentals — easy, the data points the same direction, you're in or
      out. NVDA doesn't do that. Look at the spread:</p>

      <ul>
        <li><strong>Smart Money 97</strong> (top 3%) — insiders are
        net-accumulating. Congressional disclosures and SEC Form 4 buying
        — both flowing in.</li>
        <li><strong>Momentum 87</strong> (top 13%) — short-term price action
        is accelerating, volume is confirming, breakouts are recent.</li>
        <li><strong>Trend 41</strong> (below median) — but the multi-timeframe
        trend isn't fully aligned yet. The weekly and monthly haven't caught
        up to the burst the momentum factor is seeing.</li>
        <li><strong>Relative Strength 32</strong> (bottom third) — and the
        name is actually <em>lagging</em> tech peers on the multi-week view.</li>
      </ul>

      <p>That's a contradiction. Smart money is in. Short-term price is
      ripping. But the longer-timeframe trend hasn't confirmed yet, and the
      sector is running ahead of it on a 1M view. You read that as: the
      institutional buying may be early to a move that hasn't fully started,
      OR it's catching a bounce inside a chop and the bigger trend won't
      cooperate. The score can't tell you which. You have to overlay your
      own read of where we are in the regime.</p>

      <h2>Step 3 — Use the macro factor to ground it</h2>
      <p>This is the factor most other scanners don't expose at all. NVDA's
      <strong>Macro 65</strong> says the market-wide regime classification is
      mildly supportive — the same reading every ticker on the board carries
      on that tick. That matters. A 58 composite in a friendly regime reads very differently
      from a 58 composite during a vol shock; the latter is a "wait and see"
      and the former is closer to "this is a real setup the regime isn't
      fighting."</p>

      <p>You can think of macro as the gain on the whole signal. Same factor
      configuration in a hostile regime gets a different verdict. We surface
      it explicitly so you don't have to remember.</p>

      <h2>Step 4 — Read the fundamentals factor like a quality filter</h2>
      <p><strong>Fundamentals 55</strong> on NVDA is the least interesting
      number in the row, which is itself informative. It says: this isn't a
      fundamentals trade. The earnings quality, margin trend, balance-sheet
      health — all sitting in the "supportive but not the reason to be here"
      zone. If you're trading on a multi-quarter horizon, you'd want this
      number higher. If you're trading the next two weeks, 55 is fine — it's
      saying the name isn't fundamentally broken.</p>

      <h2>Step 5 — What the composite actually meant</h2>
      <p>So back to the headline number. 57.9 CONSTRUCTIVE on NVDA isn't
      "buy this." It's "the data is net-positive but split between leading
      and lagging factors, in a regime that's mildly helpful." If you were
      already long, the composite says hold. If you were flat, the composite
      says either wait for the trend factor to confirm (it'll climb when the
      weekly catches up to the daily) or take a smaller-than-normal size
      because the leading-vs-lagging spread is wide.</p>

      <p>Every other scanner that gives you a "BUY" or a "7/10" hides this.
      The composite hides it too. The six-factor radar is what shows it.</p>

      <h2>Step 6 — Compare to what the scorecard recorded</h2>
      <p>This part is the accountability check. On the
      <a href="/scorecard">public scorecard</a>, every top-10 daily pick
      we've flagged is logged with its composite, its signal label, its
      one-sentence reason, and the next-day return vs SPY. So if NVDA
      surfaces in tomorrow's top 10, we'll record what the model thought
      tonight, and we'll know in 24 hours whether the read held up.</p>

      <p>Most scanners never close that loop. They tell you the score
      tonight and they're silent the next morning. We're the opposite:
      tonight's score lives on the page tomorrow, with the realised return
      next to it. If our reads are systematically wrong on a factor,
      <em>you can see it</em>, and you can adjust.</p>

      <h2>The five things to take from this</h2>
      <ol>
        <li>The composite is a summary. The factor row is the signal.</li>
        <li>Look for contradictions between Trend, RS, Smart Money, and
        Momentum — that's where the real read lives.</li>
        <li>The Macro factor scales everything; same composite in different
        regimes is not the same trade.</li>
        <li>Fundamentals is a quality filter, not a directional vote — use
        it to confirm the name isn't broken.</li>
        <li>Cross-reference every read against the scorecard. If our model
        is consistently wrong on the kind of setup you're looking at, the
        scorecard will show it.</li>
      </ol>

      <p>Run the same walkthrough on any ticker you care about at
      <a href="/t/AAPL">/t/&lt;TICKER&gt;</a>. Every page shows the
      composite, the radar, the factor sub-scores, and the why sentence.
      If you want them all in one view ranked by score, the live
      <a href="/app/scanner">scanner</a> is the home for that — Free
      gets live scores for the top 10 rows plus 12 look-ups a day
      (unmetered for the first 24 hours); the
      <a href="/signup">14-day Premium trial</a> — a card at first sign-in,
      $0 charged that day — opens the full real-time universe with unlimited look-ups.</p>
    `,
  },
  {
    slug: "evaluating-a-stock-scanner",
    title: "How to evaluate a stock scanner: 5 questions before you pay.",
    excerpt:
      "Most scanner sales pages are 50 filters and a screenshot. Here are the five questions that actually predict whether a tool will be useful in six months — and how Finviz, Trade Ideas, Zacks, and Tapeline answer them.",
    publishedAt: "2026-05-03",
    author: "Tapeline",
    body: `
      <p>I've signed up for almost every prosumer stock scanner since 2018.
      Most fail the same way: the tool is fine for a week, then you realise
      you have no way to tell whether the calls it surfaces are actually
      working. By month three you've added it to the pile of $20-$50/month
      subscriptions you keep forgetting to cancel.</p>

      <p>If you're shopping for a scanner, these five questions will save you
      the cycle:</p>

      <h2>1. Can you see the methodology?</h2>
      <p>If the answer is "we use a proprietary blend of signals" you're being
      sold magic. The two questions you can't answer about magic are "is this
      working?" and "will this still work next month?" Tipranks, Zacks,
      Kavout, WallStreetZen all hide theirs. Tapeline names all six factors and
      shows each one's contribution per ticker on <a href="/how-it-works">/how-it-works</a>.</p>

      <h2>2. Where's the public scorecard?</h2>
      <p>Newsletter shops have known for 30 years that you should hide your
      losers. Mark Hulbert built a career being the only neutral grader of
      newsletter performance because everyone else hid the data. Look for
      a tool that <em>auto-publishes</em> every call it makes against the
      next-day market move — not a curated highlight reel. We do this at
      <a href="/scorecard">/scorecard</a>; almost nobody else does.</p>

      <h2>3. What does the data come from?</h2>
      <p>"AI-powered signals" usually means "we bought a feed from a third-party market-data feed
      and slapped a score on top." Which is fine — that's also our spine.
      But know it. Bloomberg Terminal at $32k/yr uses similar feeds; the
      premium is the speed and breadth of their proprietary chat and
      curated news, not the raw data. Anyone charging $200/month for
      "exclusive AI signals" is reselling a third-party market-data feed and a third-party data feed.</p>

      <h2>4. Is the cheapest tier real?</h2>
      <p>Test it. If the free or cheapest paid tier strips out so many
      features the product is unusable, the team is incentivised to
      upgrade-trap rather than retain. Tapeline's answer is to put the whole
      published record outside the paywall entirely: the daily Top 10, every
      pick ever made with its next-session result vs SPY, a page per scored
      ticker, and the raw CSV/JSON — no account, no card. The signed-in app
      itself takes a card at first sign-in and starts a 14-day Premium trial
      ($0 that day, first charge on day 14, one click to cancel). Judge the
      product on the record before you decide whether to open an account.</p>

      <h2>5. Can you cancel in one click?</h2>
      <p>If you have to email support to cancel, that's a tell about how
      the team treats you generally. Stripe-portal cancel-in-one-click is
      table stakes; if it's not there, leave. (Yes, ours is.)</p>

      <p>If a tool can't answer questions 1 and 2, walk away regardless of
      price. They're cheap to ask and predict 80% of the future regret.</p>
    `,
  },
  {
    slug: "what-signal-labels-mean",
    title: "What our signal labels mean: HIGH CONVICTION through WEAK.",
    excerpt:
      "Six descriptive labels, no buy/sell language. Here's what each one represents in the underlying score, why we picked descriptive words, and what it means when a ticker moves between them.",
    publishedAt: "2026-05-03",
    author: "Tapeline",
    body: `
      <p>Every Tapeline ticker carries one of six labels. They're not buy
      signals. They're descriptions of the score's tier — which exists for
      legal reasons (we are not a registered investment adviser) and for
      design reasons (you should make the call, we just summarise the data).</p>

      <h2>The mapping</h2>
      <ul>
        <li><strong>HIGH CONVICTION</strong> (85-100) — all six factors
        aligned positive. Trend up, RS strong, fundamentals fine, smart-money
        net buying, macro supportive, momentum healthy. Rare.</li>
        <li><strong>STRONG SETUP</strong> (70-84) — most factors favourable,
        usually 4-5 of 6. The kind of name that shows up in our scorecard
        most often.</li>
        <li><strong>CONSTRUCTIVE</strong> (55-69) — net positive but with
        meaningful trade-offs. Often a great fundamentals story with a weak
        trend, or a hot trend with stretched valuation.</li>
        <li><strong>NEUTRAL</strong> (40-54) — factors cancel. The data
        isn't telling you to do anything.</li>
        <li><strong>CAUTION</strong> (25-39) — more factors negative than
        positive. Trend down, RS lagging, smart money distributing.</li>
        <li><strong>WEAK</strong> (0-24) — broadly negative. Almost always
        reflects a clear downtrend confirmed by deteriorating fundamentals.</li>
      </ul>

      <h2>Why descriptive, not prescriptive</h2>
      <p>The previous version of these labels said BUY NOW, STRONG
      ACCUMULATE, ACCUMULATE, HOLD, WATCH, AVOID. We changed them on day
      one. Two reasons:</p>
      <ul>
        <li><strong>Legal.</strong> Prescriptive language pushes you toward
        being classified as an investment adviser in the US, AU, and UK.
        Descriptive language ("here's what the data says") protects the
        publisher's exemption.</li>
        <li><strong>Honest.</strong> A score of 92 doesn't mean you should
        buy. It means six independent signals are aligned. Whether to act
        depends on your portfolio, risk tolerance, time horizon, and tax
        situation — none of which we know.</li>
      </ul>

      <h2>What a label change means</h2>
      <p>The most useful watchlist signal isn't an absolute level — it's a
      transition. CONSTRUCTIVE → STRONG SETUP is a meaningful shift; STRONG
      SETUP → STRONG SETUP with the score moving from 71 to 84 is also
      meaningful. We send watchlist alerts when the underlying score moves
      by your threshold (default 10 points), not just when the label flips,
      so you don't miss meaningful intra-tier moves.</p>

      <p>If you're new and want to play with this, the public scorecard at
      <a href="/scorecard">/scorecard</a> shows every top-10 we've published
      and how each name moved the next day. That's the most honest demo of
      what the labels actually predict.</p>
    `,
  },
  {
    slug: "why-we-score-2500-not-5000",
    title: "Why we score 2,500 tickers, not 5,000.",
    excerpt:
      "A third-party market-data feed covers thousands of US tickers. We actively score ~2,500 by daily dollar-volume — here's why that cutoff exists, what we do with the rest, and why bigger isn't better.",
    publishedAt: "2026-05-03",
    author: "Tapeline",
    body: `
      <p>The data feed (a third-party market-data feed) gives us coverage of
      every listed US security — the full liquid US universe, after filtering
      out OTC. We actively score the top ~2,500 by daily dollar-volume.
      Roughly half the new-user feedback is "why isn't $XYZ scored?" — so
      here's the reasoning, written once.</p>

      <h2>The filter is liquidity</h2>
      <p>The 2,500 are picked by daily dollar-volume — price × volume —
      and the cutoff lands well below the S&amp;P MidCap 400, deep into
      small-cap territory. Everything below has bid-ask spreads wide
      enough that the "score" stops representing anything actionable. A
      90 score on a $0.15 stock that trades 80,000 shares a day is a
      fiction; you can't get in or out at that price without moving the
      tape against yourself.</p>

      <h2>The factors aren't equally available below the cutoff</h2>
      <p>Trend, momentum, and macro work fine on any ticker with a year
      of bars. Fundamentals and insider Form 4 are sparse for sub-$200M
      caps — small companies just file less often, and analyst coverage
      thins out. Forcing a score across the entire liquid US universe
      would mean thousands of confidence values landing under 40%. That's
      noise, not signal — exactly the experience we're trying to
      replace.</p>

      <h2>What we do with the rest</h2>
      <p>The full universe table is auto-populated weekly from
      a third-party market-data feed's reference API. We use it for: watchlist tracking (you
      can watch any ticker, scored or not), per-ticker pages with price
      and 1-day change, news feeds with sentiment tagging, and ranking —
      so when liquidity grows on a name, it gets promoted into the
      active 2,500 automatically on the next refresh cycle.</p>

      <h2>Why not just score the whole universe?</h2>
      <p>Two reasons. First, the noise above. Second, a third-party data feed's free tier
      is 60 calls/minute — enough for the fundamentals refresh on ~2,500
      names but not the full universe. A bigger universe means a bigger a third-party data feed bill,
      not a better product. We'll only expand if customer behaviour says
      the marginal names are actually being scanned.</p>

      <p>The 2,500 covers basically every US name a retail trader is
      plausibly considering: every S&amp;P 500 + every NASDAQ-100 + every
      Russell 1000 component, plus the most actively-traded sector and
      commodity ETFs. If your watchlist already lives in that range —
      which most do — Tapeline scores everything you care about.</p>
    `,
  },
  {
    slug: "the-formula-is-public",
    title: "Our methodology is public. Here's why that matters.",
    excerpt:
      "Every other prosumer score-per-ticker tool hides its methodology as IP. We name all six factors and publish a per-pick scorecard — because the day the score stops working, you should know to leave.",
    publishedAt: "2026-05-02",
    author: "Tapeline",
    body: `
      <p>If you ask Tipranks why a stock has a 7/10 Smart Score, you get
      "we aggregate analyst consensus, hedge fund moves, insider trades, and
      blogger sentiment." If you ask Zacks why a stock has a #1 rank, the answer
      is "earnings estimate revisions" but the cutoffs are proprietary. If you ask
      Kavout why their Kai Score moved, you get a black-box ML answer.</p>

      <p>Tapeline names all six. The composite is a weighted blend of
      <a href="/how-it-works">Trend, Relative Strength, Fundamentals, Smart
      Money, Macro, and Momentum</a> — weighted most heavily toward Trend and
      Relative Strength, and least toward Momentum, because short-term momentum
      on its own tends to mean-revert. And on every ticker you can see exactly
      how much each of those six factors contributed to the score in front of
      you.</p>

      <p>Why be this open?</p>
      <ul>
        <li><strong>Trust compounds when you can audit.</strong> If you find a
        ticker scoring 90 when its trend is clearly broken, you can call it out
        — and we'd rather you do that than churn silently.</li>
        <li><strong>The moat isn't a secret list of factors, it's the data
        spine and the record.</strong> Plenty of competitors could name six
        factors too. None of them will publish a public scorecard back-checking
        every call against next-day prices the way we do.</li>
        <li><strong>If the score stops working, you should leave.</strong>
        We'd rather you make that call honestly than discover via a slow drip
        of bad picks.</li>
      </ul>

      <p>Any change to the factor set is versioned in our changelog. The day it
      changes, you see why. That's the whole product, in one paragraph.</p>
    `,
  },
  // ---- 2026-05-20: educational long-tail posts ----
  // Each post targets a high-volume "explain this concept" search query
  // that retail traders type into Google constantly. Internal links back to
  // /how-it-works, /scorecard, and the relevant /best-stocks-for/ slug so
  // the educational traffic warm-funnels into the product.
  {
    slug: "what-is-rsi",
    title: "What is RSI in stocks? A retail trader's plain-English guide (with examples).",
    metaTitle: "What is RSI in stocks? A plain-English guide",
    excerpt:
      "RSI stands for Relative Strength Index — a 0–100 momentum oscillator that signals overbought vs oversold conditions. Here's how it actually works, what the 70/30 thresholds mean, and the three mistakes retail traders make using it.",
    publishedAt: "2026-05-20",
    author: "Tapeline",
    body: `
      <p>RSI is one of those acronyms every trading YouTube channel mentions
      and almost no one explains properly. Here's the plain-English version:
      what it is, how it's computed, what the 70/30 thresholds mean, and the
      three mistakes retail traders make using it.</p>

      <h2>What RSI actually measures</h2>
      <p><strong>RSI = Relative Strength Index</strong>. It's a momentum
      oscillator that compares the magnitude of recent gains to the magnitude
      of recent losses over a lookback period (default: 14 trading days).
      The output is a 0–100 number, where:</p>
      <ul>
        <li><strong>RSI &gt; 70</strong> — traditionally read as "overbought".
        The stock has rallied hard and may be due for a pause or pullback.</li>
        <li><strong>RSI &lt; 30</strong> — traditionally read as "oversold".
        The stock has dropped hard and may be due for a bounce.</li>
        <li><strong>RSI 30–70</strong> — neutral zone. Most of the time RSI
        sits here and isn't telling you much on its own.</li>
      </ul>

      <h2>How RSI is computed</h2>
      <p>The formula is straightforward. Over the lookback window (14 days
      standard):</p>
      <pre>
RS = average gain / average loss
RSI = 100 - (100 / (1 + RS))</pre>
      <p>Average gain = sum of positive daily changes / 14. Average loss =
      sum of absolute negative daily changes / 14. The 100 / (1 + RS) part
      bounds the output to 0–100. The exact arithmetic doesn't matter for
      trading; the intuition does: <strong>RSI rises when up-days outweigh
      down-days, and falls when down-days outweigh up-days.</strong></p>

      <h2>The three mistakes retail traders make with RSI</h2>

      <h3>1. Trading the 70/30 cross mechanically</h3>
      <p>"RSI hit 70, time to short" is the most common — and the most
      reliably wrong — RSI rule. Strong uptrends ride RSI in the 70–90 range
      for weeks. Selling every time RSI crosses 70 means selling every
      strong rally early. Strong downtrends similarly camp out at RSI 20–30.
      Mechanical 70/30 trades work in choppy range-bound markets and lose
      in trending ones.</p>

      <h3>2. Ignoring the timeframe</h3>
      <p>RSI on a 1-minute chart is noise. RSI on a daily chart is signal.
      RSI on a weekly chart is a long-term sentiment gauge. Same number,
      wildly different meanings. Most retail traders look at RSI on whatever
      timeframe their chart happens to be open to, then trade as if the
      signal is universal. It isn't. Pick your timeframe deliberately.</p>

      <h3>3. Treating RSI as a standalone signal</h3>
      <p>RSI is most useful in confluence with other indicators — trend,
      relative strength vs the market, volume, fundamentals. Pure-RSI
      trading is gambling on mean reversion in a market that mostly
      trends. Reading RSI alongside a broader composite (like
      <a href="/how-it-works">Tapeline's six-factor score</a>) is a far more
      reliable filter than RSI on its own.</p>

      <h2>Where RSI sits relative to the Tapeline score</h2>
      <p>It doesn't feed it. RSI is not one of Tapeline's inputs. The
      <strong>Momentum</strong> factor — the lightest-weighted of the six —
      covers the same ground RSI reaches for, short-horizon rate of change,
      but it is built from its own inputs. What each factor reads is set out
      factor by factor on <a href="/how-it-works">how the score works</a>.</p>

      <p>The reason Momentum is the lightest factor — rather than one of the
      heavyweights — is exactly because short-horizon signals like RSI mean-revert
      so reliably. The composite balances it against
      <a href="/how-it-works">Trend, Relative Strength, Fundamentals,
      Smart Money, and Macro</a> so you're not betting your account on a
      single overbought reading.</p>

      <h2>Practical use cases</h2>
      <ul>
        <li><strong>Pullback entries</strong> — in a confirmed uptrend
        (price above 200DMA, rising RS line), an RSI dip into 35–45 is a
        higher-probability pullback entry than a random pullback to a
        chart level. Confluence with the bigger trend.</li>
        <li><strong>Exhaustion warning</strong> — RSI above 80 on the
        daily, sustained for multiple sessions, is a yellow flag that the
        rally is running on fumes. Doesn't mean short; means don't add.</li>
        <li><strong>Divergence</strong> — when price makes a new high but
        RSI makes a lower high (or vice versa), the underlying momentum
        isn't confirming the price action. Rare but high-quality when
        you spot it.</li>
      </ul>

      <h2>The bottom line</h2>
      <p>RSI is a useful tool — not a crystal ball. Treat the 70/30
      thresholds as warnings, not triggers. Pair RSI with trend and
      relative-strength context. Don't fight strong trends because RSI
      is "overbought" — that's how retail traders blow up.</p>

      <p>Want to see RSI in context for every US ticker? The Tapeline
      composite blends RSI into a single 0–100 score along with five other
      factors. <a href="/signup">Try the 14-day Premium trial</a> — a new
      account adds a card at first sign-in, $0 is charged that day, and one
      click cancels before the day-14 charge. If you'd rather not put a card
      down, the <a href="/scorecard">public record</a> and the daily Top 10
      stay open with no account.</p>
    `,
    howToTime: "PT8M",
    howToSteps: [
      {
        name: "Understand what RSI measures",
        text: "RSI compares the magnitude of recent gains to recent losses on a 0–100 scale over a 14-day window. Above 70 = 'overbought'. Below 30 = 'oversold'. 30–70 is neutral.",
      },
      {
        name: "Avoid trading the 70/30 cross mechanically",
        text: "Strong uptrends ride RSI in the 70–90 range for weeks. Selling every 70 cross means selling every rally early. Use 70/30 as warnings, not triggers.",
      },
      {
        name: "Pick your timeframe deliberately",
        text: "RSI on 1-minute charts is noise. RSI on daily charts is signal. Pick the timeframe that matches your holding period — they tell completely different stories.",
      },
      {
        name: "Combine RSI with trend and relative strength",
        text: "Pure-RSI trading bets on mean reversion in a market that mostly trends. Use RSI in confluence with trend, relative strength, volume, and fundamentals.",
      },
      {
        name: "Look for confluence at pullback entries and divergences",
        text: "In a confirmed uptrend, RSI dipping to 35–45 is a high-probability pullback entry. Watch for RSI/price divergence — rare but high-signal.",
      },
    ],
  },
  {
    slug: "how-to-find-momentum-stocks",
    title: "How to find momentum stocks (without buying every spike).",
    excerpt:
      "Momentum investing rewards stocks where price is sustainably accelerating up. The problem: pure 'biggest movers' lists are mostly noise. Here's how to filter for real momentum, including the three confluence checks that separate runners from head-fakes.",
    publishedAt: "2026-05-20",
    author: "Tapeline",
    body: `
      <p>Every retail trader wants to find momentum stocks early. The problem:
      pure "biggest movers today" lists are mostly noise — small-caps spiking
      on rumours, short squeezes that fail by tomorrow, news-pop reversals.
      Finding <em>real</em> momentum means filtering for stocks where the
      move is backed by trend, volume, and underlying fundamentals — not
      stocks where the move <em>is</em> the trade.</p>

      <p>This post is the practical playbook. Three confluence checks to
      apply to any momentum candidate before you take a position.</p>

      <h2>What "momentum" actually means</h2>
      <p>Academic finance defines momentum as the tendency of stocks that
      have outperformed over a 3–12 month window to continue outperforming
      over the next 1–3 months. Retail finance uses "momentum" more loosely
      — usually to mean "a stock that's moving up right now." Both are valid
      but they're not the same thing.</p>

      <p>For trading purposes, momentum is the combination of: <strong>price
      acceleration</strong> (the rate of price change is increasing),
      <strong>volume confirmation</strong> (more shares trading on up-days
      than down-days), and <strong>relative strength</strong> (the stock is
      outperforming its sector and the broader market). Without all three,
      what you have is a price spike, not momentum.</p>

      <h2>The three confluence checks</h2>

      <h3>1. Is the stock above its 200-day moving average?</h3>
      <p>Simple but devastating. Real momentum almost always happens in
      stocks already in established uptrends — meaning price is above the
      200-day moving average and the 200DMA itself is sloping up. A stock
      surging 15% in a day while still below its 200DMA is more often a
      dead-cat bounce than a momentum breakout. The 200DMA filter cuts the
      list by 60–70% and removes most of the false signals.</p>

      <h3>2. Is volume confirming the move?</h3>
      <p>Real momentum moves on above-average volume. A 5% up-day on 0.5×
      average volume is suspicious — somebody's chasing the price but the
      institutional flow isn't there. A 5% up-day on 2× average volume is
      structural — real demand is showing up. Always check the volume
      multiple (day's volume / 20-day average) before treating a price
      move as actionable. Below 1.2× is weak; above 1.5× is real.</p>

      <h3>3. Is the stock outperforming its sector AND the S&amp;P 500?</h3>
      <p>The relative-strength check. If the stock is up 10% but the sector
      ETF is also up 8%, what you have is sector beta — the stock isn't
      actually doing anything special, the whole sector is moving. Real
      momentum stocks show meaningful spread between the stock's return
      and the sector's return, AND between the sector's return and SPY's.
      That's leadership. Without it, you're just buying the sector at a
      slight markup.</p>

      <h2>The mistakes to avoid</h2>

      <h3>Buying after the gap</h3>
      <p>Most momentum trades fail because the trader sees the move, buys
      at the top of the daily range, and watches it mean-revert. The
      structural setup is identified the day <em>before</em> the spike —
      stocks already in uptrends with rising relative strength and
      accumulating volume, that haven't yet had their breakout day.
      Tapeline's composite is built to catch these <em>before</em> the
      spike, not after.</p>

      <h3>Ignoring fundamentals</h3>
      <p>Pure-momentum scans pick up junk stocks too. A $2 small-cap with
      no revenue spiking 80% on a press release isn't momentum — it's a
      pump. Real momentum tends to come with at least decent fundamentals
      (positive cash flow, manageable debt, sector tailwind). When a
      momentum scan and a fundamentals scan disagree, trust the
      fundamentals scan.</p>

      <h3>Treating every list the same</h3>
      <p>A "top 30 by 1-day move" list and a "top 30 by 1-month move" list
      are wildly different universes. Day-trading momentum lives in the
      1-day list. Swing-trading momentum lives in the 5-day to 1-month
      list. Long-term position momentum lives in the 3-month to 12-month
      list. Pick the timeframe that matches how long you intend to hold,
      then filter that specific list.</p>

      <h2>How Tapeline filters momentum</h2>
      <p>The Tapeline composite includes a Momentum factor — the
      lightest-weighted of the six — that captures price acceleration in a
      single 0–100 sub-score. But Momentum alone
      isn't enough — the composite leans far more on Trend,
      Relative Strength, and Fundamentals precisely because
      pure-momentum signals mean-revert.</p>

      <p>The pre-filtered momentum lists are at
      <a href="/best-stocks-for/momentum">/best-stocks-for/momentum</a>
      (5-day move + composite 60+),
      <a href="/best-stocks-for/breakouts">/best-stocks-for/breakouts</a>
      (1-day move + composite 70+), and
      <a href="/best-stocks-for/growth-stocks">/best-stocks-for/growth-stocks</a>
      (1-month move + composite 65+). Same universe, different timeframes.
      Pick the one that matches your holding period.</p>

      <h2>The bottom line</h2>
      <p>Finding momentum stocks is easy. Finding the momentum stocks
      that <em>continue</em> is hard — and is mostly about filtering out
      the head-fakes. Confluence is the answer: above 200DMA, volume
      confirming, beating sector + SPY, supportive fundamentals. Any one
      of those is necessary but not sufficient. All four together is the
      pattern.</p>
    `,
    howToTime: "PT10M",
    howToSteps: [
      {
        name: "Filter to stocks above their 200-day moving average",
        text: "Real momentum almost always happens in established uptrends. Stocks below their 200DMA are dead-cat bounces more often than breakouts. This single filter cuts 60–70% of false signals.",
      },
      {
        name: "Confirm with above-average volume",
        text: "Calculate volume multiple (today's volume / 20-day average). Below 1.2× is weak; above 1.5× is structural demand. Pure price spikes on light volume are head-fakes.",
      },
      {
        name: "Check relative strength vs sector AND SPY",
        text: "Real momentum stocks outperform their sector AND the broader market. If the stock is up 10% but the sector ETF is also up 8%, what you have is sector beta, not stock leadership.",
      },
      {
        name: "Identify the setup the day before the spike",
        text: "Most momentum trades fail because traders chase the gap. The structural setup — rising RS, accumulating volume, still-tight range — is visible BEFORE the breakout day. Find it then.",
      },
      {
        name: "Match the scan timeframe to your holding period",
        text: "Day-trading momentum lives in the 1-day list. Swing-trading momentum lives in 5-day to 1-month. Position momentum lives in 3–12 month. Mismatching scan to holding period guarantees losses.",
      },
    ],
  },
  {
    slug: "best-time-to-buy-stocks",
    title: "What's the best time to buy stocks? The data answer (it's not what you'd think).",
    metaTitle: "What's the best time to buy stocks? The data answer",
    excerpt:
      "Retail trading folklore says 'buy at the open', 'wait until the last hour', or 'never on Mondays'. We pulled the data on intraday + day-of-week + month-of-year patterns. Here's what actually holds up — and what's just superstition.",
    publishedAt: "2026-05-20",
    author: "Tapeline",
    body: `
      <p>Every retail trader has heard them: "Mondays are bearish." "Buy at
      the open, sell at the close." "Avoid trading the first 30 minutes."
      "Tax-loss season hits the market in November." A lot of this is
      folklore that survived because it sounds plausible. Some of it is
      real, with explanations rooted in market structure.</p>

      <p>Here's what actually holds up under data scrutiny — for the
      retail trader making decisions about <em>when</em> to enter a
      position, not just which one.</p>

      <h2>Day-of-week effects</h2>

      <h3>The Monday Effect (mostly gone)</h3>
      <p>Decades of academic studies documented a "Monday effect" —
      historical underperformance of Mondays vs Tuesday–Friday. The
      explanation was bad news being held until weekends + Sunday-night
      hand-wringing pricing in by Monday open. Most studies after 2010
      find the effect has faded substantially — possibly because
      24/7 financial news + extended-hours trading prices weekend news
      in faster. Mondays still skew slightly negative on average but the
      edge is too small to trade on its own.</p>

      <h3>The Friday-into-Monday rollover</h3>
      <p>One pattern that <em>has</em> held up: Friday afternoons see
      reduced institutional positioning ahead of the weekend, which can
      produce thin liquidity and outsized moves on relatively normal
      news. If you're entering a position late Friday, expect more noise
      than usual. If you're holding through weekend, expect a Monday gap
      either direction.</p>

      <h2>Intraday timing</h2>

      <h3>The first 30 minutes</h3>
      <p>The market open (9:30–10:00 ET) is the most volatile window of
      the trading day. Spreads are wider, prices gap on overnight news,
      retail order flow is concentrated. For most retail traders, the
      first 30 minutes is the worst time to enter — you're trading
      against algos optimised for that exact window. Wait until 10:00 ET
      and the picture stabilises substantially.</p>

      <h3>The midday lull</h3>
      <p>11:30 ET to roughly 14:00 ET is the lowest-volume window of the
      US session — institutional desks are at lunch, news flow slows.
      Prices drift, ranges compress. For swing traders, this is a fine
      window to enter at a confirmed setup. For day traders, this is
      often a time to do nothing.</p>

      <h3>The close</h3>
      <p>The last 30 minutes (15:30–16:00 ET) sees a return of volume
      and volatility as end-of-day flows hit: closing auctions, MOC
      orders, index rebalancing. The closing print sets the official
      record for the day's price. If you're entering on a confirmed
      breakout, the last hour is often a stronger entry than the
      midday range because volume confirms the move.</p>

      <h2>Month and quarter effects</h2>

      <h3>The January Effect</h3>
      <p>Small-caps have historically outperformed in January, possibly
      because of December tax-loss selling reversing + new-year fund
      allocations. The effect has weakened over the last 20 years but
      isn't dead. Small-cap-heavy strategies have a mild structural
      tailwind in early January.</p>

      <h3>Sell in May and go away</h3>
      <p>This one is half-real. The May–October window has, on average,
      lower returns than the November–April window over the last century.
      But "lower" doesn't mean "negative" — May–October has been
      positive on average. The trade isn't "sell in May" so much as "be
      a bit more selective about new positions in the summer months."</p>

      <h3>Earnings seasons</h3>
      <p>Mid-January, mid-April, mid-July, mid-October — earnings
      announcements concentrate. Implied volatility rises across the
      board. Individual stocks gap on earnings beats and misses. If
      you're trading individual names, knowing which weeks are dense
      with reports for your holdings matters more than any seasonal
      calendar effect. Tapeline's earnings calendar at
      <a href="/app/earnings">/app/earnings</a> filters to the names
      you actually care about.</p>

      <h2>The honest answer</h2>
      <p>The best time to buy a stock is when the setup is right, not
      when the calendar says so. Day-of-week effects are weak and
      mostly arbitraged away. Intraday timing matters more — avoid
      the first 30 minutes, use the close window for confirmed
      breakouts, treat the midday lull as a research window. Month
      effects are real but small.</p>

      <p>The bigger question — "is this stock setting up?" — matters
      far more than "what time of day is it?" The Tapeline composite
      is built to answer the first question. The second question
      mostly takes care of itself once the first one is settled.</p>

      <p><a href="/signup">Try the 14-day Premium trial</a> — a new account
      adds a card at first sign-in, $0 charged today, first charge on day 14,
      cancel in one click before then. Read
      every score the same way our public scorecard does.</p>
    `,
    howToTime: "PT7M",
    howToSteps: [
      {
        name: "Avoid the first 30 minutes of the session",
        text: "The 9:30–10:00 ET window is the most volatile of the day. Spreads are wide, gaps are common, retail order flow runs into algos. Wait until 10:00 ET for stable prices.",
      },
      {
        name: "Use the midday lull as research time, not entry time",
        text: "11:30–14:00 ET is the lowest-volume window. Day traders should do nothing; swing traders can use confirmed setups but expect tight ranges.",
      },
      {
        name: "Treat the close window (15:30–16:00 ET) as a stronger entry for confirmed breakouts",
        text: "End-of-day flows confirm the move with real volume. If the setup held all day and is closing on its highs, the last 30 minutes is often a higher-quality entry than midday.",
      },
      {
        name: "Be selective about Friday afternoon and Monday gap entries",
        text: "Friday afternoons see thin institutional liquidity ahead of the weekend. Monday gaps can move either way on weekend news. Expect more noise than usual at both ends.",
      },
      {
        name: "Use the calendar effects as tiebreakers, not triggers",
        text: "Small-caps have a mild January tailwind. May–October is slightly weaker than November–April. These edges are real but small — let the setup decide, not the date.",
      },
      {
        name: "Track earnings weeks for your specific watchlist",
        text: "Mid-January, April, July, October. Implied volatility rises across the board. Knowing which weeks your holdings report matters more than any seasonal calendar effect.",
      },
    ],
  },
  {
    slug: "best-stock-scanner-under-30",
    title: "Best stock scanner under $30/month in 2026 (honest cost-quality breakdown).",
    metaTitle: "Best stock scanner under $30/month in 2026",
    excerpt:
      "We benchmarked the four sub-$30/mo stock scanners retail traders actually consider in 2026 — Finviz Elite, Stock Rover Essentials, Zacks Premium, and Tapeline Pro — across feature depth, data freshness, and (the part nobody else publishes) whether the picks beat SPY. Here's the honest matrix.",
    publishedAt: "2026-05-20",
    author: "Tapeline",
    body: `
      <p>Most "best stock scanner under $30" articles you find online
      are affiliate-fee farms. The author gets paid per signup, every
      product gets a 9/10 review, and the conclusion is always "they're
      all great, pick what suits you." If you've read more than two of
      them, you know the type.</p>

      <p>This isn't that. Tapeline is one of the four scanners in this
      matrix and we're not going to pretend otherwise — but the
      comparison is structured so you can rule us out cleanly if we
      don't fit. The criteria are public, the rankings are explicit,
      and the rows where we lose are highlighted, not hidden.</p>

      <h2>The four scanners under $30/mo retail traders actually buy</h2>

      <p>"Under $30/mo" rules out the institutional tier — Bloomberg
      Terminal ($24K/yr), Koyfin Plus ($59/mo), Trade Ideas Premium
      ($188/mo), Benzinga Pro ($177/mo). Those are tools built for
      sell-side and prop-desk users; if you're a retail trader running
      one or two accounts, they're not realistic. The actual sub-$30/mo
      shortlist in 2026:</p>

      <ul>
        <li><strong>Finviz Elite</strong> — $24.96/mo annual ($29.96/mo
        monthly). The veteran. Maps + heatmaps + 70+ screener filters.
        Free tier is the entry point most retail traders started with.</li>
        <li><strong>Stock Rover Essentials</strong> — $7.99/mo annual
        ($9.99/mo monthly). Long-only fundamentals focus. Strong
        portfolio analytics, weaker on intraday data.</li>
        <li><strong>Zacks Premium</strong> — $20.83/mo annual ($24.95/mo
        monthly). Earnings + analyst-rating focus. The Zacks Rank is the
        core differentiator; everything else is supporting.</li>
        <li><strong>Tapeline Pro</strong> — $8.25/mo annual ($9.99/mo
        monthly). One 0-100 composite per ticker from a
        <a href="/how-it-works">published six-factor methodology</a>, with a
        public daily back-checked scorecard.</li>
      </ul>

      <h2>The matrix (data current as of 2026-05-21)</h2>

      <p>I've split the comparison into four axes that actually matter
      to the retail trader spending $25/mo on a scanner: feature depth,
      data freshness, transparency of the methodology, and — the one
      nobody else publishes — whether the daily picks actually beat
      SPY.</p>

      <h3>1. Feature depth</h3>

      <p><strong>Finviz Elite</strong> wins on raw filter count — 70+
      screening criteria, real-time data, advanced charting, custom
      groups. If you're the type who wants to express a thesis as a
      seven-condition AND-filter, it's hard to beat.</p>

      <p><strong>Stock Rover</strong> wins on fundamentals depth —
      150+ fundamental metrics, multi-year history, portfolio tracking
      with allocation drift alerts. Built for the long-only quality
      investor.</p>

      <p><strong>Zacks</strong> wins on earnings + analyst ratings —
      the Zacks Rank is the original "stock signal" and still the
      reference for that style of scoring. Earnings ESP, broker rating
      changes, and surprise history are deeper than competitors.</p>

      <p><strong>Tapeline Pro</strong> ranks lower on raw filter
      breadth (we don't try to expose 70 filters), higher on signal
      density — the composite score does the synthesis work that
      filter-by-filter screening makes the user do manually. Different
      product philosophy, not necessarily a better one for everyone.</p>

      <h3>2. Data freshness</h3>

      <p>This one's measurable. We checked the actual delay on each
      product's free tier:</p>

      <ul>
        <li>Finviz free: 15-minute delay. Elite: real-time.</li>
        <li>Stock Rover free: end-of-day. Essentials: 15-minute delay.</li>
        <li>Zacks free: 20-minute delay. Premium: real-time on most exchanges.</li>
        <li>Tapeline free: live scores (no delay) on the top 10 scanner rows;
        full ~2,500-ticker universe at ~60-second freshness on Pro+.</li>
      </ul>

      <p>Tapeline gates on breadth rather than freshness — Free is live, just
      narrower (top 10 rows, 12 look-ups a day, unmetered for the first 24 hours),
      and Pro opens the full real-time
      universe. If you're testing the product, the
      <a href="/scorecard">public scorecard</a> shows the real
      composite quality at full freshness.</p>

      <h3>3. Methodology transparency</h3>

      <p>This is the criterion most retail-trader comparisons skip
      entirely. "How is the score calculated?" is a question every
      product answers with marketing copy ("proprietary algorithm",
      "decades of research"). The actual formula is rarely published.</p>

      <ul>
        <li><strong>Finviz</strong>: no composite score. Filters only.
        N/A.</li>
        <li><strong>Stock Rover</strong>: "Score" and "Growth Score"
        published as relative-to-universe percentile rankings; weights
        not disclosed.</li>
        <li><strong>Zacks</strong>: The Zacks Rank methodology is
        published at high level (earnings ESP + earnings surprise +
        broker rating changes) but the exact weights are proprietary.</li>
        <li><strong>Tapeline</strong>: All six factors named at
        <a href="/how-it-works">/how-it-works</a>, with the weighting ordered
        publicly (most on Trend and Relative Strength, least on Momentum) and
        each factor's contribution shown per ticker. Any change to the factor
        set is announced in the changelog before it ships.</li>
      </ul>

      <h3>4. Does it beat SPY?</h3>

      <p>This is the question that should drive the buy decision and
      the one nobody answers honestly. The reason: most product owners
      don't actually track it. The "back-tested results" in marketing
      materials are usually one-time historical simulations, not live
      forward-tracked records.</p>

      <p>Of the four, Tapeline is the only one that publishes a
      permanent, append-only daily log of every top-10 pick with
      next-day return vs SPY at
      <a href="/scorecard">tapeline.io/scorecard</a>. The losers stay
      on the page. The hit rate, median alpha, and best/worst days
      update automatically.</p>

      <p>Stock Rover and Zacks both publish historical performance for
      their internal ranks (Stock Rover's Premier list, Zacks #1
      Strong Buy), but those use proprietary universe-construction
      rules that aren't easy to verify externally. Finviz doesn't
      claim a stock-picking record at all — it's a tool, not a
      signal.</p>

      <h2>When to pick which</h2>

      <ul>
        <li><strong>Pick Finviz Elite</strong> if you have a specific
        thesis to express as a filter and want raw breadth (the most
        screens, the most filters).</li>
        <li><strong>Pick Stock Rover Essentials</strong> if you're a
        long-only quality investor with portfolio analytics needs and
        don't trade intraday.</li>
        <li><strong>Pick Zacks Premium</strong> if you trade earnings
        events and want the deepest analyst-rating + earnings-surprise
        data set.</li>
        <li><strong>Pick Tapeline Pro</strong> if you want one
        synthesised read on every US ticker, six named factors
        you can argue with, and a live track record you can audit
        before you trust it.</li>
      </ul>

      <h2>The honest pitch for Tapeline</h2>

      <p>I'm not going to tell you Tapeline replaces Finviz's filter
      breadth, because it doesn't. I'm not going to tell you it has
      Stock Rover's portfolio analytics, because it doesn't. What it
      does have is one read per ticker built from six named factors you
      can argue with one by one, and a public daily record of whether that
      score's top-10 picks actually beat SPY.</p>

      <p>If that's the criterion that should drive the buy decision —
      and we'd argue it should — then the
      <a href="/scorecard">scorecard</a> is the test. Read it. If the
      numbers don't hold up, we're not the right product for you. If
      they do, the
      <a href="/signup?utm_source=blog&utm_medium=post&utm_campaign=best_scanner_under_30">14-day
      Premium trial</a> is the way to see it from the inside — a card, $0
      charged today, and one click to cancel before the day-14 charge.</p>
    `,
  },
  {
    slug: "how-to-read-sec-form-4",
    title: "How to read SEC Form 4 insider buying (and what's actually a signal).",
    metaTitle: "How to read SEC Form 4 insider buying",
    excerpt:
      "SEC Form 4 — the filing every corporate insider must submit within 2 business days of a trade — is the rawest 'smart money' signal retail traders can access. But 90% of Form 4 activity is noise. Here's how to filter for the 10% that matters, and how Tapeline's Smart Money sub-score does it automatically.",
    publishedAt: "2026-05-20",
    author: "Tapeline",
    body: `
      <p>If you've ever read a finance Twitter thread that ends with
      "the insider just bought 50,000 shares" and felt vaguely
      compelled to investigate further, you've encountered SEC Form 4.
      It's the filing every corporate insider — directors, officers,
      anyone with 10%+ ownership — must submit to the SEC within 2
      business days of any trade in the company's stock. It's been
      mandatory since 1934. The signal is real. The noise around it is
      what kills retail traders.</p>

      <p>This post is the field guide: what Form 4 actually contains,
      which 90% of filings to ignore, and what the remaining 10%
      reliably predicts. Tapeline's Smart Money sub-score — one of the six
      named factors in the composite
      (<a href="/how-it-works">see the methodology</a>) — does
      this filtering automatically, but the underlying logic is worth
      understanding regardless of what tool you use.</p>

      <h2>What Form 4 actually is</h2>

      <p>A Form 4 filing has six things you care about:</p>

      <ol>
        <li><strong>The insider's name and role</strong> — CEO, CFO,
        director, 10%+ owner. Role matters; we'll get to why.</li>
        <li><strong>Transaction code</strong> — a one-letter code from
        a fixed table. The ones that matter for "is this a signal":
        <code>P</code> (open-market purchase), <code>S</code>
        (open-market sale), <code>A</code> (grant — almost never
        meaningful), <code>F</code> (tax-withholding sale — almost
        never meaningful).</li>
        <li><strong>Number of shares</strong> — raw count, not dollar
        amount. You compute the $ from price.</li>
        <li><strong>Price per share</strong> — the executed price.</li>
        <li><strong>Date of trade</strong> — not the filing date. The
        filing window is 2 business days, so the trade is up to 48
        hours older than the filing.</li>
        <li><strong>Shares held after transaction</strong> — total
        post-trade. This is the field most retail traders ignore and
        the one that determines whether the trade is a signal or
        noise.</li>
      </ol>

      <h2>The 90% that's noise — what to ignore</h2>

      <h3>1. Anything that isn't transaction code P or S</h3>

      <p>Form 4 has 30+ transaction codes. Most of them — grants,
      vestings, exercises, gifts, withholdings — are not voluntary
      market activity. An insider getting shares via an automatic
      restricted-stock vesting tells you nothing about their view of
      the company's valuation. They didn't choose to acquire the
      shares; the comp plan did. Filter to code P (open-market buy)
      and code S (open-market sale) only. Everything else is HR
      paperwork dressed as a filing.</p>

      <h3>2. 10b5-1 sales</h3>

      <p>10b5-1 plans are pre-arranged trading schedules executives
      use to sell stock systematically without being accused of
      insider trading. A CFO who set up a 10b5-1 plan in March 2025
      that triggers a sale of 10,000 shares every quarter is selling
      mechanically — it's not their reaction to current information.
      These show up as code S sales but are explicitly marked
      "pursuant to 10b5-1 plan" in footnotes. Filter them out;
      they're noise.</p>

      <h3>3. Tiny purchases relative to ownership</h3>

      <p>A board member who already owns 500,000 shares buying 100
      more is not a signal. They're rounding error in their own
      portfolio. The relevant ratio is <em>shares purchased ÷ shares
      held after</em>. Anything under 1-2% is meaningless.</p>

      <h3>4. Director purchases at companies with mandatory
      share-ownership requirements</h3>

      <p>Many large companies require directors to own at least N×
      their annual cash retainer in stock. When a newly-appointed
      director makes a small open-market purchase, they're often just
      complying with the requirement — not expressing a view on
      valuation. The clue: it's their first purchase, it's small, and
      it happens within 90 days of board appointment.</p>

      <h2>The 10% that matters — what's actually a signal</h2>

      <h3>1. Cluster buying</h3>

      <p>The single highest-information Form 4 pattern. Multiple
      different insiders — usually CEO + CFO + at least one director
      — all making open-market purchases (code P) within a tight
      time window (say 30 days), at meaningful sizes (1%+ of their
      existing holdings each). This is hard to fake and hard to
      explain via comp-plan mechanics. When you see it, the people
      closest to the company's actual numbers have collectively
      decided the stock is mispriced low.</p>

      <h3>2. CEO purchases at a meaningful percentage of net worth</h3>

      <p>If the CEO buys $1M of stock and their compensation suggests
      a net worth in the $50M range, that's 2% of their net worth in
      one position. That's a real bet. Cross-check via the proxy
      statement (DEF 14A) for total compensation history.</p>

      <h3>3. CFO buying when others are selling</h3>

      <p>The CFO has the cleanest, earliest view of the company's
      actual financials — quarterly closing, working-capital trends,
      cash-flow forecast. When a CFO buys against a sector tape that
      has other peers selling, it's an unusually strong dissenting
      signal.</p>

      <h3>4. First-time purchases at companies that haven't seen
      insider buying for 12+ months</h3>

      <p>Companies in steady-state mode often see zero insider
      open-market activity for stretches. When that dry spell breaks
      with a meaningful purchase, something has changed in management's
      view. Pull the most-recent 4-5 Form 4s and check the gap.</p>

      <h2>How Tapeline scores this automatically</h2>

      <p>Tapeline's Smart Money sub-score — one of the six named factors in the
      <a href="/how-it-works">composite</a> — nets the disclosed
      Form 4 purchases and sales in a recent rolling window by their signed
      dollar value, and maps that balance onto a 0-100 scale. What it reads,
      and the statutory lags it inherits, are set out on
      <a href="/how-it-works/smart-money">the Smart Money factor page</a>.</p>

      <p>The result is a 0-100 sub-score that lands in the composite.
      Recent insider buys are also displayed on Tapeline Premium at
      <a href="/app/holdings">/app/holdings</a> — Form 4
      data per ticker, sorted by date. Read alongside the composite score,
      not in place of it.</p>

      <h2>Where the signal breaks down</h2>

      <p>Three honest caveats:</p>

      <ul>
        <li><strong>2-day filing lag</strong>. By the time you see the
        Form 4, the insider's trade is up to 48 hours old. The market
        often already moved.</li>
        <li><strong>Selling is less informative than buying</strong>.
        Insiders sell for personal reasons (diversification, house
        purchase, divorce) that aren't tied to their view of the
        company. Buying is almost always a directional view; selling
        is mixed.</li>
        <li><strong>Small-cap signal-to-noise is worse than
        large-cap</strong>. Microcap insiders trade more frequently
        for personal-liquidity reasons. The cluster filter helps but
        doesn't eliminate the noise.</li>
      </ul>

      <h2>The pitch</h2>

      <p>Form 4 is one of the few real edges retail traders have
      access to — the raw data is public, the filing is mandatory,
      and most retail traders don't read it. The hard part isn't
      access; it's filtering. Tapeline Premium does the filtering
      and surfaces it as both (1) a sub-score in the composite and
      (2) raw filtered transactions at /app/holdings.</p>

      <p><a href="/signup?utm_source=blog&utm_medium=post&utm_campaign=form_4_insider_buying">14-day
      Premium trial — $0 today</a>. Read 90 days of filtered Form 4
      activity across the full universe. The trial takes a card; the first
      charge is on day 14 and one click cancels before then.</p>
    `,
  },
  {
    slug: "how-to-evaluate-a-stock-scanner-track-record",
    title: "How to evaluate a stock scanner you can actually trust (5 criteria most fail).",
    metaTitle: "How to evaluate a stock scanner you can trust",
    excerpt:
      "Every stock scanner claims to beat the market. Almost none publish a daily, append-only, back-checked track record you can audit. Here are the five tests we'd put any scanner through before paying — and how to read between the lines when the answers get vague.",
    publishedAt: "2026-05-21",
    author: "Tapeline",
    body: `
      <p>Choosing a stock scanner is mostly an exercise in detecting
      what isn't said. Every product claims to "beat the market" or
      "outperform" or "deliver signals." Almost none publish the data
      that would let you verify those claims. The asymmetry is the
      whole story: the products with real records publish them
      prominently; the products without real records hide behind
      proprietary algorithms and selected case studies.</p>

      <p>This post is the buyer's checklist — five tests we'd put any
      scanner through, with the questions to ask and what each answer
      tells you. Tapeline is one of the products you might evaluate
      with these criteria; we score ourselves at the end so you can
      compare us against the same yardstick we'd apply to a
      competitor.</p>

      <h2>Test 1: Can you see every pick, including the losers?</h2>

      <p>This is the single most important test and the one most
      products fail. "Picks of the day" or "today's recommendations"
      are easy to publish; what's hard is publishing every pick that
      was wrong, with the same prominence, on the same page, with the
      original score and signal still attached.</p>

      <p>The right answer looks like: <em>"Yes, every top-10 daily
      pick we've ever published is logged at this URL, sorted by
      date, with the next-day return and the original score visible.
      The page is append-only — we can't go back and edit it. You can
      see every win and every miss."</em></p>

      <p>The wrong answer looks like: <em>"Our algorithm has a 67%
      win rate based on internal testing"</em> with no link to the
      raw record. That's a marketing claim, not a verifiable
      statement.</p>

      <p>Test it: ask for the URL of the daily picks log. If they
      hesitate, you have your answer.</p>

      <h2>Test 2: Is the benchmark named?</h2>

      <p>"Outperforms the market" is a meaningless claim without a
      named benchmark. Outperforms which market? The S&amp;P 500?
      Russell 2000? Equal-weighted universe? Sector ETF? The choice
      of benchmark changes the answer by 5-10 percentage points
      annually.</p>

      <p>Real answer: <em>"Picks are back-checked against SPY (S&amp;P
      500 ETF) on a same-day, next-trading-day basis. Alpha is the
      pick's 1-day return minus SPY's same-day return."</em></p>

      <p>Vague answer: <em>"Outperforms the broader market"</em> with
      no specific index named.</p>

      <p>Tapeline's choice: SPY same-day-pick to next-trading-day-close
      vs SPY same window. Documented at
      <a href="/scorecard">/scorecard</a>.</p>

      <h2>Test 3: Is the scoring methodology published?</h2>

      <p>This is the test most products fail through omission rather
      than misdirection. They simply don't disclose the formula at
      all. "Proprietary algorithm developed over X years" is the
      standard formulation.</p>

      <p>The right answer names the inputs and is honest about how they're
      weighted. Tapeline's example: six named factors — Trend, Relative
      Strength, Fundamentals, Smart Money, Macro, and Momentum — weighted most
      toward Trend and Relative Strength and least toward Momentum, blended into
      a 0-100 composite, with each factor's contribution shown on every ticker.
      The factors and data sources are documented at
      <a href="/how-it-works">/how-it-works</a>.</p>

      <p>What this enables: if the product underperforms in a
      particular regime, you can look at the score breakdown and see
      <em>which factor is dragging</em>. You can disagree with the
      weights and reason about that disagreement. With a black box,
      you can't do any of that — you can only stop using it.</p>

      <h2>Test 4: How fresh is the data?</h2>

      <p>"Real-time" means different things at different price tiers.
      On a free tier, "real-time" often means 15-minute delayed,
      because that's the IEX exchange delay limit on free
      consolidated feeds. On a paid tier, "real-time" usually means
      direct exchange data with sub-second latency.</p>

      <p>Test it by checking the timestamp on a single quote. If
      it's behind the broker quote you'd see at your trading
      platform, you have your answer.</p>

      <p>For composite scanners (like Tapeline), the question is
      slightly different: how often does the SCORE refresh, not just
      the underlying price? Tapeline's worker ticks every 60 seconds
      during market hours, recomputing the composite from fresh
      snapshot data — and the public ticker pages show that live score
      without an account.</p>

      <h2>Test 5: What's the unsubscribe / cancel friction?</h2>

      <p>This is the dirtiest test, but the most diagnostic. Products
      that are confident in their value make it trivial to leave.
      Products that depend on dark-pattern retention make it hard.</p>

      <p>Check before you sign up:</p>

      <ul>
        <li>Can you cancel from a settings page in one click, or do
        you need to email support and wait?</li>
        <li>Is the trial auto-converting? Do you have to add a credit
        card?</li>
        <li>What's the refund window?</li>
      </ul>

      <p>Tapeline's policy: the trial takes a card at first sign-in and
      charges $0 until day 14, cancel from /app/billing in one click,
      30-day refund window on monthly subscriptions. The published
      record — daily Top 10, scorecard, per-ticker pages, raw CSV/JSON —
      needs no account or card at all. We'd rather lose subscribers
      cleanly than retain them via friction.</p>

      <h2>How Tapeline scores against the checklist</h2>

      <table>
        <thead>
          <tr><th>Test</th><th>Tapeline</th></tr>
        </thead>
        <tbody>
          <tr><td>Public daily picks log with losers visible</td>
              <td>Yes — <a href="/scorecard">/scorecard</a></td></tr>
          <tr><td>Named benchmark</td><td>SPY, same-day-pick to next-trading-day-close</td></tr>
          <tr><td>Public scoring methodology</td>
              <td>Yes — six named factors at <a href="/how-it-works">/how-it-works</a>, contribution shown per ticker</td></tr>
          <tr><td>Data freshness</td>
              <td>60s composite refresh; the public ticker pages show the same live score with no account</td></tr>
          <tr><td>Cancel friction</td>
              <td>One-click cancel, 30-day refund. The trial takes a card at first sign-in and charges $0 until day 14; the published record needs no account at all</td></tr>
        </tbody>
      </table>

      <h2>What this checklist does NOT test</h2>

      <p>To be honest: none of these criteria tell you whether the
      product will work for YOUR specific trading style. You might
      need filter breadth Tapeline doesn't have. You might need
      international coverage we don't offer (US-only for now). You
      might prefer the analyst-rating focus Zacks does better than
      anyone. The checklist tells you whether the product is
      <em>honest about what it does</em>, not whether what it does
      matches your needs.</p>

      <p>The two questions you need to answer separately:</p>

      <ol>
        <li>Does this product publish enough evidence for me to
        verify their claims? (Checklist above.)</li>
        <li>Does the thing they're publishing evidence FOR match what
        I actually want to do? (Read the product page + try the free
        tier + read the scorecard.)</li>
      </ol>

      <p>Tapeline's pitch: we'd rather lose your business to a
      product that fits you better than win it via misleading
      claims. If the scorecard convinces you, the
      <a href="/signup?utm_source=blog&utm_medium=post&utm_campaign=evaluate_scanner">14-day
      Premium trial</a> is the way to see the rest — a new account adds a card
      at first sign-in, $0 is charged today, and one click cancels before the
      day-14 charge. If it doesn't, that's useful
      information too.</p>
    `,
  },
];

export function findPost(slug: string): BlogPost | null {
  return POSTS.find((p) => p.slug === slug) ?? null;
}
