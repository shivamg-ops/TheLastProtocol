"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { useEffect, useState } from "react";

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
      // ignore JSON parse error
    }
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
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2">
              <div className="w-10 h-10 rounded-lg bg-[#A94D37] flex items-center justify-center font-bold text-white shadow-inner">
                JS
              </div>
              <div>
                <span className="font-extrabold text-xl tracking-tight text-white">
                  JANSAHAYAK <span className="text-[#A94D37]">AI</span>
                </span>
                <p className="text-[10px] text-gray-400 -mt-1 font-medium tracking-wide">
                  FROM VOICE TO RESOLUTION
                </p>
              </div>
            </Link>
          </div>

          <div className="hidden md:flex items-center space-x-6 text-sm font-medium">
            <Link
              href="/"
              className={`hover:text-[#A94D37] transition ${
                pathname === "/" ? "text-[#A94D37]" : "text-gray-300"
              }`}
            >
              Home
            </Link>
            <Link
              href="/report"
              className={`hover:text-[#A94D37] transition ${
                pathname === "/report" ? "text-[#A94D37]" : "text-gray-300"
              }`}
            >
              Report Issue
            </Link>
            <Link
              href="/citizen"
              className={`hover:text-[#A94D37] transition ${
                pathname.startsWith("/citizen") ? "text-[#A94D37]" : "text-gray-300"
              }`}
            >
              Citizen Portal
            </Link>
            <Link
              href="/staff"
              className={`hover:text-[#A94D37] transition ${
                pathname.startsWith("/staff") ? "text-[#A94D37]" : "text-gray-300"
              }`}
            >
              Staff Workspace
            </Link>
            <Link
              href="/admin"
              className={`hover:text-[#A94D37] transition ${
                pathname.startsWith("/admin") ? "text-[#A94D37]" : "text-gray-300"
              }`}
            >
              Admin Centre
            </Link>
          </div>

          <div className="flex items-center gap-3">
            {user ? (
              <div className="flex items-center gap-3">
                <span className="text-xs bg-gray-800 border border-gray-700 px-2.5 py-1 rounded-full text-gray-300">
                  {user.username} <strong className="text-[#A94D37] capitalize">({user.role})</strong>
                </span>
                <button
                  onClick={handleLogout}
                  className="text-xs bg-red-950/60 hover:bg-red-900 border border-red-800/80 text-red-200 px-3 py-1.5 rounded-md flex items-center gap-1.5 transition"
                >
                  <LogOut className="w-3.5 h-3.5" /> Logout
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  href="/login"
                  className="text-sm px-4 py-2 text-gray-200 hover:text-white transition"
                >
                  Log In
                </Link>
                <Link
                  href="/signup"
                  className="text-sm px-4 py-2 bg-[#A94D37] hover:bg-[#8e3e2b] text-white font-medium rounded-lg shadow-sm transition"
                >
                  Sign Up
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
