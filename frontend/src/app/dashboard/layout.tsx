"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/dashboard/tests", label: "Tests" },
  { href: "/dashboard/history", label: "History" },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { clientName, logout } = useAuth();

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <div className="min-h-screen bg-gray-950 flex">
      {/* Sidebar */}
      <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="px-5 py-5 border-b border-gray-800">
          <h1 className="text-lg font-bold text-white">DQF</h1>
          <p className="text-xs text-gray-500 mt-0.5">Data Quality Framework</p>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block px-3 py-2 rounded-lg text-sm transition-colors ${
                  active
                    ? "bg-blue-600/20 text-blue-400 font-medium"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="px-5 py-4 border-t border-gray-800">
          <p className="text-sm text-white truncate">{clientName}</p>
          <button
            onClick={handleLogout}
            className="text-xs text-gray-500 hover:text-red-400 mt-1 transition-colors"
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
