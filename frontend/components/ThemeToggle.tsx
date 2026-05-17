"use client";

/**
 * Theme toggle button — cycles light → dark → system → light.
 *
 * Designed for the public MarketingNav, where the only existing affordance
 * for theme was the OS preference. Logged-out visitors had no way to flip
 * the look. Logged-in users get the same control via UserChip → menu in
 * the app shell; this gives parity on the marketing surfaces.
 *
 * Why cycle-on-click instead of a dropdown:
 *   - The nav bar is tight on mobile; a 3-item menu would crowd it.
 *   - Three states fits in one icon swap with a tooltip explaining the
 *     next-state behaviour on hover.
 *   - Persists to the same `tapeline_theme` localStorage key the
 *     ThemeProvider already manages — no race, no double-source-of-truth.
 *
 * Icons are inline SVG so the bar doesn't depend on an icon font load on
 * first paint (the nav is above the fold on every page).
 */

import { useTheme, type Theme } from "@/components/ThemeProvider";

const NEXT: Record<Theme, Theme> = {
  light: "dark",
  dark: "system",
  system: "light",
};

const LABEL_NEXT: Record<Theme, string> = {
  light: "Switch to dark theme",
  dark: "Switch to system theme",
  system: "Switch to light theme",
};

const TITLE_CURRENT: Record<Theme, string> = {
  light: "Theme: light",
  dark: "Theme: dark",
  system: "Theme: system",
};

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, setTheme } = useTheme();

  return (
    <button
      type="button"
      onClick={() => setTheme(NEXT[theme])}
      aria-label={LABEL_NEXT[theme]}
      title={`${TITLE_CURRENT[theme]} · click to ${LABEL_NEXT[theme].toLowerCase().replace("switch to ", "")}`}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-md text-muted transition-colors hover:bg-panel/70 hover:text-fg ${className}`}
    >
      {theme === "light" ? <SunIcon /> : theme === "dark" ? <MoonIcon /> : <SystemIcon />}
    </button>
  );
}

function SunIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function SystemIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="4" width="18" height="12" rx="1" />
      <path d="M8 20h8M12 16v4" />
    </svg>
  );
}
