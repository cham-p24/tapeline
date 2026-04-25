"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

type ToastKind = "info" | "success" | "error";
type Toast = { id: number; msg: string; kind: ToastKind };

const ToastCtx = createContext<{ push: (msg: string, kind?: ToastKind) => void }>({ push: () => {} });

export function useToast() { return useContext(ToastCtx); }

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);

  const push = useCallback((msg: string, kind: ToastKind = "info") => {
    const id = ++idRef.current;
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3500);
  }, []);

  return (
    <ToastCtx.Provider value={{ push }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex flex-col items-end gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`card pointer-events-auto min-w-[260px] px-4 py-3 text-sm shadow-xl ${
              t.kind === "success" ? "border-up/40" :
              t.kind === "error" ? "border-down/40" : ""
            }`}
          >
            <span className={
              t.kind === "success" ? "text-up" :
              t.kind === "error" ? "text-down" : "text-fg"
            }>{t.msg}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
