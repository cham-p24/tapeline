# Tapeline — Frontend

Next.js 14 App Router dashboard. **Not yet initialized.**

## Initialize

Run from `C:\Project 1\frontend\`:

```bash
npx create-next-app@latest . --typescript --tailwind --app --eslint --no-src-dir --import-alias "@/*"
```

Then install core UI deps:

```bash
npm install @clerk/nextjs @stripe/stripe-js lucide-react
npx shadcn-ui@latest init
npx shadcn-ui@latest add button card table input select dialog toast
```

## Pages to build (in order)

| Week | Page | Purpose |
|---|---|---|
| 2 | `app/page.tsx` | Public landing + pricing |
| 2 | `app/(app)/scanner/page.tsx` | Filterable ticker table |
| 2 | `app/(app)/squeeze/page.tsx` | Squeeze setup list |
| 3 | `app/(app)/regime/page.tsx` | Market regime dashboard |
| 3 | `app/(app)/alerts/page.tsx` | Alert rule config |
| 4 | `app/(app)/billing/page.tsx` | Stripe portal link |
| 4 | `app/(app)/congress/page.tsx` | Premium-only congress feed |

## Live data

Use `EventSource` (SSE) against `/api/stream/live`:

```ts
const es = new EventSource(`${process.env.NEXT_PUBLIC_API_URL}/api/stream/live`, {
  withCredentials: true,
});
es.onmessage = (e) => {
  const patch = JSON.parse(e.data);
  // apply to Zustand/Jotai store
};
```

## Design tokens

- Font: Inter (sans) + JetBrains Mono (numbers/tickers)
- Palette: neutral grayscale + single accent (proposed: `#10b981` emerald for positive, `#ef4444` red for negative)
- Density: tables use compact row height, 13px font, tabular-nums CSS
- Dark mode default; light mode optional
