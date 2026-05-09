# Handover: Marketing agent

## Mission

Drive Tapeline's launch announcement and the 90-day post-launch
content cadence across Twitter/X, LinkedIn, Reddit, Hacker News, and
the blog. Every piece of marketing reinforces the **transparency
moat** (public formula, public scorecard, descriptive labels) — that
positioning is the brand and competitors literally cannot copy it.

## Why this matters

Tapeline is competing against TipRanks ($25M+ ARR), WallStreetZen,
Simply Wall St, and Zacks — all of which spend on paid acquisition and
have years of brand. The only way Tapeline wins is on a sharper,
narrower wedge: **"the only retail scanner that publishes its formula
and back-checks every call vs SPY publicly."** Every piece of
marketing should drive that one knife-point home.

## Scope

### IN scope
1. **Launch playbook** — a sequenced, dated plan for the first 14 days
   covering HN, Reddit (r/algotrading, r/stocks, r/investing), Twitter
   thread, LinkedIn announcement, personal-network email, ProductHunt
2. **Twitter/X content cadence** — 3-5 posts/week, mix of: scorecard
   wins/losses (publish both), market commentary using Tapeline data,
   methodology explainers, replies to retail finance influencers
3. **Reddit posts** — designed to land in the top 3 of relevant
   subreddits; never copy-pasted across subs
4. **Hacker News Show HN** — single shot, draft + iterate to perfection
5. **LinkedIn** — slower cadence, 1-2 posts/week, B2B angle
   (financial advisors, fintech ops, finance Twitter creators who
   might want to embed scores)
6. **Press / podcast outreach** — finance podcasts (Animal Spirits,
   The Compound, Risk Reversal Radio, Excess Returns) — pitch the
   founder for guest spots
7. **Monthly performance reviews** — `outputs/marketing-2026-MM.md`

### OUT of scope
- Paid acquisition (separate decision; product needs to be working
  on free organic before spending)
- Influencer paid sponsorship (same)
- Email drips (handled by the email-generation agent)
- SEO content (handled by the SEO agent)

## Concrete tasks (priority-ordered)

### 1. Launch playbook (FIRST, BEFORE LAUNCH)

Produce `outputs/launch-playbook-2026.md` with a dated sequence:

**Day -7:** Polish HN draft. Three writing passes minimum.
**Day -3:** Personal-network email. Send to 50 people who'd genuinely
care (founder's existing network, ex-colleagues, finance Twitter
people the founder follows).
**Day 0 (launch day, Tuesday morning AEST = Monday evening US
Eastern):**
  - 9:00 AEST: Personal-network email blast
  - 11:00 AEST: Twitter thread + LinkedIn announcement
  - 12:00 AEST: Show HN: Tapeline (timed for Monday morning Eastern,
    biggest HN traffic window)
**Day 0.5:** ProductHunt
**Day 1:** Reddit r/algotrading (technical pitch, not promotional)
**Day 3:** Reddit r/stocks (value-prop pitch with scorecard link)
**Day 5:** Reddit r/investing (longer-form, methodology focus)
**Day 7:** First "weekly scorecard recap" tweet thread
**Day 10:** Reach out to 5 finance podcast hosts pitching the founder
as a guest

For each item: draft copy, posting time, expected response handling.

### 2. Twitter/X content engine

- [ ] Set up posting cadence: Mon, Wed, Fri (skip weekends initially —
  retail trader audience doesn't engage Sat/Sun on US markets)
- [ ] Content mix per week:
  - 1 × scorecard recap (this week's HIGH CONVICTION + how each one
    actually moved next-day) — **always show losers honestly**
  - 1 × methodology explainer (deep-dive on one of the 6 factors)
  - 1 × market commentary using Tapeline's regime indicator
  - 1 × reply / quote-tweet to a relevant finance Twitter person
  - 0-1 × ad-hoc product update
- [ ] All scorecard recap tweets MUST link to `/scorecard` so the
  proof is one click away
- [ ] Founder's voice — first person, plain English, occasionally
  blunt about what didn't work

### 3. Reddit posts (3 in first 2 weeks, then monthly)

Each post is unique, never crossposted. Subreddit-tuned.

**r/algotrading** — technical audience, pitch the published formula
- Title: "I built a stock scanner with the formula on the homepage —
  here's the math"
- Lead with: the literal `score = 0.25 * trend + 0.20 * rs + ...`
  expression. Explain why each factor + weight. Link to `/how-it-works`.

**r/stocks** — broader retail, pitch the public scorecard
- Title: "Every stock pick we publish is back-checked against SPY the
  next day. Here's our scorecard."
- Lead with: a screenshot of `/scorecard` — including a bad week.

**r/investing** — methodology-curious, longer-form
- Title: "Why we publish our scoring formula instead of treating it as
  IP"
- Lead with: the Tipranks/Zacks/Kavout opacity problem, then explain
  Tapeline's approach.

**Rule for all Reddit posts:** the founder must reply to every comment
within the first 6 hours. No copy-paste replies. Reddit punishes
"professional" replies — sound like a human who built the thing.

### 4. Hacker News Show HN

One shot. Draft, sleep on it, redraft. Target post:

- Title: `Show HN: Tapeline – a stock scanner that publishes its
  formula and back-checks every pick`
- Submit Monday morning US Eastern (8-10 AM ET)
- First comment by founder: 2-3 paragraphs explaining the
  motivation, link to `/how-it-works` and `/scorecard`, and ASK FOR
  HONEST CRITIQUE (HN crowd loves being asked)
- Expect 50-100 comments, mostly skeptical. Reply to every single one
  in the first 24 hours.

### 5. LinkedIn cadence

Lower volume, more polished, B2B-leaning. 1-2 posts/week.
Audience: financial advisors, fintech operators, journalists,
acquihirers.

Topics:
- "Why retail finance products hide their methodology" — connects to
  fiduciary duty narrative
- "What the public scorecard discipline taught me about my own bias"
- "If you're a fintech building a scoring product — please publish
  your formula"

### 6. Podcast outreach

Pitch list (finance + indie SaaS):
- Animal Spirits (Michael Batnick + Ben Carlson)
- The Compound (Josh Brown)
- Excess Returns (Matt Zeigler)
- Risk Reversal Radio (Dan Nathan)
- The Pomp Podcast
- Indie Hackers (different angle — building a finance product solo)
- My First Million (broader audience)

Pitch template each gets — never paste-spam. 4-6 pitches/quarter
maximum, lovingly crafted.

### 7. Monthly review

End-of-month `outputs/marketing-2026-MM.md`:
- Followers gained per channel
- Top 3 posts by engagement (with hypothesis on why)
- Bottom 3 (what didn't land)
- Outreach replies received
- Recommended content focus for next month

## Files / surfaces

```
docs/LAUNCH_POSTS.md         # existing draft launch posts — read these first
docs/PRICING.md              # message house for any pricing-related content
CLAUDE.md                    # legal posture, signal labels, boundaries
frontend/app/blog/posts.ts   # blog manifest (coordinate with SEO agent)
frontend/app/scorecard/      # the scorecard surface — every post should screenshot or link this
```

## Tools / integrations

- WebFetch for SERP / competitor monitoring
- Read access to all Tapeline content
- Output goes to `outputs/marketing-*.md` for owner review
- Owner posts on Twitter/Reddit/HN — agent drafts, doesn't auto-post

## Success criteria

1. **Launch day**: HN front page (top 30) for 2+ hours
2. **Week 1**: 50+ paid signups (mix of trial + lifetime)
3. **Week 4**: 200 Twitter followers, 1 podcast booking
4. **Week 12**: 1,000 Twitter followers, 3 podcast appearances, sustained
   organic Reddit mentions (people posting Tapeline links without
   prompting)
5. **Quarter 1**: 500 paying customers (combination of trial converts
   + Founder's Lifetime sales)

## Recommended starter prompt

> I'm picking up the marketing handover at
> `docs/handovers/marketing-agent.md`. Read it, then read CLAUDE.md
> for legal posture (descriptive not prescriptive — important), then
> read `docs/LAUNCH_POSTS.md` to see the existing draft launch
> material. Your first deliverable is the launch playbook at
> `outputs/launch-playbook-2026.md` — full sequenced 14-day plan
> with day-by-day actions, draft copy, and timing. I'll review and
> iterate before we lock the actual launch date.
