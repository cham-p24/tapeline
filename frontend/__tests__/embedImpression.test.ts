/**
 * Embed-impression tracking (lib/embedImpression.ts).
 *
 * The badge SVG and the iframe widget are rendered on OTHER people's sites.
 * Tracking those renders must:
 *   - persist the embedding HOSTNAME ONLY (a referring URL's path/query can
 *     carry a search phrase, a title, or a session token from that site)
 *   - skip renders that carry no signal: no referer, tapeline.io itself,
 *     localhost
 *   - never throw — a failing tracker must not break the embed it rides on
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  recordEmbedImpression,
  refererHost,
  trackEmbedImpression,
} from "@/lib/embedImpression";

describe("refererHost", () => {
  it("keeps only the hostname of a URL carrying a path and query string", () => {
    const host = refererHost(
      "https://blog.example.com/posts/why-i-track-nvda?user=jsmith&token=sekret#top",
    );
    expect(host).toBe("blog.example.com");
    expect(host).not.toContain("/posts");
    expect(host).not.toContain("jsmith");
    expect(host).not.toContain("sekret");
  });

  it("treats www.example.com and example.com as one site", () => {
    expect(refererHost("https://www.example.com/x")).toBe("example.com");
  });

  it("skips a missing or unparseable referer", () => {
    expect(refererHost(null)).toBeNull();
    expect(refererHost(undefined)).toBeNull();
    expect(refererHost("")).toBeNull();
    expect(refererHost("   ")).toBeNull();
    expect(refererHost("not a url")).toBeNull();
  });

  it("skips self-referral — our own pages aren't a distribution signal", () => {
    expect(refererHost("https://tapeline.io/embed")).toBeNull();
    expect(refererHost("https://www.tapeline.io/t/NVDA")).toBeNull();
    expect(refererHost("https://api.tapeline.io/docs")).toBeNull();
  });

  it("skips local/dev renders", () => {
    expect(refererHost("http://localhost:3000/embed")).toBeNull();
    expect(refererHost("http://127.0.0.1:3000/")).toBeNull();
    expect(refererHost("http://mymac.local/page")).toBeNull();
  });

  it("caps the stored host length", () => {
    const host = refererHost(`https://${"a".repeat(400)}.example.com/`);
    expect(host === null || host.length <= 100).toBe(true);
  });
});

describe("recordEmbedImpression", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts the hostname only — never the full referring URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await recordEmbedImpression(
      "https://blog.example.com/posts/nvda?user=jsmith",
      "nvda",
      "badge",
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/api/embed/impression");
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body).toEqual({
      host: "blog.example.com",
      symbol: "NVDA",
      surface: "badge",
    });
    // Nothing beyond the hostname may cross the wire.
    expect((init as RequestInit).body).not.toContain("/posts");
    expect((init as RequestInit).body).not.toContain("jsmith");
  });

  it("does not spend a request on a skipped referer", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await recordEmbedImpression(null, "NVDA", "badge");
    await recordEmbedImpression("https://tapeline.io/embed", "NVDA", "iframe");
    await recordEmbedImpression("http://localhost:3000/", "NVDA", "badge");

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("never throws when the backend fails — the embed still renders", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("backend down"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      recordEmbedImpression("https://blog.example.com/x", "NVDA", "iframe"),
    ).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("trackEmbedImpression", () => {
  it("does not throw when called outside a request scope", () => {
    // `after()` throws without a request scope. The embed surfaces call this
    // helper synchronously on the render path, so it swallowing that is the
    // difference between "no impression counted" and "badge fails to render".
    expect(() =>
      trackEmbedImpression("https://blog.example.com/x", "NVDA", "badge"),
    ).not.toThrow();
  });
});
