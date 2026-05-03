import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./test-setup.ts"],
    css: false,
    // Vitest auto-discovers any `*.spec.ts` file. The Playwright E2E specs
    // under `e2e/` import `@playwright/test` which Vitest can't resolve, so
    // exclude them — Playwright runs them via `npm run e2e` instead.
    exclude: ["node_modules", "dist", ".next", "e2e/**"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
