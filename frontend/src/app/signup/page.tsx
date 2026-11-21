"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { User, Mail, Lock, AlertCircle, ArrowRight, KeyRound, CheckCircle2 } from "lucide-react";

export default function SignupPage() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    username: "",
    email: "",
    password: "",
    first_name: "",
    last_name: "",
    role: "citizen",
    phone_number: "",
    preferred_language: "en",
    organization_name: "",
  });

  const [otp, setOtp] = useState("");
  const [isOtpSent, setIsOtpSent] = useState(false);
  const [isEmailVerified, setIsEmailVerified] = useState(false);
  const [otpLoading, setOtpLoading] = useState(false);
  const [otpSuccessMsg, setOtpSuccessMsg] = useState("");

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSendSignupOtp = async () => {
    if (!formData.email) {
      setError("Please enter your email address first to verify.");
      return;
    }
    setError("");
    setOtpSuccessMsg("");
    setOtpLoading(true);

    try {
      const res = await api.post("/auth/otp/send_otp/", {
        email: formData.email.trim(),
        purpose: "signup",
      });
      setIsOtpSent(true);
      setOtpSuccessMsg(res.data.message || `Verification code sent to ${formData.email}`);
    } catch (err: any) {
      setError(err.response?.data?.error || "Failed to send verification code.");
    } finally {
      setOtpLoading(false);
    }
  };

  const handleVerifySignupOtp = async () => {
    if (!otp) {
      setError("Please enter the 6-digit OTP code.");
      return;
    }
    setError("");
    setOtpLoading(true);

    try {
      await api.post("/auth/otp/verify_signup_otp/", {
        email: formData.email.trim(),
        otp: otp.trim(),
      });
      setIsEmailVerified(true);
      setOtpSuccessMsg("Email successfully verified with Gmail OTP!");
    } catch (err: any) {
      setError(err.response?.data?.error || "Invalid or expired OTP code.");
    } finally {
      setOtpLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isEmailVerified) {
      setError("Please verify your email address via OTP before registering.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      await api.post("/auth/register/", formData);
      router.push("/login?registered=true");
    } catch (err: any) {
      const msg = err.response?.data?.username?.[0] || err.response?.data?.email?.[0] || "Registration failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      <Navbar />
      <div className="flex-1 flex items-center justify-center p-4 py-8">
        <div className="w-full max-w-lg bg-white p-8 rounded-2xl border border-gray-200 shadow-xl">
          <div className="text-center mb-6">
            <h1 className="text-2xl font-bold text-[#17191D]">Create an Account</h1>
            <p className="text-xs text-gray-500 mt-1">Register as a Citizen, NGO or Society Representative</p>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {otpSuccessMsg && (
            <div className="mb-4 p-3 bg-green-50 border border-green-200 text-green-700 text-xs rounded-lg flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{otpSuccessMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">First Name</label>
                <input
                  type="text"
                  required
                  value={formData.first_name}
                  onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37]"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Last Name</label>
                <input
                  type="text"
                  value={formData.last_name}
                  onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37]"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Username</label>
              <input
                type="text"
                required
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37]"
              />
            </div>

            {/* Email & OTP Verification */}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">
                Email Address {isEmailVerified && <span className="text-[#25845B] font-bold">(Verified ✓)</span>}
              </label>
              <div className="flex gap-2">
                <input
                  type="email"
                  required
                  disabled={isEmailVerified}
                  value={formData.email}
                  onChange={(e) => {
                    setFormData({ ...formData, email: e.target.value });
                    setIsOtpSent(false);
                    setIsEmailVerified(false);
                  }}
                  className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37] disabled:bg-gray-100"
                  placeholder="e.g. citizen@gmail.com"
                />
                {!isEmailVerified && (
                  <button
                    type="button"
                    onClick={handleSendSignupOtp}
                    disabled={otpLoading || !formData.email}
                    className="px-3.5 py-2 bg-[#A94D37] hover:bg-[#8e3e2b] text-white text-xs font-semibold rounded-lg transition disabled:opacity-50 shrink-0"
                  >
                    {otpLoading ? "Sending..." : isOtpSent ? "Resend OTP" : "Verify Email"}
                  </button>
                )}
              </div>
            </div>

            {/* OTP Input Field when sent */}
            {isOtpSent && !isEmailVerified && (
              <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-xl space-y-2">
                <label className="block text-xs font-semibold text-[#17191D]">
                  Enter 6-Digit Code sent to your Gmail:
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    maxLength={6}
                    value={otp}
                    onChange={(e) => setOtp(e.target.value)}
                    placeholder="6-digit code"
                    className="w-36 px-3 py-2 text-center text-sm font-mono tracking-widest border border-amber-300 rounded-lg bg-white focus:outline-none focus:border-[#A94D37]"
                  />
                  <button
                    type="button"
                    onClick={handleVerifySignupOtp}
                    disabled={otpLoading || otp.length < 6}
                    className="px-4 py-2 bg-[#25845B] hover:bg-[#1f6d4b] text-white text-xs font-semibold rounded-lg transition disabled:opacity-50"
                  >
                    Confirm Code
                  </button>
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1">Password</label>
              <input
                type="password"
                required
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37]"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Role</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37]"
                >
                  <option value="citizen">Individual Citizen</option>
                  <option value="ngo">NGO</option>
                  <option value="small_society">Small Society</option>
                  <option value="large_society">Large Society</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">Language</label>
                <select
                  value={formData.preferred_language}
                  onChange={(e) => setFormData({ ...formData, preferred_language: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37]"
                >
                  <option value="en">English</option>
                  <option value="hi">हिंदी (Hindi)</option>
                  <option value="mr">मराठी (Marathi)</option>
                  <option value="hinglish">Hinglish</option>
                </select>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !isEmailVerified}
              className="w-full py-2.5 bg-[#A94D37] hover:bg-[#8e3e2b] text-white font-medium text-sm rounded-lg transition shadow flex items-center justify-center gap-2 mt-4 disabled:opacity-50"
            >
              {loading ? "Creating..." : "Sign Up"} <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          <p className="text-center text-xs text-gray-600 mt-6">
            Already have an account?{" "}
            <Link href="/login" className="text-[#A94D37] font-semibold hover:underline">
              Sign In
            </Link>
          </p>
        </div>
      </div>
      <Footer />
    </div>
  );
}
