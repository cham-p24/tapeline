/**
 * Open-redirect guard for the `?next=` post-auth redirect param.
 *
 * The signin / signup / onboarding flows read `next` straight from the URL
 * and navigate to it after auth. Without validation a crafted link like
 * `/signin?next=//evil.com` or `?next=https://evil.com` would phish the user
 * to an external site immediately after they sign in.
 *
 * `safeNext` returns the value ONLY when it is an internal, same-origin path:
 * it must start with a single "/" and must NOT be protocol-relative ("//" or
 * "/\\") or carry a scheme. Anything else falls back to a safe default.
 */
export function safeNext(
  next: string | null | undefined,
  fallback = "/app/scanner",
): string {
  if (!next) return fallback;

  // Strip the ASCII control characters (TAB, LF, CR) that the WHATWG URL
  // parser removes from a URL *before* parsing it. Without this, a value like
  // `/\t//evil.com` slips past the prefix guards below — index 1 is TAB, not
  // "/" — and the browser's later `new URL()` resolution strips the TAB to
  // yield `///evil.com`, whose origin is evil.com: a post-auth open redirect.
  // Clean first, validate the cleaned value, and return the cleaned value
  // (returning the raw string would re-open the hole).
  const cleaned = next.replace(/[\t\n\r]/g, "");

  if (
    !cleaned.startsWith("/") ||
    cleaned.startsWith("//") ||
    cleaned.startsWith("/\\")
  ) {
    return fallback;
  }

  // Belt-and-suspenders: resolve against a throwaway origin and require the
  // result stay on it. Catches any residual parser quirk (backslash
  // normalisation, encoded controls) the prefix checks alone might miss — the
  // same origin-equality test the browser uses to decide internal-vs-external.
  try {
    const resolved = new URL(cleaned, "https://internal.invalid");
    if (resolved.origin !== "https://internal.invalid") return fallback;
  } catch {
    return fallback;
  }

  return cleaned;
}
