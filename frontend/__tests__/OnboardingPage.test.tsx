/**
 * Onboarding page should render every section + both Save and Skip buttons.
 * The form is intentionally all-optional, and Skip must always be visible
 * so we don't accidentally trap users in a forced flow.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import OnboardingPage from "@/app/app/onboarding/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => ({ get: (_: string) => null }),
}));

vi.mock("@vercel/analytics", () => ({
  track: vi.fn(),
}));

describe("OnboardingPage", () => {
  it("renders the headline + all five question prompts", () => {
    render(<OnboardingPage />);
    expect(
      screen.getByRole("heading", { name: /tell us a bit about you/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/what's your investing experience\?/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/how do you typically trade\?/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/roughly what size portfolio do you run\?/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/which sectors are you most interested in\?/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/how did you hear about tapeline\?/i),
    ).toBeInTheDocument();
  });

  it("renders both Save and Skip controls so the form is never forced", () => {
    render(<OnboardingPage />);
    expect(
      screen.getByRole("button", { name: /save and continue/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /skip for now/i }),
    ).toBeInTheDocument();
  });

  it("renders the marketing-opt-in checkbox unchecked by default (explicit consent)", () => {
    render(<OnboardingPage />);
    const checkbox = screen.getByRole("checkbox") as HTMLInputElement;
    expect(checkbox).toBeInTheDocument();
    expect(checkbox.checked).toBe(false);
  });
});
