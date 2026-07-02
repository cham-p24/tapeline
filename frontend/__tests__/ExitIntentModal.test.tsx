/**
 * ExitIntentModal — last-chance email capture mounted on / and /pricing.
 * What matters:
 *   1. Renders nothing until an exit signal (it must never block the page).
 *   2. Fires when the cursor crosses the TOP viewport edge AFTER the 5s
 *      grace period — not before, and not on mouseouts elsewhere.
 *   3. Fires once per browser session — sessionStorage flag suppresses it.
 *   4. Embeds the NewsletterCapture form (the actual conversion surface).
 *   5. Close button dismisses it for good.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { ExitIntentModal } from "@/components/ExitIntentModal";

const STORAGE_KEY = "tapeline_exit_intent_shown_v1";

/** Simulate the pointer leaving the document across a given viewport y. */
function mouseOutAt(clientY: number) {
  act(() => {
    // relatedTarget defaults to null = pointer left the document entirely,
    // which is the component's strongest exit signal.
    window.dispatchEvent(new MouseEvent("mouseout", { clientY, bubbles: true }));
  });
}

/** Advance past the 5s post-mount grace period. */
function passGracePeriod() {
  act(() => {
    vi.advanceTimersByTime(5001);
  });
}

beforeEach(() => {
  sessionStorage.removeItem(STORAGE_KEY);
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("ExitIntentModal", () => {
  it("renders nothing before any exit signal", () => {
    const { container } = render(<ExitIntentModal source="pricing" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("does not fire during the 5s grace period", () => {
    render(<ExitIntentModal source="pricing" />);
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    mouseOutAt(0);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens on a top-edge exit after the grace period, with the capture form", () => {
    render(<ExitIntentModal source="pricing" />);
    passGracePeriod();
    mouseOutAt(0);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/free daily picks instead/i)).toBeInTheDocument();
    // The embedded NewsletterCapture form is live and submittable.
    expect(
      screen.getByRole("form", { name: /newsletter signup/i }),
    ).toBeInTheDocument();
    // Session flag set → won't re-fire this session.
    expect(sessionStorage.getItem(STORAGE_KEY)).toBe("1");
  });

  it("ignores mouseouts that are not at the top edge", () => {
    render(<ExitIntentModal source="homepage" />);
    passGracePeriod();
    mouseOutAt(300); // mid-viewport — e.g. moving between elements
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("stays hidden when the session flag is already set", () => {
    sessionStorage.setItem(STORAGE_KEY, "1");
    render(<ExitIntentModal source="homepage" />);
    passGracePeriod();
    mouseOutAt(0);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes via the dismiss button and stays closed", () => {
    render(<ExitIntentModal source="pricing" />);
    passGracePeriod();
    mouseOutAt(0);
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /no thanks/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    // A second exit signal must not resurrect it.
    mouseOutAt(0);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
