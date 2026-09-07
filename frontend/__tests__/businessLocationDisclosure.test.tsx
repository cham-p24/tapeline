/**
 * Google's "Financial products and services" ad policy requires the AD
 * DESTINATION PAGE to carry the physical address of the business offering the
 * service, and says such disclosures "can't be posted as roll-over text or
 * made available through another link or tab."
 *
 * Two things have to hold for that, and both are easy to break silently:
 *
 *   1. The line has to be VISIBLE TEXT on every page an ad can land on.
 *      docs/PAID_ACQUISITION_DEEP_DIVE_2026-09.md recommends MarketingFooter,
 *      which would have been wrong: /signup — "the page every paid ad lands
 *      on", per its own file header — does not render MarketingFooter, and
 *      neither does /signin. The only surface that is truly on every route is
 *      GeneralInformationNotice, mounted once in app/layout.tsx. So this suite
 *      pins BOTH the copy and the mount; moving the notice out of the layout
 *      silently un-discloses every landing page.
 *
 *   2. The machine-readable address must not disagree with the printed one.
 *      Google's finance review has a manual step, and an Organization schema
 *      claiming a different locality than the visible footer is worse than
 *      publishing neither.
 *
 * The locality is city-level on purpose — Tapeline is a sole trader working
 * from home, so there is no street address to publish that is not a private
 * residence. These tests assert consistency and presence, NOT that a street
 * number exists; if one is ever added (a virtual office), the cross-check
 * below is what keeps the three surfaces in step.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { GeneralInformationNotice } from "@/components/GeneralInformationNotice";
import { organizationJsonLd, pressContactPageJsonLd } from "@/lib/jsonld";

const LAYOUT = join(__dirname, "..", "app", "layout.tsx");

/** Executable source only. The component and the layout both EXPLAIN this
 *  requirement in prose that quotes the exact strings asserted below, so a
 *  naive grep would pass against a comment while the markup was gone. */
function code(path: string): string {
  return readFileSync(path, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

describe("the publisher's location is disclosed as visible page text", () => {
  it("names the city, state and country in the persistent notice", () => {
    const { container } = render(<GeneralInformationNotice />);
    const text = container.textContent ?? "";
    expect(text).toMatch(/Melbourne/);
    expect(text).toMatch(/Victoria/);
    expect(text).toMatch(/Australia/);
  });

  it("attributes it to Tapeline, so the reader knows whose address it is", () => {
    render(<GeneralInformationNotice />);
    expect(screen.getByText(/Published by Tapeline/i)).toBeInTheDocument();
  });

  it("gives a working contact route alongside the location", () => {
    render(<GeneralInformationNotice />);
    const link = screen.getByRole("link", { name: /support@tapeline\.io/i });
    expect(link).toHaveAttribute("href", "mailto:support@tapeline.io");
  });

  it("prints the location itself rather than hiding it behind a link", () => {
    // The policy bars disclosures "made available through another link or
    // tab". Strip every anchor's text and the location must still be there.
    const { container } = render(<GeneralInformationNotice />);
    container.querySelectorAll("a").forEach((a) => a.remove());
    expect(container.textContent ?? "").toMatch(/Melbourne, Victoria, Australia/);
  });

  it("is not a tooltip — no title/aria-label carries the address", () => {
    // "Roll-over text" is named in the policy. Belt and braces: the address
    // must not live only in an attribute.
    const { container } = render(<GeneralInformationNotice />);
    const attrs = Array.from(container.querySelectorAll("*"))
      .flatMap((el) => [el.getAttribute("title"), el.getAttribute("aria-label")])
      .filter(Boolean)
      .join(" ");
    expect(attrs).not.toMatch(/Melbourne/);
  });
});

describe("the disclosure reaches every ad destination", () => {
  it("is mounted in the root layout, not in MarketingFooter", () => {
    // MarketingFooter is absent from /signup and /signin. If someone 'tidies'
    // this into the footer, paid landing pages lose the disclosure.
    expect(code(LAYOUT)).toMatch(/<GeneralInformationNotice\s*\/>/);
  });
});

describe("the structured address agrees with the printed one", () => {
  it("Organization schema carries the same locality, region and country", () => {
    const org = organizationJsonLd() as {
      address: Record<string, string>;
    };
    expect(org.address.addressLocality).toBe("Melbourne");
    expect(org.address.addressRegion).toBe("VIC");
    expect(org.address.addressCountry).toBe("AU");
  });

  it("the Organization locality matches what the notice actually prints", () => {
    const org = organizationJsonLd() as { address: Record<string, string> };
    const { container } = render(<GeneralInformationNotice />);
    expect(container.textContent ?? "").toContain(org.address.addressLocality);
  });

  it("the press page's founding location does not contradict it", () => {
    const org = organizationJsonLd() as { address: Record<string, string> };
    const press = pressContactPageJsonLd()[0] as {
      mainEntity: { foundingLocation: { address: Record<string, string> } };
    };
    expect(press.mainEntity.foundingLocation.address).toMatchObject({
      addressLocality: org.address.addressLocality,
      addressRegion: org.address.addressRegion,
      addressCountry: org.address.addressCountry,
    });
  });
});
