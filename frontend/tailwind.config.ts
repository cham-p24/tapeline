import type { Config } from "tailwindcss";

/**
 * Tapeline Tailwind config.
 *
 * Theming: colour names map to CSS variables defined in `globals.css`, so
 * `bg-background`, `text-fg`, `border-border`, etc. all resolve at runtime
 * to the active light/dark theme. Flipping `data-theme` on <html> switches
 * the whole UI in one go.
 *
 * The 'rgb(<r g b>)' syntax with Tailwind's alpha modifier means
 * `bg-accent/20` still works — Tailwind injects the alpha into the
 * `rgb(... / <alpha>)` slot at build time. The few semi-transparent tokens
 * (panel, border, shadow) ship as `rgb(... / <a>)` directly because we
 * want a fixed alpha regardless of utility class.
 */
const tokenRgb = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;
const tokenWithAlpha = (name: string) => `rgb(var(--${name}))`;

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // iOS-first system stack so the app inherits SF Pro on Apple devices
        // and Segoe UI Variable on Windows 11. Inter (self-hosted via
        // next/font, exposed as the --font-inter CSS var) remains the explicit
        // web font for non-system browsers; the system-ui keyword does the
        // right thing on macOS / iOS / iPadOS.
        sans: [
          "var(--font-inter)",
          "-apple-system",
          "BlinkMacSystemFont",
          "Inter",
          "Segoe UI Variable",
          "Segoe UI",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
        mono: ["var(--font-jetbrains-mono)", "JetBrains Mono", "ui-monospace", "monospace"],
      },
      colors: {
        // Tokens with full RGB triplet — Tailwind's <alpha-value> slot
        // lets utilities like `bg-accent/20` compose alpha at build time.
        background: tokenRgb("background"),
        surface:    tokenRgb("surface"),
        fg:         tokenRgb("fg"),
        muted:      tokenRgb("muted"),
        subtle:     tokenRgb("subtle"),
        accent:     tokenRgb("accent"),
        // `accent2` — gradient pair for accent. iOS systemIndigo. Used in
        // `from-accent to-accent2` button + badge gradients across the
        // marketing surfaces. Was missing before; gradients silently fell
        // back to flat accent.
        accent2:    tokenRgb("accent2"),
        up:         tokenRgb("up"),
        down:       tokenRgb("down"),
        // iOS systemYellow / amber. Used for CAUTION-tier signal pills,
        // warning banners, trial-ending callouts. Adapts per theme:
        // darker amber on light bg (for readable contrast against white),
        // brighter amber on dark bg (matches iOS dark-mode systemYellow).
        warn:       tokenRgb("warn"),
        // Tokens that ship with built-in alpha — surface tints + the
        // hairline divider. Alpha modifiers won't compose on these; use a
        // different utility (`bg-fg/10` etc.) if you need a custom alpha.
        panel:   tokenWithAlpha("panel"),
        // `panel2` — one shade deeper than panel. For nested surfaces
        // (input fields inside cards, the "Everything in Pro" strip inside
        // the pricing card, etc.). Previously undefined.
        panel2:  tokenWithAlpha("panel2"),
        border:  tokenWithAlpha("border"),
        // `border2` — emphasised border, more visible than the hairline.
        // For interactive elements that need a tactile edge (pricing card
        // CTA buttons, etc.). Previously undefined.
        border2: tokenWithAlpha("border2"),
      },
      boxShadow: {
        // iOS-style elevation. Soft, low-spread, biased toward dark on
        // light bg (and barely visible on dark — the panel tint does the
        // lift in dark mode).
        sm:  "0 1px 2px rgb(var(--shadow))",
        DEFAULT: "0 4px 12px rgb(var(--shadow))",
        md:  "0 6px 20px rgb(var(--shadow))",
        lg:  "0 12px 36px rgb(var(--shadow))",
      },
      borderRadius: {
        // iOS uses larger radii than typical web (corner radius 12-22px on
        // standard cards/buttons). Adding a `xl` step so common widgets
        // can pick a slightly chunkier corner.
        xl: "14px",
        "2xl": "18px",
        "3xl": "22px",
      },
    },
  },
  plugins: [],
};

export default config;
