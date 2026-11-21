"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { api } from "@/lib/api";
import {
  MapPin,
  Flame,
  ShieldAlert,
  AlertTriangle,
  RefreshCw,
  Layers,
  CheckCircle,
  Filter
} from "lucide-react";

// Dynamically import Leaflet Map with SSR disabled
const LocationIntelligenceMap = dynamic(
  () => import("@/components/LocationIntelligenceMap"),
  {
    ssr: false,
    loading: () => (
      <div className="h-[600px] flex items-center justify-center bg-gray-100 rounded-2xl text-xs text-gray-400">
        Loading interactive geospatial intelligence map...
      </div>
    )
  }
);

export default function HotspotsPage() {
  const [locationData, setLocationData] = useState<any>(null);
  const [predictiveHotspots, setPredictiveHotspots] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [selectedHotspot, setSelectedHotspot] = useState<any>(null);

  const fetchHotspotIntelligence = async () => {
    setLoading(true);
    setErrorMsg("");
    try {
      const [locRes, predRes] = await Promise.all([
        api.get("/analytics/location_intelligence/"),
        api.get("/analytics/predictive/hotspots/")
      ]);
      setLocationData(locRes.data);
      setPredictiveHotspots(predRes.data.hotspot_risk_scores || []);
    } catch (err: any) {
      console.error(err);
      setErrorMsg("Failed to load geospatial hotspot data. Ensure you have administrative permissions.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHotspotIntelligence();
  }, []);

  return (
    <div className="flex flex-col min-h-screen bg-[#FAFAF9]">
      <Navbar />

      <main className="w-full px-3 sm:px-5 lg:px-6 py-6 flex-1">
        {/* Header Bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#DC2626] animate-pulse"></span>
              <h1 className="text-2xl font-bold text-[#17191D]">Civic Hotspot Intelligence Map</h1>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Geospatial cluster analysis, recurring localized incident mapping, and spatial risk scoring
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchHotspotIntelligence}
              disabled={loading}
              className="px-4 py-2 bg-white hover:bg-gray-100 border border-gray-200 text-gray-800 text-xs font-semibold rounded-lg shadow-sm transition flex items-center gap-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh Map
            </button>
          </div>
        </div>

        {errorMsg && (
          <div className="p-4 mb-6 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs font-medium flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {errorMsg}
          </div>
        )}

        {/* Geospatial KPI Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wider block">Geolocated Grievances</span>
              <div className="text-2xl font-extrabold text-[#17191D] mt-0.5">
                {locationData?.summary?.geolocated_complaints_count || 0}
              </div>
              <span className="text-[10px] text-gray-400">GPS verified complaints</span>
            </div>
            <div className="w-9 h-9 rounded-full bg-blue-50 flex items-center justify-center text-blue-600">
              <MapPin className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wider block">Identified Hotspots</span>
              <div className="text-2xl font-extrabold text-[#DC2626] mt-0.5">
                {locationData?.summary?.hotspot_count || 0}
              </div>
              <span className="text-[10px] text-gray-400">Spatial grievance clusters</span>
            </div>
            <div className="w-9 h-9 rounded-full bg-red-50 flex items-center justify-center text-[#DC2626]">
              <Flame className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wider block">High-Risk Clusters</span>
              <div className="text-2xl font-extrabold text-amber-600 mt-0.5">
                {predictiveHotspots.filter((h) => h.risk_level === "high").length}
              </div>
              <span className="text-[10px] text-amber-600">Urgent field intervention needed</span>
            </div>
            <div className="w-9 h-9 rounded-full bg-amber-50 flex items-center justify-center text-amber-600">
              <ShieldAlert className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wider block">Address-Only Complaints</span>
              <div className="text-2xl font-extrabold text-gray-700 mt-0.5">
                {locationData?.summary?.non_geolocated_complaints_count || 0}
              </div>
              <span className="text-[10px] text-gray-400">Non-GPS reports (isolated)</span>
            </div>
            <div className="w-9 h-9 rounded-full bg-gray-100 flex items-center justify-center text-gray-600">
              <Layers className="w-5 h-5" />
            </div>
          </div>
        </div>

        {/* Main Grid: Interactive Map & Hotspot Scoring Drawer */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Interactive Map (2 Columns) */}
          <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden flex flex-col">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-[#17191D]">Live Municipal Geospatial Map</h2>
                <p className="text-[11px] text-gray-400">Interactive OpenStreetMap with color-coded density clusters</p>
              </div>
              <div className="flex items-center gap-3 text-[11px] text-gray-500">
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-red-600"></span> Hotspots</span>
                <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-blue-600"></span> Complaints</span>
              </div>
            </div>

            <div className="flex-1 min-h-[560px]">
              {locationData ? (
                <LocationIntelligenceMap
                  markers={locationData.complaints || []}
                  hotspots={locationData.hotspots || []}
                  mapCenter={locationData.summary?.map_center || null}
                  onSelectHotspot={(hs) => setSelectedHotspot(hs)}
                />
              ) : (
                <div className="h-[560px] flex items-center justify-center text-xs text-gray-400">
                  Loading map data...
                </div>
              )}
            </div>
          </div>

          {/* Hotspot Risk Rankings & Details */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-4 flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100 mb-3">
              <h3 className="text-xs font-bold text-gray-900 flex items-center gap-1.5">
                <ShieldAlert className="w-4 h-4 text-[#DC2626]" /> Spatial Risk Score Ranking
              </h3>
              <span className="text-[10px] font-mono text-gray-400">Scale 0-100</span>
            </div>

            <div className="space-y-3 overflow-y-auto max-h-[530px] flex-1">
              {predictiveHotspots.length > 0 ? (
                predictiveHotspots.map((hs: any) => (
                  <div
                    key={hs.hotspot_id}
                    onClick={() => setSelectedHotspot(hs)}
                    className={`p-3 rounded-xl border text-xs cursor-pointer transition ${
                      selectedHotspot?.hotspot_id === hs.hotspot_id
                        ? "border-[#DC2626] bg-red-50/40 shadow-sm"
                        : "border-gray-200 hover:border-gray-300 bg-white"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-gray-900">{hs.hotspot_id}</span>
                        <span className="text-gray-500 font-medium">({hs.primary_category})</span>
                      </div>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase font-mono ${
                        hs.risk_level === "high"
                          ? "bg-red-100 text-red-700 border border-red-200"
                          : hs.risk_level === "medium"
                          ? "bg-amber-100 text-amber-700 border border-amber-200"
                          : "bg-emerald-100 text-emerald-700 border border-emerald-200"
                      }`}>
                        Risk: {hs.risk_score}
                      </span>
                    </div>

                    <div className="text-[10px] text-gray-500 space-y-0.5 mt-2">
                      {hs.contributing_factors?.map((f: string, idx: number) => (
                        <p key={idx}>• {f}</p>
                      ))}
                    </div>

                    <div className="mt-2 text-[10px] font-mono text-gray-400 bg-gray-50 px-2 py-1 rounded border border-gray-100 flex items-center justify-between">
                      <span>{hs.latitude.toFixed(4)}, {hs.longitude.toFixed(4)}</span>
                      <span>{hs.complaint_count} reports</span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="py-12 text-center text-xs text-gray-400">
                  No spatial grievance clusters detected yet.
                </div>
              )}
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
