/**
 * StatsStrip is the observability strip at the top of the admin inbox page.
 *
 * These tests cover the LLM-error signal added alongside backend PR #292
 * (llm_errors_24h / llm_attempts_24h / llm_error_rate / last_error_at). The
 * point of that signal is to make SILENT classifier degradation visible: on
 * the $0-Anthropic-credit incident every classify call 401'd but the bot
 * looked "up" because tier counts kept moving. So we assert:
 *   - errors > 0 → a loud red banner naming the count + last-error time
 *   - errors > 0 → a subtle "LLM errors" chip with the count
 *   - errors === 0 but attempts > 0 → no banner, chip reads a healthy "0"
 *   - attempts === 0 → chip hidden (nothing to report yet)
 */
import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { StatsStrip } from "@/app/app/inbox/page";

// A fully-populated, healthy baseline. Each test overrides only the LLM-health
// fields it cares about so the assertions stay focused on the new signal.
function makeStats(overrides: Record<string, unknown> = {}) {
  return {
    today_spend_usd: 0.12,
    today_classifications: 10,
    cap_usd: 5,
    cap_tripped: false,
    llm_errors_24h: 0,
    llm_attempts_24h: 10,
    llm_error_rate: 0,
    last_error_at: null,
    tier_counts_today: { "1": 1, "2": 2, "3": 3, unclassified: 0 },
    tier_counts_last_7d: { "1": 1, "2": 2, "3": 3, unclassified: 0 },
    channel_counts_today: {},
    status_counts_today: {},
    latency_p50_ms: 800,
    latency_p95_ms: 1200,
    cache_hit_ratio: 0.95,
    pending_count: 0,
    bot_enabled: true,
    dry_run: false,
    ...overrides,
  } as any;
}

describe("StatsStrip LLM-error signal", () => {
  it("shows a loud banner + chip with count and last-error time when errors > 0", () => {
    // 2026-06-16T14:05 UTC → formatted as local HH:MM. We assert on the
    // count and the surrounding copy rather than the exact clock value so the
    // test isn't coupled to the runner's timezone.
    render(
      <StatsStrip
        stats={makeStats({
          llm_errors_24h: 3,
          llm_attempts_24h: 12,
          llm_error_rate: 0.25,
          last_error_at: "2026-06-16T14:05:00Z",
        })}
      />,
    );

    // Loud banner: names the count + the 24h/total context + error rate.
    expect(screen.getByText(/LLM errors: 3/)).toBeInTheDocument();
    expect(
      screen.getByText(/3 of 12 classifier calls failed in the last 24h \(25% error rate\)/),
    ).toBeInTheDocument();

    // Subtle chip: count is rendered in the down/red tone alongside attempts.
    const chip = screen.getByText("LLM errors").closest("div") as HTMLElement;
    expect(within(chip).getByText("3")).toBeInTheDocument();
    expect(within(chip).getByText(/\/ 12/)).toBeInTheDocument();
    // The "last <time>" hint is present (HH:MM, runner-tz-dependent).
    expect(within(chip).getByText(/last \d{1,2}:\d{2}/)).toBeInTheDocument();
  });

  it("renders no error banner and a healthy chip when errors === 0 but attempts > 0", () => {
    render(<StatsStrip stats={makeStats({ llm_errors_24h: 0, llm_attempts_24h: 10 })} />);

    expect(screen.queryByText(/LLM errors: /)).not.toBeInTheDocument();

    const chip = screen.getByText("LLM errors").closest("div") as HTMLElement;
    expect(within(chip).getByText("0")).toBeInTheDocument();
    expect(within(chip).getByText(/\/ 10/)).toBeInTheDocument();
  });

  it("hides the LLM-errors chip entirely when no classifier calls were attempted", () => {
    render(<StatsStrip stats={makeStats({ llm_errors_24h: 0, llm_attempts_24h: 0 })} />);

    expect(screen.queryByText("LLM errors")).not.toBeInTheDocument();
    expect(screen.queryByText(/LLM errors: /)).not.toBeInTheDocument();
  });

  it("keeps the error copy descriptive, not prescriptive", () => {
    const { container } = render(
      <StatsStrip
        stats={makeStats({
          llm_errors_24h: 1,
          llm_attempts_24h: 5,
          llm_error_rate: 0.2,
          last_error_at: "2026-06-16T09:00:00Z",
        })}
      />,
    );
    // No buy/sell-style prescriptive language leaks into operator copy.
    expect(container.textContent ?? "").not.toMatch(/\b(buy|sell|guaranteed)\b/i);
  });
});
