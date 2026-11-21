"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Mic, LogOut, LayoutDashboard } from "lucide-react";
import { useEffect, useState } from "react";
import NotificationBell from "./NotificationBell";

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<{ username: string; role: string } | null>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("user");
      if (stored) {
        setUser(JSON.parse(stored));
      }
    } catch {
      // ignore
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
    router.push("/login");
  };

  // Determine user's specific portal path based on their role
  const getDashboardPath = (role?: string) => {
    if (role === "admin") return "/admin";
    if (role === "staff") return "/staff";
    return "/citizen";
  };

  return (
    <nav className="bg-[#17191D] text-white border-b border-gray-800 sticky top-0 z-50 shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo */}
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#A94D37] to-[#8e3e2b] flex items-center justify-center font-bold text-white shadow-md group-hover:scale-105 transition">
                JS
              </div>
              <div>
                <span className="font-extrabold text-xl tracking-tight text-white">
                  JANSAHAYAK <span className="text-[#A94D37]">AI</span>
                </span>
                <p className="text-[9px] text-gray-400 font-medium tracking-widest uppercase">
                  From Voice to Resolution
                </p>
              </div>
            </Link>
          </div>

          {/* Clean Public Navigation Links (Standard SaaS) */}
          <div className="hidden md:flex items-center space-x-8 text-xs font-semibold tracking-wide">
            <Link
              href="/"
              className={`transition hover:text-white ${
                pathname === "/" ? "text-[#A94D37]" : "text-gray-300"
              }`}
            >
              Overview
            </Link>

            <Link
              href="/#categories"
              className="text-gray-300 hover:text-white transition"
            >
              Civic Verticals
            </Link>

            <Link
              href="/#workflow"
              className="text-gray-300 hover:text-white transition"
            >
              How It Works
            </Link>

            {/* If user is logged in, show their personal Dashboard link */}
            {user && (
              <Link
                href={getDashboardPath(user.role)}
                className={`flex items-center gap-1.5 transition hover:text-white ${
                  pathname.startsWith(getDashboardPath(user.role))
                    ? "text-[#A94D37]"
                    : "text-gray-300"
                }`}
              >
                <LayoutDashboard className="w-3.5 h-3.5 text-[#A94D37]" /> Dashboard
              </Link>
            )}
          </div>

          {/* Right Action Buttons */}
          <div className="flex items-center gap-3">
            <Link
              href="/report"
              className="hidden sm:inline-flex items-center gap-2 px-3.5 py-2 bg-gradient-to-r from-[#A94D37] to-[#8e3e2b] hover:opacity-95 text-white text-xs font-semibold rounded-lg shadow-sm transition"
            >
              <Mic className="w-3.5 h-3.5" /> Voice / AI Report
            </Link>

            {user ? (
              <div className="flex items-center gap-2.5">
                <NotificationBell />
                <span className="text-[11px] bg-gray-800 border border-gray-700 px-2.5 py-1 rounded-full text-gray-300 font-medium">
                  {user.username}{" "}
                  <strong className="text-[#A94D37] capitalize font-semibold">
                    ({user.role})
                  </strong>
                </span>
                <button
                  onClick={handleLogout}
                  className="text-xs bg-red-950/60 hover:bg-red-900 border border-red-800/80 text-red-200 px-2.5 py-1.5 rounded-lg flex items-center gap-1.5 transition"
                  title="Sign Out"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  href="/login"
                  className="text-xs px-3 py-1.5 text-gray-300 hover:text-white font-medium transition"
                >
                  Sign In
                </Link>
                <Link
                  href="/signup"
                  className="text-xs px-3.5 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-white font-semibold rounded-lg transition"
                >
                  Register
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
