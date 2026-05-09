# Tapeline — Agent handovers

Each file in this directory is a self-contained brief for a Claude Code
session focused on one workstream. The intent: open a fresh chat, paste
the file's recommended starter prompt, and the agent has everything it
needs to start producing work without re-discovering Tapeline's context
from scratch.

| File | Workstream | Type |
|---|---|---|
| [`news-freshness-audit.md`](./news-freshness-audit.md) | Diagnose + fix news ingest staleness across the universe | Backend technical |
| [`seo-agent.md`](./seo-agent.md) | Generate per-ticker SEO content, monitor rankings, expand long-tail | Content + ops |
| [`marketing-agent.md`](./marketing-agent.md) | Twitter, LinkedIn, Reddit, HN copy + a launch announcement playbook | Content |
| [`email-generation-agent.md`](./email-generation-agent.md) | Drip emails, weekly digests, re-engagement, cold outreach | Content + backend |
| [`business-leverage.md`](./business-leverage.md) | Affiliate, API monetization, white-label, partnerships, scale strategy | Strategy |

## Conventions every agent should follow

1. **Read [CLAUDE.md](../../CLAUDE.md) first.** It's the canonical map of
   what Tapeline is, the moat (public formula + scorecard), legal posture
   (descriptive not prescriptive), and "things not to change without
   thinking" (6-factor weights, signal labels, three-tier pricing).
2. **Ask before changing pricing, signal labels, or scoring weights.**
   These are load-bearing for the brand.
3. **No new features without checking against pre-launch focus.** Owner is
   pre-launch — every diff competes with shipping.
4. **Commit messages: explain WHY, not WHAT.** The diff shows what; the
   message should say why it was worth shipping.
5. **Each agent owns its lane.** SEO agent doesn't write product code;
   marketing agent doesn't refactor backend; news-audit agent doesn't
   write blog copy.

## Cross-cutting: data sources Tapeline already has

| Source | Purpose | Status | Key |
|---|---|---|---|
| Massive (formerly Polygon.io) | Market data + reference + news | Live | `MASSIVE_API_KEY` |
| Finnhub | Fundamentals + earnings + IPO + news fallback + analyst recs | Live | `FINNHUB_API_KEY` |
| Benzinga | News wire + analyst ratings | Live | `BENZINGA_API_KEY` |
| FRED | Macro indicators (DXY, 10Y, VIX) | Live | `FRED_API_KEY` |
| Quiver QuantData | 13F + Congressional trades | Live | `QUIVER_API_KEY` |
| Resend | Transactional email | Live | `RESEND_API_KEY` |
| Stripe | Billing | **NOT YET LIVE** | needs setup |

## Coordination

If you're a human reading this, the SEO + marketing + email agents
generate output but **never push directly to production without owner
review**. Each agent should produce a numbered changes file (e.g.
`outputs/seo-2026-05-15.md`) which the owner can scan and approve before
deploy. The news-audit and business-leverage agents are
analysis/code-only and can ship via the normal commit/push flow.
