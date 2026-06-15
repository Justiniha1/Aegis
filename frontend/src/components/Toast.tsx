"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";
import Link from "next/link";
import { useTheme } from "@/lib/theme";
import { NEUTRAL_SCALE, STATUS_PALETTE } from "@/lib/constants";

interface ToastPayload { message: string; href?: string; }
interface ToastCtx { showToast: (t: ToastPayload) => void; }

const Ctx = createContext<ToastCtx | null>(null);
const AUTO_DISMISS_MS = 8000;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const { theme } = useTheme();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const [toast, setToast] = useState<ToastPayload | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback((t: ToastPayload) => {
    if (timer.current) clearTimeout(timer.current);
    setToast(t);
    timer.current = setTimeout(() => setToast(null), AUTO_DISMISS_MS);
  }, []);

  const dismiss = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    setToast(null);
  }, []);

  return (
    <Ctx.Provider value={{ showToast }}>
      {children}
      {toast && (
        <div
          role="status"
          className="fixed bottom-12 right-6 z-50 max-w-sm px-4 py-3 flex items-start gap-3"
          style={{
            backgroundColor: palette.surfaceElevated,
            border: `1px solid ${STATUS_PALETTE.FAILED}`,
            borderRadius: "8px",
            boxShadow: "0 6px 20px rgb(0 0 0 / 0.18)",
          }}
        >
          <span style={{ display: "inline-block", marginTop: "5px", width: "8px", height: "8px", borderRadius: "9999px", backgroundColor: STATUS_PALETTE.FAILED, flex: "0 0 auto" }} />
          <div className="min-w-0">
            <p className="text-body" style={{ color: palette.textPrimary }}>{toast.message}</p>
            {toast.href && (
              <Link href={toast.href} onClick={dismiss} className="text-caption" style={{ color: STATUS_PALETTE.FAILED, textTransform: "none", letterSpacing: "0" }}>
                View detail
              </Link>
            )}
          </div>
          <button onClick={dismiss} aria-label="Dismiss" className="text-caption" style={{ color: palette.textSecondary, background: "none", border: "none", cursor: "pointer" }}>
            Close
          </button>
        </div>
      )}
    </Ctx.Provider>
  );
}

export function useToast(): ToastCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
