/**
 * chargeDisclosureLine — the sentence shown before the Stripe redirect.
 *
 * The point of this helper is that it can NEVER assert a tax claim the
 * backend hasn't confirmed. `taxAdded: null` means "we don't know yet"
 * (API unreachable, or a tax_behavior="exclusive" price the server refused
 * to make a negative claim about), and the correct output in that case is
 * the currency alone. A missing sentence is recoverable; a wrong tax claim
 * at the payment step is the exact surprise this feature exists to prevent.
 */
import { describe, it, expect } from "vitest";
import {
  chargeDisclosureLine,
  DEFAULT_CHARGE_DISCLOSURE,
} from "@/lib/chargeDisclosure";
import { PRICING } from "@/lib/pricing";

describe("chargeDisclosureLine", () => {
  it("states currency only while the tax posture is unknown", () => {
    const line = chargeDisclosureLine({ currency: "USD", taxAdded: null });
    expect(line).toBe("Charged in USD.");
    expect(line).not.toMatch(/tax/i);
  });

  it("says nothing is added when the server confirmed no tax", () => {
    const line = chargeDisclosureLine({ currency: "USD", taxAdded: false });
    expect(line).toMatch(/^Charged in USD\./);
    expect(line).toMatch(/the amount shown is the amount charged/i);
  });

  it("warns that tax may be added when the server says it is", () => {
    const line = chargeDisclosureLine({ currency: "AUD", taxAdded: true });
    expect(line).toMatch(/^Charged in AUD\./);
    expect(line).toMatch(/tax may be added at checkout/i);
  });

  it("defaults to the shared PRICING currency and no tax claim", () => {
    // The pre-network state has to be safe on first paint: a real currency
    // (the same constant driving the visible prices and the JSON-LD
    // priceCurrency) and silence on tax until the server answers.
    expect(DEFAULT_CHARGE_DISCLOSURE.currency).toBe(PRICING.currency);
    expect(DEFAULT_CHARGE_DISCLOSURE.taxAdded).toBeNull();
    expect(chargeDisclosureLine(DEFAULT_CHARGE_DISCLOSURE)).not.toMatch(/tax/i);
  });
});
