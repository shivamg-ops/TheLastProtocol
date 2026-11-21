"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Mic,
  ChevronDown,
  Shield,
  Briefcase,
  Users,
  LogOut,
  Sparkles,
  LayoutDashboard,
  Search,
} from "lucide-react";
import { useEffect, useState, useRef } from "react";

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<{ username: string; role: string } | null>(null);
  const [portalsOpen, setPortalsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("user");
      if (stored) {
        setUser(JSON.parse(stored));
      }
    } catch {
      // ignore
    }

    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setPortalsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
    router.push("/login");
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

          {/* Clean Public Navigation Links */}
          <div className="hidden md:flex items-center space-x-7 text-xs font-semibold tracking-wide">
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

            {/* Quick Track link */}
            <Link
              href="/citizen"
              className={`flex items-center gap-1.5 transition hover:text-white ${
                pathname.startsWith("/citizen") ? "text-[#A94D37]" : "text-gray-300"
              }`}
            >
              <Search className="w-3.5 h-3.5 text-gray-400" /> Track Status
            </Link>

            {/* Portals Dropdown */}
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setPortalsOpen(!portalsOpen)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800/80 hover:bg-gray-800 border border-gray-700/80 text-gray-200 text-xs font-semibold transition"
              >
                <span>Workspaces</span>
                <ChevronDown
                  className={`w-3.5 h-3.5 transition-transform duration-200 ${
                    portalsOpen ? "rotate-180 text-[#A94D37]" : "text-gray-400"
                  }`}
                />
              </button>

              {portalsOpen && (
                <div className="absolute right-0 mt-2 w-64 bg-[#1f2329] border border-gray-700 rounded-xl shadow-2xl py-2 z-50 text-xs animate-in fade-in slide-in-from-top-2">
                  <div className="px-3 py-1.5 text-[10px] uppercase font-bold text-gray-400 tracking-wider">
                    Role-Based Portals
                  </div>

                  <Link
                    href="/citizen"
                    onClick={() => setPortalsOpen(false)}
                    className="flex items-start gap-3 px-3.5 py-2.5 hover:bg-gray-800 transition text-gray-200 group"
                  >
                    <div className="p-1.5 rounded-lg bg-blue-950/60 text-blue-400 group-hover:bg-blue-900 transition">
                      <Users className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="font-semibold text-white">Citizen Portal</div>
                      <div className="text-[11px] text-gray-400">File & track community issues</div>
                    </div>
                  </Link>

                  <Link
                    href="/staff"
                    onClick={() => setPortalsOpen(false)}
                    className="flex items-start gap-3 px-3.5 py-2.5 hover:bg-gray-800 transition text-gray-200 group"
                  >
                    <div className="p-1.5 rounded-lg bg-amber-950/60 text-amber-400 group-hover:bg-amber-900 transition">
                      <Briefcase className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="font-semibold text-white">Staff Workspace</div>
                      <div className="text-[11px] text-gray-400">Field tasks & resolution proof</div>
                    </div>
                  </Link>

                  <Link
                    href="/admin"
                    onClick={() => setPortalsOpen(false)}
                    className="flex items-start gap-3 px-3.5 py-2.5 hover:bg-gray-800 transition text-gray-200 group border-t border-gray-800/80"
                  >
                    <div className="p-1.5 rounded-lg bg-red-950/60 text-[#A94D37] group-hover:bg-red-900 transition">
                      <Shield className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="font-semibold text-white">Admin Command</div>
                      <div className="text-[11px] text-gray-400">SLAs, triage & department dispatch</div>
                    </div>
                  </Link>
                </div>
              )}
            </div>
          </div>

          {/* Right Action Buttons */}
          <div className="flex items-center gap-3">
            {/* Primary Report CTA Button */}
            <Link
              href="/report"
              className="hidden sm:inline-flex items-center gap-2 px-3.5 py-2 bg-gradient-to-r from-[#A94D37] to-[#8e3e2b] hover:opacity-95 text-white text-xs font-semibold rounded-lg shadow-sm transition"
            >
              <Mic className="w-3.5 h-3.5" /> Voice / AI Report
            </Link>

            {user ? (
              <div className="flex items-center gap-2.5">
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
