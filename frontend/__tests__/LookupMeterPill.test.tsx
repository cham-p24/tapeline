/**
 * LookupMeterPill is the pre-cap half of the freemium look-up meter.
 *
 * The failure it exists to prevent: the backend computed used/limit/remaining
 * on every free look-up and discarded them, so a free user's FIRST contact
 * with metering was the hard 402 wall at 12/12 — no warning at 9, 10 or 11.
 * That turns a normal limit into a punishment.
 *
 * The risk in fixing it is over-correcting into a growth-dark-pattern. So the
 * assertions here are two-sided:
 *   - it must APPEAR near the cap and state the real count, and
 *   - it must stay invisible with runway / for unmetered callers, and carry
 *     NO alarm styling and NO urgency language (COMPLIANCE_COPY_RULES R6:
 *     a factual statement of the user's own usage is permitted, manufactured
 *     pressure is not), and no market/performance claims (R1).
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import {
  LookupMeterPill,
  LOOKUP_METER_REMAINING_THRESHOLD,
} from "@/app/app/ticker/[symbol]/page";

const CAP = 12;

describe("LookupMeterPill", () => {
  describe("visibility", () => {
    it("renders the real count once the caller is near the cap", () => {
      render(<LookupMeterPill used={9} limit={CAP} remaining={3} />);
      expect(screen.getByText(/look-up 9 of 12 today/i)).toBeInTheDocument();
    });

    it("still renders — calmly — on the last allowed look-up", () => {
      render(<LookupMeterPill used={12} limit={CAP} remaining={0} />);
      expect(screen.getByText(/look-up 12 of 12 today/i)).toBeInTheDocument();
    });

    it("stays hidden while the caller has runway", () => {
      const { container } = render(
        <LookupMeterPill
          used={CAP - LOOKUP_METER_REMAINING_THRESHOLD - 1}
          limit={CAP}
          remaining={LOOKUP_METER_REMAINING_THRESHOLD + 1}
        />,
      );
      expect(container).toBeEmptyDOMElement();
    });

    it("stays hidden for unmetered callers (paid / trial / grace)", () => {
      // limit === null is the UNLIMITED sentinel from the API.
      const { container } = render(
        <LookupMeterPill used={0} limit={null} remaining={null} />,
      );
      expect(container).toBeEmptyDOMElement();
    });

    it("stays hidden when remaining is unknown", () => {
      const { container } = render(
        <LookupMeterPill used={4} limit={CAP} remaining={null} />,
      );
      expect(container).toBeEmptyDOMElement();
    });
  });

  describe("treatment stays calm (R6)", () => {
    it("uses no red / warn / alarm styling and no animation", () => {
      const { container } = render(
        <LookupMeterPill used={12} limit={CAP} remaining={0} />,
      );
      const markup = container.innerHTML;
      // The app's alarm tones: `down` is the loss/red token, `warn` the amber.
      expect(markup).not.toMatch(/text-down|bg-down|border-down/);
      expect(markup).not.toMatch(/text-warn|bg-warn|border-warn/);
      expect(markup).not.toMatch(/text-red|bg-red|border-red/);
      // No pulsing / ticking treatment.
      expect(markup).not.toMatch(/animate-/);
    });

    it("carries no urgency, scarcity or pressure language", () => {
      const text =
        render(<LookupMeterPill used={11} limit={CAP} remaining={1} />)
          .container.textContent ?? "";
      expect(text).not.toMatch(
        /running out|hurry|act now|last chance|don't miss|expires? in|only \d+|\d+ left|limited time/i,
      );
      // No countdown seconds and no exclamatory pressure.
      expect(text).not.toMatch(/\b\d+:\d\d\b/);
      expect(text).not.toContain("!");
    });

    it("describes the plans without implying a market outcome (R1)", () => {
      const text =
        render(<LookupMeterPill used={10} limit={CAP} remaining={2} />)
          .container.textContent ?? "";
      expect(text).not.toMatch(
        /\b(buy|sell|recommend|guaranteed|should|beat|outperform|winning|profit|returns?)\b/i,
      );
      // It does say what the limit is and that the count resets — the calm,
      // factual framing that keeps the free tier feeling usable.
      expect(text).toMatch(/resets tomorrow/i);
      expect(text).toMatch(/not metered/i);
    });
  });

  it("links to plans with a plain, non-pressuring link", () => {
    render(<LookupMeterPill used={9} limit={CAP} remaining={3} />);
    expect(
      screen.getByRole("link", { name: /compare plans/i }),
    ).toHaveAttribute("href", "/pricing");
  });
});
