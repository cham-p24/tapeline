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

  return (
    <UserCtx.Provider value={{ user, loading, refresh, signout }}>
      {children}
    </UserCtx.Provider>
  );
}
