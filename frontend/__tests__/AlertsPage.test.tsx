/**
 * Alerts page tier-gate UX:
 *   - free users default into the web_push channel (the ONE channel they can
 *     actually create — defaulting to email walked them straight into a 403)
 *   - tier-gate 403s render humanized copy with a REAL billing link, never a
 *     raw feature slug or a non-clickable "/app/billing" string
 *   - creating a web_push rule without browser notification permission
 *     surfaces the "Enable browser notifications" prompt (the rule can never
 *     deliver until this browser subscribes)
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AlertsPage from "@/app/app/alerts/page";

vi.mock("@/components/UserContext", () => ({
  useUser: vi.fn(),
}));

// The alerts page reads ?symbol= / ?type= once for initial form state
// (pre-arm from context). `nav.search` is swapped per-test before render.
const nav = vi.hoisted(() => ({ search: new URLSearchParams() }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => nav.search,
}));

// importActual keeps the REAL TierGateError class so the page's `instanceof`
// check works against the errors we reject with.
const rulesMock = vi.fn();
const eventsMock = vi.fn();
const createMock = vi.fn();
const searchMock = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      alertRules: () => rulesMock(),
      alertEvents: () => eventsMock(),
      alertRuleCreate: (body: unknown) => createMock(body),
      alertRuleDelete: vi.fn(),
      search: (q: string, limit?: number) => searchMock(q, limit),
    },
  };
});

const statusMock = vi.fn();
const subscribeMock = vi.fn();
vi.mock("@/lib/webPush", () => ({
  getWebPushStatus: () => statusMock(),
  subscribeToWebPush: () => subscribeMock(),
}));

import { useUser } from "@/components/UserContext";
import { TierGateError } from "@/lib/api";
const mockedUseUser = useUser as ReturnType<typeof vi.fn>;

const freeUser = { id: "u1", email: "f@example.com", name: null, tier: "free", created_at: null };
const proUser = { id: "u2", email: "p@example.com", name: null, tier: "pro", created_at: null };
const asUser = (user: object | null) => ({
  user, loading: false, refresh: vi.fn(), signout: vi.fn(),
});

// The two comboboxes render in source order: rule type first, channel second.
// (The ticker typeahead is a plain <input>, not a combobox role, so it does
// not change this count or order.)
const channelSelect = () => screen.getAllByRole("combobox")[1] as HTMLSelectElement;
const ruleTypeSelect = () => screen.getAllByRole("combobox")[0] as HTMLSelectElement;

beforeEach(() => {
  mockedUseUser.mockReset();
  nav.search = new URLSearchParams();
  rulesMock.mockReset().mockResolvedValue({ count: 0, items: [] });
  eventsMock.mockReset().mockResolvedValue({ count: 0, items: [] });
  createMock.mockReset();
  statusMock.mockReset().mockResolvedValue("default");
  subscribeMock.mockReset();
  searchMock.mockReset().mockResolvedValue({ results: [] });
});

describe("AlertsPage channel default", () => {
  it("defaults free users to web_push (their one creatable channel)", async () => {
    mockedUseUser.mockReturnValue(asUser(freeUser));
    render(<AlertsPage />);
    await waitFor(() => expect(rulesMock).toHaveBeenCalled());
    expect(channelSelect().value).toBe("web_push");
  });

  it("keeps email as the default for paid tiers", async () => {
    mockedUseUser.mockReturnValue(asUser(proUser));
    render(<AlertsPage />);
    await waitFor(() => expect(rulesMock).toHaveBeenCalled());
    expect(channelSelect().value).toBe("email");
  });
});

describe("AlertsPage locked delivery channels (show don't hide)", () => {
  it("shows Email (Pro) as VISIBLE-but-locked for free users", async () => {
    mockedUseUser.mockReturnValue(asUser(freeUser));
    render(<AlertsPage />);
    await waitFor(() => expect(rulesMock).toHaveBeenCalled());

    const panel = screen.getByTestId("alerts-channels-locked");
    // The paid delivery channel is surfaced, not hidden, with its tier.
    expect(within(panel).getByText("Email")).toBeInTheDocument();
    expect(within(panel).getByText("Pro")).toBeInTheDocument();
    // Web push is shown as the included/free channel.
    expect(within(panel).getByText(/Web push/i)).toBeInTheDocument();
    // A descriptive upgrade CTA points at billing.
    expect(within(panel).getByRole("link", { name: /Unlock email delivery/i }))
      .toHaveAttribute("href", "/app/billing?intent=pro");
  });

  it("does not show the locked-channels panel for paid tiers", async () => {
    mockedUseUser.mockReturnValue(asUser(proUser));
    render(<AlertsPage />);
    await waitFor(() => expect(rulesMock).toHaveBeenCalled());
    expect(screen.queryByTestId("alerts-channels-locked")).not.toBeInTheDocument();
  });
});

describe("AlertsPage tier-gate errors", () => {
  it("humanizes the web-push cap 403 and renders a real billing link", async () => {
    mockedUseUser.mockReturnValue(asUser(freeUser));
    createMock.mockRejectedValue(
      new TierGateError(
        "Free web-push alert limit reached (2 on free). "
        + "Upgrade for 10 alerts/day at /app/billing.",
      ),
    );
    render(<AlertsPage />);
    await userEvent.type(screen.getByPlaceholderText("AAPL"), "AAPL");
    await userEvent.click(screen.getByRole("button", { name: /Create rule/i }));

    const gateMsg = await screen.findByText(/Free web-push alert limit reached \(2 on free\)/);
    // The billing path must be a REAL link, not inline text. Scope to the
    // error paragraph — the free-taste hint has its own "See plans" link.
    expect(screen.queryByText(/\/app\/billing/)).not.toBeInTheDocument();
    const link = within(gateMsg.closest("p")!).getByRole("link", { name: /See plans/i });
    expect(link).toHaveAttribute("href", "/app/billing");
  });

  it("translates raw feature slugs (alerts.email) into human channel names", async () => {
    mockedUseUser.mockReturnValue(asUser(freeUser));
    createMock.mockRejectedValue(
      new TierGateError("alerts.email requires a higher tier. Upgrade at /app/billing"),
    );
    render(<AlertsPage />);
    await userEvent.selectOptions(channelSelect(), "email");
    await userEvent.type(screen.getByPlaceholderText("AAPL"), "AAPL");
    await userEvent.click(screen.getByRole("button", { name: /Create rule/i }));

    await waitFor(() => {
      expect(screen.getByText(/Email alerts are a Pro feature\./)).toBeInTheDocument();
    });
    expect(screen.queryByText(/alerts\.email/)).not.toBeInTheDocument();
  });
});

describe("AlertsPage web-push enable prompt", () => {
  it("prompts to enable browser notifications after creating a web_push rule without permission", async () => {
    mockedUseUser.mockReturnValue(asUser(freeUser));
    createMock.mockResolvedValue({ id: 1 });
    statusMock.mockResolvedValue("default"); // permission not yet granted
    subscribeMock.mockResolvedValue({ ok: true });
    render(<AlertsPage />);
    await userEvent.type(screen.getByPlaceholderText("AAPL"), "AAPL");
    await userEvent.click(screen.getByRole("button", { name: /Create rule/i }));

    const enableBtn = await screen.findByRole("button", { name: /Enable browser notifications/i });
    await userEvent.click(enableBtn);
    await waitFor(() => {
      expect(screen.getByText(/Browser notifications enabled/)).toBeInTheDocument();
    });
    expect(subscribeMock).toHaveBeenCalled();
  });

  it("does not prompt when the browser has already granted permission", async () => {
    mockedUseUser.mockReturnValue(asUser(freeUser));
    createMock.mockResolvedValue({ id: 1 });
    statusMock.mockResolvedValue("granted");
    render(<AlertsPage />);
    await userEvent.type(screen.getByPlaceholderText("AAPL"), "AAPL");
    await userEvent.click(screen.getByRole("button", { name: /Create rule/i }));

    await waitFor(() => expect(createMock).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: /Enable browser notifications/i })).not.toBeInTheDocument();
  });
});

describe("AlertsPage pre-arm from context (deep link)", () => {
  it("pre-fills the ticker field from ?symbol=NVDA (uppercased)", async () => {
    mockedUseUser.mockReturnValue(asUser(proUser));
    nav.search = new URLSearchParams("symbol=nvda");
    render(<AlertsPage />);
    await waitFor(() => expect(rulesMock).toHaveBeenCalled());
    expect(screen.getByPlaceholderText("AAPL")).toHaveValue("NVDA");
  });

  it("preselects the news rule from ?type=news", async () => {
    mockedUseUser.mockReturnValue(asUser(proUser));
    nav.search = new URLSearchParams("type=news");
    render(<AlertsPage />);
    await waitFor(() => expect(rulesMock).toHaveBeenCalled());
    expect(ruleTypeSelect().value).toBe("news");
  });

  it("ignores an invalid ?type= value and keeps the default rule", async () => {
    mockedUseUser.mockReturnValue(asUser(proUser));
    nav.search = new URLSearchParams("type=bogus");
    render(<AlertsPage />);
    await waitFor(() => expect(rulesMock).toHaveBeenCalled());
    expect(ruleTypeSelect().value).toBe("score");
  });
});

describe("AlertsPage ticker typeahead (api.search)", () => {
  it("sets the symbol when a search result is selected", async () => {
    mockedUseUser.mockReturnValue(asUser(proUser));
    searchMock.mockResolvedValue({
      results: [
        { symbol: "TSLA", name: "Tesla Inc", sector: "Consumer Cyclical", score: 88 },
      ],
    });
    render(<AlertsPage />);
    await waitFor(() => expect(rulesMock).toHaveBeenCalled());

    const field = screen.getByPlaceholderText("AAPL");
    await userEvent.type(field, "tesl");
    // Debounced search resolves and renders the result option.
    const option = await screen.findByRole("option", { name: /TSLA/ });
    await userEvent.click(within(option).getByRole("button"));

    expect(screen.getByPlaceholderText("AAPL")).toHaveValue("TSLA");
    expect(searchMock).toHaveBeenCalledWith(expect.stringMatching(/tesl/i), 8);
  });
});
