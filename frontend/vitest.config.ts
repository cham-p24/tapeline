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
    // A timeout here catches a HANG, not slowness, and the default 5s was
    // failing correct tests whenever the machine was busy. Measured 2026-09-18
    // on the founder's 12-core machine: legalCanonicals' page walk takes 28ms at
    // the median with or without load, but under 12 parallel CPU+file-reading
    // processes its p95 was 3.7s, its p99 4.6s, and 2 of 800 runs passed 5s
    // (worst 9.1s) - with no exception and no false result in any of them. A full
    // suite under the same load failed five correct tests: four React-render
    // tests that take 1-3s normally timed out at 5s, and a fifth failed because
    // a timed-out render left its DOM behind. That is how legalCanonicals failed
    // once on 2026-09-17 while several agent processes were running. With 30s,
    // four full suites under the same load passed 5,340/5,340; the slowest tests
    // in them took 10.2s (legalCanonicals) and 13.5s (sellCopyIntegrity), both
    // failures at 5s. 30s is over twice the worst seen and still fails a hang.
    testTimeout: 30_000,
    hookTimeout: 30_000,
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
