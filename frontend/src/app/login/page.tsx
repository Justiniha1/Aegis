"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const { theme } = useTheme();
  const dark = theme === "dark";
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const inputCls = `w-full px-3 py-2 rounded-lg border focus:outline-none focus:border-blue-500 ${
    dark
      ? "bg-gray-800 border-gray-700 text-white placeholder-gray-500"
      : "bg-white border-gray-300 text-gray-900 placeholder-gray-400"
  }`;

  return (
    <div className={`min-h-screen flex items-center justify-center ${dark ? "bg-gray-950" : "bg-gray-50"}`}>
      <div className="w-full max-w-sm">
        <div className={`rounded-xl border p-8 shadow-xl ${dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"}`}>
          <h1 className={`text-2xl font-bold mb-1 ${dark ? "text-white" : "text-gray-900"}`}>DQF Dashboard</h1>
          <p className={`mb-8 text-sm ${dark ? "text-gray-400" : "text-gray-500"}`}>
            Sign in to monitor your data quality
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className={`block text-sm mb-1 ${dark ? "text-gray-300" : "text-gray-700"}`}>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className={inputCls}
                placeholder="you@company.com"
              />
            </div>
            <div>
              <label className={`block text-sm mb-1 ${dark ? "text-gray-300" : "text-gray-700"}`}>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className={inputCls}
                placeholder="Enter your password"
              />
            </div>

            {error && (
              <p className="text-red-500 text-sm bg-red-500/10 px-3 py-2 rounded-lg">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 disabled:text-gray-400 text-white rounded-lg font-medium transition-colors"
            >
              {loading ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
