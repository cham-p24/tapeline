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
  if (
    !next ||
    !next.startsWith("/") ||
    next.startsWith("//") ||
    next.startsWith("/\\")
  ) {
    return fallback;
  }
  return next;
}
