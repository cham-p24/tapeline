/**
 * NewsletterCapture — the lead-magnet email form. The regression that
 * motivated this suite: /t/[symbol] pages were tagged source="blog", so
 * every ticker-page subscriber was mis-attributed to the blog in
 * newsletter_subscribers.source. These tests pin the contract that the
 * `source` prop is what gets POSTed — including the new "ticker" value.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { NewsletterCapture } from "@/components/NewsletterCapture";

// The Meta pixel is ON for these tests, so the Lead assertions below exercise
// the real lib/metaConversions path down to `window.fbq`, not a stub of it.
vi.mock("@/lib/trackers", () => ({ trackerEnabled: { meta: true } }));

function mockSubscribe(status = "subscribed") {
  const fetchMock = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ status }),
    }),
  );
  global.fetch = fetchMock as unknown as typeof fetch;
  return fetchMock;
}

function fillAndSubmit() {
  fireEvent.change(screen.getByLabelText(/email address/i), {
    target: { value: "trader@example.com" },
  });
  fireEvent.submit(screen.getByRole("form", { name: /newsletter signup/i }));
}

describe("NewsletterCapture", () => {
  it("posts the ticker source so /t page signups attribute correctly", async () => {
    const fetchMock = mockSubscribe();
    render(<NewsletterCapture source="ticker" heading="" sub="" />);
    fillAndSubmit();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      { body: string },
    ];
    expect(url).toMatch(/\/api\/newsletter\/subscribe$/);
    const body = JSON.parse(init.body) as { email: string; source: string };
    expect(body.source).toBe("ticker");
    expect(body.email).toBe("trader@example.com");
    // Success state replaces the form.
    expect(await screen.findByRole("status")).toHaveTextContent(/you.re in/i);
  });

  it("posts the source it was mounted with (pricing exit-intent path)", async () => {
    const fetchMock = mockSubscribe();
    render(<NewsletterCapture source="pricing" heading="" sub="" />);
    fillAndSubmit();

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      { body: string },
    ];
    expect(JSON.parse(init.body).source).toBe("pricing");
  });

  it("shows the already-subscribed state without a fake success", async () => {
    mockSubscribe("already_subscribed");
    render(<NewsletterCapture source="ticker" heading="" sub="" />);
    fillAndSubmit();
    expect(await screen.findByRole("status")).toHaveTextContent(
      /already subscribed/i,
    );
  });
});

/**
 * Meta `Lead` (decision "L1") — the conversion the free-email ad set optimises
 * on. It must count SUBSCRIBERS, not form submits: the server answers "new"
 * exactly once per address (a later submit is "already_subscribed", a return
 * after unsubscribing is "resubscribed", and the honeypot / disposable-domain
 * screens also answer "already_subscribed"), so "new" is the only status that
 * may fire it. An overcount here would make the ad look cheaper per lead than
 * it is, and cost-per-lead is what decides whether it keeps spending.
 */
describe("NewsletterCapture — Meta Lead", () => {
  afterEach(() => {
    delete (window as unknown as { fbq?: unknown }).fbq;
  });

  function installPixel() {
    const fbq = vi.fn();
    (window as unknown as { fbq: unknown }).fbq = fbq;
    return fbq;
  }

  function leadCalls(fbq: ReturnType<typeof vi.fn>) {
    return fbq.mock.calls.filter((c) => c[0] === "track" && c[1] === "Lead");
  }

  it("fires Lead once for a NEW subscription, with no email in it", async () => {
    const fbq = installPixel();
    mockSubscribe("new");
    render(<NewsletterCapture source="homepage" heading="" sub="" />);
    fillAndSubmit();

    await waitFor(() => expect(leadCalls(fbq)).toHaveLength(1));
    const [call] = leadCalls(fbq);
    expect(call[2]).toEqual({});
    expect(call[3]).toEqual({ eventID: expect.stringMatching(/^lead\.[0-9a-f]{32}$/) });
    // The address typed into the form never reaches the pixel.
    expect(JSON.stringify(fbq.mock.calls)).not.toContain("trader@example.com");
    expect(JSON.stringify(fbq.mock.calls)).not.toContain("@");
  });

  it.each([
    ["resubscribed", /you.re in/i],
    ["already_subscribed", /already subscribed/i],
  ])("does NOT fire Lead when the server says %s", async (status, shown) => {
    const fbq = installPixel();
    mockSubscribe(status);
    render(<NewsletterCapture source="homepage" heading="" sub="" />);
    fillAndSubmit();

    expect(await screen.findByRole("status")).toHaveTextContent(shown);
    // Let any pending async dispatch settle before asserting it never came.
    await new Promise((r) => setTimeout(r, 0));
    expect(leadCalls(fbq)).toHaveLength(0);
  });

  it("does NOT fire Lead when the subscribe request fails", async () => {
    const fbq = installPixel();
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 429,
        json: () => Promise.resolve({ detail: "Too many requests." }),
      }),
    ) as unknown as typeof fetch;
    render(<NewsletterCapture source="homepage" heading="" sub="" />);
    fillAndSubmit();

    expect(await screen.findByRole("alert")).toHaveTextContent(/too many/i);
    await new Promise((r) => setTimeout(r, 0));
    expect(leadCalls(fbq)).toHaveLength(0);
  });
});
