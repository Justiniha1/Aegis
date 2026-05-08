"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/dashboard/tests", label: "Tests" },
  { href: "/dashboard/history", label: "History" },
  { href: "/dashboard/settings", label: "Settings" },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { clientName, logout } = useAuth();
  const { theme, toggle } = useTheme();

  const dark = theme === "dark";

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <div className={`h-screen flex ${dark ? "bg-gray-950" : "bg-gray-50"}`}>
      {/* Sidebar */}
      <aside className={`w-56 border-r flex flex-col ${dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"}`}>
        <div className={`px-5 py-6 border-b ${dark ? "border-gray-800" : "border-gray-200"}`}>
          <h1 className={`text-lg font-bold ${dark ? "text-white" : "text-gray-900"}`}>Aegis</h1>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block px-3 py-2 rounded-lg text-sm transition-colors ${
                  active
                    ? "bg-blue-600/20 text-blue-400 font-medium"
                    : dark
                    ? "text-gray-400 hover:text-white hover:bg-gray-800"
                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className={`px-5 py-4 border-t ${dark ? "border-gray-800" : "border-gray-200"}`}>
          <div className="flex items-center justify-between">
            <p className={`text-sm truncate ${dark ? "text-white" : "text-gray-900"}`}>{clientName}</p>
            {/* Quick theme toggle */}
            <button
              onClick={toggle}
              className={`text-sm transition-colors ${dark ? "text-gray-500 hover:text-white" : "text-gray-400 hover:text-gray-700"}`}
              title={`Switch to ${dark ? "light" : "dark"} mode`}
            >
              {dark ? "☀️" : "🌙"}
            </button>
          </div>
          <button
            onClick={handleLogout}
            className={`text-xs mt-1 transition-colors ${dark ? "text-gray-500 hover:text-red-400" : "text-gray-400 hover:text-red-500"}`}
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 p-8 overflow-auto">{children}</main>
    </div>
  );
}
