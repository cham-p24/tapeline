# Tapeline Inbox Auto-Handler Bot — build prompt

**Drop this prompt into a fresh Claude Code session at `C:\Project 1\`.** It is self-contained — no prior conversation context required.

---

## What you're building

A backend service inside the existing Tapeline FastAPI app that **auto-handles inbound messages across Reddit, email, and Telegram**, classifies them via the Claude API, and either auto-replies (Tier 2 / Tier 3) or routes a pre-drafted reply to the founder's Telegram for one-tap approval (Tier 1).

Founder context: solo founder running Tapeline pre-launch, drowning in DM volume across X / LinkedIn / Reddit / email. He explicitly told Claude "you're doing everything to do with posting and replying from now on". This bot is the answer for the three channels with workable APIs. X DMs need $200/mo X API Basic (skip). LinkedIn DMs have no public API (skip — stays manual at founder's pace).

---

## Tapeline project context

- **Code lives at:** `C:\Project 1\` (Windows). Backend at `backend/`, frontend at `frontend/`.
- **Stack:** FastAPI + SQLAlchemy + Alembic (Python 3.12) backend, Next.js 14 + TypeScript frontend.
- **Deploy:** Fly.io (backend, **manual** `fly deploy` from `C:\Project 1\` — NOT CI), Vercel (frontend, auto-deploys main).
- **DB:** SQLite local / Postgres prod (Neon, secret `DATABASE_URL`).
- **Read `C:\Project 1\CLAUDE.md` first** for the full project map. Pay attention to: tier model, scoring formula (do NOT change it), signal labels (descriptive not prescriptive), retired channels (Discord + SMS — don't re-enable).
- **Existing services to leverage:**
  - `backend/app/services/email.py` — Resend integration (already configured)
  - `backend/app/services/telegram.py` — Telegram bot (already configured)
  - `backend/app/workers/signal_publisher.py` — pattern for periodic worker tasks
  - `backend/app/db.py` — async SQLAlchemy session factory

---

## Hard constraints

- **Founder voice = first person, no "we"**. He posts as "Christian Piyatilaka" publicly, "Chamara" privately. Default to "Christian" for public-facing replies.
- **Never auto-send a Tier 1 reply**. Tier 1 = high-value (FinTwit influencers, journalists, real prospects). The bot drafts; the founder approves via Telegram. Auto-send to a Tier 1 = brand risk that's not worth the time saved.
- **Never re-enable Discord or SMS channels.** They were retired 2026-05-04.
- **Don't touch the 6-factor scoring formula, the descriptive signal labels, or the three-tier pricing.** Anything that smells like a methodology change ships only after explicit founder approval.
- **Lawyer-safe language.** Descriptive language only — "constructive setup", "high conviction", "weak". Never "buy", "sell", "you should", or any prescriptive recommendation. The Australian publisher exemption from AFSL depends on this — breaking it is an existential risk to the business.
- **Idempotency.** Inbound message IDs are unique per channel. If the same Reddit comment ID / email message-id / Telegram update_id is processed twice, the second pass must no-op. Use a `processed_messages` table.

---

## Architecture

### New backend modules

```
backend/app/services/inbox_classifier.py   # Claude API → Tier 1/2/3 + suggested reply
backend/app/services/inbox_reply.py        # Auto-send Tier 2/3, Telegram-route Tier 1
backend/app/services/reddit_inbox.py       # PRAW poller for comments + DMs on @tapeline_io's posts
backend/app/services/email_inbox.py        # Resend inbound webhook handler
backend/app/services/telegram_inbox.py     # Telegram bot getUpdates poller
backend/app/workers/inbox_worker.py        # 5-min cron: poll all channels, classify, route
backend/app/routers/inbox.py               # Admin UI endpoints (list pending, approve Tier 1, reject)
backend/app/models/inbox.py                # InboundMessage + ProcessedMessage tables
backend/alembic/versions/20260520_NNNN_inbox_auto_handler.py  # Migration
```

### Database schema (sketch — refine in implementation)

```python
class InboundMessage(Base):
    __tablename__ = "inbound_messages"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "reddit:t1_abc123"
    channel: Mapped[str]                                       # "reddit_comment" / "reddit_dm" / "email" / "telegram"
    author: Mapped[str]                                        # @handle / email / chat_id
    subject: Mapped[str | None]                                # email subject, or first 80 chars
    body: Mapped[str]                                          # full message text
    received_at: Mapped[datetime]                              # when it landed
    tier: Mapped[int | None]                                   # 1 / 2 / 3 — null until classified
    tier_reason: Mapped[str | None]                            # one-line LLM explanation
    suggested_reply: Mapped[str | None]                        # LLM draft
    status: Mapped[str]                                        # "new" / "approved" / "sent" / "rejected" / "auto_replied"
    handled_at: Mapped[datetime | None]                        # when reply went out
    telegram_message_id: Mapped[int | None]                    # for editing the approval message
```

### Tier classification logic

Use the Anthropic SDK directly (already in `backend/pyproject.toml`). System prompt:

```
You are an inbox triage assistant for Tapeline — a SaaS stock-scanning tool
run solo by founder "Christian Piyatilaka" (Melbourne, Australia). Classify
each inbound message into:

Tier 1 = high-value, NEEDS FOUNDER VOICE. Examples:
- FinTwit account with 5K+ followers asking about methodology
- Real retail trader (real name, finance title) with specific ticker question
- Newsletter / podcaster / YouTuber inquiry about coverage
- Journalist from reputable outlet
- Inbound LinkedIn DM from finance-titled professional
- Long thoughtful (200+ char) methodology critique

Tier 2 = templatable, AUTO-REPLY SAFE. Examples:
- "What's the score for $TICKER?"  → reply with live API curl + breakdown
- "How does the free tier work?" → canonical pricing reply
- "Can I get a free trial?" → trial signup reply
- Generic "cool product" / "interesting tool" → short thanks + invite

Tier 3 = ignore. Examples:
- Crypto shillers / pump-and-dump
- Bot accounts (newly created, generic profile, follow count <50)
- Off-platform paid-signal-service offers
- Hostile / trolls (one-line "this is fake" / "no track record")

Return JSON: {"tier": 1|2|3, "reason": "<one line>", "suggested_reply": "<draft or null>"}
```

Use `claude-sonnet-4-5` (cheapest capable model). Prompt-cache the system prompt.

### Reply templates (for Tier 2 auto-send)

Hardcode in `inbox_reply.py`:

```python
TEMPLATES = {
    "ticker_score": lambda symbol, data: (
        f"$" + symbol.upper() + f" currently scores {data['score']:.1f}/100 ({data['signal']}). "
        f"Breakdown: Trend {data['breakdown']['trend']['value']:.0f} · "
        f"RS {data['breakdown']['rs']['value']:.0f} · "
        f"Fundamentals {data['breakdown']['fundamentals']['value']:.0f} · "
        f"Smart Money {data['breakdown']['smart_money']['value']:.0f} · "
        f"Macro {data['breakdown']['macro']['value']:.0f} · "
        f"Momentum {data['breakdown']['momentum']['value']:.0f}. "
        f"Full breakdown + chart at tapeline.io/t/{symbol.upper()}. "
        "Drop another ticker if you want me to pull it."
    ),
    "pricing": lambda: (
        "Free tier covers the top 20 tickers (24h delayed) + the public scorecard + a 5-ticker watchlist. "
        "Pro is $8.25/mo annual ($9.99 monthly) for the full ~2,500-ticker live scan + smart watchlist alerts. "
        "Premium is $16.58/mo annual ($19.99 monthly) for everything in Pro + congressional trades + insider Form 4 buys + unlimited Telegram alerts. "
        "Every signup gets a 14-day Premium trial, no card. tapeline.io/pricing has the full comparison."
    ),
    "trial": lambda: (
        "Yep — every signup gets 14 days of Premium free, no card required. "
        "tapeline.io/signup. The full ~2,500-ticker universe, scorecard, watchlist alerts, congressional/insider feeds, all included for the trial window."
    ),
    "thanks": lambda: (
        "Thanks for the kind words. If you want to put it through its paces, drop a ticker and I'll send you its current score + the 6-factor breakdown."
    ),
}
```

For "ticker_score", call `GET https://api.tapeline.io/api/ticker/{symbol}` to get live data. Reply with the formatted string.

### Tier 1 Telegram approval flow

When a Tier 1 message is classified:

1. Insert into `inbound_messages` with `status = "new"`, `tier = 1`, `suggested_reply` populated.
2. Send a Telegram message to founder's chat_id (`TELEGRAM_CHAT_ID` env var):
   ```
   🟢 *Tier 1 inbound — needs your eyes*

   *From:* @user_handle (Reddit / Email / Telegram)
   *Reason:* Real retail trader asking specific methodology question

   *Their message:*
   > [first 400 chars of the message body, truncated with …]

   *Draft reply:*
   [the suggested_reply text]

   /approve_<id>   /edit_<id>   /reject_<id>
   ```
3. Telegram message_id stored on the row for later edits.
4. Telegram bot handler listens for `/approve_<id>` → send the suggested_reply via the channel-appropriate adapter (Reddit PRAW reply, Resend send_email, Telegram sendMessage). Set `status = "approved"` and `handled_at`.
5. `/reject_<id>` → set `status = "rejected"`, don't send anything.
6. `/edit_<id>` → next message from the founder becomes the reply (state machine).

### Worker schedule

In `backend/app/workers/inbox_worker.py`, add to the existing signal_publisher loop pattern:

```python
async def inbox_tick():
    """Poll all channels, classify new messages, route appropriately."""
    async with get_session() as session:
        await poll_reddit(session)
        await poll_email(session)
        await poll_telegram(session)
        await classify_new(session)        # batch any tier=null messages through Claude
        await route_classified(session)    # auto-send Tier 2/3, Telegram-route Tier 1
```

Schedule every **5 min** during US market hours, every **15 min** off-hours. Use the existing scheduler (look at how `_refresh_universe` etc. are scheduled in `signal_publisher.py`).

---

## Implementation phases — ship in this order

### Phase A — Foundations (1 hour)
- Migration for `inbound_messages` + `processed_messages` tables
- `models/inbox.py` definitions + add to `models/__init__.py`
- Stub `services/inbox_classifier.py` with one `classify(message: dict) -> dict` function

### Phase B — Email channel (1 hour)
- Resend inbound webhook setup: configure `inbound@tapeline.io` in Resend dashboard to POST to `api.tapeline.io/api/inbox/email`
- Router `/api/inbox/email` accepts the Resend webhook payload, validates HMAC signature (`RESEND_INBOUND_SECRET` env var), inserts into `inbound_messages`
- Auto-classify on insert; if Tier 2, queue auto-reply via Resend `send_email`

### Phase C — Reddit channel (1 hour)
- Add `praw` to `backend/pyproject.toml`
- Env vars: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD`, `REDDIT_USER_AGENT="tapeline-inbox-bot/0.1 by /u/{REDDIT_USERNAME}"`
- `poll_reddit(session)` fetches:
  - Comments on @tapeline_io's last 30-day post history
  - Inbox DMs (`reddit.inbox.unread()`)
- For new items, insert + classify + route. After processing, call `comment.reply()` for Tier 2 auto-replies.

### Phase D — Telegram channel (1 hour)
- Bot is already configured (`TELEGRAM_BOT_TOKEN` secret on Fly).
- Long-poll `getUpdates` in `poll_telegram`, persist offset.
- Inbound DMs from anyone NOT the founder → classify + route.
- `/approve_<id>`, `/edit_<id>`, `/reject_<id>` commands from founder's chat_id → dispatch.

### Phase E — Admin UI (45 min)
- `/app/inbox` page in frontend showing the last 100 inbound messages, filterable by tier/channel/status
- Buttons: Approve / Edit / Reject for any Tier 1 message in `status = "new"`
- Useful for catching anything Telegram missed + retroactive review

### Phase F — Tests + deploy (45 min)
- Pytest: tier classification harness with 10-15 fixture messages
- Pytest: idempotency check (process same message twice → second call no-ops)
- Pytest: template renders correctly for ticker_score / pricing / trial / thanks
- Manual smoke test: send yourself a Reddit DM, watch the bot classify + reply
- `fly deploy` from `C:\Project 1\` (deploys are MANUAL — see `tapeline_deploy_workflow.md` memory)
- Tail logs via `fly logs -a tapeline-backend | grep -i inbox` to verify the first 5 inbound cycles

---

## Env vars to add (Fly secrets)

```
ANTHROPIC_API_KEY=sk-ant-...                # for tier classification (founder has one)
REDDIT_CLIENT_ID=...                        # https://www.reddit.com/prefs/apps (founder creates)
REDDIT_CLIENT_SECRET=...
REDDIT_USERNAME=...                         # founder's reddit handle
REDDIT_PASSWORD=...
REDDIT_USER_AGENT=tapeline-inbox-bot/0.1
RESEND_INBOUND_SECRET=...                   # founder configures the Resend webhook signing secret
INBOX_FOUNDER_TELEGRAM_CHAT_ID=...          # founder's personal Telegram chat_id (already known)
```

Set via:
```powershell
fly secrets set -a tapeline-backend KEY=value KEY2=value2
```

---

## Success criteria

The bot is "shipped" when:

1. A Tier 2 Reddit comment ("what's $NVDA score?") receives an auto-reply containing the live score within 5 minutes.
2. A Tier 1 LinkedIn-tone email (long methodology critique) arrives → founder gets a Telegram notification with the draft reply → founder hits `/approve_<id>` → the reply lands in the inbox within 30 seconds.
3. The same Reddit comment delivered twice (e.g. PRAW polled the same window) is processed once — second pass is a no-op.
4. Discord and SMS channels are NOT re-enabled (founder retired them 2026-05-04 for unit economics reasons).
5. Pytest suite passes; `fly deploy` lands; first 5 inbound messages in production are correctly classified.

---

## Anti-patterns / things NOT to do

- **Do not** ship full auto-send for Tier 1. The Telegram-approve loop is the deliberate firewall against brand-damage replies.
- **Do not** add an LLM call into the hot reply path for Tier 2. Ticker-score, pricing, trial, thanks should all be deterministic templates. Only Tier 1 drafting calls the LLM.
- **Do not** scrape LinkedIn DMs. No browser automation against linkedin.com. Account-ban risk is real and there's no recovery if @christian-piyatilaka-16192a40a gets nuked.
- **Do not** introduce a new database (Redis, etc.) for queueing. The 5-min worker pattern handles the volume — there's no real-time SLA on inbox replies and the existing Postgres is plenty.
- **Do not** wire X DMs / mentions until founder approves the $200/mo X API Basic spend. He's explicitly skipping that for now.
- **Do not** edit `services/tier.py` to add an "inbox" feature gate. The bot operates server-side as the founder's identity; it's not a customer-tier feature.

---

## When you're done

1. Open a PR titled `feat(inbox): auto-handler for Reddit + email + Telegram with Tier 1 Telegram approval`
2. PR body includes a screenshot of the Telegram approval message format
3. Auto-merge enabled (CI green → merges to main)
4. Founder gets a Telegram notification on first real inbound classified — that's the smoke test
5. Update `C:\Project 1\CLAUDE.md` to add the bot to the "Critical file map" + "Pending TODOs" sections

---

## Open questions the founder will need to answer

1. **Founder's Reddit username** — needed for PRAW auth. (Check `tapeline_outreach_identity.md` memory first.)
2. **Founder's Telegram chat_id** — needed for `INBOX_FOUNDER_TELEGRAM_CHAT_ID`. The `/app/billing` Telegram setup card shows this in his account.
3. **Reddit app credentials** — founder creates a script-tier app at https://www.reddit.com/prefs/apps (`name: tapeline-inbox-bot`, `type: script`, `redirect_uri: http://localhost`). Returns `client_id` and `client_secret`.
4. **Resend inbound domain** — does `inbound@tapeline.io` already MX-route to Resend, or does the founder need to add MX records in Cloudflare? If MX records aren't set, this is a blocker for Phase B.
5. **The Tier 2 templates use placeholder dollar amounts** ($8.25, $16.58). Confirm these are still canonical — `services/tier.py` is the source of truth.

If any of these are unanswered after a quick look at the codebase + memory files, leave a sensible default + a `TODO(founder): confirm X` comment and proceed. Don't block waiting for him.

---

## Communication style

- Tight, factual reporting. Lead with the recommendation, offer to implement.
- No unprompted refactors. Do not "while I'm here" rewrite the worker scheduler.
- If you find a bug in adjacent code while building, leave a `# TODO(inbox-bot): noticed X` comment and file it as a follow-up PR instead of expanding scope.
- Update `C:\Project 1\CLAUDE.md` with the new bot's existence + critical files, so the next agent inheriting the project knows where it lives.

---

## Reference: Founder's identity rules

- **Public outreach** = "Christian Piyatilaka" — LinkedIn, X (@tapeline_io), Reddit, podcast pitches, all Tier-1 replies
- **Private / internal / direct-with-Claude** = "Chamara" — git commit author, internal docs, this prompt's recipient
- The bot's auto-reply signature should NOT include "Christian" or "Chamara" — just unsigned founder voice, first person ("I built Tapeline because...", not "We built Tapeline...").

That's the brief. Start with Phase A.
