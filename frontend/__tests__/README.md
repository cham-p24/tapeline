# Frontend tests

Vitest + React Testing Library. Tests run in jsdom (no real browser).

## Setup (one-off, on a fresh clone)

```powershell
cd frontend
npm install
```

This pulls in vitest, @testing-library/react, @testing-library/jest-dom,
@testing-library/user-event, jsdom, and @vitejs/plugin-react.

## Run

```powershell
npm test                # one-off run, exits with 0/1
npm run test:watch      # watch mode for active development
```

## Coverage

The initial test set covers the highest-leverage surfaces:

- **Paywall.test.tsx** — gated content actually hides for non-Premium users
  (revenue-critical; a bug here leaks paid features)
- **PricingTable.test.tsx** — Free/Pro/Premium plans render with the
  canonical names; anchor row (Team/Enterprise/Lifetime) is present
- **SignupForm.test.tsx** — honeypot field is rendered, hidden, and
  carries the right ARIA attributes (bot-protection layer)
- **ScannerPreview.test.tsx** — landing-hero scanner shows descriptive
  labels (HIGH CONVICTION etc.), never prescriptive ones (BUY NOW etc.) —
  protects the publisher's-exemption legal posture
- **LiveBadge.test.tsx** — the SSE stream hook (useLiveStream, with a small
  in-file EventSource mock) and the freshness badge: pings never read as
  updates, the badge never says "Live", "Auto-refreshing" only while update
  events arrive, failed loads never move the "Updated" time, and
  `enabled: false` pages never refetch

## What's not covered (yet)

- API client / lib/api.ts — needs `msw` for HTTP mocking, easy add later
- Full page render of /app/scanner — needs API mocking + provider stubs
- E2E flows (signup → scanner → paywall) — Playwright would land later

Add tests by dropping `*.test.tsx` files in this directory.
