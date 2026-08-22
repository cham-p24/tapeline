/**
 * Where the card-gate verdict comes from, and — far more important — every
 * way it must come back FALSE.
 *
 * UserProvider is the single place the browser learns whether an account owes
 * us a card. The wall routes off it, so a false positive here is a
 * bait-and-switch on a grandfathered user who signed up under "free, no card".
 * Every unknown must therefore resolve to "not gated": no session, an API that
 * 500s, an API that can't be reached, a payload minted before the field
 * existed. The only thing that produces a wall is the server saying so.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";

const sessionMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/auth")>();
  return {
    ...actual,
    authApi: { ...actual.authApi, session: sessionMock, signout: vi.fn() },
  };
});

const OLD_ACCOUNT = {
  id: "u_old",
  email: "old@example.com",
  name: null,
  tier: "free" as const,
  created_at: "2026-03-01T00:00:00Z",
};

/**
 * Renders the real provider with a probe that prints the resolved verdict, so
 * the assertions read off the DOM rather than reaching into internals.
 *
 * Both halves come from the SAME dynamic import: `vi.resetModules()` between
 * tests means a top-level `useUser` would belong to a different module
 * instance than the freshly-imported provider, and would silently read the
 * default context instead.
 */
async function renderProvider() {
  const { UserProvider, useUser } = await import("@/components/UserContext");
  function Probe() {
    const { loading, mustAddCard } = useUser();
    return <div data-testid="verdict">{loading ? "loading" : mustAddCard ? "gated" : "open"}</div>;
  }
  // `act` around the mount so the async verdict (session → /api/me → state)
  // settles inside React's batching rather than after the assertion.
  let result!: ReturnType<typeof render>;
  await act(async () => {
    result = render(
      <UserProvider>
        <Probe />
      </UserProvider>,
    );
  });
  return result;
}

/** Stub /api/me with a body, a status, or a thrown network error. */
function stubMe(opts: { ok?: boolean; body?: unknown; throws?: boolean } = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/me")) {
        if (opts.throws) return Promise.reject(new Error("offline"));
        return Promise.resolve({
          ok: opts.ok ?? true,
          status: opts.ok === false ? 500 : 200,
          json: () => Promise.resolve(opts.body ?? {}),
        });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) });
    }),
  );
}

const verdict = () => screen.getByTestId("verdict").textContent;

beforeEach(() => {
  vi.resetModules();
  sessionMock.mockReset();
  stubMe();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("card gate — resolving the verdict", () => {
  it("gates when /api/me says so", async () => {
    sessionMock.mockResolvedValue({ user: { ...OLD_ACCOUNT, id: "u_new" } });
    stubMe({ body: { authenticated: true, must_add_card: true } });
    await renderProvider();
    await waitFor(() => expect(verdict()).toBe("gated"));
  });

  it("does NOT gate when /api/me says false — the grandfathered account", async () => {
    sessionMock.mockResolvedValue({ user: OLD_ACCOUNT });
    stubMe({ body: { authenticated: true, must_add_card: false } });
    await renderProvider();
    await waitFor(() => expect(verdict()).toBe("open"));
  });

  it("prefers the session payload when it carries the field, and skips /api/me", async () => {
    sessionMock.mockResolvedValue({ user: { ...OLD_ACCOUNT, must_add_card: false } });
    stubMe({ body: { must_add_card: true } }); // must be ignored
    await renderProvider();
    await waitFor(() => expect(verdict()).toBe("open"));
    const calls = (global.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls;
    expect(calls.some((c) => String(c[0]).includes("/api/me"))).toBe(false);
  });
});

describe("card gate — every unknown fails open", () => {
  it("signed out", async () => {
    sessionMock.mockResolvedValue({ user: null });
    await renderProvider();
    await waitFor(() => expect(verdict()).toBe("open"));
  });

  it("a payload minted before the field existed", async () => {
    sessionMock.mockResolvedValue({ user: OLD_ACCOUNT });
    stubMe({ body: { authenticated: true } }); // no must_add_card at all
    await renderProvider();
    await waitFor(() => expect(verdict()).toBe("open"));
  });

  it("/api/me returns an error status", async () => {
    sessionMock.mockResolvedValue({ user: OLD_ACCOUNT });
    stubMe({ ok: false });
    await renderProvider();
    await waitFor(() => expect(verdict()).toBe("open"));
  });

  it("/api/me is unreachable", async () => {
    sessionMock.mockResolvedValue({ user: OLD_ACCOUNT });
    stubMe({ throws: true });
    await renderProvider();
    await waitFor(() => expect(verdict()).toBe("open"));
  });

  it("the session call itself fails", async () => {
    sessionMock.mockRejectedValue(new Error("boom"));
    await renderProvider();
    await waitFor(() => expect(verdict()).toBe("open"));
  });

  it("a truthy-but-not-true value is not a gate", async () => {
    sessionMock.mockResolvedValue({ user: OLD_ACCOUNT });
    stubMe({ body: { must_add_card: "yes" } });
    await renderProvider();
    await waitFor(() => expect(verdict()).toBe("open"));
  });
});

describe("card gate — the loading contract", () => {
  it("stays 'loading' until the verdict is in, so nothing renders on a guess", async () => {
    let release: (v: { user: typeof OLD_ACCOUNT }) => void = () => {};
    sessionMock.mockReturnValue(new Promise((r) => { release = r; }));
    await renderProvider();
    expect(verdict()).toBe("loading");
    await act(async () => { release({ user: OLD_ACCOUNT }); });
    await waitFor(() => expect(verdict()).toBe("open"));
  });
});
