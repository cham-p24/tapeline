/**
 * The in-app freshness badge states what the page is actually doing.
 *
 * Measured 14 Sep 2026 during the US session: /api/stream/live sent 1 hello,
 * 11 pings and 0 update events in 300s, while the old hook marked status
 * "live" on hello and ping, so every /app page showed a pulsing "Live" badge
 * and never refetched. Prices are also the vendor's ~15-minute-delayed prices.
 * The badge must never say "Live" again, and must only claim auto-refreshing
 * while update events are really arriving.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";

import { LiveBadge, badgeLabel, formatBadgeTime } from "@/components/LiveBadge";
import {
  AUTO_REFRESH_WINDOW_MS,
  COALESCE_MS,
  MIN_REFETCH_GAP_MS,
  deriveLiveStatus,
  useLiveStream,
} from "@/lib/useLiveStream";

class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  static instances: MockEventSource[] = [];
  readyState = MockEventSource.CONNECTING;
  onerror: (() => void) | null = null;
  url: string;
  private listeners = new Map<string, Array<() => void>>();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
  addEventListener(name: string, fn: () => void) {
    this.listeners.set(name, [...(this.listeners.get(name) ?? []), fn]);
  }
  close() {
    this.readyState = MockEventSource.CLOSED;
  }
  emit(name: string) {
    if (name !== "error") this.readyState = MockEventSource.OPEN;
    for (const fn of this.listeners.get(name) ?? []) fn();
  }
  fail(closed = true) {
    if (closed) this.readyState = MockEventSource.CLOSED;
    this.onerror?.();
  }
  static latest() {
    return MockEventSource.instances[MockEventSource.instances.length - 1];
  }
}

const START = new Date("2026-09-14T14:00:00Z");

function Harness({ onUpdate }: { onUpdate: () => void | Promise<unknown> }) {
  const { status, lastUpdate } = useLiveStream(onUpdate);
  return <LiveBadge status={status} lastUpdate={lastUpdate} />;
}

function badgeText() {
  return screen.getByTestId("live-badge").textContent ?? "";
}

function expectNeverLive() {
  const el = screen.getByTestId("live-badge");
  expect(el.textContent ?? "").not.toMatch(/live/i);
  expect(el.getAttribute("title") ?? "").not.toMatch(/live/i);
  expect(el.innerHTML).not.toContain("animate-pulse");
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(START);
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("LiveBadge driven by useLiveStream", () => {
  it("hello and pings only: shows 'Updated HH:MM' from the page load, never 'Live'", () => {
    const onUpdate = vi.fn();
    render(<Harness onUpdate={onUpdate} />);
    const es = MockEventSource.latest();

    act(() => es.emit("hello"));
    for (let i = 0; i < 12; i++) {
      act(() => {
        vi.advanceTimersByTime(25_000);
        es.emit("ping");
      });
      expect(badgeText()).toBe(`Updated ${formatBadgeTime(START)}`);
      expectNeverLive();
    }
    expect(onUpdate).not.toHaveBeenCalled();
  });

  it("an update event: 'Auto-refreshing · updated HH:MM' with the arrival time, and one refetch", () => {
    const onUpdate = vi.fn();
    render(<Harness onUpdate={onUpdate} />);
    const es = MockEventSource.latest();
    act(() => es.emit("hello"));

    act(() => vi.advanceTimersByTime(70_000));
    const arrived = new Date(Date.now());
    act(() => es.emit("update"));
    expect(badgeText()).toBe(`Auto-refreshing · updated ${formatBadgeTime(arrived)}`);
    expectNeverLive();

    act(() => vi.advanceTimersByTime(COALESCE_MS));
    expect(onUpdate).toHaveBeenCalledTimes(1);
  });

  it("stale: no update for longer than the window drops back to 'Updated HH:MM'", () => {
    const onUpdate = vi.fn();
    render(<Harness onUpdate={onUpdate} />);
    const es = MockEventSource.latest();
    act(() => es.emit("hello"));
    act(() => es.emit("update"));
    act(() => vi.advanceTimersByTime(COALESCE_MS));
    const loaded = new Date(Date.now());
    expect(badgeText()).toMatch(/^Auto-refreshing/);

    act(() => {
      vi.advanceTimersByTime(AUTO_REFRESH_WINDOW_MS + 30_000);
      es.emit("ping");
    });
    expect(badgeText()).toBe(`Updated ${formatBadgeTime(loaded)}`);
    expectNeverLive();
  });

  it("offline: 'Offline · updated HH:MM', then reconnects with backoff", () => {
    render(<Harness onUpdate={vi.fn()} />);
    const first = MockEventSource.latest();
    act(() => first.emit("hello"));
    act(() => first.fail(true));
    expect(badgeText()).toBe(`Offline · updated ${formatBadgeTime(START)}`);
    expectNeverLive();

    act(() => vi.advanceTimersByTime(1_000));
    expect(MockEventSource.instances.length).toBe(2);
    act(() => MockEventSource.latest().emit("hello"));
    expect(badgeText()).toBe(`Updated ${formatBadgeTime(START)}`);
  });

  it("events from one pass refetch once; a burst inside the gap gives one trailing refetch", async () => {
    const onUpdate = vi.fn(() => Promise.resolve());
    render(<Harness onUpdate={onUpdate} />);
    const es = MockEventSource.latest();
    act(() => es.emit("hello"));

    act(() => {
      es.emit("update");
      es.emit("update");
    });
    await act(async () => {
      vi.advanceTimersByTime(COALESCE_MS);
    });
    expect(onUpdate).toHaveBeenCalledTimes(1);

    // Two more events 10s and 20s later: still inside the refetch gap.
    act(() => {
      vi.advanceTimersByTime(10_000);
      es.emit("update");
    });
    act(() => {
      vi.advanceTimersByTime(10_000);
      es.emit("update");
    });
    expect(onUpdate).toHaveBeenCalledTimes(1);
    await act(async () => {
      vi.advanceTimersByTime(MIN_REFETCH_GAP_MS);
    });
    expect(onUpdate).toHaveBeenCalledTimes(2);

    // Nothing else pending.
    await act(async () => {
      vi.advanceTimersByTime(5 * 60_000);
    });
    expect(onUpdate).toHaveBeenCalledTimes(2);
  });

  it("a scanner-style callback (load('stream')) runs on update and updates the load time", async () => {
    const load = vi.fn((_source?: string) => Promise.resolve());
    render(<Harness onUpdate={() => load("stream")} />);
    const es = MockEventSource.latest();
    act(() => es.emit("hello"));
    act(() => vi.advanceTimersByTime(60_000));
    act(() => es.emit("update"));
    await act(async () => {
      vi.advanceTimersByTime(COALESCE_MS);
    });
    expect(load).toHaveBeenCalledWith("stream");
    const refetched = new Date(Date.now());

    act(() => {
      vi.advanceTimersByTime(AUTO_REFRESH_WINDOW_MS + 15_000);
    });
    expect(badgeText()).toBe(`Updated ${formatBadgeTime(refetched)}`);
  });

  it("closes the stream and pending timers on unmount", () => {
    const onUpdate = vi.fn();
    const { unmount } = render(<Harness onUpdate={onUpdate} />);
    const es = MockEventSource.latest();
    act(() => es.emit("hello"));
    act(() => es.emit("update"));
    unmount();
    expect(es.readyState).toBe(MockEventSource.CLOSED);
    vi.advanceTimersByTime(MIN_REFETCH_GAP_MS * 2);
    expect(onUpdate).not.toHaveBeenCalled();
  });
});

describe("LiveBadge rendered from props", () => {
  const t = new Date("2026-09-14T14:08:55Z");

  it.each([
    ["connecting", null],
    ["connecting", t],
    ["connected", null],
    ["connected", t],
    ["auto", t],
    ["offline", null],
    ["offline", t],
    // Legacy value still passed by some page-test mocks.
    ["live", null],
    ["live", t],
  ] as const)("never says Live or pulses (status=%s, lastUpdate=%s)", (status, lastUpdate) => {
    vi.setSystemTime(new Date(t.getTime() + 30_000));
    render(<LiveBadge status={status} lastUpdate={lastUpdate} />);
    expectNeverLive();
  });

  it("a stale 'auto' prop renders as 'Updated HH:MM'", () => {
    const now = t.getTime() + AUTO_REFRESH_WINDOW_MS + 1;
    expect(badgeLabel("auto", t, now).text).toBe(`Updated ${formatBadgeTime(t)}`);
    expect(badgeLabel("auto", t, t.getTime() + 60_000).text).toBe(
      `Auto-refreshing · updated ${formatBadgeTime(t)}`,
    );
  });

  it("the legacy 'live' status renders as connected, not live", () => {
    expect(badgeLabel("live", t, t.getTime()).text).toBe(`Updated ${formatBadgeTime(t)}`);
    expect(badgeLabel("live", null, t.getTime()).text).toBe("Connected");
  });

  it("deriveLiveStatus: pings never make 'auto'; only a recent update does", () => {
    const now = t.getTime();
    expect(deriveLiveStatus("open", null, now)).toBe("connected");
    expect(deriveLiveStatus("open", new Date(now - 60_000), now)).toBe("auto");
    expect(deriveLiveStatus("open", new Date(now - AUTO_REFRESH_WINDOW_MS - 1), now)).toBe(
      "connected",
    );
    expect(deriveLiveStatus("offline", new Date(now), now)).toBe("offline");
    expect(deriveLiveStatus("connecting", null, now)).toBe("connecting");
  });
});
