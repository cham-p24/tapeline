# Phase 1 execution plan — agent-shippable vs. founder-gated

Drafted 2026-05-17 against `docs/MORNING_QUEUE.md` (PR #73). The morning queue holds two engineering chunks the founder deferred ("Phase 1" — sheet → backend live-push webhook; "Phase A" — multi-watchlists + screener presets) plus a small SPIKE parser fix and two 5-minute user-side credential unlocks. This document classifies every item as agent-shippable, decision-gated, or founder-only, writes a per-item brief, and proposes a sequence.

The deliverable here is the plan only — no Phase 1 code is touched in this PR.

---

## What "Phase 1" actually is

Two distinct work items live under the "Phase 1" umbrella in `MORNING_QUEUE.md`. Naming was loose; the doc itself uses "Phase 1" for one thing and "Phase A" for the other:

- **Phase 1 — Live-push webhook.** Replace the 5-minute CSV poll from the signal-system's Google Sheet with an Apps Script `onChange` trigger that POSTs to `/api/internal/sheet-changed`. Backend validates a shared secret, debounces, and triggers the 5 existing `sheet_feed.refresh_*` tab refreshes in the background. CSV poll stays as a fallback. End-to-end lag goes from up to 5 min → 1-3 sec.
- **Phase A — Multi-watchlists + screener presets.** Adds a `Watchlist` parent model (so users can have N named lists like "Tech" / "AI Plays" / "My Core" with a `watchlist_id` FK on `WatchlistItem`), a `ScannerPreset` model (saved JSON filter blobs), a new tier cap `watchlists` (Free=1, Pro=5, Premium=20), and ten REST endpoints. Data backfill migrates every existing user's items into a default `"My Watchlist"`.

The queue also flags one bug (SPIKE parser returning 0 rows after the upstream schema changed — already shipped in PR #75, so it's stale here) and two user-only credential unlocks.

---

## Three-bucket classification

| Bucket | Item | Notes |
|---|---|---|
| Agent | Phase A backend foundation (models + migration + tier cap + endpoints + tests) | Spec is explicit; no founder choices needed |
| Agent | Phase A frontend (multi-watchlist tabs + preset save/load on scanner) | Spec is explicit; should land after backend |
| Agent | Phase 1 backend route (`/api/internal/sheet-changed` + debounce + secret check) | Spec is explicit; safe to ship without the Apps Script — CSV poll remains primary until webhook is set up |
| Decision | Apps Script content & `SHEET_WEBHOOK_SECRET` rotation policy | Founder owns the Sheet; needs to paste the script into Extensions → Apps Script and add the secret as a script property |
| Decision | Behaviour of `/api/watchlist` GET when user has >1 list and no `list_id` is passed | Spec says "default: all items, current behavior" — confirm vs. "default to first list" |
| Decision | Whether to enforce the `watchlists` cap on creation (block) or display-only (warn + ask to upgrade) | Spec is silent on the UX |
| Founder | Set `SHEET_WEBHOOK_SECRET` Fly secret + paste it as Apps Script script property | Requires Sheet edit access + Fly secrets write |
| Founder | Paste `RESEND_API_KEY` into local `C:\Project 1\.env` line 41 | Local-only — 30 sec |
| Founder | `fly secrets set QUIVER_API_KEY=... -a tapeline-backend` | 30 sec; activates real 13F |
| Stale | SPIKE parser rewrite | Already shipped in PR #75 (`334b471`). Skip. |

---

## Agent-executable items

### A1. Phase A backend foundation

**Title:** Multi-watchlists + scanner presets — backend foundation

**Summary:** Introduces a `Watchlist` parent model with a nullable `watchlist_id` FK on `WatchlistItem`, a `ScannerPreset` model, a `watchlists` tier cap (1/5/20), and ten new endpoints. Backwards-compatible — single-list users see no behavioural change.

**Files likely touched:**
- `backend/app/models/watchlist.py` — add `Watchlist`, add `watchlist_id` column on `WatchlistItem`
- `backend/app/models/scanner_preset.py` — new
- `backend/app/models/__init__.py` — export new models
- `backend/alembic/versions/20260517_0020_watchlists_and_presets.py` — new migration with data backfill
- `backend/app/services/tier.py` — add `"watchlists"` key to all three `TIER_LIMITS` dicts
- `backend/app/routers/watchlist.py` — split into list-management + items endpoints, add `list_id` filter
- `backend/app/routers/presets.py` — new
- `backend/app/main.py` — mount `presets` router
- `backend/tests/test_smoke.py` (or new `test_watchlists.py` / `test_presets.py`) — endpoint coverage

**Tests to add:**
- Default watchlist auto-created on first item add when user has none (preserves current single-list UX)
- POST `/api/watchlists` enforces the tier cap (Free=1 blocks the second create)
- POST `/api/watchlists` enforces `UniqueConstraint("user_id", "name")`
- DELETE cascades to items
- GET `/api/watchlist?list_id=X` filters; GET without param keeps current "all items" behaviour
- POST `/api/presets` enforces `saved_scans` cap (existing — Free=0 blocks)
- Migration round-trip: apply 0020, every pre-existing item gets attached to a default `"My Watchlist"`, downgrade restores schema cleanly

**Acceptance criteria:**
- All 8 existing backend smoke tests still pass
- New endpoints return 401 without auth, 403 on cap exceeded, 404 on cross-user access
- Default-watchlist backfill is idempotent (re-running the data migration on a freshly-migrated DB is a no-op)
- Sheet-feed refresh path is untouched

**Effort:** M (~half a day including tests + migration round-trip)

---

### A2. Phase A frontend integration

**Title:** Multi-watchlists tabs + scanner preset save/load

**Summary:** Adds list tabs at the top of `/app/watchlist`, a "+ New list" button gated on the `watchlists` cap, a "Save preset" button on `/app/scanner`, and a preset-load dropdown. Free tier (cap=1) hides tabs entirely; Pro+ shows them.

**Files likely touched:**
- `frontend/app/app/watchlist/page.tsx` — tab row, list switcher, new-list modal
- `frontend/app/app/scanner/page.tsx` — preset save/load UI
- `frontend/components/WatchlistTabs.tsx` — new
- `frontend/components/PresetMenu.tsx` — new
- `frontend/lib/api.ts` — wrapper functions for the ten new endpoints
- `frontend/__tests__/WatchlistTabs.test.tsx` — new RTL test
- `frontend/__tests__/PresetMenu.test.tsx` — new RTL test

**Tests to add:**
- Tabs render when user has >1 list, hidden when user has 1
- "+ New list" disabled when tier cap reached, with upgrade CTA tooltip
- Preset save calls POST with the current filter state
- Preset load applies the filter state to the scanner

**Acceptance criteria:**
- Existing watchlist page still works for single-list users with zero UI shift
- All current Vitest passes still green
- Visual: tabs match the iOS-feel polish from PR #68

**Effort:** M (~half a day)

**Depends on:** A1 (backend foundation must be merged first; the endpoints have to exist)

---

### A3. Phase 1 backend webhook route

**Title:** Add `/api/internal/sheet-changed` webhook for sheet live-push

**Summary:** New backend route that validates the `SHEET_WEBHOOK_SECRET` shared secret, debounces multiple incoming pings within 10 sec, and dispatches all 5 `sheet_feed.refresh_*` calls as a FastAPI `BackgroundTasks` job. Returns 200 in <50ms (Apps Script's 30-sec hard timeout). Safe to ship without the Apps Script being wired — the 5-min CSV poll in the worker stays the primary path until the founder pastes the script and sets the secret.

**Files likely touched:**
- `backend/app/routers/internal.py` — add the new endpoint (router already mounted)
- `backend/app/config.py` — add `sheet_webhook_secret: str | None = None`
- `backend/app/services/sheet_feed.py` — extract a `refresh_all_tabs(session)` helper that runs the 5 refreshes serially (the worker can switch to it later, but this PR leaves the worker unchanged)
- `backend/tests/test_smoke.py` — bad-secret → 401, no-secret-configured → 503, good-secret → 200 with refresh scheduled

**Tests to add:**
- 401 on missing / wrong `secret` body field
- 503 (or 200-with-warning per founder preference) when `SHEET_WEBHOOK_SECRET` is unset
- Two pings within the debounce window only fire one refresh (use a module-level last-fired timestamp + asyncio lock)
- Response p99 < 50ms even when the background job is heavy (assert by mocking `refresh_all_tabs`)

**Acceptance criteria:**
- Existing CSV poll path in `signal_publisher` is untouched
- Adding the secret is a pure unlock — no code changes needed when the founder wires the Apps Script
- Endpoint is documented in the router's module docstring (URL, body shape, debounce window)

**Effort:** S (~2 hours including tests)

---

## Decision-gated items

### D1. Apps Script + secret rotation policy

**Question:** Is the Apps Script template in `MORNING_QUEUE.md` the final shape, or do we want to log which tab changed and only refresh that one?

**Options:**
- **Refresh all 5 tabs on any change** (what the spec says). Simpler. Fires extra DB writes when only one tab changed. Roughly 5-15 sec of refresh work per ping.
- **Inspect the change event and refresh selectively.** `e.source.getActiveSheet().getName()` is available inside the `onChange` trigger — pass the sheet name as part of the webhook payload, branch on it server-side. More efficient, more code surface to maintain.

**Recommendation:** Ship the spec as-written for v1. The 5-tab refresh is bounded (~15 sec worst case) and runs in the background. Selectivity can come later if it ever matters.

**Plus:** rotation cadence for `SHEET_WEBHOOK_SECRET` — match `INTERNAL_ALERT_SECRET` (manual rotation via `fly secrets set` when prompted, no scheduled rotation) unless the founder wants different.

---

### D2. Default behaviour when user has >1 list

**Question:** When a Pro+ user with multiple lists hits `GET /api/watchlist` with no `list_id` param, what do they get?

**Options:**
- **All items across all lists** (what the spec says — preserves current behaviour for users who never create a second list). Frontend would call `?list_id=X` for the active tab.
- **First list only** (cleaner default — matches what the tab UI shows by default). Old single-list users still see their items because the migration assigned everything to a default list.

**Recommendation:** Spec-as-written (all items). The tab UI always sends an explicit `list_id`, so this only matters for API consumers — and "all items" is the least surprising default for the public-API Premium tier.

---

### D3. Cap enforcement UX

**Question:** When a Free user (cap = 1 list) hits POST `/api/watchlists` to create a second, do we 403 with an upgrade message, or do we 200-success-but-no-op and let the frontend show an upsell modal?

**Options:**
- **Hard 403** with `{"detail": "watchlists cap reached", "upgrade_to": "pro"}`. Frontend reads the error, shows a modal. Consistent with how `watchlist_tickers` cap is currently enforced (see `routers/watchlist.py`).
- **Frontend-only gate** (button disabled, modal on click). API still 403s as a defence-in-depth.

**Recommendation:** Hard 403 (matches existing pattern). Frontend should also disable the button — defence in depth.

---

## Founder-only items

### F1. Wire the Apps Script + set `SHEET_WEBHOOK_SECRET`

**Next step:**
1. Generate a 32-char urlsafe token: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. `fly secrets set SHEET_WEBHOOK_SECRET=<token> -a tapeline-backend`
3. Open the "Live Dashboard - Stocks" sheet → Extensions → Apps Script
4. Paste the template from `docs/MORNING_QUEUE.md` lines 38-49
5. File → Project properties → Script properties → add `TAPELINE_WEBHOOK_SECRET` = same token
6. Triggers → Add Trigger → `notifyTapeline` / Head / From spreadsheet / On change
7. Save. Edit any cell on the sheet to verify. Check `tail -f` on Fly logs for `internal.sheet-changed.received`.

Cannot be done by an agent: requires the founder's Google account to be the script owner so the trigger fires under their auth scope. A service-account approach exists but adds OAuth setup that isn't worth it for a single webhook.

---

### F2. Paste `RESEND_API_KEY` into local `.env`

**Next step:** Open `C:\Project 1\.env`, paste the key from resend.com/api-keys onto line 41 (or wherever `RESEND_API_KEY=` lives). Restart `.\scripts\run_nodocker.ps1` if running. Production already has this set per CLAUDE.md.

30 seconds. Local-only — no production impact.

---

### F3. Set `QUIVER_API_KEY` on Fly

**Next step:** `fly secrets set QUIVER_API_KEY=<key from quiverquant.com> -a tapeline-backend`. The next daily worker tick will pick up the elite-13F refresh and the `mock_elite_13f_holdings()` fallback will go silent. Verify with `curl https://api.tapeline.io/api/holdings?limit=5` (Premium auth required) — the response shape stays the same but `source` flips from `"mock"` to `"quiver"`.

30 seconds.

---

## Recommended sequence

1. **A3 first (Phase 1 webhook backend)** — smallest scope, no dependencies, zero risk to existing code paths. Ships unblocked. Once merged, F1 becomes an unattended user task — the founder can wire the Apps Script whenever and the unlock is immediate.

2. **A1 second (Phase A backend foundation)** — the migration is the load-bearing piece; better to land it on its own commit so any rollback is clean. Depends on D2 + D3 being answered first (5-min founder call).

3. **A2 third (Phase A frontend)** — strictly downstream of A1. UI can iterate without DB risk once the API contract is stable.

4. **F2 + F3 in parallel** — these are 30-sec founder unlocks that don't block any of the above. Worth doing immediately to clear two known dev/prod data-source gaps.

**Why this order:**
- A3 is small, isolated, and the unlock is asymmetric — one tiny PR removes up to 5 min of staleness across the entire universe view.
- A1's migration is the only piece with a meaningful rollback story; landing it alone makes the diff easy to read in `fly releases` and easy to revert in a panic.
- A2 has no DB side effects so it can ship behind a feature flag if needed.

**Dependencies graph:**

```
A3 (webhook backend) ──→ F1 (founder wires Apps Script) ──→ live-push goes hot
                                                            
D2, D3 answered ──→ A1 (backend foundation) ──→ A2 (frontend tabs + presets)

F2 (Resend local) — independent
F3 (Quiver prod) — independent
```

---

## Open / unclear items

- **No spec for what the "Save preset" button captures.** The morning queue says `filters: object` but doesn't enumerate which scanner filter fields are in scope. Inferring from the existing scanner page is fine, but the founder should sanity-check the field list during code review.
- **No spec for preset visibility.** Are presets private per-user (assumed) or could they ever be shared by URL? Spec is silent — defaulting to private, no sharing.
- **The "Phase 1" / "Phase A" naming is going to bite us.** They're two unrelated workstreams. Suggest renaming "Phase A" to "Multi-watchlists" in `MORNING_QUEUE.md` once this lands so the codebase doesn't end up with PRs titled "Phase A backend" three months later when nobody remembers what A meant. Out of scope for this doc, but worth a one-line edit in the next housekeeping pass.
