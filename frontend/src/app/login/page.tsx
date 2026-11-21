"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { Lock, User, AlertCircle, ArrowRight } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await api.post("/auth/login/", { username, password });
      const { access, refresh } = res.data;
      localStorage.setItem("token", access);
      localStorage.setItem("refreshToken", refresh);

      // Fetch user profile to know the role
      const profileRes = await api.get("/user/me/");
      const user = profileRes.data.user;
      localStorage.setItem("user", JSON.stringify(user));

      // Route based on role
      if (user.role === "admin") {
        router.push("/admin");
      } else if (user.role === "staff") {
        router.push("/staff");
      } else {
        router.push("/citizen");
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Invalid username or password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      <Navbar />
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-white p-8 rounded-2xl border border-gray-200 shadow-xl">
          <div className="text-center mb-6">
            <div className="w-12 h-12 bg-[#A94D37] text-white rounded-xl flex items-center justify-center font-bold text-lg mx-auto mb-3 shadow">
              JS
            </div>
            <h1 className="text-2xl font-bold text-[#17191D]">Sign in to JanSahayak</h1>
            <p className="text-xs text-gray-500 mt-1">Access your citizen portal or administrative workspace</p>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Username</label>
              <div className="relative">
                <User className="w-4 h-4 text-gray-400 absolute left-3 top-3" />
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter your username"
                  className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37]"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-gray-400 absolute left-3 top-3" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37]"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-[#A94D37] hover:bg-[#8e3e2b] text-white font-medium text-sm rounded-lg transition shadow flex items-center justify-center gap-2"
            >
              {loading ? "Authenticating..." : "Sign In"} <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          <p className="text-center text-xs text-gray-600 mt-6">
            Don&apos;t have an account yet?{" "}
            <Link href="/signup" className="text-[#A94D37] font-semibold hover:underline">
              Create an Account
            </Link>
          </p>
        </div>
      </div>
      <Footer />
    </div>
  );
}
