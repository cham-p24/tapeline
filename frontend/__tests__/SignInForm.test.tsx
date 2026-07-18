/**
 * Sign-in page — inline validation and accessible error messaging.
 *
 * The form previously ran no client-side validation at all: an empty or
 * mistyped email went to the API and came back as the generic "incorrect
 * email or password", which tells a user who fat-fingered their address that
 * their *credentials* are wrong. And the single error box sat at the foot of
 * the form, unassociated with any field and invisible to assistive tech.
 *
 * Contract asserted here:
 *   1. Validation runs on BLUR — not on every keystroke, not only on submit.
 *   2. The message renders adjacent to the offending field and says what to
 *      do about it.
 *   3. aria-invalid + aria-describedby link input → message, the message
 *      carries role="alert", and the form-level error lives in an
 *      always-mounted live region.
 *   4. A failed submit preserves what the user typed.
 *   5. No suitability data is collected (compliance Rule 8).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SignInPage from "@/app/signin/page";

const signinMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/auth", () => ({
  authApi: {
    signin: signinMock,
    signin2fa: vi.fn(),
    session: vi.fn().mockResolvedValue({ user: null }),
    signup: vi.fn(),
    signout: vi.fn(),
  },
  hasMinTier: vi.fn(() => false),
  canUse: vi.fn(() => false),
  FEATURE_TIERS: {},
}));

// The page bounces already-signed-in visitors to `next`; keep the test user
// signed out so the form renders.
vi.mock("@/components/UserContext", () => ({
  useUser: () => ({ user: null, loading: false, refresh: vi.fn() }),
}));

const nav = vi.hoisted(() => ({ search: new URLSearchParams() }));
const routerSpies = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
  back: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => routerSpies,
  useSearchParams: () => nav.search,
  usePathname: () => "/signin",
}));

beforeEach(() => {
  nav.search = new URLSearchParams();
  signinMock.mockReset();
  signinMock.mockResolvedValue({ user: { id: "u1" } });
  routerSpies.push.mockClear();
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({ google: false, microsoft: false, apple: false }),
      }),
    ),
  );
});

function fill(label: RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe("SignInPage validation", () => {
  it("renders the email + password fields", () => {
    render(<SignInPage />);
    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
  });

  it("does NOT raise an error while the user is still typing", () => {
    render(<SignInPage />);
    const email = screen.getByLabelText(/^email$/i);
    fireEvent.change(email, { target: { value: "trade" } });
    fireEvent.change(email, { target: { value: "trader@" } });
    expect(email).not.toHaveAttribute("aria-invalid");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("validates the email ON BLUR with an actionable message", () => {
    render(<SignInPage />);
    const email = screen.getByLabelText(/^email$/i);
    fireEvent.change(email, { target: { value: "trader@example" } });
    fireEvent.blur(email);

    const error = screen.getByRole("alert");
    expect(error.textContent).toMatch(/needs a domain|complete email address/i);
    expect(error.textContent).not.toMatch(/^invalid/i);
    // Rendered next to the field it belongs to.
    expect(email.parentElement).toContainElement(error);
  });

  it("validates an empty password ON BLUR and points at password recovery", () => {
    render(<SignInPage />);
    const password = screen.getByLabelText(/^password$/i);
    fireEvent.focus(password);
    fireEvent.blur(password);

    expect(password).toHaveAttribute("aria-invalid", "true");
    expect(document.getElementById("signin-password-error")!.textContent).toMatch(
      /forgot password/i,
    );
  });

  it("wires aria-invalid + aria-describedby to a real, existing error node", () => {
    render(<SignInPage />);
    const email = screen.getByLabelText(/^email$/i);
    fireEvent.blur(email);

    expect(email).toHaveAttribute("aria-invalid", "true");
    const describedBy = email.getAttribute("aria-describedby");
    expect(describedBy).toBe("signin-email-error");
    expect(document.getElementById("signin-email-error")).not.toBeNull();
    expect(document.getElementById("signin-email-error")!.getAttribute("role")).toBe(
      "alert",
    );
  });

  it("drops aria-describedby entirely when the field is valid", () => {
    render(<SignInPage />);
    const email = screen.getByLabelText(/^email$/i);
    fireEvent.change(email, { target: { value: "trader@example.com" } });
    fireEvent.blur(email);
    expect(email).not.toHaveAttribute("aria-invalid");
    expect(email).not.toHaveAttribute("aria-describedby");
  });

  it("blocks submit and never calls the API when the email is malformed", async () => {
    const { container } = render(<SignInPage />);
    fill(/^email$/i, "trader-at-example.com");
    fill(/^password$/i, "hunter2hunter2");
    fireEvent.submit(container.querySelector("form")!);

    await waitFor(() =>
      expect(screen.getByLabelText(/^email$/i)).toHaveAttribute("aria-invalid", "true"),
    );
    expect(signinMock).not.toHaveBeenCalled();
  });

  it("PRESERVES the typed credentials when submit fails validation", async () => {
    const { container } = render(<SignInPage />);
    fill(/^email$/i, "trader-at-example.com");
    fill(/^password$/i, "hunter2hunter2");
    fireEvent.submit(container.querySelector("form")!);

    await waitFor(() =>
      expect(screen.getByLabelText(/^email$/i)).toHaveAttribute("aria-invalid", "true"),
    );
    expect((screen.getByLabelText(/^email$/i) as HTMLInputElement).value).toBe(
      "trader-at-example.com",
    );
    expect((screen.getByLabelText(/^password$/i) as HTMLInputElement).value).toBe(
      "hunter2hunter2",
    );
  });

  it("PRESERVES the typed credentials when the API rejects the sign-in", async () => {
    signinMock.mockRejectedValue(new Error("Incorrect email or password"));
    const { container } = render(<SignInPage />);
    fill(/^email$/i, "trader@example.com");
    fill(/^password$/i, "wrongpassword");
    fireEvent.submit(container.querySelector("form")!);

    await waitFor(() => expect(signinMock).toHaveBeenCalled());
    expect((screen.getByLabelText(/^email$/i) as HTMLInputElement).value).toBe(
      "trader@example.com",
    );
    expect((screen.getByLabelText(/^password$/i) as HTMLInputElement).value).toBe(
      "wrongpassword",
    );
  });

  it("announces the form-level error from an always-mounted live region", async () => {
    const { container } = render(<SignInPage />);
    const region = container.querySelector('[aria-live="assertive"]');
    expect(region).not.toBeNull();
    expect(region!.textContent).toBe("");

    fill(/^email$/i, "nope");
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => expect(region!.textContent).toMatch(/needs? fixing/i));
  });

  it("submits normally once both fields are valid", async () => {
    const { container } = render(<SignInPage />);
    fill(/^email$/i, "trader@example.com");
    fill(/^password$/i, "hunter2hunter2");
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() =>
      expect(signinMock).toHaveBeenCalledWith("trader@example.com", "hunter2hunter2"),
    );
  });

  // ── 2FA step ─────────────────────────────────────────────────────────────

  it("validates the authenticator code on the 2FA step", async () => {
    signinMock.mockResolvedValue({ mfa_required: true, mfa_token: "tok" });
    const { container } = render(<SignInPage />);
    fill(/^email$/i, "trader@example.com");
    fill(/^password$/i, "hunter2hunter2");
    fireEvent.submit(container.querySelector("form")!);

    const code = await screen.findByLabelText(/authentication code/i);
    fireEvent.change(code, { target: { value: "1234" } });
    fireEvent.blur(code);

    expect(code).toHaveAttribute("aria-invalid", "true");
    expect(
      document.getElementById("signin-mfa-code-error")!.textContent,
    ).toMatch(/4 digits.*6 digits/i);
  });

  // ── Compliance Rule 8 ────────────────────────────────────────────────────

  it("collects NO suitability data (experience, capital, risk tolerance, goals)", () => {
    const { container } = render(<SignInPage />);
    const banned =
      /experience|portfolio|capital|net worth|risk toleran|investment goal|holdings/i;
    for (const el of Array.from(container.querySelectorAll("input, select, textarea"))) {
      expect(el.getAttribute("name") ?? "").not.toMatch(banned);
      expect(el.getAttribute("id") ?? "").not.toMatch(banned);
    }
    expect(container.textContent ?? "").not.toMatch(
      /portfolio size|risk tolerance|investing experience/i,
    );
  });
});
