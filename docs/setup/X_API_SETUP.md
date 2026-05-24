# X (Twitter) API setup — 10 minutes, ONE-TIME

This is the single highest-ROI 10 minutes of founder work left. After
this, the growth bot stops emailing tweet drafts to your inbox and
starts posting them directly to @tapeline_io.

Free tier limits (sufficient for our cadence):
- 500 posts/month (we'd use ~25 — one daily tweet + 1-2 fintwit replies
  per weekday)
- 100 read requests / 24h (we'd use ~30 — checking fintwit timelines)

---

## Step 1 — Apply for a developer account (3 min)

1. Go to https://developer.x.com/en/portal/petition/essential/basic-info
2. Sign in with your @tapeline_io account
3. Fill in the petition:
   - **Use case**: "Automated posting for a stock-scanning SaaS"
   - **Will tweets be made available?** Yes
   - **Will government accounts be analysed?** No
   - **Will analyses be displayed outside X?** No
4. Submit. Approval is usually instant for non-research use.

---

## Step 2 — Create a project + app (2 min)

1. Once approved, go to https://developer.x.com/en/portal/projects
2. Click "Create Project"
   - Name: `tapeline-growth-bot`
   - Use case: "Making a bot"
   - Description: "Posts daily quantitative stock-score updates from
     the @tapeline_io brand account"
3. Click "Create App"
   - Name: `tapeline-growth-bot-v1`
4. You'll see the **API Key**, **API Key Secret**, **Bearer Token**.
   Copy these somewhere safe (you can't view the secret again, only
   regenerate).

---

## Step 3 — Enable OAuth 1.0a + generate access tokens (3 min)

1. In the App settings, find "User authentication settings" → click
   Set up
2. App permissions: **Read and write** (do NOT pick DMs — we don't
   need them and minimum permissions is good security hygiene)
3. Type of App: **Web App, Automated App or Bot**
4. Callback URI: `https://tapeline.io/x-callback` (placeholder — the
   automated app doesn't use it, but the form requires a value)
5. Website URL: `https://tapeline.io`
6. Save. Then go back to "Keys and tokens" tab → click "Generate" under
   **Access Token and Secret**. Copy both.

You now have 4 strings:
- `X_API_KEY`
- `X_API_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_TOKEN_SECRET`

The Bearer Token from Step 2 is NOT needed for posting (it's a
read-only token). Keep it as a backup.

---

## Step 4 — Drop them in Fly secrets (1 min)

Open PowerShell in `C:\Project 1`:

```powershell
fly secrets set `
  X_API_KEY="paste-here" `
  X_API_SECRET="paste-here" `
  X_ACCESS_TOKEN="paste-here" `
  X_ACCESS_TOKEN_SECRET="paste-here" `
  X_AUTO_POST=true `
  -a tapeline-backend
```

That'll trigger a rolling deploy. Wait ~60s.

---

## Step 5 — Smoke test (1 min)

```powershell
curl -X POST https://api.tapeline.io/api/admin/growth-tick/run `
  -H "X-Admin-Key: $env:TAPELINE_ADMIN_KEY"
```

You should see:
- Within ~10 seconds: the email digest arrive in tapeline.inbox@gmail.com
- Within ~30 seconds: the day's tweet appear on https://x.com/tapeline_io
- Within ~60 seconds: any fintwit reply candidates that matched fresh
  tweets get posted

Confirm on https://x.com/tapeline_io that the new tweet is live with
the correct UTM-tagged URL.

---

## Step 6 — Disable the kill switch

The bot defaults to OFF on first deploy so it doesn't surprise you
with autoposts before tokens are configured. Flip it on:

```powershell
fly secrets set GROWTH_BOT_ENABLED=true -a tapeline-backend
```

That's it. Going forward, the worker fires the bot daily at 22:00 UTC
(8am Melbourne) Mon-Fri, no further action needed.

---

## To pause posting later

```powershell
fly secrets set X_AUTO_POST=false -a tapeline-backend
```

This keeps the worker running and the digest emails arriving, but
stops actual posting. Useful for vacations or if you want to manually
review for a week.

To kill the bot entirely:

```powershell
fly secrets set GROWTH_BOT_ENABLED=false -a tapeline-backend
```

---

## Troubleshooting

**"Could not authenticate you"**: re-generate access tokens in the X
portal (step 3) — sometimes they expire silently after long inactivity.

**429 rate limit**: free tier is 500 posts/month. The bot uses ~25 so
this only fires if something's looping. Check `fly logs -a
tapeline-backend | grep "x_post"` for the offending call.

**Bot posts but tweet looks wrong**: edit the templates in
`backend/app/services/growth_bot.py` (functions `draft_daily_tweet`,
`draft_linkedin_post`, `draft_fintwit_reply_candidates`). Templates
are intentionally short + factual — keep them in that voice.

**"Forbidden" on tweet POST**: your access tokens were generated
BEFORE you upgraded the app to Read+Write. Regenerate (step 3).

---

Total founder time after this guide: zero per day. Worker handles it.
