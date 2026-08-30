"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { authApi, type SessionUser } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/**
 * The session user, plus the `must_add_card` verdict if the session endpoint
 * happens to carry it.
 *
 * NOT A GATE ANY MORE. #683 (2026-08-30) removed the route wall this flag used
 * to drive; it now means "this account has never put a card down" and is read
 * for COPY — the /app/start trial offer, upgrade prompts, funnel cohorts. An
 * account it is true for can use the whole free product.
 *
 * It is computed ENTIRELY server-side (backend services/tier.must_add_card,
 * keyed on the single CARD_GATE_START constant) and simply reported here. The
 * browser deliberately does NOT re-derive it from `created_at`: a billing
 * predicate with two implementations is how the two drift apart, so it has
 * exactly one, and it is not this one.
 *
 * Optional on purpose. `/api/auth/session` does not return the field today
 * (see `resolveCardGate` below), and absent means false — a payload that
 * predates the field can never make the app act as though a card is owed.
 */
export type SessionUserWithGate = SessionUser & {
  must_add_card?: boolean;
};

/**
 * Resolve the card gate for a signed-in user.
 *
 * `/api/me` is the endpoint that owns this flag — it is where the backend
 * exposes `must_add_card`, and routers/auth.py's `_user_out` (which feeds
 * `/api/auth/session`) does not carry it. So we read the session first, and
 * then ask the endpoint that actually knows.
 *
 * The session payload takes precedence whenever it DOES carry the field, so
 * the day `_user_out` starts returning it this second request disappears on
 * its own with no further change here.
 *
 * Every failure path returns false. An unreachable API, a non-200, a body
 * without the field — none of them are evidence that somebody owes us a card,
 * and wrongly walling a grandfathered user is the single worst outcome this
 * feature has. Fail open, always.
 */
async function resolveCardGate(user: SessionUserWithGate | null): Promise<boolean> {
  if (user === null) return false;
  if (user.must_add_card !== undefined) return user.must_add_card === true;
  try {
    const res = await fetch(`${API_BASE}/api/me`, {
      credentials: "include",
      cache: "no-store",
    });
    if (!res.ok) return false;
    const body = await res.json();
    return body?.must_add_card === true;
  } catch {
    return false;
  }
}

type Ctx = {
  user: SessionUserWithGate | null;
  loading: boolean;
  /**
   * True only when the server says this account must add a card before it can
   * reach /app. Read it as `mustAddCard === true`, never as truthiness of a
   * possibly-absent field.
   *
   * OPTIONAL in the type so that consumers which build a Ctx value by hand —
   * today, the non-production preview harness in app/preview-trial-welcome —
   * keep compiling without having to opt into a gate they don't model. Those
   * consumers get `undefined`, i.e. not gated, which is the safe direction.
   */
  mustAddCard?: boolean;
  refresh: () => Promise<void>;
  signout: () => Promise<void>;
};

// Exported so a guarded, non-production preview route can inject a mocked
// session (see app/preview-trial-welcome) to render auth-gated components like
// OnboardingTip / TrialEarlyCapture without a real logged-in user.
export const UserCtx = createContext<Ctx>({
  user: null, loading: true, mustAddCard: false,
  refresh: async () => {}, signout: async () => {},
});

export function useUser() { return useContext(UserCtx); }

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUserWithGate | null>(null);
  const [loading, setLoading] = useState(true);
  const [mustAddCard, setMustAddCard] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const { user } = await authApi.session();
      setUser(user);
      // Resolved BEFORE `loading` clears, deliberately. Consumers treat
      // `loading: false` as "the verdict is in"; publishing the user while the
      // gate is still unknown would flash the product at a gated account for a
      // beat, and the app shell would mount and fire its authed fetches.
      setMustAddCard(await resolveCardGate(user));
    } catch {
      setUser(null);
      setMustAddCard(false);
    } finally {
      setLoading(false);
    }
  }, []);

  const signout = useCallback(async () => {
    try { await authApi.signout(); } catch {}
    setUser(null);
    setMustAddCard(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // 2026-05-20 — Back-button sign-out bug fix.
  //
  // When a user signs in and then hits Back, Chrome/Firefox restore the
  // previous page (e.g. /signin) from the back-forward cache (bfcache).
  // React component instances are preserved exactly as they were when the
  // page was put into bfcache — including `user: null` from before the
  // signin completed. That makes the whole app look signed-out even
  // though the auth cookie is still valid.
  //
  // The fix: listen for `pageshow` with `event.persisted === true` (the
  // browser signal that a page was restored from bfcache) and re-fetch
  // the session so the React state catches up with the cookie state.
  // Also re-fetch on `visibilitychange` -> visible, which covers tab
  // switching where the cookie state may have changed in another tab
  // (e.g. user signs out elsewhere).
  useEffect(() => {
    const onPageShow = (e: PageTransitionEvent) => {
      if (e.persisted) refresh();
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") refresh();
    };
    window.addEventListener("pageshow", onPageShow);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("pageshow", onPageShow);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [refresh]);

  return (
    <UserCtx.Provider value={{ user, loading, mustAddCard, refresh, signout }}>
      {children}
    </UserCtx.Provider>
  );
}
