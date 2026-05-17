# Morning queue — 2026-05-17

State of play as of last night. Pick up here.

## Already deployed (today's 18 PRs, summary)

| Theme | PRs |
|---|---|
| Sheet bridge live (universe + scores from signal-system) | #52 #54 #55 #69 |
| Tier-gate leak fix (4 routes) | #56 |
| Heatmap rebuild (51 → 14 sectors + search) | #57 #67 |
| UX polish (shortcut, account hub, scanner search, holdings empty state) | #58 |
| ETF financials all-null fix | #59 |
| News bar 3-at-a-time + 20 fetch | #60 |
| Insider feed DB persistence | #61 |
| SEC EDGAR 8-K direct feed | #62 |
| Sector backfill cap 200 → 2500 | #63 |
| Borderless surfaces + fluid type | #64 |
| Auth credentials cross-origin fix | #65 |
| Diagnostics script | #66 |
| iOS feel + light/dark/system theme | #68 |
| Changelog v0.1.11 | #70 |
| Next.js 14 → 16, React 18 → 19 | #71 #72 |

Live state confirmed via `fly ssh console -a tapeline-backend -C 'python -m app.scripts.diagnostics'`:

```
tickers=7,162  scored=4,399  distinct_sectors=14  worker_lag=0.4 min
news_items=1,729  insider_transactions=13,312+
```

## Phase 1 — Live-push webhook (deferred)

Decision made last night: defer the CSV → push refactor.

Spec when ready (~1 day build):

1. **Apps Script on the sheet** (Extensions → Apps Script):
   ```javascript
   function notifyTapeline() {
     UrlFetchApp.fetch('https://api.tapeline.io/api/internal/sheet-changed', {
       method: 'post',
       contentType: 'application/json',
       payload: JSON.stringify({
         secret: PropertiesService.getScriptProperties().getProperty('TAPELINE_WEBHOOK_SECRET')
       }),
       muteHttpExceptions: true
     });
   }
   ```
   Wire as installable `onChange` trigger (fires on programmatic Sheets-API writes too — important since the signal-system probably writes via gspread, not keyboard).

2. **Backend route** `/api/internal/sheet-changed`:
   - Validates shared secret (new Fly secret `SHEET_WEBHOOK_SECRET`)
   - Triggers all 5 tab refreshes in a background task
   - Returns 200 in <50ms (Apps Script has 30-sec timeout)
   - Debounces — if multiple webhooks arrive in 10 sec, only refresh once

3. **Keep the 5-min CSV poll as fallback** in case Apps Script has a trigger outage.

End-to-end lag: 1-3 seconds (was up to 5 min).

## Phase A — Multi-watchlists + screener presets (~1 day, half-built scope below)

User can have N named watchlists ("Tech", "AI Plays", "My Core"), each with M tickers. Saved scanner presets are JSON blobs of filter state.

### Backend foundation

**New models:**

```python
# backend/app/models/watchlist.py — add:
class Watchlist(Base):
    __tablename__ = "watchlists"
    id: Mapped[int] = ...primary_key, autoincrement
    user_id: Mapped[str] = ...FK users.id, indexed
    name: Mapped[str] = ...String(60), nullable=False
    sort_order: Mapped[int] = ...default 0
    created_at: Mapped[datetime] = ...
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_watchlist_user_name"),)

# WatchlistItem gets:
    watchlist_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("watchlists.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
```

**Migration 0020:**
- Create `watchlists` table
- Add nullable `watchlist_id` to `watchlist_items`
- Data backfill: for every distinct user_id in `watchlist_items`, create a default `Watchlist(name="My Watchlist", sort_order=0)` and assign all their items to it
- (Leave `watchlist_id` nullable — soft constraint; the API only writes via the new endpoints that always set it)

**New model:**

```python
# backend/app/models/scanner_preset.py
class ScannerPreset(Base):
    __tablename__ = "scanner_presets"
    id: Mapped[int] = ...primary_key, autoincrement
    user_id: Mapped[str] = ...FK users.id, indexed
    name: Mapped[str] = ...String(60), nullable=False
    filters: Mapped[str] = ...JSON, stored as String/Text
    created_at: Mapped[datetime] = ...
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_preset_user_name"),)
```

**New tier cap** in `services/tier.py`:

```python
# Add to TIER_LIMITS:
"watchlists": <Free=1, Pro=5, Premium=20>
# saved_scans already exists: Free=0, Pro=10, Premium=100
```

### API endpoints to add

```
GET    /api/watchlists           — list user's lists
POST   /api/watchlists           — create new (body: { name })
PATCH  /api/watchlists/{id}      — rename
DELETE /api/watchlists/{id}      — delete (cascade items)

GET    /api/watchlist?list_id=X  — filter to one list (default: all items, current behavior)
POST   /api/watchlist            — add list_id to body (required if user has >1 list)

GET    /api/presets              — list user's screener presets
POST   /api/presets              — create (body: { name, filters: object })
DELETE /api/presets/{id}         — remove
```

### Frontend integration (separate PR)

- `/app/watchlist` page: tabs at top for switching between lists, "+ New list" button at end
- `/app/scanner` page: "Save preset" button next to filters, dropdown to load saved presets
- Use the new tier limit `watchlists` to gate the "+ New list" button visually
- For Free tier (cap=1): hide tabs entirely; for Pro+: show

### Test plan

- Backend tests for the new endpoints + cap enforcement
- Existing watchlist tests must still pass (backward compat — single-list users see no change)
- Migration round-trip test (apply + rollback)

## Today's 5-min unlocks

These need user-side values that came up yesterday:

```powershell
# 1. Local .env Resend key (paste line 41 of C:\Project 1\.env)
RESEND_API_KEY=<paste from resend.com/api-keys>

# 2. Quiver API key (already paying — just need the key)
fly secrets set QUIVER_API_KEY=<paste from quiverquant.com> -a tapeline-backend
```

## What's NOT done from the original launch list

(See yesterday's audit in chat — these are still user-only:
Persona KYC, OpenAI top-up, Stripe identity doc upload, account
signups [AlternativeTo / G2 / Capterra / Stocktwits / Crunchbase /
Microsoft Entra / LinkedIn company page], $24.99 self-purchase test,
Holley Nethercote lawyer call, X banner upload, LinkedIn photo upload,
5 fintwit DMs, 4 manual outreach, Show HN submission.)

## SPIKE parser todo

The SPIKE INTELLIGENCE tab schema changed since I wrote the parser
(it's now per-ticker-spike with `Spike Score / Spike Direction / Buy By`,
not per-day-spike with `move_day_pc / volume_multiple`). Currently
returns 0 rows on refresh. Rewrite is ~30 min — read the new schema
in `backend/app/services/sheet_feed.parse_spike_intelligence_csv` and
update column lookups.

Sample row from the live tab:
```
Spike Rank, Ticker, Buy By, Time Window, Stage, Entry Trigger,
Stop / Risk, Price, Spike Score, Spike Direction, Type, Spike Urgency,
Suggested Window, Buy Timing, Decision, Score, Source Confidence,
Source Notes, Volume Expansion, RSI14, OBV Trend, Breakout Type,
Spike Reasons, Why This May Move, Main Risk, Core Signal, Hold Duration
```
