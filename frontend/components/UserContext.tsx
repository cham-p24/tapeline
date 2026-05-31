"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { authApi, type SessionUser } from "@/lib/auth";

type Ctx = {
  user: SessionUser | null;
  loading: boolean;
  refresh: () => Promise<void>;
  signout: () => Promise<void>;
};

const UserCtx = createContext<Ctx>({
  user: null, loading: true, refresh: async () => {}, signout: async () => {},
});

export function useUser() { return useContext(UserCtx); }

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { user } = await authApi.session();
      setUser(user);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const signout = useCallback(async () => {
    try { await authApi.signout(); } catch {}
    setUser(null);
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
    <UserCtx.Provider value={{ user, loading, refresh, signout }}>
      {children}
    </UserCtx.Provider>
  );
}
