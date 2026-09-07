/**
 * LookupMeterPill is the pre-cap half of the freemium look-up meter.
 *
 * The failure it originally exists to prevent: the backend computed
 * used/limit/remaining on every free look-up and discarded them, so a free
 * user's FIRST contact with metering was the hard 402 wall at 12/12 — no
 * warning at 9, 10 or 11. That turns a normal limit into a punishment.
 *
 * THE SECOND HALF OF THAT BUG, FIXED 2026-09-07. The first fix only showed the
 * meter once three or fewer look-ups remained, so look-ups 1-8 still carried no
 * evidence an allowance existed and the meter itself appeared out of nowhere at
 * nine. A cap you can see from the start is a described product; a cap that
 * materialises near the end is a trap. It now counts up from look-up 1, and
 * names the no-account allowance so the value of having signed up is legible
 * next to the value of paying.
 *
 * The risk in fixing it is over-correcting into a growth-dark-pattern. So the
 * assertions here are two-sided:
 *   - it must APPEAR from the first look-up and state the real count, and
 *   - it must stay invisible for unmetered callers, and carry NO alarm styling
 *     and NO urgency language (COMPLIANCE_COPY_RULES R6: a factual statement of
 *     the user's own usage is permitted, manufactured pressure is not), and no
 *     market/performance claims (R1).
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { LookupMeterPill } from "@/app/app/ticker/[symbol]/page";
import { ANON_LIMITS, FREE_LIMITS } from "@/lib/pricing";

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

    it("counts from the FIRST look-up, not only once the cap is close", () => {
      // The regression: with the old remaining>3 early-return this rendered
      // nothing, so a free user saw no allowance at all for eight look-ups.
      render(
        <LookupMeterPill used={1} limit={CAP} remaining={CAP - 1} />,
      );
      expect(screen.getByText(/look-up 1 of 12 today/i)).toBeInTheDocument();
    });

    it("is visible right through the middle of the allowance", () => {
      render(<LookupMeterPill used={3} limit={CAP} remaining={9} />);
      expect(screen.getByTestId("lookup-meter")).toBeInTheDocument();
      expect(screen.getByText(/look-up 3 of 12 today/i)).toBeInTheDocument();
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

  describe("it names the no-account allowance too", () => {
    // Someone reading this meter is signed in and metered. Naming what a
    // visitor with no account gets is what makes the account itself legible as
    // a step that already bought them something — and it comes from
    // lib/pricing.ts, the only place on the client a cap may be written down
    // (see freeCapsComeFromOneSource.test.tsx).
    it("states the anonymous daily allowance", () => {
      const text =
        render(<LookupMeterPill used={2} limit={CAP} remaining={10} />)
          .container.textContent ?? "";
      expect(text).toMatch(
        new RegExp(`without an account it is ${ANON_LIMITS.dailyLookups} a day`, "i"),
      );
    });

    it("reads both allowances out of lib/pricing rather than restating them", () => {
      // Discriminating: the anonymous cap (2) and the free cap (12) are
      // different numbers, so a page that printed one where the other belongs
      // fails here rather than passing by coincidence.
      expect(ANON_LIMITS.dailyLookups).not.toBe(FREE_LIMITS.dailyLookups);
      const text =
        render(
          <LookupMeterPill
            used={1}
            limit={FREE_LIMITS.dailyLookups}
            remaining={FREE_LIMITS.dailyLookups - 1}
          />,
        ).container.textContent ?? "";
      expect(text).toContain(`of ${FREE_LIMITS.dailyLookups} today`);
      expect(text).toContain(`${ANON_LIMITS.dailyLookups} a day`);
    });
  });
});
