# Feed-coverage audit — 2026-08-30

*`SAAS_OPTIMISATION_PLAYBOOK.md` §5.1 item 3, and the `OPERATING_RULES.md` §1 gate-jumping
candidate. Done-when: "a one-paragraph finding in `docs/`; if the cause is licence/vendor it
joins the lawyer brief; if it is a mapping bug it is the **one** engineering item that jumps
the interview gate."*

**Finding: it is not a licence problem, not a symbol-mapping problem, and not a universe
choice. It is a self-reinforcing bug in the daily aggregates pass that has pinned the entire
scanner to tickers whose symbols begin with A–E.** Read-only queries against production, no
writes.

## The evidence

Universe: **11,808 tickers**. Coverage across it:

| | count | share |
|---|---|---|
| no price | 4,573 | 38.7% |
| **no volume** | **8,523** | **72.2%** |
| no score | 5,095 | 43.1% |
| no 5-day return | 9,033 | 76.5% |

Every one of 42 hand-picked mega-caps **is present in the universe** (only INTC and QCOM lack a
price/volume read), so discovery is fine and symbol mapping is fine. But coverage by first
letter is not a distribution — it is a cliff:

| A | B | C | D | E | F–R | S | T | Y | Z |
|---|---|---|---|---|---|---|---|---|---|
| 94% | 95% | 92% | **65%** | **26%** | 4–12% | **1%** | **1%** | **0%** | **0%** |

S has volume for 10 of 916 tickers. T, 8 of 608. **Y and Z have zero.** The scanner cannot see
most of the alphabet.

And the published Top 10 at the time of the audit, with dollar volume computed:

| symbol | score | price | volume | $ volume |
|---|---|---|---|---|
| CHCI | 84.4 | $19.84 | 737 | **$0.0M** |
| AVAH | 84.2 | $13.36 | 126,349 | $1.7M |
| BBP | 83.5 | $106.08 | 202 | **$0.0M** |
| DCBO | 83.1 | $26.16 | 4,323 | $0.1M |
| BBH | 82.9 | $236.82 | 249 | $0.1M |
| ASRV | 82.2 | $4.85 | 575 | **$0.0M** |
| CGAU | 82.1 | $22.02 | 144,265 | $3.2M |
| DSX | 81.9 | $2.73 | 24,726 | $0.1M |
| CIX | 81.9 | $31.53 | 243 | **$0.0M** |
| AII | 81.8 | $26.27 | 5,038 | $0.1M |

Every single one starts with A, B, C or D. Several trade a few hundred shares a day — not
"small", effectively untradeable. The most liquid name on the list moves $3.2M.

## The cause

`backend/app/workers/signal_publisher.py`, `_refresh_aggregates`:

```python
AGGREGATES_CAP = ACTIVE_UNIVERSE_SIZE            # 2,500
select(Ticker.symbol)
    .order_by(_desc(func.coalesce(Ticker.volume * Ticker.price, -1)))
    .limit(AGGREGATES_CAP)
```

The intent, per the comment directly above it, is to refresh the 2,500 highest-dollar-volume
tickers and skip "micro-caps no scanner user filters into."

**The ordering key is the very column the pass exists to populate.** `Ticker.volume` is NULL
for any ticker that has never been through this pass, so `volume * price` is NULL, so
`coalesce(..., -1)` sorts it *last*.

That makes it a closed loop:

1. First run: every row is NULL → all tie at −1 → Postgres returns them in physical order,
   which is insertion order, which is ascending symbol (discovery inserts alphabetically).
   The first 2,500 — A through mid-E — get volume.
2. Every run after: those 2,500 now have a real dollar volume, so they sort **first** and are
   refreshed again. The other ~9,300 still have NULL, still sort last, and are **never
   selected**.

The covered set cannot grow. It is frozen at whatever won the first tie-break, and that was
the alphabet.

This is the same failure shape as the `DISCOVERY_MAX_TICKERS` bug already documented in
`CLAUDE.md` — a cap that binds while the vendor returns symbols in ascending order truncates
the universe alphabetically. That one was caught. This one wears a dollar-volume `ORDER BY`,
so it reads as deliberate.

## Consequences

- The composite ranks ~2,500 A–E tickers instead of ~11,800. Among a few thousand
  alphabetically-early names, the illiquid ones win — which is the entire explanation for the
  "microcap-heavy Top 10" question that has been open across the Manager and CEO sessions.
- `change_pct_5d` / `change_pct_1m` are bar-derived, so 76.5% of the universe renders an
  em-dash.
- The public scorecard has been recording a track record for picks drawn from this truncated,
  liquidity-blind pool.

## The fix, and why it is not applied here

The cap needs a bootstrap: never-refreshed tickers must get a rotating share of each pass so
the dollar-volume ranking has real numbers to rank. Roughly 80% of the budget by dollar volume
(keeps liquid names fresh) and 20% round-robin over NULL-volume tickers oldest-first would
cover all 11,808 within about a week and stay correct afterwards. A
`last_aggregates_refresh_at` column makes the round-robin honest.

**Not applied, deliberately.** It materially changes what the scanner publishes, and the
published Top 10 feeds a public track record. `OPERATING_RULES.md` §1 permits this to jump the
interview gate as a correctness bug on a user-visible surface — but the same item has twice
been left open with the note *"it needs a product call from you on what the default scanner
should surface,"* and fixing coverage and choosing a default view are two decisions, not one.
Coverage is a bug; a liquidity floor is a policy.

Founder call needed on: (a) ship the coverage fix now, and (b) whether the default view gets a
liquidity floor once the full universe is actually visible — noting a prior audit refused a
blunt volume filter because, at 72% missing volume, it *"would empty the production scanner."*
That objection dissolves once coverage is fixed.
