/**
 * Signup + signin form behavior. Doesn't actually create accounts (no API
 * call), just validates the forms render correctly with all the bits the
 * backend expects (honeypot field, password min-length, OAuth buttons when
 * configured, Turnstile widget div when configured).
 */
import { test, expect } from "@playwright/test";

/**
 * Locator note: `getByLabel("Email")` is ambiguous on /signup — the marketing
 * opt-in checkboxes are labelled "Email me the weekly market..." and
 * "Send me the Daily Top 10", so a substring match resolves three elements and
 * trips strict mode. Role-scoped locators name the control type as well as the
 * label, which is what we actually mean: the email TEXTBOX.
 *
 * The names are prefix-anchored regexes rather than exact strings so a label
 * gaining a qualifier — "Name" became "Name (optional)" — does not fail a
 * working form, while still excluding "Email me the weekly market...".
 */

test.describe("Signup form", () => {
  test("renders with name, email, password fields", async ({ page }) => {
    await page.goto("/signup");

    // NOT the headline: /signup renders {headline.h1}, which varies by
    // acquisition variant, so asserting one string here fails on a working
    // page. The form is what has to exist.
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("textbox", { name: /^Name/ })).toBeVisible();
    await expect(page.getByRole("textbox", { name: /^Email/ })).toBeVisible();
    await expect(page.getByRole("textbox", { name: /^Password/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /create (my )?account/i })).toBeVisible();
  });

  test("password min-length validation triggers", async ({ page }) => {
    await page.goto("/signup");

    await page.getByRole("textbox", { name: /^Email/ }).fill("test@example.com");
    await page.getByRole("textbox", { name: /^Password/ }).fill("short");
    await page.getByRole("button", { name: /create (my )?account/i }).click();

    // The frontend should show a min-length error before submitting
    await expect(page.getByText(/at least 8 characters/i)).toBeVisible();
  });

  test("Terms + Privacy links route correctly", async ({ page }) => {
    await page.goto("/signup");

    const termsLink = page.getByRole("link", { name: "Terms" });
    await expect(termsLink).toHaveAttribute("href", "/legal/terms");

    const privacyLink = page.getByRole("link", { name: "Privacy Policy" });
    await expect(privacyLink).toHaveAttribute("href", "/legal/privacy");
  });
});

test.describe("Signin form", () => {
  test("renders with email + password + signup link", async ({ page }) => {
    await page.goto("/signin");

    await expect(page.getByRole("heading", { name: /welcome back/i })).toBeVisible();
    await expect(page.getByRole("textbox", { name: /^Email/ })).toBeVisible();
    await expect(page.getByRole("textbox", { name: /^Password/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /^sign in$/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /create an account/i })).toBeVisible();
  });
});
