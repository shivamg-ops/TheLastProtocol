"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { Mail, Lock, AlertCircle, ArrowRight, KeyRound, CheckCircle2 } from "lucide-react";

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [step, setStep] = useState<"email" | "reset">("email");

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await api.post("/auth/otp/send_otp/", {
        email: email.trim(),
        purpose: "reset_password",
      });
      setStep("reset");
      setSuccess(res.data.message || `Password reset OTP sent to ${email}`);
    } catch (err: any) {
      setError(err.response?.data?.error || "Failed to send OTP code.");
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await api.post("/auth/otp/reset_password_with_otp/", {
        email: email.trim(),
        otp: otp.trim(),
        new_password: newPassword,
      });
      setSuccess("Password reset successfully! Redirecting to login...");
      setTimeout(() => {
        router.push("/login");
      }, 2000);
    } catch (err: any) {
      setError(err.response?.data?.error || "Failed to reset password. Check your OTP.");
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
              <KeyRound className="w-6 h-6" />
            </div>
            <h1 className="text-2xl font-bold text-[#17191D]">Reset Password</h1>
            <p className="text-xs text-gray-500 mt-1">
              Securely reset your password using a 6-digit Gmail OTP
            </p>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="mb-4 p-3 bg-green-50 border border-green-200 text-green-700 text-xs rounded-lg flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{success}</span>
            </div>
          )}

          {step === "email" ? (
            <form onSubmit={handleSendOtp} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Registered Email Address
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-gray-400 absolute left-3 top-3" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Enter your registered email"
                    className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37]"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 bg-[#A94D37] hover:bg-[#8e3e2b] text-white font-medium text-sm rounded-lg transition shadow flex items-center justify-center gap-2"
              >
                {loading ? "Sending OTP..." : "Send Reset Code"} <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          ) : (
            <form onSubmit={handleResetPassword} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  6-Digit OTP Code
                </label>
                <input
                  type="text"
                  maxLength={6}
                  required
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                  placeholder="Enter 6-digit code from email"
                  className="w-full px-3 py-2 text-center text-lg font-mono tracking-widest border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  New Password
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-gray-400 absolute left-3 top-3" />
                  <input
                    type="password"
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Minimum 8 characters"
                    className="w-full pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37]"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 bg-[#25845B] hover:bg-[#1f6d4b] text-white font-medium text-sm rounded-lg transition shadow flex items-center justify-center gap-2"
              >
                {loading ? "Updating Password..." : "Set New Password"}
                <CheckCircle2 className="w-4 h-4" />
              </button>
            </form>
          )}

          <div className="text-center mt-6">
            <Link href="/login" className="text-xs text-gray-500 hover:text-[#A94D37] underline">
              Back to Sign In
            </Link>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}
