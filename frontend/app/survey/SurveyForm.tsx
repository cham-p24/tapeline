"use client";

import { useState } from "react";
import { errorText } from "@/lib/errorText";

type Status = "idle" | "submitting" | "sent" | "error";

/**
 * Q1's options. The `value` strings match STATUS_OPTIONS in
 * backend/app/routers/survey.py, and the email's one-tap links pass one of them
 * as `?a=`.
 *
 * "I don't remember signing up" is not filler. Every carded customer arrived via
 * Google OAuth from a paid click, and 22 of 32 external accounts never returned
 * after their signup day — so a person who genuinely does not recall signing up
 * is a real and important segment, and one the database cannot distinguish from
 * someone who tried the product and quietly gave up. Those two need opposite
 * responses from the business.
 */
const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "using_it", label: "I'm using it" },
  { value: "signed_up_not_used", label: "I signed up but haven't really used it" },
  { value: "used_then_stopped", label: "I used it for a bit and stopped" },
  {
    value: "no_account_meaning_to",
    label: "I'm on the mailing list — I've been meaning to try it",
  },
  {
    value: "no_account_not_for_me",
    label: "I looked at it and it wasn't for me",
  },
  { value: "dont_remember", label: "I don't remember signing up" },
];

export function SurveyForm({ initialStatus }: { initialStatus?: string }) {
  const valid = STATUS_OPTIONS.some((o) => o.value === initialStatus);
  const [status, setStatus] = useState<string | null>(valid ? initialStatus! : null);
  const [state, setState] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setState("submitting");
    setErrorMsg(null);

    const fd = new FormData(e.currentTarget);
    const payload = {
      status,
      trigger_story: String(fd.get("trigger_story") || "").trim() || null,
      friction: String(fd.get("friction") || "").trim() || null,
      wants_call: fd.get("wants_call") === "on",
      contact_email: String(fd.get("contact_email") || "").trim() || null,
      // Honeypot — off-screen, so a human never fills it.
      website: String(fd.get("website") || ""),
    };

    if (
      !payload.status &&
      !payload.trigger_story &&
      !payload.friction &&
      !payload.wants_call &&
      !payload.contact_email
    ) {
      setState("error");
      setErrorMsg("Nothing to send yet — answer whichever bits you like.");
      return;
    }

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
      const res = await fetch(`${apiBase}/api/survey`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setState("error");
        setErrorMsg(errorText(body, `Could not send (HTTP ${res.status}).`));
        return;
      }
      setState("sent");
    } catch (err) {
      setState("error");
      setErrorMsg(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  if (state === "sent") {
    return (
      <div className="mt-10 rounded-lg border border-accent/40 bg-accent/5 p-6">
        <p className="font-medium">Thank you — that's genuinely useful.</p>
        <p className="mt-2 text-sm text-muted">
          I read every one of these myself, and I'll reply if you left an address.
          {" "}
          — Christian
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="mt-10 space-y-10">
      {/* Q1 — one tap. Pre-selected when arriving from the email's links. */}
      <fieldset>
        <legend className="text-base font-medium">
          Which of these is closest to true for you right now?
        </legend>
        <div className="mt-4 space-y-2">
          {STATUS_OPTIONS.map((o) => (
            <label
              key={o.value}
              className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm transition ${
                status === o.value
                  ? "border-accent bg-accent/5"
                  : "border-border hover:border-muted"
              }`}
            >
              <input
                type="radio"
                name="status"
                value={o.value}
                checked={status === o.value}
                onChange={() => setStatus(o.value)}
                className="accent-accent"
              />
              {o.label}
            </label>
          ))}
        </div>
      </fieldset>

      {/*
        Q2 — the payload. NO placeholder text, no "e.g.", no examples. Placeholder
        text functions as a category list: Pew found that displaying an option
        raised its selection by 23 points, and that 43% of open respondents named
        something absent from the closed list entirely. You get exactly one chance
        per person to see what comes to mind unaided, and it is gone the moment
        you suggest anything.

        Worded as "what was going on", not "why did you sign up": "why" invites a
        theory of one's own behaviour, "what happened" invites an event. Anchored
        to the signup as a landmark rather than to a date range, which is the
        standard fix for recall error.
      */}
      <div>
        <label htmlFor="trigger_story" className="block text-base font-medium">
          What was going on when you first came across Tapeline — what made you
          go looking for something like this then?
        </label>
        <textarea
          id="trigger_story"
          name="trigger_story"
          rows={5}
          className="mt-3 w-full rounded-lg border border-border bg-surface p-3 text-sm"
        />
      </div>

      {/*
        Q3 — "if anything" is load-bearing. It legitimates the null answer.
        Without it the question presupposes frustration exists and manufactures
        the finding it claims to measure.
      */}
      <div>
        <label htmlFor="friction" className="block text-base font-medium">
          What, if anything, was confusing or frustrating about it?
        </label>
        <p className="mt-1 text-sm text-muted">Optional.</p>
        <textarea
          id="friction"
          name="friction"
          rows={4}
          className="mt-3 w-full rounded-lg border border-border bg-surface p-3 text-sm"
        />
      </div>

      {/* Q4 — the actual point. Placed last: someone who has just typed two
          paragraphs is a different person from someone who just opened a page. */}
      <div className="rounded-lg border border-border p-5">
        <label className="flex cursor-pointer items-start gap-3">
          <input
            type="checkbox"
            name="wants_call"
            className="mt-1 accent-accent"
          />
          <span>
            <span className="font-medium">
              Happy to talk it through on a call?
            </span>
            <span className="mt-1 block text-sm text-muted">
              20 minutes, I do the listening, any time that suits you.
            </span>
          </span>
        </label>
        <div className="mt-4">
          <label htmlFor="contact_email" className="block text-sm text-muted">
            Email, if you'd like a reply or a call. Optional.
          </label>
          <input
            id="contact_email"
            name="contact_email"
            type="email"
            autoComplete="email"
            className="mt-2 w-full rounded-lg border border-border bg-surface p-3 text-sm"
          />
        </div>
      </div>

      {/* Honeypot. Off-screen rather than display:none — some bots skip hidden
          inputs but fill positioned ones. Same trick as the signup form. */}
      <div aria-hidden="true" className="absolute left-[-9999px]">
        <label htmlFor="website">Website</label>
        <input id="website" name="website" type="text" tabIndex={-1} autoComplete="off" />
      </div>

      {errorMsg && <p className="text-sm text-danger">{errorMsg}</p>}

      <button
        type="submit"
        disabled={state === "submitting"}
        className="rounded-lg bg-accent px-6 py-3 font-medium text-black disabled:opacity-60"
      >
        {state === "submitting" ? "Sending…" : "Send"}
      </button>
    </form>
  );
}
