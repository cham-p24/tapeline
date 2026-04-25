import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      colors: {
        background: "#0a0a0a",
        panel: "#121214",
        border: "#1f1f23",
        muted: "#9ca3af",
        fg: "#f4f4f5",
        up: "#10b981",
        down: "#ef4444",
        accent: "#3b82f6",
      },
    },
  },
  plugins: [],
};

export default config;
