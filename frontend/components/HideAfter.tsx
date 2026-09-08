"use client";

import { useEffect, useState, type ReactNode } from "react";

/**
 * Hide time-limited markup once a fixed instant passes, even from a stale cache.
 *
 * ── WHY THIS EXISTS ──────────────────────────────────────────────────────
 * Date-gated server components are baked into whatever ISR cache rendered
 * them. `OpenAccessBanner` gates itself on `freeOpenAccess()`, which is
 * correct at render time — but the page holding it revalidates on its own
 * schedule (30 min for the homepage, 6 h for /pricing). So for up to six hours
 * after the open-access month ends, a cached /pricing could keep telling
 * visitors that "every signed-in account sees the full scanner list — up to
 * 1,000 rows", which stops being true at the boundary. The backend has already
 * reverted by then; only the HTML is behind.
 *
 * Lowering the revalidate would trade the whole page's caching for one strip,
 * and would still leave a window. This closes it in the browser instead, where
 * the clock is always current, and works for ANY revalidate value on ANY page.
 *
 * ── HYDRATION ────────────────────────────────────────────────────────────
 * The first client render MUST reproduce the server's HTML or React reports a
 * mismatch. So `expired` starts false — matching the server, which only ever
 * emits children it believed were live — and the clock is consulted in an
 * effect, which runs after hydration. That is the whole trick: never branch on
 * `Date.now()` during the initial render of a component that was server-rendered.
 *
 * The interval is a second-order nicety: it also catches a tab left open across
 * the boundary, rather than only a stale cache at load.
 */
export function HideAfter({
  at,
  children,
}: {
  /** ISO-8601 instant. At or after this, the children stop rendering. */
  at: string;
  children: ReactNode;
}) {
  const [expired, setExpired] = useState(false);

  // Deliberately reads the REAL clock and takes no injectable `now`.
  //
  // That was tried and reverted: threading a caller's date in here defeats the
  // entire point of the component, which is to blank content on a page that was
  // CACHED while the promo was live and is being served after it ended. The
  // server's render date is exactly the stale value we must not trust.
  // `test_hides_itself_when_the_page_was_cached_during_the_promo` catches it.
  //
  // A test that needs this component past its deadline should move the clock
  // (vi.useFakeTimers + vi.setSystemTime), not hand it a date.
  useEffect(() => {
    const deadline = new Date(at).getTime();
    // A malformed `at` must not blank live content — fail toward showing it.
    if (Number.isNaN(deadline)) return;

    const check = () => setExpired(Date.now() >= deadline);
    check();
    const id = window.setInterval(check, 60_000);
    return () => window.clearInterval(id);
  }, [at]);

  if (expired) return null;
  return <>{children}</>;
}
