"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { Lock, User, Mail, AlertCircle, ArrowRight, KeyRound, CheckCircle2 } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [authMode, setAuthMode] = useState<"password" | "otp">("password");

  // Standard password login state
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  // OTP login state
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otpLoading, setOtpLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await api.post("/auth/login/", { username, password });
      const { access, refresh } = res.data;
      localStorage.setItem("token", access);
      localStorage.setItem("refreshToken", refresh);

      const profileRes = await api.get("/user/me/");
      const user = profileRes.data.user;
      localStorage.setItem("user", JSON.stringify(user));

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

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccessMsg("");
    setOtpLoading(true);

    try {
      const res = await api.post("/auth/otp/send_otp/", {
        email: email.trim(),
        purpose: "login",
      });
      setOtpSent(true);
      setSuccessMsg(res.data.message || `Verification OTP sent to ${email}`);
    } catch (err: any) {
      setError(err.response?.data?.error || "Failed to send OTP code to your email.");
    } finally {
      setOtpLoading(false);
    }
  };

  const handleVerifyOtpLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await api.post("/auth/otp/verify_login_otp/", {
        email: email.trim(),
        otp: otp.trim(),
      });

      const { access, refresh, user } = res.data;
      localStorage.setItem("token", access);
      localStorage.setItem("refreshToken", refresh);
      localStorage.setItem("user", JSON.stringify(user));

      if (user.role === "admin") {
        router.push("/admin");
      } else if (user.role === "staff") {
        router.push("/staff");
      } else {
        router.push("/citizen");
      }
    } catch (err: any) {
      setError(err.response?.data?.error || "Invalid or expired OTP code.");
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
            <div className="w-12 h-12 bg-[#DC2626] text-white rounded-xl flex items-center justify-center font-bold text-lg mx-auto mb-3 shadow">
              JS
            </div>
            <h1 className="text-2xl font-bold text-[#17191D]">Sign in to JanSahayak</h1>
            <p className="text-xs text-gray-500 mt-1">Access your citizen portal or administrative workspace</p>
          </div>

          {/* Toggle Login Method */}
          <div className="flex rounded-lg bg-gray-100 p-1 mb-6 text-xs font-semibold">
            <button
              type="button"
              onClick={() => {
                setAuthMode("password");
                setError("");
                setSuccessMsg("");
              }}
              className={`flex-1 py-1.5 rounded-md transition ${authMode === "password"
                ? "bg-white text-[#17191D] shadow-sm"
                : "text-gray-500 hover:text-gray-900"
                }`}
            >
              Password Login
            </button>
            <button
              type="button"
              onClick={() => {
                setAuthMode("otp");
                setError("");
                setSuccessMsg("");
              }}
              className={`flex-1 py-1.5 rounded-md transition flex items-center justify-center gap-1.5 ${authMode === "otp"
                ? "bg-white text-[#DC2626] shadow-sm"
                : "text-gray-500 hover:text-gray-900"
                }`}
            >
              <KeyRound className="w-3.5 h-3.5" /> Email OTP
            </button>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="mb-4 p-3 bg-green-50 border border-green-200 text-green-700 text-xs rounded-lg flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {authMode === "password" ? (
            <form onSubmit={handlePasswordLogin} className="space-y-4">
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
                    className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#DC2626]"
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-semibold text-gray-700">Password</label>
                  <Link
                    href="/forgot-password"
                    className="text-[11px] text-[#DC2626] hover:underline font-medium"
                  >
                    Forgot?
                  </Link>
                </div>
                <div className="relative">
                  <Lock className="w-4 h-4 text-gray-400 absolute left-3 top-3" />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#DC2626]"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 bg-[#DC2626] hover:bg-[#B91C1C] text-white font-medium text-sm rounded-lg transition shadow flex items-center justify-center gap-2"
              >
                {loading ? "Authenticating..." : "Sign In"} <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          ) : (
            <div className="space-y-4">
              {!otpSent ? (
                <form onSubmit={handleSendOtp} className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1">
                      Account Registered Email
                    </label>
                    <div className="relative">
                      <Mail className="w-4 h-4 text-gray-400 absolute left-3 top-3" />
                      <input
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="e.g. citizen@example.com"
                        className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#DC2626]"
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={otpLoading}
                    className="w-full py-2.5 bg-[#DC2626] hover:bg-[#B91C1C] text-white font-medium text-sm rounded-lg transition shadow flex items-center justify-center gap-2"
                  >
                    {otpLoading ? "Sending OTP via Gmail..." : "Send Verification OTP"}
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </form>
              ) : (
                <form onSubmit={handleVerifyOtpLogin} className="space-y-4">
                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <label className="block text-xs font-semibold text-gray-700">
                        Enter 6-digit OTP
                      </label>
                      <button
                        type="button"
                        onClick={() => {
                          setOtpSent(false);
                          setOtp("");
                        }}
                        className="text-[11px] text-[#DC2626] hover:underline"
                      >
                        Change Email
                      </button>
                    </div>
                    <div className="relative">
                      <KeyRound className="w-4 h-4 text-gray-400 absolute left-3 top-3" />
                      <input
                        type="text"
                        maxLength={6}
                        required
                        value={otp}
                        onChange={(e) => setOtp(e.target.value)}
                        placeholder="6-digit code"
                        className="w-full pl-9 pr-3 py-2 text-center text-lg font-mono tracking-widest border border-gray-300 rounded-lg focus:outline-none focus:border-[#DC2626]"
                      />
                    </div>
                    <p className="text-[11px] text-gray-500 mt-1">
                      Check your inbox at <span className="font-medium text-gray-700">{email}</span>
                    </p>
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full py-2.5 bg-[#25845B] hover:bg-[#1f6d4b] text-white font-medium text-sm rounded-lg transition shadow flex items-center justify-center gap-2"
                  >
                    {loading ? "Verifying..." : "Verify OTP & Log In"}
                    <CheckCircle2 className="w-4 h-4" />
                  </button>

                  <div className="text-center pt-2">
                    <button
                      type="button"
                      onClick={handleSendOtp}
                      disabled={otpLoading}
                      className="text-xs text-gray-500 hover:text-[#DC2626] underline"
                    >
                      {otpLoading ? "Resending..." : "Didn't receive code? Resend OTP"}
                    </button>
                  </div>
                </form>
              )}
            </div>
          )}

          <p className="text-center text-xs text-gray-600 mt-6">
            Don&apos;t have an account yet?{" "}
            <Link href="/signup" className="text-[#DC2626] font-semibold hover:underline">
              Create an Account
            </Link>
          </p>
        </div>
      </div>
      <Footer />
    </div>
  );
}
