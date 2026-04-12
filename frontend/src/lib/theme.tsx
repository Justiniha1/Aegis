"use client";

import { createContext, useContext, useEffect, useState } from "react";

type Theme = "dark" | "light";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "dark",
  setTheme: () => {},
  toggle: () => {},
});

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("dqf-theme") as Theme | null;
    if (saved === "light" || saved === "dark") setThemeState(saved);
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    localStorage.setItem("dqf-theme", theme);
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme, mounted]);

  const setTheme = (t: Theme) => setThemeState(t);
  const toggle = () => setThemeState((prev) => (prev === "dark" ? "light" : "dark"));

  // Prevent flash of wrong theme
  if (!mounted) return null;

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);

/* ── CSS variable classes for components ─────────────────────────────────── */
export const t = {
  // Backgrounds
  bg: (theme: Theme) => theme === "dark" ? "bg-gray-950" : "bg-gray-50",
  bgCard: (theme: Theme) => theme === "dark" ? "bg-gray-900" : "bg-white",
  bgHover: (theme: Theme) => theme === "dark" ? "hover:bg-gray-800/30" : "hover:bg-gray-100",
  bgInput: (theme: Theme) => theme === "dark" ? "bg-gray-800" : "bg-gray-100",
  bgSidebar: (theme: Theme) => theme === "dark" ? "bg-gray-900" : "bg-white",

  // Borders
  border: (theme: Theme) => theme === "dark" ? "border-gray-800" : "border-gray-200",
  borderLight: (theme: Theme) => theme === "dark" ? "border-gray-700" : "border-gray-300",

  // Text
  text: (theme: Theme) => theme === "dark" ? "text-white" : "text-gray-900",
  textSecondary: (theme: Theme) => theme === "dark" ? "text-gray-400" : "text-gray-600",
  textMuted: (theme: Theme) => theme === "dark" ? "text-gray-500" : "text-gray-400",
  textDim: (theme: Theme) => theme === "dark" ? "text-gray-600" : "text-gray-300",
};
