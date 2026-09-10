# Video creative + Meta Ad Library review — September 2026

Three ad videos and six stills, plus what the competition is actually running.

## Why video at all

Tapeline had none. The August burst shipped nine text-card PNGs
(`docs/ads/meta-burst-2026-08/`) and nothing that moves. A sweep of the Meta Ad
Library on 2026-09-08 (US, active ads, keyword `stock screener` and
`stock scanner`) found video on most of the direct competitors:

| Advertiser | Format | Length | Mechanism |
|---|---|---|---|
| CoverEdge.io | video | 1:15 | long problem-first narrative, names a specific workflow that breaks |
| U.S. Daily Stock Alerts | video | 0:43 | pure FOMO — *"3 weeks from now, you'll probably wish you grabbed these stocks"* |
| StockCharts.com | video + static | 0:12 | feature checklist, "New Tool Alert", 30-day trial offer |
| Wheel Strategy Options | 7-card carousel | — | one benefit per card + a Trustpilot card |
| investors.atlas | static ×5 | — | teaches a concept, sells nothing in the copy |
| FITools.com | static | — | describes the manual process the tool replaces |
| Momentum. | static | — | 8-item feature list, seven-day trial framing |
| Day Trading Strategies | static | — | free lite scanner as the lead magnet |

## What the sweep actually teaches

**1. The hypey lane is crowded and closed to us.** "Real-Time Buy & Sell
Alerts", "Executives just loaded up on their own stock", "spot the morning
breakout before the crowd" — this is the dominant register, and every one of
those phrases is prescriptive. Under the publisher-exemption posture Tapeline
cannot write any of it (`docs/COMPLIANCE_COPY_RULES.md`). Competing on that axis
is not an option, so stop treating it as the benchmark.

**2. The calm lane is real and thinly occupied.** investors.atlas and FITools
both run ads that explain something and never issue an instruction. That is the
same register Tapeline is legally confined to — which means the constraint is
also the differentiator, and there is proof other advertisers sustain spend
there.

**3. Nobody shows the product.** Across the sweep, not one ad shows a calm,
specific product moment — a real screen with a real number on it. They show
logos, stock photography, feature lists and talking heads. Tapeline's ticker
page is genuinely distinctive-looking, and it was not appearing in any ad.

**4. Everyone leads with the trial, nobody with the money question.** Verbatim,
from four different advertisers in the sweep:

<!-- copy-compliance-allow * -- quoting competitors' live ad copy as evidence of the register Tapeline must NOT use; these are their words, never ours -->
> "FREE FOR 7 DAYS" · "Risk Free Trial" · "30-day FREE trial" · "no credit card required."

The one Tapeline concept that has ever produced a card (Concept B, 2 of 3
signups) does the opposite: it names what this will cost and when, before the
click. That remains the differentiated angle and it is what these videos are
built on.

## What is here

| File | Ratio | Use |
|---|---|---|
| `tapeline-9x16.mp4` | 1080×1920 | Reels, Stories |
| `tapeline-4x5.mp4` | 1080×1350 | feed (tallest allowed) |
| `tapeline-1x1.mp4` | 1080×1080 | feed, square placements |
| `stills/4x5/*.png` | 1080×1350 | each scene also stands alone as a static ad |

18.03s, h264 / yuv420p, 30fps, `+faststart` — within Meta's spec for all
placements. Six scenes: hook → turn → **real product frame** → the plain-sentence
promise → the money question → CTA to the record.

Regenerate everything with `node build.mjs` (needs `ffmpeg-static` and Chrome).
9:16 and 1:1 stills are not committed because the script reproduces them.

## Two things the build does on purpose

**Constants are read, never typed.** `build.mjs` parses `TRIAL_DAYS` out of
`frontend/lib/trial.ts` and the Premium prices out of `frontend/lib/pricing.ts`
at render time. This is not tidiness: the trial moved 14 → 30 days on
2026-09-05 (#737) and a live ad kept saying 14, because the creative had the
number baked in. A build that reads the source cannot drift.

**The disclosure sits inside the safe zone.** The first pass pinned it to the
bottom of the 1920px canvas, where Instagram's caption, profile row and CTA
button cover it — legally required text that no viewer would ever see. It is now
anchored above the reserved bottom 690px, and the stage is shortened so copy can
never overlap it.

Copy passes the strict ad ruleset:

```
node scripts/lint-copy-compliance.mjs --ads docs/ads/2026-09-video/README.md
```

## What this does not solve

The August burst's problem was never the creative. CTR was 2.37%, landing→signup
21%, signup→card 67% — the funnel after the click worked. The problem was a CPM
around A$103, three to ten times normal. Better creative can lift CTR; it does
not fix impression cost.

And the harder fact underneath: of 35 accounts, four have ever run a scan, and
both live trials have run zero. New creative buys more signups of the kind that
do not activate. Worth running only alongside something that makes an account
worth keeping.
