# Tapeline browser extension

Shows Tapeline's six-factor score, the one-line reason, and the factor
breakdown for whatever ticker the user is already looking at — on Yahoo
Finance, TradingView, Google Finance, MarketWatch, Seeking Alpha, Stocktwits,
Finviz, Barchart, CNBC, Robinhood and Nasdaq — plus a manual lookup in the
toolbar popup that works anywhere.

**No account required.** That is deliberate: the extension is a top-of-funnel
surface, and the score + reason are already public (`/daily-picks`, `/t/{symbol}`,
`/badge/{symbol}`). Gating it behind a login would defeat its purpose.

## Try it in 60 seconds

1. Open `chrome://extensions`
2. Turn on **Developer mode** (top right)
3. **Load unpacked** → select this `extension/` folder
4. Visit <https://finance.yahoo.com/quote/NVDA> — a pill appears bottom-right.
   Click it for the breakdown.

Same steps work on Edge (`edge://extensions`) and Brave. Firefox needs the
small port noted below.

## How it works

```
content.js ──"NVDA"──▶ background.js ──▶ api.tapeline.io/api/ticker/NVDA
   (detects symbol            (service worker:
    from the URL)              caches 15 min, de-dupes)
```

Three design decisions worth keeping:

**The network call lives in the service worker, not the content script.** Since
Chrome 85 a content-script `fetch` is subject to the *host page's* CORS, and the
API only allows the app origin — a fetch from `finance.yahoo.com` would be
blocked. Service-worker fetches covered by `host_permissions` are exempt, so the
backend needs no CORS change.

**We read the ticker from the URL, never the host's data.** Detection is a regex
over `location` (see `sites.js`), so it survives the host redesigning its markup,
costs nothing on load, and keeps us clear of both the sites' terms and the Chrome
Web Store single-purpose policy. We learn *which* symbol the user is viewing and
show *our own* numbers for it.

**The UI is in a shadow root and collapsed by default.** Finance sites ship broad
CSS that would restyle an open div within a release or two. And an overlay that
covers someone's chart is an uninstall — so the pill states the score and nothing
else until clicked, and it can be dismissed.

## Load discipline

`/api/ticker/{symbol}` also backs the public SSR pages, so the extension caches
per symbol for 15 minutes in `chrome.storage.session` and collapses concurrent
requests for the same symbol into one. Scores move on a daily cadence, so a
stale-by-minutes read is correct.

Anonymous callers are **not** metered on that endpoint — see the comment in
`backend/app/routers/ticker.py` (the per-IP anon cap once 402'd our own SSR
renders and broke the whole `/t/` surface, so it was deliberately disabled).
If that ever changes, this extension needs its own lightweight public endpoint
returning just `{score, signal, reason, factors}`.

## Tests

```bash
node extension/test-detection.js
```

Covers every supported host plus the negative cases (article pages, bare chart
pages, unrelated domains). Run it when adding a site — detection failures are
silent, which is exactly how these extensions rot.

## Attribution

Every outbound link carries `?utm_source=extension&utm_medium=overlay`, so
installs show up as their own channel in the weekly prod-pulse acquisition
readout rather than as `direct`.

## Porting

- **Edge / Brave / Opera** — same MV3 build, no changes.
- **Firefox** — needs `browser_specific_settings.gecko.id`, and `background.js`
  as a non-module script; Firefox MV3 uses an event page rather than a true
  service worker. The `chrome.*` calls used here are all polyfilled by Firefox's
  `browser`/`chrome` compatibility shim.
- **Safari** — requires `xcrun safari-web-extension-converter` and a paid Apple
  developer account. Not worth it until installs justify it.

## Not in v1, deliberately

Price/quote data of our own (the host page already shows it), watchlist writes,
alerts, login, options/crypto, and any per-user framing of a holding — the last
one drifts toward personal advice and needs the lawyer consult booked in
`docs/COMPETITOR_GAP_ANALYSIS.md` first.

## Icons

`icons/*.png` are **generated** from the canonical brand mark, not hand-drawn —
a `#0a0a0a` rounded square with a centred `#3b82f6` pill bar, the same geometry
as `frontend/public/favicon.svg` and `frontend/app/icon.tsx`. The extension's
in-UI mark (the pill badge and the popup header) is built from the same two
shapes in CSS.

If the brand mark ever changes, change it in `favicon.svg` / `icon.tsx` first,
then re-render:

```bash
node extension/icons/make-icons.js
```

Chrome requires PNG for toolbar icons, which is why these are rasterised rather
than referenced as SVG.
