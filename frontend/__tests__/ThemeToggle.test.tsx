/**
 * ThemeToggle should:
 *   - cycle light → dark → system → light on successive clicks
 *   - expose a usable aria-label that reflects the next state
 *   - persist the choice via the ThemeProvider's localStorage key
 */
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ThemeToggle } from "@/components/ThemeToggle";

function setup() {
  return render(
    <ThemeProvider>
      <ThemeToggle />
    </ThemeProvider>,
  );
}

describe("ThemeToggle", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("defaults to system theme and exposes a switch-to-light aria-label", () => {
    setup();
    const btn = screen.getByRole("button");
    expect(btn).toHaveAttribute("aria-label", "Switch to light theme");
  });

  it("cycles system → light → dark → system on successive clicks", () => {
    setup();
    const btn = screen.getByRole("button");
    // Start: system. Click cycles to light.
    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-label", "Switch to dark theme");
    expect(window.localStorage.getItem("tapeline_theme")).toBe("light");

    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-label", "Switch to system theme");
    expect(window.localStorage.getItem("tapeline_theme")).toBe("dark");

    fireEvent.click(btn);
    expect(btn).toHaveAttribute("aria-label", "Switch to light theme");
    expect(window.localStorage.getItem("tapeline_theme")).toBe("system");
  });

  it("sets data-theme on <html> for light and dark, removes for system", () => {
    setup();
    const btn = screen.getByRole("button");
    // system → light
    fireEvent.click(btn);
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    // light → dark
    fireEvent.click(btn);
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    // dark → system removes the attribute (OS preference takes over via CSS)
    fireEvent.click(btn);
    expect(document.documentElement.getAttribute("data-theme")).toBeNull();
  });
});
