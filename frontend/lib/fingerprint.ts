/**
 * Lightweight device fingerprint for trial-abuse prevention.
 *
 * Why this is a tiny homemade implementation instead of FingerprintJS Pro:
 * - We only need to detect same-device retrials (different VPN + new email),
 *   not bullet-proof identification. ~80% reliability is plenty for the
 *   threat model.
 * - No npm dep (~30KB saved) and no third-party API call (privacy + cost).
 * - The user can always wear a different mask (incognito + new device + new
 *   IP + new email) and that's fine — at that level of effort the Premium
 *   trial value is below their hourly rate.
 *
 * Inputs are stable per-browser-install: UA, language, timezone, screen,
 * hardware concurrency, plus a 2D canvas pixel hash that varies by GPU +
 * font rendering. Output is a 16-char hex hash. Stable across normal
 * navigation; resets when a user wipes browser storage AND swaps GPU.
 *
 * Returns "" on SSR or any failure (caller falls back to other defences).
 */
export async function deviceFingerprint(): Promise<string> {
  if (typeof window === "undefined") return "";
  try {
    const parts: string[] = [];
    parts.push(navigator.userAgent || "");
    parts.push(navigator.language || "");
    parts.push(String((navigator.languages || []).join(",")));
    parts.push(String(Intl.DateTimeFormat().resolvedOptions().timeZone || ""));
    parts.push(String(navigator.hardwareConcurrency || 0));
    parts.push(`${screen.width}x${screen.height}x${screen.colorDepth}`);
    parts.push(String((navigator as { deviceMemory?: number }).deviceMemory || 0));
    parts.push(String(new Date().getTimezoneOffset()));

    // Canvas pixel-hash. Different GPUs / font stacks render the same
    // string slightly differently — adds ~30 bits of distinguishing power.
    try {
      const cvs = document.createElement("canvas");
      cvs.width = 240; cvs.height = 60;
      const ctx = cvs.getContext("2d");
      if (ctx) {
        ctx.textBaseline = "top";
        ctx.font = "14px 'Arial', sans-serif";
        ctx.fillStyle = "#f60";
        ctx.fillRect(125, 1, 62, 20);
        ctx.fillStyle = "#069";
        ctx.fillText("Tapeline fp 😬", 2, 15);
        ctx.fillStyle = "rgba(102, 204, 0, 0.7)";
        ctx.fillText("Tapeline fp 😬", 4, 17);
        parts.push(cvs.toDataURL().slice(-128));
      }
    } catch {
      // Canvas may be blocked by privacy extensions; UA + screen still gives signal
    }

    const text = parts.join("|");
    const buf = new TextEncoder().encode(text);
    const digest = await crypto.subtle.digest("SHA-256", buf);
    const bytes = new Uint8Array(digest);
    let hex = "";
    for (let i = 0; i < 8; i++) hex += bytes[i].toString(16).padStart(2, "0");
    return hex;
  } catch {
    return "";
  }
}
