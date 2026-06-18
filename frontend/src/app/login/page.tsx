"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import {
  BRAND_NAVY,
  BRAND_TEAL,
  NEUTRAL_SCALE,
  STATUS_PALETTE,
} from "@/lib/constants";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const { theme } = useTheme();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      const raw = err instanceof Error ? err.message : "";
      const isNetwork = /network|fetch|reach|connect|abort|failed to fetch/i.test(raw);
      setError(
        isNetwork
          ? "Can't reach the server. Try again, or check that the API is running."
          : "Sign-in failed — check your email and password and try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{ backgroundColor: palette.surfaceBg }}
    >
      <div style={{ width: "100%", maxWidth: "360px" }}>
        <div
          style={{
            backgroundColor: palette.surfaceElevated,
            border: `1px solid ${palette.borderSubtle}`,
            borderRadius: "8px",
            padding: "32px",
          }}
        >
          {/* Brand: 32px teal monogram + Comet-dq wordmark (login uses the full name) */}
          <div className="flex items-center gap-3 mb-6">
            <div
              className="flex items-center justify-center"
              style={{
                width: "32px",
                height: "32px",
                backgroundColor: BRAND_TEAL,
                borderRadius: "6px",
                fontFamily: "var(--font-jetbrains-mono)",
                fontSize: "14px",
                fontWeight: 600,
                color: "#FFFFFF",
                lineHeight: 1,
              }}
              aria-label="Comet-dq"
            >
              Co
            </div>
            <h1
              className="text-display"
              style={{
                color: palette.textPrimary,
                letterSpacing: "-0.01em",
              }}
            >
              Comet-dq
            </h1>
          </div>

          <p
            className="mb-6 text-body"
            style={{
              fontFamily: "var(--font-jetbrains-mono)",
              color: palette.textSecondary,
            }}
          >
            Sign in to your data quality dashboard
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                className="block text-caption mb-1"
                style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0", fontWeight: 500 }}
              >
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@company.com"
                className="w-full px-3 text-body focus:outline-none"
                style={{
                  height: "36px",
                  backgroundColor: palette.surfaceBg,
                  color: palette.textPrimary,
                  border: `1px solid ${palette.borderSubtle}`,
                  borderRadius: "8px",
                }}
              />
            </div>
            <div>
              <label
                className="block text-caption mb-1"
                style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0", fontWeight: 500 }}
              >
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="Enter your password"
                className="w-full px-3 text-body focus:outline-none"
                style={{
                  height: "36px",
                  backgroundColor: palette.surfaceBg,
                  color: palette.textPrimary,
                  border: `1px solid ${palette.borderSubtle}`,
                  borderRadius: "8px",
                }}
              />
            </div>

            {error && (
              <p
                className="text-body px-3 py-2"
                style={{
                  color: STATUS_PALETTE.FAILED,
                  backgroundColor: `${STATUS_PALETTE.FAILED}1A`,
                  border: `1px solid ${STATUS_PALETTE.FAILED}33`,
                  borderRadius: "8px",
                }}
                role="alert"
              >
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full text-body font-medium transition-colors"
              style={{
                height: "36px",
                backgroundColor: BRAND_NAVY,
                color: "#FFFFFF",
                border: "none",
                borderRadius: "8px",
                cursor: loading ? "not-allowed" : "pointer",
                opacity: loading ? 0.5 : 1,
              }}
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
