/**
 * The persistent general-information statement must:
 *   - state all four required points in plain English
 *   - be a static, non-dismissible part of the page chrome (not a modal,
 *     no dismiss control, no dialog role)
 *   - be reachable as a labelled landmark
 *
 * The assertions below are deliberately about the SUBSTANCE, not the exact
 * wording — but each required point is legally load-bearing, so a copy edit
 * that drops one should fail here rather than ship.
 *
 * See docs/COMPLIANCE_COPY_RULES.md. Note Rule 9: this notice is additional
 * to compliant copy, never a substitute for it.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { GeneralInformationNotice } from "@/components/GeneralInformationNotice";

describe("GeneralInformationNotice", () => {
  it("says the product is general information and descriptive analytics", () => {
    render(<GeneralInformationNotice />);
    expect(
      screen.getByText(/general information and descriptive analytics/i),
    ).toBeInTheDocument();
  });

  it("says it is not financial advice and issues no recommendations", () => {
    const { container } = render(<GeneralInformationNotice />);
    const text = container.textContent ?? "";
    expect(text).toMatch(/not financial, investment, tax or legal advice/i);
    expect(text).toMatch(/no score, signal, label or list is a recommendation/i);
    expect(text).toMatch(/buy, sell or hold/i);
  });

  it("says it does not consider the reader's objectives or circumstances", () => {
    const { container } = render(<GeneralInformationNotice />);
    expect(container.textContent ?? "").toMatch(
      /do not know your objectives, financial situation or needs/i,
    );
  });

  it("states that past performance is not indicative of future performance", () => {
    render(<GeneralInformationNotice />);
    expect(
      screen.getByText(/past performance is not indicative of future performance/i),
    ).toBeInTheDocument();
  });

  it("is a labelled landmark rather than a modal", () => {
    render(<GeneralInformationNotice />);
    expect(
      screen.getByRole("complementary", { name: /general information notice/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("cannot be dismissed — there is no close control", () => {
    render(<GeneralInformationNotice />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByText(/dismiss|close|got it|don't show/i)).not.toBeInTheDocument();
  });

  it("links to the full risk disclosure without relying on it", () => {
    render(<GeneralInformationNotice />);
    const link = screen.getByRole("link", { name: /full risk disclosure/i });
    expect(link).toHaveAttribute("href", "/legal/risk");
  });
});
