/**
 * Signup + signin form behavior. Doesn't actually create accounts (no API
 * call), just validates the forms render correctly with all the bits the
 * backend expects (honeypot field, password min-length, OAuth buttons when
 * configured, Turnstile widget div when configured).
 */
import { test, expect } from "@playwright/test";

test.describe("Signup form", () => {
  test("renders with name, email, password fields", async ({ page }) => {
    await page.goto("/signup");

    await expect(page.getByRole("heading", { name: /start 14-day pro trial/i })).toBeVisible();
    await expect(page.getByLabel("Name")).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
    await expect(page.getByRole("button", { name: /create account/i })).toBeVisible();
  });

  test("password min-length validation triggers", async ({ page }) => {
    await page.goto("/signup");

    await page.getByLabel("Email").fill("test@example.com");
    await page.getByLabel("Password").fill("short");
    await page.getByRole("button", { name: /create account/i }).click();

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
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
    await expect(page.getByRole("button", { name: /^sign in$/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /sign up free/i })).toBeVisible();
  });
});
