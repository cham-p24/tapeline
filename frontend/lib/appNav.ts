/**
 * Single source of truth for signed-in app navigation.
 *
 * Both the left sidebar / mobile drawer (app/app/layout.tsx) and the ⌘K command
 * palette (components/GlobalSearch.tsx) import from here so the two can never
 * drift — previously the palette kept its own hardcoded DESTINATIONS list, which
 * had fallen behind the sidebar and could not reach Regime / Congress / Insider
 * buys / News / Earnings / IPOs.
 *
 * Copy note: hints are plain descriptions of the destination — no performance,
 * return, or urgency claims.
 */

export type NavItem = { href: string; label: string; hint?: string };
export type NavGroup = { label: string; items: NavItem[] };

/**
 * App navigation, grouped for the left rail. The old flat 8-tab top bar was at
 * its width limit and left several built routes (News, Earnings, IPOs) with no
 * inbound link at all — a sidebar has room to surface them. "Alerts" stays a
 * top-group item since it's the #1 pay-driver and watchlist→alert is the flow.
 */
export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Trade",
    items: [
      { href: "/app/scanner", label: "Scanner", hint: "Rank the whole market" },
      { href: "/app/watchlist", label: "Watchlist", hint: "Your saved tickers" },
      { href: "/app/alerts", label: "Alerts", hint: "Score & price alerts" },
    ],
  },
  {
    label: "Signals",
    items: [
      { href: "/app/heatmap", label: "Heatmap", hint: "Sector heatmap" },
      { href: "/app/squeeze", label: "Squeeze", hint: "Short-squeeze setups" },
      { href: "/app/regime", label: "Regime", hint: "Market regime" },
    ],
  },
  {
    label: "Ownership & markets",
    items: [
      { href: "/app/congress", label: "Congress", hint: "Congress trades" },
      { href: "/app/holdings", label: "Insider buys", hint: "Insider buying" },
      { href: "/app/news", label: "News", hint: "Latest headlines" },
      { href: "/app/earnings", label: "Earnings", hint: "Earnings calendar" },
      { href: "/app/ipos", label: "IPOs", hint: "Recent & upcoming IPOs" },
    ],
  },
];

/**
 * Palette-only destinations that don't live in the sidebar rail: the public
 * Scorecard and the Billing page (Billing is also reachable from the account
 * menu, but the palette should be able to jump straight there).
 */
export const EXTRA_DESTINATIONS: NavItem[] = [
  { href: "/scorecard", label: "Scorecard", hint: "Public track record" },
  { href: "/app/billing", label: "Billing & plan", hint: "Manage subscription" },
];

/**
 * Flat destination list for the ⌘K palette: every sidebar destination plus the
 * palette-only extras, in the sidebar's order. Derived from NAV_GROUPS so it
 * stays in lockstep with the rail.
 */
export const PALETTE_DESTINATIONS: NavItem[] = [
  ...NAV_GROUPS.flatMap((g) => g.items),
  ...EXTRA_DESTINATIONS,
];
