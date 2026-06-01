import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// jsdom doesn't implement matchMedia. Components read it on mount —
// ThemeProvider (prefers-color-scheme), FadeIn + useCountUp (prefers-reduced-
// motion), ExitIntentModal (pointer: coarse) — and throw without this stub.
// `matches: false` is the safe default; the affected tests assert on cycle
// logic / rendered copy, not on the resolved media value.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  configurable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(), // legacy API — some libs still call it
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(() => false),
  })),
});

// Stub Next.js navigation hooks (jsdom doesn't have them)
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/",
}));

// Stub Next.js Link to a plain anchor for snapshot stability
vi.mock("next/link", () => ({
  default: ({ children, href, ...rest }: any) => {
    const anchor = require("react").createElement(
      "a", { href, ...rest }, children,
    );
    return anchor;
  },
}));

// Default fetch mock — individual tests can override
global.fetch = vi.fn(() =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({}),
  })
) as any;
