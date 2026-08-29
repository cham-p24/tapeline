/**
 * Two audit findings from 2026-08-29, pinned so they can't silently return.
 *
 * 1. NO WEB APP MANIFEST. `app/app/billing/page.tsx` tells customers, on the
 *    paid-upgrade page: "Lock-screen notifications on desktop and Android.
 *    iOS requires the PWA to be installed." There was no manifest at all —
 *    GET /manifest.webmanifest returned 404 and no <link rel="manifest"> was
 *    emitted — so on iOS "Add to Home Screen" made a Safari bookmark, not a
 *    web app, and a bookmark cannot register for push. The billing page was
 *    selling an iOS capability that could not be reached.
 *
 * 2. NO DEFAULT og:image. The root layout declared `openGraph` WITHOUT an
 *    `images` key, which suppresses Next's file-convention inheritance for
 *    descendant routes. 236 of 313 pages emitted no og:image while
 *    `twitter.card` still claimed "summary_large_image" — a large-image card
 *    with no image renders as a bare grey box on X, LinkedIn, Slack and
 *    iMessage.
 */
import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import manifest from "../app/manifest";

const APP = join(__dirname, "..", "app");

describe("web app manifest", () => {
  const m = manifest();

  it("declares standalone display — the field iOS push depends on", () => {
    // iOS only grants the Push API to a Home Screen web app running
    // standalone. `browser` (the default with no manifest) does not qualify,
    // which is exactly why the billing page's promise was unreachable.
    expect(m.display).toBe("standalone");
  });

  it("ships raster icons, because manifests cannot install from SVG alone", () => {
    expect(m.icons?.length).toBeGreaterThan(0);
    for (const icon of m.icons ?? []) {
      expect(icon.type).toBe("image/png");
      expect(icon.sizes).toBeTruthy();
    }
    // Android's install prompt needs a maskable icon or it letterboxes the
    // mark inside its own shape.
    expect((m.icons ?? []).some((i) => i.purpose === "maskable")).toBe(true);
  });

  it("starts in the app, not on the marketing page", () => {
    expect(m.start_url).toBe("/app");
    expect(m.scope).toBe("/");
  });

  it("has a name and short_name — both required for an install prompt", () => {
    expect(m.name).toBeTruthy();
    expect(m.short_name).toBeTruthy();
    // Home Screen labels truncate hard; anything longer is ellipsised.
    expect((m.short_name ?? "").length).toBeLessThanOrEqual(12);
  });
});

describe("icon routes backing the manifest", () => {
  it("app/icon.tsx exists and renders a PNG", () => {
    const src = readFileSync(join(APP, "icon.tsx"), "utf8");
    expect(src).toMatch(/contentType\s*=\s*"image\/png"/);
    expect(src).toMatch(/ImageResponse/);
  });

});

describe("default social card", () => {
  const layout = readFileSync(join(APP, "layout.tsx"), "utf8");

  it("root openGraph declares images", () => {
    // Without this key, declaring `openGraph` at all suppresses the
    // file-convention og:image for every descendant route.
    const og = layout.slice(layout.indexOf("openGraph:"), layout.indexOf("twitter:"));
    expect(og).toMatch(/images:\s*\[/);
    expect(og).toMatch(/opengraph-image/);
  });

  it("twitter card declares an image to match its summary_large_image claim", () => {
    const tw = layout.slice(layout.indexOf("twitter:"), layout.indexOf("robots:"));
    expect(tw).toMatch(/card:\s*"summary_large_image"/);
    expect(tw).toMatch(/images:/);
  });
});

describe("auth pages server-render their heading", () => {
  // Both pages call useSearchParams(), which makes Next bail out of
  // prerendering the subtree. With `fallback={null}` the server sent 570
  // bytes and ZERO headings: a blank page on slow connections, and nothing
  // for a screen reader to announce, on the two highest-intent routes.
  for (const page of ["signin", "signup"]) {
    it(`/${page} has a non-null Suspense fallback`, () => {
      const src = readFileSync(join(APP, page, "page.tsx"), "utf8");
      expect(src).not.toMatch(/<Suspense fallback=\{null\}>/);
      expect(src).toMatch(/<Suspense fallback=\{<\w+Skeleton\s*\/>\}>/);
    });

    it(`/${page} skeleton renders an h1`, () => {
      const src = readFileSync(join(APP, page, "page.tsx"), "utf8");
      const skeleton = src.slice(src.indexOf("Skeleton()"));
      expect(skeleton).toMatch(/<h1/);
    });
  }

  it("the signup skeleton reads FROM_COPY rather than duplicating the string", () => {
    // A hand-copied headline would drift from the CARD HONESTY block, which
    // is the one piece of copy on this page that must not drift.
    const src = readFileSync(join(APP, "signup", "page.tsx"), "utf8");
    const skeleton = src.slice(src.indexOf("function SignUpSkeleton"));
    expect(skeleton).toMatch(/FROM_COPY\._default/);
  });
});

describe("pageMeta carries the default card (the fix the layout alone did not make)", () => {
  // Adding `images` to the root layout was NOT enough. pageMeta builds a
  // COMPLETE openGraph object, and a page-level openGraph REPLACES the
  // layout's rather than merging — which is the reason the helper exists at
  // all. Every route calling pageMeta() therefore overwrote the layout's
  // default and still emitted no og:image. Verified live: /limitations, /why
  // and /glossary had og:title and og:description but no og:image.
  it("emits an og:image for a page with no image of its own", async () => {
    const { pageMeta } = await import("../lib/seo");
    const m = pageMeta({ title: "T", description: "D", path: "/limitations" });
    const images = m.openGraph?.images as Array<{ url: string }> | undefined;
    expect(images?.[0]?.url).toBeTruthy();
  });

  it("emits a twitter image to back summary_large_image", async () => {
    const { pageMeta } = await import("../lib/seo");
    const m = pageMeta({ title: "T", description: "D", path: "/why" });
    expect((m.twitter as { images?: unknown[] })?.images?.length).toBeGreaterThan(0);
  });

  it("still lets a route override with its own image", async () => {
    const { pageMeta } = await import("../lib/seo");
    const m = pageMeta({
      title: "T", description: "D", path: "/x", ogImage: "/custom-image",
    });
    const images = m.openGraph?.images as Array<{ url: string }>;
    expect(images[0].url).toBe("/custom-image");
  });
});

describe("apple-touch-icon", () => {
  // iOS cannot use an SVG for the Home Screen tile — it falls back to a
  // screenshot, which defeats the PWA install the billing page tells
  // customers to perform.
  //
  // This points at /icon rather than an apple-icon.tsx file convention for
  // two measured reasons: defining `metadata.icons` at all suppresses the
  // icon FILE conventions (verified live — with `apple` merely removed, no
  // apple-touch-icon tag was emitted at all), and an app/apple-icon.tsx
  // produced no route (GET /apple-icon returned text/html) while the
  // structurally identical app/icon.tsx did.
  function iconsBlock(): string {
    const layout = readFileSync(join(APP, "layout.tsx"), "utf8");
    const start = layout.indexOf("icons:");
    return layout.slice(start, layout.indexOf("};", start));
  }

  it("points at a raster icon, never the SVG", () => {
    const apple = iconsBlock().slice(iconsBlock().indexOf("apple:"));
    expect(apple).toMatch(/apple:/);
    expect(apple).not.toMatch(/apple:.*favicon\.svg/);
    expect(apple).toMatch(/image\/png/);
  });

  it("references a route that actually exists", () => {
    expect(iconsBlock()).toMatch(/apple:[\s\S]*url:\s*"\/icon"/);
    expect(existsSync(join(APP, "icon.tsx"))).toBe(true);
  });
});
