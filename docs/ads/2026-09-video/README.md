# Video creative + Meta Ad Library review — September 2026

> **Current files (2026-09-14): `voiceover/` and `voiceover-15s/` only, each video with its
> `.en_US.srt`. Ad text: `meta-copy-2026-09.md`.** Everything else in this folder is
> superseded and must not be uploaded. See
> [Update 2026-09-14](#update-2026-09-14--concept-e-rewritten-15-s-cuts-captions) at the end.
>
> **15 September 2026:** the long cuts of B2 and D in `voiceover/` show a scene-02 line that
> implies scores move through the session. Do not upload those six files until they are
> re-rendered; the 15 s cuts and concept E are unaffected. See "Superseded: do not upload".

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

---

## Update 2026-09-11 — voice-over cuts, concepts D and E, and the Reels 40% rule

**Use `voiceover/` only.** Nine cuts: concepts B (money question), D (swing
traders) and E (published record), each in 9:16, 4:5 and 1:1. The silent
`tapeline-*.mp4` files at the top of this folder are superseded. Their 9:16 cut puts the
disclosure inside the band Meta says to keep clear, so it must not be uploaded.

- **Voice:** Microsoft neural `en-US-AndrewNeural` via edge-tts. Local SAPI
  only has David and Zira, which would make the ads worse than no voice.
- **Timing follows the voice.** The first script ran 45s. The shipped cuts are
  26.6–28.5s. Each scene is held for its spoken length plus a lead-in and a
  tail, never the reverse.
- **Loudness:** −16 LUFS integrated, the social-video norm.
- **Compliance gate inside the build:** `build3.mjs` writes every spoken line to
  `vo-script.md` and runs `lint-copy-compliance.mjs --ads` on it before
  synthesising anything. A failing line stops the build.
- **The trial length is on screen, not spoken.** It is parsed from `frontend/lib/trial.ts`.
- Scenes 05–06 are identical across B, D and E, sound included, so results
  are attributable to the hook.

**Reels 40% rule.** For Reels ads that carry a disclaimer, Meta says to keep the
bottom 40% free of text, logos and key elements. The 9:16 cuts now use a
770px bottom band (the disclosure ends at about y=1120, with the line at
y=1152). The product frame is fitted by height as well as width, so it cannot
overflow on 9:16 or 1:1.

**Concept E hook changed.** It was "Every scanner shows you its good weeks." That is
false: Zacks has published a record for decades. It is now "Anyone can show
you their good weeks."

**Why D and E exist, and the test design:** see `docs/META_ADS_PLAYBOOK_2026-09-11.md`
(verified research on how large advertisers run Meta, translated to A$25/day)
and `docs/GOOGLE_DATA_2026-09-11.md` (the Ads, Search Console and GA4 pull
behind concept D). Copy for all three ads, with the price and billing interval
Meta's subscription policy requires: `meta-copy-2026-09.md`.

---

## Update 2026-09-14 — concept E rewritten, 15 s cuts, captions

**What to upload is at the end of this section.** Nothing here has been uploaded to Meta,
and the Ads Manager drafts (D, E, B2) still hold the 2026-09-11 files and text. Replacing
them needs a separate founder yes.

### What was wrong, and what changed

<!-- copy-compliance-allow * -- quotes the retired concept E lines so nobody writes them again; they are not ad copy -->
1. **Concept E made false claims about the record.** It said "We publish every day. Including
   the bad ones.", "Each session's top ten is written down when it prints, and never re-ranked,
   back-filled or removed afterwards", and "The same score that goes in the archive is the one
   you see on the page". Its primary text said Tapeline "never re-ranks" the list. The record
   has US trading days with no top ten, and recorded values were corrected after the fact; both
   are dated on `/scorecard`. E now says only what is true, with no figures:
   - the public scorecard shows the misses too;
   - it lists top-ten scores by date, each next to the following session's price move and SPY's;
   - gaps and corrections are dated on the page;
   - reading it needs no account, and without Pro or Premium the entries show on a delay (read
     from `_FREE_DELAY_DAYS` in `backend/app/routers/scorecard.py`).

   E's proof scene is now the shared ticker-page scene, because the screenshot is a ticker page,
   not the archive.
2. **The shared CTA said the record "needs no account and no card".** One scene after the
   card-required trial, that reads as a trial without a card. It now says "The public scorecard
   needs no account."
3. **The money scene headline is now "$0 today. Card required."** The price and interval
   ("then $19.99/mo or $199/yr, the plan you choose") and "Cancel in one click" are on the same
   screen. "$0 today" never appears without "card required".
4. **Meta text fields rewritten for D, E and B2** (`meta-copy-2026-09.md`, now generated by the
   build). Every primary text opens with the card, $0, price, interval and cancel terms inside
   the first 125 characters. Both plans are named, because the billing period after the trial
   is an open founder decision. B2's headline is "$0 today. Card required." (24 characters; it
   was 41). The description is "Not investment advice." (22 characters).
5. **A new ≤15 s cut per concept**, following Meta's guidance that 6–15 s performs better and
   that frame 1 should show motion or a compelling visual. Three scenes: the hook over the real
   product frame, already moving from frame 1 (a slow push-in on the score panel), then the
   money scene, then the CTA. The disclosure line is on every frame.
6. **Verbatim captions.** Every video has a `.en_US.srt` next to it, timed from the TTS
   service's sentence boundaries on the video's own clock. Two spoken forms are written the way
   the screen writes them: "Tapeline dot I O" as `tapeline.io`, and "five hundred" as `500`. The
   build fails if the captions do not reassemble into the voice-over.

### Gates inside `build3.mjs`

The build refuses to synthesise anything unless these pass. The first four were each run
against a deliberately broken copy of the script and seen to fail.

| Gate | Seen failing on |
|---|---|
| `lint-copy-compliance.mjs --ads` over every spoken, on-screen and caption line (`vo-script.md`) and every Meta field (`meta-copy-2026-09.md`) | a stock-tip word swapped into the Meta opener; a card-free claim placed next to the trial in the CTA |
| Record-claim check, for what the linter misses: "every day", "each session", "daily", "frozen", "logged", "never re-ranked", "when it prints", any `%`, "hit rate", "alpha", "beat" | "We publish every day. Including the bad ones."; "Frozen when it prints." |
| No trial length typed into the script (it is read from `frontend/lib/trial.ts`) | a typed "30-day" in the money scene, and in the Meta opener |
| Meta limits: card, $0, both prices, both intervals and one-click cancel inside 125 characters; headline ≤ 40; description ≤ 25; no "$0" headline without "card required" | the old 41-character B2 headline; the price pushed past character 125 |
| Every 15 s cut is ≤ 15 s; captions are verbatim | not mutation-tested |

### Outputs, as probed

All 18 videos probed (with `ffmpeg -i`; there is no ffprobe on the build machine): h264 yuv420p
at 30 fps, AAC 48 kHz stereo, `+faststart`, loudness normalised to −16 LUFS. Each concept's three
ratios share one audio track and one caption file's timings.

| Concept | Long cut | Words | 15 s cut | Words | Hook sentence spoken by (15 s) |
|---|---|---|---|---|---|
| B2 | 28.63 s | 68 | 13.73 s | 31 | 2.7 s |
| D | 27.73 s | 67 | 13.63 s | 31 | 2.6 s |
| E | 27.83 s | 66 | 13.73 s | 31 | 2.1 s |

Word counts include "Tapeline dot I O" as four words. Resolutions: `9x16` 1080×1920, `4x5`
1080×1350, `1x1` 1080×1080.

The 9:16 cuts keep the top 270 px (14%) and the bottom 770 px (40%) free of text, with 84 px
sides (7.8%, against Meta's 6%). The 4:5 and 1:1 cuts do not meet the Reels and Stories safe
zone, so opt them out of those placements (blueprint §4.2, R5 and R7).

Frame 1 and the frame at 1.5 s of all 18 videos were extracted and read by eye, along with every
changed scene in all three ratios. In the 15 s cuts, frame 1 already shows the product and the
push-in is visible by 1.5 s. Text stays inside the safe bands in all 18 videos, and the disclosure
is legible in every one. The build writes these grabs to `check/`, which is not committed. On 1:1
the line under the product frame sits close above the disclosure, but they do not overlap.

### What to upload where

One ad per concept. Load **every** asset below before publishing, never mid-flight: adding
assets can restart learning (blueprint §4.2, R8). Upload each `.en_US.srt` with its video.

| Placement | Long cut | 15 s cut |
|---|---|---|
| Reels and Stories | `voiceover/tapeline-concept-X-vo-9x16.mp4` | `voiceover-15s/tapeline-concept-X-vo15-9x16.mp4` |
| Facebook and Instagram Feed | `voiceover/tapeline-concept-X-vo-4x5.mp4` | `voiceover-15s/tapeline-concept-X-vo15-4x5.mp4` |
| Other square placements | `voiceover/tapeline-concept-X-vo-1x1.mp4` | `voiceover-15s/tapeline-concept-X-vo15-1x1.mp4` |

X is `b` for the B2 ad, `d` for "D - Swing traders (VO)" and `e` for "E - The record (VO)".
The text for each ad is in `meta-copy-2026-09.md`. Meta's guidance favours under 15 s for Feed
and Reels, so if only one cut can go in, use the 15 s cut.

### Superseded: do not upload

- **Any copy of `voiceover/*.mp4` made before 2026-09-14**, including the files already in the
  D, E and B2 Ads Manager drafts. The filenames did not change; the contents did. The old E is
  false, and the old CTA's card-free wording lands one scene after the card-required trial.
- **The 2026-09-11 text fields**, and anything pasted from them into the drafts: the 41-character
  B2 headline without "card required", and E's primary text.
- `tapeline-9x16.mp4`, `tapeline-4x5.mp4`, `tapeline-1x1.mp4` (the silent cuts). The 9:16 puts
  the disclosure in the band Meta says to keep clear, and all three end on the old "no account
  and no card" CTA.
- `stills/4x5/06-cta.png` and `build.mjs`. The same old CTA line is in the still, and
  `build.mjs` would regenerate it.
- `stills/4x5/02-turn.png` (added 15 September 2026). It still shows "Six named factors, one
  0–100 composite, re-scored through the US session." Scores are recalculated on every
  pass, but most inputs are daily readings, so a score usually changes about once a day;
  the line implies scores move through the session. The silent `tapeline-*.mp4` cuts carry
  the same line.
- **The long cuts of B2 and D** (`voiceover/tapeline-concept-b-vo-{1x1,4x5,9x16}.mp4` and
  `voiceover/tapeline-concept-d-vo-{1x1,4x5,9x16}.mp4`), added 15 September 2026, for the
  same scene-02 line (it comes from `build3.mjs`). Use the 15 s cuts of B2 and D, which do
  not carry it, or re-render the long cuts after that line is changed. See the note at the
  top of `vo-script.md`.

### Regenerate

From a working folder that holds `node_modules/ffmpeg-static`, a copy of `shot-ticker.png`, and
an edge-tts venv at `../ttsvenv`:

```
TAPELINE_REPO=<checkout> node build3.mjs                      # everything
TAPELINE_REPO=<checkout> node build3.mjs --copy-only          # text and gates only
TAPELINE_REPO=<checkout> node build3.mjs --only=short:e:9x16  # a subset
```

Then copy `voiceover/`, `voiceover-15s/`, `vo-script.md` and `meta-copy-2026-09.md` into this
folder. There is no ffprobe on the build machine, so the probe reads `ffmpeg -i`.

### Still open

<!-- copy-compliance-allow * -- names two words visible in the product screenshot in order to flag them; not ad copy -->
- **The product screenshot shows the words "SIGNAL" and "STRONG SETUP".** They are on the real
  ticker page, but in ad *text* the `--ads` linter bans both (stock-tip vocabulary and a
  score-band name). The linter cannot read pixels, so no gate catches them. Re-shooting the page
  without that row is a creative call and was not made here.
- **B's long-cut hook still says "Every stock screener hands you 500 filters".** That line was
  out of scope. The 15 s cut asks it as a question instead: "500 filters and a blank stare?"
- **The CTA names `tapeline.io/scorecard`**, while the ad destination may be `/signup`
  (blueprint §4.3 cross-check). Still undecided.
