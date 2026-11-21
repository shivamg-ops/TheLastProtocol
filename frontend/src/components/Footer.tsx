"use client";

import Link from "next/link";

export default function Footer() {
  return (
    <footer className="bg-[#17191D] text-gray-400 text-sm border-t border-gray-800 py-10 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-1 md:grid-cols-4 gap-8">
        <div>
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 rounded bg-[#A94D37] flex items-center justify-center font-bold text-white text-xs">
              JS
            </div>
            <span className="font-bold text-white tracking-wide">JANSAHAYAK AI</span>
          </div>
          <p className="text-xs text-gray-400 leading-relaxed">
            Empowering citizens and municipal departments through Multilingual AI, voice reports, and verifiable resolution tracking.
          </p>
        </div>

        <div>
          <h4 className="text-white font-semibold text-xs tracking-wider uppercase mb-3">Platform</h4>
          <ul className="space-y-2 text-xs">
            <li><Link href="/report" className="hover:text-white transition">Voice & Text Complaint</Link></li>
            <li><Link href="/citizen" className="hover:text-white transition">Citizen Portal</Link></li>
            <li><Link href="/admin" className="hover:text-white transition">Admin AI Command</Link></li>
            <li><Link href="/staff" className="hover:text-white transition">Staff Resolution Portal</Link></li>
          </ul>
        </div>

        <div>
          <h4 className="text-white font-semibold text-xs tracking-wider uppercase mb-3">Key Categories</h4>
          <ul className="space-y-2 text-xs">
            <li>Garbage & Sanitation</li>
            <li>Water Pipeline Leaks</li>
            <li>Roads & Potholes</li>
            <li>Streetlight Outages</li>
            <li>Drainage & Sewage</li>
            <li>Traffic & Road Obstruction</li>
          </ul>
        </div>

        <div>
          <h4 className="text-white font-semibold text-xs tracking-wider uppercase mb-3">Security & Compliance</h4>
          <p className="text-xs text-gray-400 leading-relaxed">
            Role-based authenticated access. Citizens, NGOs, and municipal authorities operate within isolated permission tiers.
          </p>
        </div>
      </div>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-8 pt-6 border-t border-gray-800 text-xs text-center text-gray-500">
        &copy; 2026 JANSAHAYAK AI — From Voice to Resolution. All rights reserved.
      </div>
    </footer>
  );
}
