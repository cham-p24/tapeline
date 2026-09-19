/**
 * A price's age is the VENDOR's time for it (`quote_at`), never Tapeline's
 * write time (`updated_at`).
 *
 * Before migration 0075 every in-app "As of" read `updated_at`, which the
 * worker re-stamps on every pass even for a row the vendor returned nothing
 * for, so a price about 15 minutes old (Stocks Starter, measured 14 Sep 2026:
 * AAPL snapshot 899 s old) read as "just now". This file pins the shared
 * helpers, the badge and the stale-data banner:
 *   - a vendor time renders as an AGE ("Quote as of 15m ago"), never a bare
 *     clock time, so a Friday or day-old crypto close cannot read as today's;
 *   - no vendor time renders the no-time note ("... or more"), never a time;
 *   - a crypto pair gets crypto wording both ways, never the stock delay;
 *   - a page that does not pass a quote time keeps the old badge.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";

import { LiveBadge, badgeLabel, formatBadgeTime } from "@/components/LiveBadge";
import { StaleDataBanner } from "@/components/StaleDataBanner";
import {
  CRYPTO_CADENCE_PHRASE,
  CRYPTO_QUOTE_UNKNOWN_NOTE,
  PRICE_DELAY_NOTE,
  PRICE_DELAY_PHRASE,
  QUOTE_TIME_UNKNOWN_NOTE,
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

  it("say the quote time when there is one, else the no-time note", () => {
    const fmt = (d: Date) => d.toISOString();
    expect(quoteTimeNote(QUOTE, fmt)).toBe("Quote as of 2026-09-18T14:32:00.000Z");
    expect(quoteTimeNote(null, fmt)).toBe(QUOTE_TIME_UNKNOWN_NOTE);
    expect(quoteTimeNote("garbage", fmt)).toBe(QUOTE_TIME_UNKNOWN_NOTE);
    // With no time the age is unknown: the plan's delay is a floor, not a fact.
    expect(QUOTE_TIME_UNKNOWN_NOTE).toBe(`${PRICE_DELAY_NOTE} or more`);
  });

  it("never state the stock delay for a crypto pair", () => {
    const fmt = (d: Date) => d.toISOString();
    expect(quoteTimeNote(null, fmt, { crypto: true })).toBe(CRYPTO_QUOTE_UNKNOWN_NOTE);
    expect(CRYPTO_QUOTE_UNKNOWN_NOTE).toContain(CRYPTO_CADENCE_PHRASE);
    expect(CRYPTO_QUOTE_UNKNOWN_NOTE).not.toContain(PRICE_DELAY_PHRASE);
    expect(quoteTimeNote(QUOTE, fmt, { crypto: true })).toBe(
      "Daily close as of 2026-09-18T14:32:00.000Z",
    );
  });
});

describe("LiveBadge with a quote time", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(LOADED);
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("adds the vendor's quote time, as an age, beside the page-load time", () => {
    const { text } = badgeLabel("connected", LOADED, LOADED.getTime(), QUOTE);
    expect(text).toBe(`Updated ${formatBadgeTime(LOADED)} · Quote as of 15m ago`);
  });

  it("never prints an old quote as a bare clock time", () => {
    // Friday's close viewed on Sunday, or a day-old crypto close: a clock
    // time alone ("14:32") would read as today's.
    const old = "2026-09-16T14:32:00+00:00";
    const { text } = badgeLabel("connected", LOADED, LOADED.getTime(), old);
    expect(text).toBe(`Updated ${formatBadgeTime(LOADED)} · Quote as of 2d ago`);
    expect(text).not.toContain(formatBadgeTime(new Date(old)));
    const crypto = badgeLabel("connected", LOADED, LOADED.getTime(), old, true).text;
    expect(crypto).toBe(`Updated ${formatBadgeTime(LOADED)} · Daily close as of 2d ago`);
  });

  it("states the no-time note, not a time, when the vendor gave none", () => {
    const { text } = badgeLabel("connected", LOADED, LOADED.getTime(), null);
    expect(text).toBe(`Updated ${formatBadgeTime(LOADED)} · ${QUOTE_TIME_UNKNOWN_NOTE}`);
    expect(text).not.toMatch(/Quote as of/);
  });

  it("gives a crypto pair with no time the crypto note, not the stock delay", () => {
    const { text } = badgeLabel("connected", LOADED, LOADED.getTime(), null, true);
    expect(text).toBe(`Updated ${formatBadgeTime(LOADED)} · ${CRYPTO_QUOTE_UNKNOWN_NOTE}`);
    expect(text).not.toContain(PRICE_DELAY_PHRASE);
  });

  it("is unchanged on pages that pass no quote time", () => {
    expect(badgeLabel("connected", LOADED, LOADED.getTime()).text).toBe(
      `Updated ${formatBadgeTime(LOADED)}`,
    );
  });

  it("renders the quote time", () => {
    render(<LiveBadge status="connected" lastUpdate={LOADED} quoteAt={QUOTE} />);
    expect(screen.getByTestId("live-badge")).toHaveTextContent("Quote as of 15m ago");
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
