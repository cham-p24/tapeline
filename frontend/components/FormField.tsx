"use client";

/**
 * Shared, accessible form field for the auth pages (/signup, /signin).
 *
 * Why this exists: both auth forms previously used a private `Field` helper
 * that rendered a bare input with no error slot at all. Every failure — a
 * typo'd email, a 6-character password, a wrong password — surfaced as a
 * single form-level red box at the bottom of the form, detached from the
 * input that caused it. Nothing was wired to assistive tech, so a screen
 * reader user got no announcement and no association between the message and
 * the field. And validation only ran on submit, so the user found out about a
 * malformed email after a full round-trip.
 *
 * What this fixes, per field:
 *   - Validation runs ON BLUR — after the user has finished with the field,
 *     never while they are still typing it. Typing only ever CLEARS a shown
 *     error; it never raises a new one mid-keystroke.
 *   - The message renders adjacent to the offending input, not at the end of
 *     the form.
 *   - `aria-invalid` marks the input, `aria-describedby` points at the error
 *     (and the hint, when both are present), and the error node carries
 *     `role="alert"` so it is announced even though focus has already moved
 *     on to the next field.
 *
 * Messages are written to say what went wrong AND what to do about it. A bare
 * "Invalid input" is not an acceptable message here — it tells the user they
 * failed without telling them how to succeed.
 *
 * Ids are caller-supplied (not `useId`) so the form can focus the first
 * invalid field on a failed submit by id.
 */

export type FieldError = string | null;

/** Minimum password length. Mirrors the backend's SignupBody constraint. */
export const MIN_PASSWORD_LENGTH = 8;

/**
 * Deliberately permissive shape check — enough to catch the real-world typos
 * (missing @, missing domain, trailing comma) without rejecting the valid but
 * unusual addresses a stricter regex famously breaks on. The backend and the
 * verification email remain the actual source of truth.
 */
const EMAIL_SHAPE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function validateEmail(value: string): FieldError {
  const v = value.trim();
  if (!v) {
    return "Enter your email address — it's the address you'll sign in with.";
  }
  if (!v.includes("@")) {
    return "That email address is missing an @. Enter it in full, like you@example.com.";
  }
  if (!EMAIL_SHAPE.test(v)) {
    return "That doesn't look like a complete email address. Check the part after the @ — it needs a domain, like example.com.";
  }
  return null;
}

/** Signup: a password being created. */
export function validateNewPassword(value: string): FieldError {
  if (!value) {
    return `Choose a password — at least ${MIN_PASSWORD_LENGTH} characters.`;
  }
  if (value.length < MIN_PASSWORD_LENGTH) {
    const short = MIN_PASSWORD_LENGTH - value.length;
    return `That password is ${value.length} characters. Add ${short} more character${short === 1 ? "" : "s"} to reach the ${MIN_PASSWORD_LENGTH}-character minimum.`;
  }
  return null;
}

/** Sign-in: an existing password being recalled. No length rule — an older
    account may pre-date the current minimum, and telling a signing-in user
    their password is "too short" is both unhelpful and a small disclosure. */
export function validateCurrentPassword(value: string): FieldError {
  if (!value) {
    return "Enter your password. If you don't remember it, use the “Forgot password?” link below.";
  }
  return null;
}

/** Sign-in 2FA step. */
export function validateAuthCode(value: string): FieldError {
  const v = value.trim();
  if (!v) {
    return "Enter the 6-digit code from your authenticator app, or one of your recovery codes.";
  }
  if (/^\d+$/.test(v) && v.length !== 6) {
    return `That code is ${v.length} digits. Authenticator codes are 6 digits — check you copied all of it.`;
  }
  return null;
}

type Props = {
  /** Caller-supplied so a failed submit can focus the first invalid field. */
  id: string;
  label: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
  /** Called when the field loses focus. The form runs its validator here. */
  onBlur?: () => void;
  /** Current error for this field, or null/undefined when it is valid. */
  error?: FieldError;
  /** Static helper text. Stays visible alongside an error, not replaced by it. */
  hint?: string;
  autoComplete?: string;
  required?: boolean;
  minLength?: number;
  autoFocus?: boolean;
  inputMode?: "numeric" | "text" | "email";
  placeholder?: string;
  /** Extra classes for the input (e.g. the centred 2FA code styling). */
  inputClassName?: string;
};

export function FormField({
  id,
  label,
  type,
  value,
  onChange,
  onBlur,
  error,
  hint,
  autoComplete,
  required,
  minLength,
  autoFocus,
  inputMode,
  placeholder,
  inputClassName = "",
}: Props) {
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  // Only reference ids that actually render — a dangling aria-describedby
  // target is announced as nothing and hides the descriptions that do exist.
  const describedBy = [error ? errorId : null, hint ? hintId : null]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="block">
      <label htmlFor={id} className="block text-xs font-medium text-muted">
        {label}
      </label>
      <input
        id={id}
        type={type}
        autoComplete={autoComplete}
        required={required}
        minLength={minLength}
        autoFocus={autoFocus}
        inputMode={inputMode}
        placeholder={placeholder}
        value={value}
        // Typing never RAISES an error — it only clears one already on screen,
        // so the user is not corrected mid-word. The next blur re-checks.
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        className={`mt-1.5 block h-11 w-full rounded-md border bg-panel px-3 text-base transition-colors focus:outline-none ${
          error
            ? "border-down focus:border-down"
            : "border-border focus:border-accent"
        } ${inputClassName}`}
      />
      {hint && (
        <span id={hintId} className="mt-1 block text-xs text-subtle">
          {hint}
        </span>
      )}
      {error && (
        // role="alert" (not just aria-describedby) because blur validation
        // fires as focus LEAVES the field — describedby alone would never be
        // read out at the moment the error appears.
        <span
          id={errorId}
          role="alert"
          className="mt-1 block text-xs text-down"
        >
          {error}
        </span>
      )}
    </div>
  );
}

/**
 * Always-mounted live region for the form-level error (a failed API call, a
 * failed bot check). It must exist in the DOM BEFORE the error arrives —
 * assistive tech only announces mutations inside a live region it is already
 * observing, so mounting the region together with its first message is a
 * common way to end up announcing nothing.
 */
export function FormAlert({ message }: { message: FieldError }) {
  return (
    <div aria-live="assertive" aria-atomic="true">
      {message && (
        <div
          role="alert"
          className="rounded-md border border-down/30 bg-down/5 p-3 text-sm text-down"
        >
          {message}
        </div>
      )}
    </div>
  );
}
