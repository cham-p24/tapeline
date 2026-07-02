/**
 * NewsletterCapture — the lead-magnet email form. The regression that
 * motivated this suite: /t/[symbol] pages were tagged source="blog", so
 * every ticker-page subscriber was mis-attributed to the blog in
 * newsletter_subscribers.source. These tests pin the contract that the
 * `source` prop is what gets POSTed — including the new "ticker" value.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { NewsletterCapture } from "@/components/NewsletterCapture";

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
