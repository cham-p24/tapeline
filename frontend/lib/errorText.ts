/**
 * Turn a FastAPI error envelope into a string that is always safe to render.
 *
 * Why this exists: FastAPI's `detail` is NOT always a string.
 *
 *   - HTTPException(detail="...")  -> { detail: "a string" }
 *   - Pydantic validation (422)    -> { detail: [ {type, loc, msg, input, ctx}, ... ] }
 *
 * The 422 shape is an ARRAY OF OBJECTS. Code written as
 * `setError(body.detail || "fallback")` therefore puts an array of objects
 * into a string-typed state, and React throws error #31 ("Objects are not
 * valid as a React child") the moment it renders — a blank white screen, not
 * a validation message.
 *
 * That is a real production crash, seen in Sentry as:
 *   Minified React error #31; args[]=object with keys {type, loc, msg, input, ctx}
 * — the exact Pydantic v2 key set. It fires on the paths where a user is most
 * likely to submit imperfect input: the public contact form and the billing
 * and push-notification flows.
 *
 * Note that `||` cannot save you here: a non-empty array is truthy, so the
 * fallback never runs. The check has to be on the TYPE.
 */
export function errorText(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null | undefined)?.detail;

  if (typeof detail === "string" && detail.trim()) return detail;

  // 422: surface the individual field messages rather than a generic string —
  // "email: value is not a valid email address" beats "Could not send".
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === "string") return item;
        const msg = (item as { msg?: unknown })?.msg;
        if (typeof msg !== "string") return null;
        const loc = (item as { loc?: unknown })?.loc;
        // loc is like ["body", "email"] — the last element is the field name.
        const field = Array.isArray(loc)
          ? loc.filter((l) => typeof l === "string" && l !== "body").pop()
          : undefined;
        return field ? `${field}: ${msg}` : msg;
      })
      .filter((p): p is string => Boolean(p));
    if (parts.length) return parts.join("; ");
  }

  return fallback;
}
