/**
 * A price's age is the VENDOR's time for it (`quote_at`), never Tapeline's
 * write time (`updated_at`).
 *
 * Before migration 0075 every in-app "As of" read `updated_at`, which the
 * worker re-stamps on every pass even for a row the vendor returned nothing
 * for, so a price about 15 minutes old (Stocks Starter, measured 14 Sep 2026:
 * AAPL snapshot 899 s old) read as "just now". This file pins the shared
 * helpers, the badge and the stale-data banner:
 *   - a vendor time renders as "Quote as of HH:MM";
 *   - no vendor time renders the plan's delay, never a time;
 *   - a page that does not pass a quote time keeps the old badge.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";

import { LiveBadge, badgeLabel, formatBadgeTime } from "@/components/LiveBadge";
import { StaleDataBanner } from "@/components/StaleDataBanner";
import {
  PRICE_DELAY_NOTE,
  PRICE_DELAY_PHRASE,
  parseQuoteAt,
  quoteTimeNote,
} from "@/lib/freshness";

const QUOTE = "2026-09-18T14:32:00+00:00";
const LOADED = new Date("2026-09-18T14:47:00Z");

describe("quote-time helpers", () => {
  it("parse a vendor time and refuse junk", () => {
    expect(parseQuoteAt(QUOTE)?.toISOString()).toBe("2026-09-18T14:32:00.000Z");
    expect(parseQuoteAt(null)).toBeNull();
    expect(parseQuoteAt(undefined)).toBeNull();
    expect(parseQuoteAt("")).toBeNull();
    expect(parseQuoteAt("not a date")).toBeNull();
  });

  it("say the quote time when there is one, else the delay", () => {
    expect(quoteTimeNote(QUOTE, formatBadgeTime)).toBe(
      `Quote as of ${formatBadgeTime(new Date(QUOTE))}`,
    );
    expect(quoteTimeNote(null, formatBadgeTime)).toBe(PRICE_DELAY_NOTE);
    expect(quoteTimeNote("garbage", formatBadgeTime)).toBe(PRICE_DELAY_NOTE);
  });
});

describe("LiveBadge with a quote time", () => {
  it("adds the vendor's quote time beside the page-load time", () => {
    const { text } = badgeLabel("connected", LOADED, LOADED.getTime(), QUOTE);
    expect(text).toBe(
      `Updated ${formatBadgeTime(LOADED)} · Quote as of ${formatBadgeTime(new Date(QUOTE))}`,
    );
  });

  it("states the delay, not a time, when the vendor gave none", () => {
    const { text } = badgeLabel("connected", LOADED, LOADED.getTime(), null);
    expect(text).toBe(`Updated ${formatBadgeTime(LOADED)} · ${PRICE_DELAY_NOTE}`);
    expect(text).not.toMatch(/Quote as of/);
  });

  it("is unchanged on pages that pass no quote time", () => {
    expect(badgeLabel("connected", LOADED, LOADED.getTime()).text).toBe(
      `Updated ${formatBadgeTime(LOADED)}`,
    );
  });

  it("renders the quote time", () => {
    render(<LiveBadge status="connected" lastUpdate={LOADED} quoteAt={QUOTE} />);
    expect(screen.getByTestId("live-badge")).toHaveTextContent(
      `Quote as of ${formatBadgeTime(new Date(QUOTE))}`,
    );
  });
});

describe("StaleDataBanner", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  async function renderWith(tick: Record<string, unknown>) {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "ok", checks: { worker_last_tick: tick, database: { status: "ok" } } }),
      }),
    );
    render(<StaleDataBanner />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
  }

  it("says how old the newest vendor quote is when it knows", async () => {
    await renderWith({ status: "stale", age_seconds: 600, newest_quote_age_seconds: 1500 });
    expect(screen.getByText(/The newest price quote is ~25 min old\./)).toBeInTheDocument();
  });

  it("states the plan's delay when no price carries a vendor time", async () => {
    await renderWith({ status: "stale", age_seconds: 600, newest_quote_age_seconds: null });
    const banner = screen.getByText(/The worker last wrote scanner data ~10 min ago/);
    expect(banner).toHaveTextContent(PRICE_DELAY_PHRASE);
    expect(banner).not.toHaveTextContent(/price quote is/);
  });
});
