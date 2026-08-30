"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/Button";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

type State =
  | { kind: "loading" }
  | { kind: "signedOut" }
  | { kind: "ready"; token: string; email: string }
  | { kind: "error"; message: string };

/**
 * Mints the extension connect token.
 *
 * `credentials: "include"` is mandatory: the cookie is set with
 * Domain=tapeline.io so api.tapeline.io can see it, but fetch defaults to
 * same-ORIGIN and would drop it on the subdomain hop — the same bug that broke
 * every authed call in May.
 */
export default function ConnectClient() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [copied, setCopied] = useState(false);

  const mint = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const res = await fetch(`${API_BASE}/api/extension/token`, {
        method: "POST",
        credentials: "include",
      });
      if (res.status === 401) {
        setState({ kind: "signedOut" });
        return;
      }
      if (!res.ok) {
        setState({ kind: "error", message: "Couldn't create a code just now. Try again." });
        return;
      }
      const data = await res.json();
      setState({ kind: "ready", token: data.token, email: data.email });
    } catch {
      setState({ kind: "error", message: "Couldn't reach Tapeline. Check your connection." });
    }
  }, []);

  useEffect(() => {
    void mint();
  }, [mint]);

  if (state.kind === "loading") {
    return <p className="mt-8 text-sm text-muted">Creating your code…</p>;
  }

  if (state.kind === "signedOut") {
    return (
      <div className="mt-8 rounded-xl border border-border bg-panel p-6">
        <h2 className="text-lg font-semibold">You need an account first</h2>
        {/* The extension needs an account but not a paid one — /api/extension/token
            mints for any signed-in user, free included. Since #683 that account is
            an email and a password, so this screen no longer has to introduce a
            payment step to hand someone a connect code. It does not mention the
            trial at all: the trial takes a card, and naming it here would put a
            price next to a thing that has none. */}
        <p className="mt-2 text-sm leading-relaxed text-muted">
          The extension works with a Tapeline account. Creating one takes a few seconds
          &mdash; an email and a password, no card.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Button href="/signup?next=/extension/connect" variant="primary" shape="rounded">
            Create an account
          </Button>
          <Button href="/signin?next=/extension/connect" variant="secondary" shape="rounded">
            Sign in
          </Button>
        </div>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="mt-8 rounded-xl border border-border bg-panel p-6">
        <p className="text-sm text-muted">{state.message}</p>
        <button
          type="button"
          onClick={() => void mint()}
          className="btn btn-primary !rounded-md mt-4"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="mt-8">
      <div className="rounded-xl border border-border bg-panel p-5">
        <div className="font-mono text-xs uppercase tracking-wider text-subtle">
          Your connect code · {state.email}
        </div>
        <code className="mt-3 block break-all rounded-lg bg-panel2 p-3 font-mono text-[13px] leading-relaxed text-fg">
          {state.token}
        </code>
        <button
          type="button"
          className="btn btn-primary !rounded-md mt-4 w-full"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(state.token);
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            } catch {
              setCopied(false);
            }
          }}
        >
          {copied ? "Copied ✓" : "Copy code"}
        </button>
      </div>

      <ol className="mt-6 flex flex-col gap-3 text-sm leading-relaxed text-muted">
        <li>
          <strong className="text-fg">1.</strong> Copy the code above.
        </li>
        <li>
          <strong className="text-fg">2.</strong> Click the{" "}
          <strong className="text-fg">puzzle-piece icon</strong> at the top-right of your
          browser, then <strong className="text-fg">Tapeline</strong>. A newly installed
          extension sits in there until you pin it.
        </li>
        <li>
          <strong className="text-fg">3.</strong> Paste the code and press{" "}
          <strong className="text-fg">Connect</strong>. That&rsquo;s it &mdash; the score
          appears on stock pages from then on.
        </li>
      </ol>
    </div>
  );
}
