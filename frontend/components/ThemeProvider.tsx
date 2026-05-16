"use client";

/**
 * Theme provider — light / dark / system.
 *
 * Strategy:
 *   - Reads saved preference from localStorage (`tapeline_theme`).
 *   - If saved value is "light" or "dark", that wins.
 *   - If saved value is "system" (or missing), `prefers-color-scheme` decides.
 *   - Listens for OS theme changes so a system-mode user gets the
 *     switch as soon as macOS / Windows flips the system theme at sunset.
 *
 * Theming is implemented in globals.css via CSS variables. This component
 * only manages the `data-theme` attribute on <html> + persists the user's
 * choice. No re-render cost for the rest of the tree.
 *
 * Why a context + hook rather than just a button: the UserChip dropdown
 * needs to show the current selection (a check mark next to "Light" /
 * "Dark" / "System") and trigger updates. Pulling that through a context
 * is cleaner than reading localStorage on every render.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type Theme = "light" | "dark" | "system";

type Ctx = {
  theme: Theme;            // user's stored preference
  resolved: "light" | "dark"; // what's actually applied right now
  setTheme: (t: Theme) => void;
};

const ThemeCtx = createContext<Ctx>({
  theme: "system",
  resolved: "dark",
  setTheme: () => {},
});

const STORAGE_KEY = "tapeline_theme";

function getPreferredScheme(): "light" | "dark" {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme: Theme): "light" | "dark" {
  if (typeof document === "undefined") return "dark";
  const resolved: "light" | "dark" =
    theme === "system" ? getPreferredScheme() : theme;
  // When in system mode we DON'T set data-theme — letting the CSS
  // prefers-color-scheme media query take over so the OS-level Dark
  // Mode toggle is respected without a page reload.
  if (theme === "system") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.setAttribute("data-theme", theme);
  }
  return resolved;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // Default to "system" on SSR so the first paint matches the OS theme.
  const [theme, setThemeState] = useState<Theme>("system");
  const [resolved, setResolved] = useState<"light" | "dark">("dark");

  // On mount: hydrate from localStorage and apply.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = (window.localStorage.getItem(STORAGE_KEY) || "system") as Theme;
    setThemeState(saved);
    setResolved(applyTheme(saved));
  }, []);

  // Listen for OS theme changes — only relevant in system mode.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if (theme === "system") setResolved(applyTheme("system"));
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [theme]);

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t);
    setResolved(applyTheme(t));
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, t);
    }
  }, []);

  const value = useMemo(() => ({ theme, resolved, setTheme }), [theme, resolved, setTheme]);
  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>;
}

export function useTheme() {
  return useContext(ThemeCtx);
}

/**
 * Pre-hydration script — sets data-theme on <html> from localStorage
 * BEFORE React mounts, so users with a saved "light" preference don't
 * see a dark-mode flash on first paint. Inject this in the <head> of
 * the root layout via dangerouslySetInnerHTML.
 *
 * Kept here so the storage key + decode logic stay in one file.
 */
export const themeBootScript = `
(function() {
  try {
    var t = localStorage.getItem('${STORAGE_KEY}') || 'system';
    if (t === 'light' || t === 'dark') {
      document.documentElement.setAttribute('data-theme', t);
    }
  } catch (e) {}
})();
`;
