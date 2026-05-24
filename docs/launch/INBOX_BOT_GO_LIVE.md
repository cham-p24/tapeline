# Inbox bot — one-time go-live checklist

The inbox auto-handler ships across PRs #173 / #175 / #176 / #177.
Code is safe to deploy without any of these secrets — the bot
fail-quiets every channel that isn't wired yet, so deploys never
break.

Each step below unlocks one more channel. **Do them in order; each
one is self-contained.** None take more than 5 minutes.

---

## Step 1 — Deploy the code (after PRs merge)

```powershell
cd "C:\Project 1"
fly deploy -a tapeline-backend --remote-only --strategy=immediate
```

Verification: hit `https://api.tapeline.io/api/inbox` in your browser
while signed in as the owner account. You should see an empty list
(`{"items": [], "count": 0}`) — not a 404. If it 404s, the deploy
didn't pick up the new router.

---

## Step 2 — Wire your Telegram chat_id (5 sec)

The Tier 1 alert needs to know where to send the notification.

1. Open https://t.me/Tapeline_Bot in Telegram
2. Send `/start` if you haven't already
3. Visit https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates in
   a browser. Find the `chat.id` for your most recent message — that's
   your chat_id.
4. ```powershell
   fly secrets set INBOX_FOUNDER_TELEGRAM_CHAT_ID=<your_chat_id> -a tapeline-backend
   ```

Verification: trigger a fake Tier 1 alert by:
```powershell
curl -X POST https://api.tapeline.io/api/inbox/email \
  -H "Content-Type: application/json" \
  -d '{
    "type": "email.received",
    "data": {
      "message_id": "test-001",
      "from": "test@example.com",
      "to": ["inbox@tapeline.io"],
      "subject": "Methodology question",
      "text": "Hey — long question about how you handle the Piotroski F-score for the financial sector where the long-term-debt leverage test is essentially a category error."
    }
  }'
```

You should get a Telegram message with the alert card + buttons within
a few seconds.

---

## Step 3 — Wire the Telegram bot webhook for button clicks (30 sec)

Without this, the Approve / Reject buttons on the alert card don't do
anything (they POST callbacks to the Telegram-Bot API which has nowhere
to forward them).

```powershell
# Generate a random secret (one-time)
$SECRET = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | % {[char]$_})
echo $SECRET  # save this; you'll need it for the curl below

# Save to Fly so the backend can verify incoming Telegram requests
fly secrets set TELEGRAM_WEBHOOK_SECRET=$SECRET -a tapeline-backend

# Tell Telegram where to send updates
$TOKEN = "<your TELEGRAM_BOT_TOKEN — same one already on Fly>"
curl -X POST "https://api.telegram.org/bot$TOKEN/setWebhook" `
  -d "url=https://api.tapeline.io/api/inbox/telegram-update" `
  -d "secret_token=$SECRET"
```

Verification: trigger another fake Tier 1 alert (same curl as Step 2),
then tap ✅ Approve on the resulting Telegram card. You should see the
button card update to "Sent ✓" (or "Approved (deferred)" if the
channel adapter isn't wired yet — fine for testing).

---

## Step 4 — Wire Resend inbound for the email channel (5 min)

This routes inbound emails to the bot. Without it, the email channel
only fires on synthetic test curls.

1. Resend dashboard → Webhooks → Add endpoint
   - URL: `https://api.tapeline.io/api/inbox/email`
   - Event: `email.received` (only)
2. Copy the signing secret Resend generates.
3. ```powershell
   fly secrets set RESEND_INBOUND_SECRET=<paste_secret> -a tapeline-backend
   ```
4. Configure inbound routing in Resend:
   - Domain: `tapeline.io`
   - Inbound address: `inbox@tapeline.io` (or whatever you want)
   - Action: forward to the webhook you registered

(MX records on `tapeline.io` need to point at Resend for this to
work. If they don't yet, this step blocks until DNS is configured.)

Verification: send yourself an email to `inbox@tapeline.io`:
- Subject: "How does your pricing work?"
- Body: "Hey — what are your plans?"

You should get an auto-reply within a few seconds (Tier 2 pricing
template).

---

## Step 5 — (Optional, weeks-out) Reddit channel

The Reddit poller (Phase C) is gated on the account having enough
karma to post in r/stocks. See
`docs/growth/reddit_karma_comments.md` for the karma-building plan.
Don't wire Reddit credentials until karma is built — the poller
would silently fail on every comment-reply attempt.

When ready:

1. Create a Reddit script app at https://www.reddit.com/prefs/apps
   (name: tapeline-inbox-bot, type: script, redirect_uri: http://localhost)
2. ```powershell
   fly secrets set `
     REDDIT_CLIENT_ID=<id> `
     REDDIT_CLIENT_SECRET=<secret> `
     REDDIT_USERNAME=<your_handle> `
     REDDIT_PASSWORD=<your_password> `
     REDDIT_USER_AGENT="tapeline-inbox-bot/0.1 by /u/<your_handle>" `
     -a tapeline-backend
   ```
3. Phase C code (not yet shipped — would be a separate PR) adds the
   PRAW polling worker.

---

## What happens with no setup at all

Even if you do nothing after Step 1:

- The `/app/inbox` admin UI works (you can manually log inbound via
  the GET endpoint, just no automatic delivery)
- The classifier runs against any test payload via the webhook
- Telegram alerts don't fire (no chat_id) → fail-quiet
- Email auto-replies don't fire (no inbound webhook configured) →
  fail-quiet

In other words: deploy is always safe. Each subsequent step is
incremental and you can stop at any point without breaking what you've
already wired.
