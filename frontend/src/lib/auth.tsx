"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { apiPost } from "./api";

interface AuthState {
  token: string | null;
  clientId: number | null;
  clientName: string | null;
}

interface AuthContextType extends AuthState {
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState>({
    token: null,
    clientId: null,
    clientName: null,
  });
  const [isLoading, setIsLoading] = useState(true);

  // Restore from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("dqf_auth");
    if (saved) {
      try {
        setAuth(JSON.parse(saved));
      } catch {
        localStorage.removeItem("dqf_auth");
      }
    }
    setIsLoading(false);
  }, []);

  const login = async (email: string, password: string) => {
    const data = await apiPost("/api/v1/auth/login", { email, password });
    const state: AuthState = {
      token: data.access_token,
      clientId: data.client_id,
      clientName: data.client_name,
    };
    setAuth(state);
    localStorage.setItem("dqf_auth", JSON.stringify(state));
  };

  const logout = () => {
    setAuth({ token: null, clientId: null, clientName: null });
    localStorage.removeItem("dqf_auth");
  };

  return (
    <AuthContext.Provider value={{ ...auth, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
