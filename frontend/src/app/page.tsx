import Link from "next/link";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { Mic, Camera, ShieldCheck, CheckCircle2, ArrowRight, Activity, Building2, Sparkles, MessageSquareQuote } from "lucide-react";

export default function Home() {
  return (
    <div className="flex flex-col min-h-screen">
      <Navbar />

      {/* Hero Section */}
      <section className="bg-[#17191D] text-white py-20 px-4 sm:px-6 lg:px-8 border-b border-gray-800 relative overflow-hidden">
        <div className="absolute inset-0 opacity-10 bg-[radial-gradient(#A94D37_1px,transparent_1px)] [background-size:16px_16px]"></div>
        <div className="max-w-5xl mx-auto text-center relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-semibold uppercase tracking-wider text-gray-300 mb-6">
            <Sparkles className="w-4 h-4 text-[#A94D37]" /> Multilingual Civic AI Platform
          </div>
          <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight mb-6">
            From Voice to <span className="text-[#A94D37]">Resolution.</span>
          </h1>
          <p className="text-lg sm:text-xl text-gray-300 max-w-3xl mx-auto mb-10 leading-relaxed font-normal">
            JanSahayak AI turns citizen voice, photos and messages in Hindi, Marathi, Hinglish, and English into verified municipal tickets, auto-assigns departments, and provides verifiable resolution proof.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/report"
              className="px-6 py-3.5 bg-[#A94D37] hover:bg-[#8e3e2b] text-white font-medium rounded-xl shadow-lg flex items-center gap-2 transition"
            >
              <Mic className="w-5 h-5" /> Report Issue via Voice / AI <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              href="/citizen"
              className="px-6 py-3.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-white font-medium rounded-xl transition"
            >
              Track Complaint Status
            </Link>
          </div>

          {/* Quick Metrics Bar */}
          <div className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto border-t border-gray-800/80 pt-8 text-left">
            <div>
              <div className="text-2xl font-bold text-white">4 Languages</div>
              <div className="text-xs text-gray-400">EN, HI, MR, Hinglish</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-[#A94D37]">6 Categories</div>
              <div className="text-xs text-gray-400">Garbage, Water, Potholes & more</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-[#25845B]">100% Verifiable</div>
              <div className="text-xs text-gray-400">Photo Proof of Resolution</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-white">Real-Time</div>
              <div className="text-xs text-gray-400">Citizen & Admin Sync</div>
            </div>
          </div>
        </div>
      </section>

      {/* 6 Categories Section */}
      <section className="py-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-extrabold text-[#17191D]">Configured Complaint Verticals</h2>
          <p className="text-gray-600 text-sm mt-2">Instantly recognized by JanSahayak Multilingual AI model</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {[
            { title: "Garbage and Sanitation", dept: "Solid Waste Management", desc: "Overflowing municipal dustbins, street sweeping negligence, illegal waste dumps." },
            { title: "Water Supply", dept: "Water Supply & Sewerage", desc: "Pipeline ruptures, contaminated drinking water, severe pressure drops." },
            { title: "Roads and Potholes", dept: "Roads & Traffic Infrastructure", desc: "Hazardous potholes, crumbling asphalt, unpaved pedestrian trenches." },
            { title: "Streetlights", dept: "Electrical & Street Lighting", desc: "Dead light fixtures, flickering bulbs, exposed cables creating electrocution risks." },
            { title: "Drainage and Sewage", dept: "Stormwater & Drainage", desc: "Clogged stormwater drains, sewage overflow during rains, open manholes." },
            { title: "Traffic & Road Obstruction", dept: "Traffic & Encroachment", desc: "Unauthorized roadside parking, illegal vendor encroachment on pedestrian pathways." },
          ].map((cat, idx) => (
            <div key={idx} className="bg-white rounded-xl p-6 border border-gray-200 shadow-sm hover:border-[#A94D37] transition">
              <span className="text-xs font-semibold text-[#A94D37] uppercase tracking-wider">{cat.dept}</span>
              <h3 className="text-lg font-bold text-[#17191D] mt-1 mb-2">{cat.title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">{cat.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Workflow Section */}
      <section className="bg-white py-16 px-4 sm:px-6 lg:px-8 border-y border-gray-200">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-extrabold text-[#17191D]">Autonomous Civic Workflow</h2>
            <p className="text-gray-600 text-sm mt-2">From raw citizen voice input to verified resolution</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="p-5 rounded-xl bg-[#F7F7F5] border border-gray-200">
              <div className="w-10 h-10 rounded-lg bg-[#A94D37] text-white flex items-center justify-center font-bold mb-4">1</div>
              <h4 className="font-bold text-[#17191D] mb-1">Citizen Input</h4>
              <p className="text-xs text-gray-600">Speaks or types in native language (Hindi, Marathi, English) with photo/video.</p>
            </div>
            <div className="p-5 rounded-xl bg-[#F7F7F5] border border-gray-200">
              <div className="w-10 h-10 rounded-lg bg-[#17191D] text-white flex items-center justify-center font-bold mb-4">2</div>
              <h4 className="font-bold text-[#17191D] mb-1">AI Understanding</h4>
              <p className="text-xs text-gray-600">Extracts category, ward, priority, asks for missing landmark, detects duplicate reports.</p>
            </div>
            <div className="p-5 rounded-xl bg-[#F7F7F5] border border-gray-200">
              <div className="w-10 h-10 rounded-lg bg-[#A94D37] text-white flex items-center justify-center font-bold mb-4">3</div>
              <h4 className="font-bold text-[#17191D] mb-1">Admin & Staff Dispatch</h4>
              <p className="text-xs text-gray-600">Municipal department assigns local field staff with SLA countdown timer.</p>
            </div>
            <div className="p-5 rounded-xl bg-[#F7F7F5] border border-gray-200">
              <div className="w-10 h-10 rounded-lg bg-[#25845B] text-white flex items-center justify-center font-bold mb-4">4</div>
              <h4 className="font-bold text-[#17191D] mb-1">Verifiable Resolution</h4>
              <p className="text-xs text-gray-600">Staff uploads fix photo, citizen verifies resolution and provides rating.</p>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
