/**
 * The marketing nav's Product menu, and the transparency strip that took over
 * the links the menu dropped.
 *
 * Founder, 2026-09-19: "there's too much going on in the product section way
 * too much / Also the limitation part is fucked". The menu held seven pages,
 * one of them the same page as the "Track record" link beside it. It now holds
 * three. The pages that left are still one click from where a reader would
 * look for them, and that is pinned here so a later trim cannot quietly
 * orphan one.
 *
 * The "limitation part" also had a plain bug: /limitations and /verify
 * rendered the transparency strip without saying which page they were, so
 * each offered a card linking back to itself.
 */
import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { PRODUCT_ITEMS, TOP_LINKS } from "@/components/MarketingNav";
import { TRANSPARENCY_ITEMS } from "@/components/TransparencyStrip";

const read = (p: string) => readFileSync(join(process.cwd(), p), "utf8");

function pages(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return pages(p);
    return name === "page.tsx" ? [p] : [];
  });
}

describe("Product menu", () => {
  it("stays short", () => {
    expect(PRODUCT_ITEMS.length).toBeLessThanOrEqual(4);
  });

  it("never repeats a top-level link", () => {
    const top = new Set(TOP_LINKS.map((l) => l.href));
    for (const item of PRODUCT_ITEMS) {
      expect(top.has(item.href), `${item.href} is both in Product and top-level`).toBe(false);
    }
  });

  it("leaves every dropped page reachable from the nav bar or the footer", () => {
    const footer = read("components/MarketingFooter.tsx");
    const inNav = new Set([...PRODUCT_ITEMS, ...TOP_LINKS].map((l) => l.href));
    for (const href of ["/scorecard", "/verify", "/limitations", "/stocks"]) {
      expect(
        inNav.has(href) || footer.includes(`href="${href}"`),
        `${href} left the Product menu and is linked from neither the nav nor the footer`,
      ).toBe(true);
    }
  });
});

describe("Transparency strip", () => {
  it("never links a page to itself", () => {
    const slugs = new Set(TRANSPARENCY_ITEMS.map((i) => i.slug));
    const appDir = join(process.cwd(), "app");
    const offenders: string[] = [];
    for (const file of pages(appDir)) {
      const src = readFileSync(file, "utf8");
      if (!src.includes("<TransparencyStrip")) continue;
      // app/limitations/page.tsx -> /limitations; dynamic children are a
      // different page, so only the exact route has to name itself.
      const route = "/" + relative(appDir, file).split(sep).slice(0, -1).join("/");
      if (!slugs.has(route)) continue;
      if (!src.includes(`<TransparencyStrip current="${route}"`)) offenders.push(route);
    }
    expect(offenders, "these pages show a card linking to themselves").toEqual([]);
  });
});
