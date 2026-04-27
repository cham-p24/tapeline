import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

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
