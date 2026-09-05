<!--
BACKUP COPY, brought into the repo 2026-08-30.

The original lives at C:\Tapeline\CHROME_STORE_LISTING.md, and C:\Tapeline is
NOT a git repository — it is a scratch workspace. This file is needed to submit
the extension and existed in exactly one untracked, unbacked-up place. If the
two ever diverge, the one you are reading is the one with history.

The .zip it references is also only in C:\Tapeline and is NOT copied here
(binary, and rebuildable from origin/main at the tagged commit).
-->

# Chrome Web Store listing — Tapeline extension v1.2.3

**Package:** `C:\Tapeline\tapeline-extension-v1.2.3.zip` (26,985 bytes, 11 files)
**Upload at:** https://chrome.google.com/webstore/devconsole

> Built from `origin/main` and verified: every file byte-identical to the repo,
> `manifest.json` at the archive root, no dev artefacts.
>
> Built from `origin/main` at `4cc3dd3`, after PR #617. The earlier v1.2.1 and
> v1.2.2 zips have been **deleted** rather than left lying around: 1.2.1 predates
> PR #612 and would have shipped the "free account" and "needs no card" claims
> that PR removed, and there is no version of this where grabbing the wrong file
> is a recoverable mistake once it is in the store.

> **After the first upload, you never do this by hand again.** Registering and
> creating the item is manual (the API cannot create an item or write listing
> copy), but every version after that ships via **Actions → Publish extension**.
> Setup: `docs/CHROME_WEB_STORE_SETUP.md` in the repo.
> Everything below is final copy. Paste it field by field — no editing needed.

---

## Name (45 char max)

```
Tapeline — Stock Score & Track Record
```

*(37 chars. Matches `manifest.json` exactly — two different names is a needless metadata mismatch.)*

## Short description (132 char max)

```
Tapeline's six-factor score and track record for the stock you're viewing. Tapeline account required. Sends only the ticker.
```

*(124 chars. This is the manifest `description` verbatim, deliberately — the store field and the manifest disagreeing is the kind of small inconsistency reviewers notice. Two non-negotiables are preserved: the account requirement, because a reviewer who installs it and hits a connect screen the listing never mentioned files a functionality-mismatch rejection; and "sends only the ticker", the strongest fact in the submission.)*

**Note the wording is "Tapeline account", not "free account".** See the card gate below — "free" is no longer true for new accounts and must not reappear here.

## Category

**Primary:** Finance
*(Not "Productivity". A reviewer expects a finance tool to declare itself.)*

## Language

English (United States)

---

## Detailed description

```
Tapeline scores about 2,500 US stocks every day on six published factors, and logs every daily top-10 pick to a public record that is never edited — including the picks that lose.

This extension puts that on the pages you already read.

WHAT YOU SEE

When you open a stock page, a small pill appears in the corner with Tapeline's score for that ticker. Click it for:

• The six factors behind the score — trend, relative strength, fundamentals, smart money, macro, momentum — each scored 0-100
• A one-line plain-English reason for the score
• Confidence, based on how much factor data backs it
• Whether Tapeline has published that ticker in its daily top 10 before, and how those picks actually resolved against SPY — losing picks included

That last one is the part no other tool shows you.

WHAT IT READS

Only the ticker symbol in the page's web address. On finance.yahoo.com/quote/NVDA it reads NVDA.

It does not read the page. Not prices, not your holdings, not balances, not order history, not form fields. No tracking, no analytics, no advertising.

WHERE IT WORKS

Switched on for 21 public research sites including Yahoo Finance, TradingView, Google Finance, MarketWatch, Seeking Alpha, Finviz, Barchart, CNBC and Nasdaq.

Your broker is not included by default. Anywhere else — including brokers — it stays off until you turn it on yourself, one site at a time, from the popup. You can revoke that at any time.

You can also highlight any ticker anywhere on the web, right-click, and look it up. And the toolbar popup does manual lookups on any page at all.

WHAT YOU NEED

A Tapeline account. After installing, the welcome page takes you to tapeline.io to sign in or create one.

Signing up takes an email and a password and opens the free plan. A card is what starts the 30-day Premium trial — $0 that day, the first charge lands at the end of the trial, and one click cancels before then.

HONEST ABOUT THE RECORD

Tapeline's published picks do not currently beat SPY. Just under half beat it the next session, and the median pick trails slightly. The live figures are on the public scorecard at tapeline.io/scorecard, updated as each session resolves.

At the current sample size these numbers do not distinguish the ranking from chance. We publish them unedited anyway — the whole point is a record you can check rather than a claim you have to trust.

Scores are descriptive readings of published data. Not investment advice, price targets or forecasts.
```

**Why the record paragraph carries no percentage.** Store copy is static; the scorecard is not. As of this writing the live figures are 47.2% beating SPY next session and median alpha −0.137% over 678 entries across 72 sessions. Bake either number into the listing and it is quietly false within a week, which is precisely the failure mode PR #612 spent four rounds cleaning up. "Just under half" stays true across the plausible range and the link carries the exact figure.

**Do NOT paste the full 21-site list into the description** — excessive site lists read as keyword stuffing and are a documented rejection reason. The nine named above are enough.

---

## Privacy practices tab

**Single purpose:**
```
Display Tapeline's stock score and published track record for the ticker the user is currently viewing, and allow manual ticker lookups.
```

**Permission justifications** — one per field:

| Permission | Justification |
|---|---|
| `storage` | Stores the user's account connect token, caches fetched scores briefly so the same stock is not requested repeatedly, and records which sites the user has muted plus whether they accepted the first-run notice. All local to the device. |
| `scripting` | Registers the score overlay on sites the user has explicitly enabled via the "Enable on this site" button. Not used to inject anything into sites the user has not enabled. |
| `activeTab` | Reads the address of the current tab when the user opens the extension popup, so it can show the score for the stock they are looking at and offer to enable the extension on that site. |
| `contextMenus` | Adds a right-click "Look up in Tapeline" item so the user can select a ticker symbol on any page and open its score. |
| `host_permissions: api.tapeline.io` | The extension's own API, which returns the public score and published record for a ticker symbol. |
| `optional_host_permissions: https://*/*` | Requested one site at a time, only when the user presses "Enable on this site". Never requested at install. |

**Data usage — answer honestly, this changed with the account gate:**
- **Authentication information: YES** — the extension stores a connect token that links it to the user's Tapeline account. Declare it. Ticking "no" here while shipping a bearer token is the kind of mismatch that gets an extension pulled.
- Personally identifiable information: the extension displays the account email it is connected to. If the form treats that as PII, declare it too — over-declaring costs nothing, under-declaring is a takedown.
- Does NOT collect health, financial, location, web history or user activity data
- Does NOT collect website content

**Attestations (all three required):**
- ☑ Not being sold to third parties, outside of the approved use cases
- ☑ Not being used or transferred for purposes unrelated to the item's single purpose
- ☑ Not being used or transferred to determine creditworthiness or for lending purposes

**Privacy policy URL:**
```
https://tapeline.io/legal/extension-privacy
```
*(Must be this URL, NOT /legal/privacy — a reviewer following the link to a web-app policy is a documented rejection reason. Verified live: returns 200.)*

**Support / contact email:** a `@tapeline.io` address (e.g. `support@tapeline.io`).
Do **not** use a personal Gmail — it is a flagged trust signal in every 2026 safety checklist.

---

## Screenshots required

Store requires at least one at **1280×800** or **640×400** (1280×800 preferred). Take these **from the v1.2.3 build**, not an older one — the welcome copy changed.

1. **The panel expanded on a Yahoo Finance quote page** — the money shot. Shows score, factors, reason and the record block together, in context.
2. **The track-record block close up** — on a ticker that has appearances (e.g. `ALNT`, `CASS` or `MRK`; note NVDA has zero). This is the differentiator; make it legible.
3. **The popup with "Enable on this site"** — open it on a broker to show the opt-in model. This is the trust story.
4. **The connect screen** — the popup before connecting. A reviewer will hit this first, so showing it in the listing means the account requirement is never a surprise.
5. *(optional)* **The right-click lookup** on selected text.

How: load the unpacked extension, open the page, and use Windows `Win + Shift + S` or a full-window screenshot cropped to 1280×800.

---

## Before you submit

- [ ] Hardware-key 2FA on the developer Google account
- [ ] Verify the privacy URL loads: https://tapeline.io/legal/extension-privacy
- [ ] Support email is `@tapeline.io`
- [ ] Confirm the uploaded zip reports **1.2.3** in the dashboard
- [ ] Walk the connect flow yourself once on a clean profile: install → welcome page → sign in on tapeline.io → a score appears. That is exactly the path a reviewer takes, and it is the only way to catch a break in it. **Use a brand-new account** so you see the card gate the reviewer will see.

## Fixed before submission

`robinhood.com` was a silent dead end: absent from the manifest's match list (dropped in PR #526) yet carrying a rule in `sites.js`, which made `isKnownHost()` true — and `popup.js` only offers *Enable on this site* when that is false. Nothing rendered there and there was no way to grant the origin from the UI. Fixed in PR #617 by marking the rule `optIn: true`, which keeps the precise Robinhood URL rule while restoring the Enable button. Guarded by `test-detection.js` (39/39).

Worth knowing because Robinhood is a broker a reviewer might plausibly try.

## After it is live

- [ ] Send me the store URL — I will add the install link to `tapeline.io/whats-new`, the `/mcp` page and the footer, and put it in the next user announcement.

**Expect heightened review.** New developer + new extension + finance category = the profile that gets manual review, and there is a live banner warning of extended review times. Nothing in the package should trip it: no remote code, unminified source, minimal permissions, and every claim in the description is verifiable in under a minute.

**One asymmetry worth knowing:** since Chrome 117, a policy takedown converts your entire install base into a one-click "Remove" prompt via Safety Check. Over-comply at submission; it is much cheaper than recovering.
