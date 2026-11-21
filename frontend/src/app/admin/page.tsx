"use client";

import { useEffect, useState, useMemo } from "react";
import dynamic from "next/dynamic";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { api } from "@/lib/api";
import {
  TrendingUp,
  AlertTriangle,
  Clock,
  CheckCircle,
  Sparkles,
  Filter,
  BarChart2,
  PieChart as PieChartIcon,
  Layers,
  Calendar,
  Building2,
  Users,
  MapPin,
  Flame,
  X,
  AlertCircle,
  ShieldAlert
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  CartesianGrid,
  Legend
} from "recharts";

// Dynamically import Leaflet Map component with SSR disabled
const LocationIntelligenceMap = dynamic(
  () => import("@/components/LocationIntelligenceMap"),
  { ssr: false, loading: () => <div className="h-[500px] flex items-center justify-center bg-gray-100 rounded-2xl text-xs text-gray-400">Loading interactive geospatial intelligence...</div> }
);

const COLORS = ["#A94D37", "#25845B", "#3B82F6", "#F59E0B", "#8B5CF6", "#EC4899", "#6B7280"];

export default function AdminPage() {
  const [analytics, setAnalytics] = useState<any>(null);
  const [locationData, setLocationData] = useState<any>(null);
  const [complaints, setComplaints] = useState<any[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [staffMembers, setStaffMembers] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string>("");

  // Map Selected Item State
  const [selectedMapComplaint, setSelectedMapComplaint] = useState<any>(null);
  const [selectedHotspot, setSelectedHotspot] = useState<any>(null);

  // Filters State
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  const [selectedDept, setSelectedDept] = useState<string>("");
  const [selectedCat, setSelectedCat] = useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<string>("");

  // Assignment & AI Recommendation Modal (Task 18)
  const [assigningComplaint, setAssigningComplaint] = useState<any>(null);
  const [staffId, setStaffId] = useState("");
  const [assignError, setAssignError] = useState("");
  const [assignSuccess, setAssignSuccess] = useState("");
  const [assigning, setAssigning] = useState(false);
  const [recommendation, setRecommendation] = useState<any>(null);
  const [loadingRec, setLoadingRec] = useState<boolean>(false);

  // Dispute Review Modal (Task 17)
  const [reviewingDispute, setReviewingDispute] = useState<any>(null);
  const [reviewAction, setReviewAction] = useState<"reopen" | "uphold">("reopen");
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [reviewMsg, setReviewMsg] = useState("");

  // Task 20: Predictive Civic Intelligence States
  const [predictiveTrends, setPredictiveTrends] = useState<any>(null);
  const [predictiveForecast, setPredictiveForecast] = useState<any>(null);
  const [predictiveHotspots, setPredictiveHotspots] = useState<any[]>([]);
  const [predictiveRecs, setPredictiveRecs] = useState<any[]>([]);
  const [forecastHorizon, setForecastHorizon] = useState<number>(7);
  const [loadingPredictive, setLoadingPredictive] = useState<boolean>(false);

  useEffect(() => {
    loadInitialMeta();
  }, []);

  useEffect(() => {
    loadAnalytics();
  }, [dateFrom, dateTo, selectedDept, selectedCat, selectedStatus]);

  const loadInitialMeta = async () => {
    try {
      const [resDepts, resCats, resStaff, resComplaints] = await Promise.all([
        api.get("/departments/"),
        api.get("/categories/"),
        api.get("/user/staff-list/"),
        api.get("/complaints/"),
      ]);
      setDepartments(resDepts.data);
      setCategories(resCats.data);
      setStaffMembers(resStaff.data);
      setComplaints(resComplaints.data);
      if (resStaff.data.length > 0 && !staffId) {
        setStaffId(String(resStaff.data[0].id));
      }
    } catch (err: any) {
      console.error(err);
    }
  };

  const loadAnalytics = async () => {
    setLoading(true);
    setLoadingPredictive(true);
    setErrorMsg("");
    try {
      const params = new URLSearchParams();
      if (dateFrom) params.append("date_from", new Date(dateFrom).toISOString());
      if (dateTo) params.append("date_to", new Date(dateTo).toISOString());
      if (selectedDept) params.append("department", selectedDept);
      if (selectedCat) params.append("category", selectedCat);
      if (selectedStatus) params.append("status", selectedStatus);

      const [resSummary, resLocation, resTrends, resForecast, resHotspots, resRecs] = await Promise.all([
        api.get(`/analytics/summary/?${params.toString()}`),
        api.get(`/analytics/location_intelligence/?${params.toString()}`),
        api.get(`/analytics/predictive/trends/?${params.toString()}`),
        api.get(`/analytics/predictive/forecast/?horizon_days=${forecastHorizon}&${params.toString()}`),
        api.get(`/analytics/predictive/hotspots/?${params.toString()}`),
        api.get(`/analytics/predictive/recommendations/?${params.toString()}`),
      ]);
      setAnalytics(resSummary.data);
      setLocationData(resLocation.data);
      setPredictiveTrends(resTrends.data);
      setPredictiveForecast(resForecast.data);
      setPredictiveHotspots(resHotspots.data.hotspot_risk_scores || []);
      setPredictiveRecs(resRecs.data.recommendations || []);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || "Failed to load municipal analytics data.");
    } finally {
      setLoading(false);
      setLoadingPredictive(false);
    }
  };

  const handleResetFilters = () => {
    setDateFrom("");
    setDateTo("");
    setSelectedDept("");
    setSelectedCat("");
    setSelectedStatus("");
  };

  const openAssignmentModal = async (item: any) => {
    setAssigningComplaint(item);
    setAssignError("");
    setAssignSuccess("");
    setRecommendation(null);
    setLoadingRec(true);

    try {
      const res = await api.get(`/complaints/${item.id}/recommend_staff/`);
      setRecommendation(res.data);
      if (res.data?.recommended_staff_id) {
        setStaffId(String(res.data.recommended_staff_id));
      } else if (staffMembers.length > 0) {
        setStaffId(String(staffMembers[0].id));
      }
    } catch (err: any) {
      console.error("Could not fetch staff recommendation:", err);
      if (staffMembers.length > 0) {
        setStaffId(String(staffMembers[0].id));
      }
    } finally {
      setLoadingRec(false);
    }
  };

  const handleAssignStaff = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assigningComplaint || !staffId) return;

    setAssignError("");
    setAssignSuccess("");
    setAssigning(true);

    try {
      await api.post(`/complaints/${assigningComplaint.id}/assign_staff/`, {
        staff_id: parseInt(staffId, 10),
      });
      setAssignSuccess(`Ticket ${assigningComplaint.tracking_id} successfully assigned to field staff.`);
      setTimeout(() => {
        setAssigningComplaint(null);
        setAssignSuccess("");
      }, 1200);
      loadAnalytics();
      const resComplaints = await api.get("/complaints/");
      setComplaints(resComplaints.data);
    } catch (err: any) {
      const msg = err.response?.data?.error || "Error assigning staff. Ensure staff user exists.";
      setAssignError(msg);
    } finally {
      setAssigning(false);
    }
  };

  const handleAdminReviewDispute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reviewingDispute) return;

    setReviewMsg("");
    setReviewSubmitting(true);

    try {
      await api.post(`/complaints/${reviewingDispute.id}/admin_review_dispute/`, {
        action: reviewAction,
        notes: reviewNotes,
      });
      setReviewMsg(
        reviewAction === "reopen"
          ? "Complaint reopened and sent back to In Progress for resolution."
          : "Dispute reviewed and resolution upheld as verified."
      );
      setTimeout(() => {
        setReviewingDispute(null);
        setReviewMsg("");
        setReviewNotes("");
      }, 1200);
      loadAnalytics();
      const resComplaints = await api.get("/complaints/");
      setComplaints(resComplaints.data);
    } catch (err: any) {
      setReviewMsg(err.response?.data?.error || "Failed to process dispute review.");
    } finally {
      setReviewSubmitting(false);
    }
  };

  // Filter complaints table by current filters as well for UI consistency
  const filteredComplaints = useMemo(() => {
    return complaints.filter((c) => {
      if (selectedDept && String(c.department) !== selectedDept) return false;
      if (selectedCat && String(c.category) !== selectedCat) return false;
      if (selectedStatus && c.status !== selectedStatus) return false;
      if (dateFrom && new Date(c.created_at) < new Date(dateFrom)) return false;
      if (dateTo && new Date(c.created_at) > new Date(dateTo)) return false;
      return true;
    });
  }, [complaints, selectedDept, selectedCat, selectedStatus, dateFrom, dateTo]);

  return (
    <div className="flex flex-col min-h-screen bg-[#FAFAF9]">
      <Navbar />
      <div className="w-full px-3 sm:px-5 lg:px-6 py-6 flex-1">
        {/* Top Header */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#A94D37] animate-pulse"></span>
              <h1 className="text-2xl font-bold text-[#17191D]">AI Command & Analytics Dashboard</h1>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Data-driven municipal grievance intelligence, SLA monitoring, and explanatory AI insights
            </p>
          </div>
          <button
            onClick={() => {
              loadAnalytics();
              api.get("/complaints/").then((r) => setComplaints(r.data));
            }}
            className="px-4 py-2 bg-white hover:bg-gray-100 border border-gray-200 text-gray-800 text-xs font-semibold rounded-lg shadow-sm transition"
          >
            Refresh Analytics
          </button>
        </div>

        {/* Global Dimensional Filters Bar */}
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm mb-6">
          <div className="flex items-center justify-between gap-2 mb-3 pb-2 border-b border-gray-100">
            <span className="text-xs font-bold text-gray-700 flex items-center gap-1.5">
              <Filter className="w-3.5 h-3.5 text-[#A94D37]" /> Filter Municipal Data
            </span>
            {(dateFrom || dateTo || selectedDept || selectedCat || selectedStatus) && (
              <button
                onClick={handleResetFilters}
                className="text-[11px] text-[#A94D37] hover:underline font-semibold"
              >
                Clear all filters
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3">
            <div>
              <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">From Date</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:border-[#A94D37] bg-white text-gray-800"
              />
            </div>
            <div>
              <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">To Date</label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:border-[#A94D37] bg-white text-gray-800"
              />
            </div>
            <div>
              <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">Department</label>
              <select
                value={selectedDept}
                onChange={(e) => setSelectedDept(e.target.value)}
                className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:border-[#A94D37] bg-white text-gray-800"
              >
                <option value="">All Departments</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">Category</label>
              <select
                value={selectedCat}
                onChange={(e) => setSelectedCat(e.target.value)}
                className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:border-[#A94D37] bg-white text-gray-800"
              >
                <option value="">All Categories</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-semibold text-gray-500 uppercase mb-1">Status</label>
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:border-[#A94D37] bg-white text-gray-800"
              >
                <option value="">All Statuses</option>
                <option value="submitted">Submitted</option>
                <option value="assigned">Assigned</option>
                <option value="in_progress">In Progress</option>
                <option value="resolved">Resolved</option>
                <option value="verified">Verified</option>
                <option value="rejected">Rejected</option>
              </select>
            </div>
          </div>
        </div>

        {/* Error Banner */}
        {errorMsg && (
          <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-red-600" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Key Operational KPI Metric Cards */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-6">
          <div className="bg-[#17191D] text-white p-4 rounded-xl border border-gray-800 shadow-sm">
            <span className="text-[11px] text-gray-400 font-medium">Total Complaints</span>
            <div className="text-2xl font-extrabold text-white mt-1">
              {loading ? "..." : analytics?.total_complaints ?? 0}
            </div>
          </div>
          <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
            <span className="text-[11px] text-gray-500 font-medium">Pending Triage</span>
            <div className="text-2xl font-extrabold text-blue-600 mt-1">
              {loading ? "..." : analytics?.pending_complaints ?? 0}
            </div>
          </div>
          <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
            <span className="text-[11px] text-gray-500 font-medium">Active In Field</span>
            <div className="text-2xl font-extrabold text-amber-600 mt-1">
              {loading ? "..." : analytics?.in_progress_complaints ?? 0}
            </div>
          </div>
          <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
            <span className="text-[11px] text-gray-500 font-medium">Resolution Rate</span>
            <div className="text-2xl font-extrabold text-[#25845B] mt-1">
              {loading ? "..." : `${analytics?.resolution_rate ?? 0}%`}
            </div>
          </div>
          <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
            <span className="text-[11px] text-gray-500 font-medium">SLA Compliance</span>
            <div className="text-2xl font-extrabold text-purple-600 mt-1">
              {loading ? "..." : `${analytics?.sla_compliance_rate ?? 0}%`}
            </div>
          </div>
          <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
            <span className="text-[11px] text-gray-500 font-medium">Avg Resolution</span>
            <div className="text-2xl font-extrabold text-gray-800 mt-1">
              {loading ? "..." : `${analytics?.avg_resolution_hours ?? 0}h`}
            </div>
          </div>
        </div>

        {/* Citizen Trust & Resolution Verification KPI Cards (Task 17) */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <div className="bg-white p-4 rounded-xl border border-amber-200 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-[11px] text-amber-800 font-semibold uppercase tracking-wider block">Awaiting Confirmation</span>
              <div className="text-2xl font-extrabold text-amber-600 mt-0.5">
                {loading ? "..." : analytics?.pending_citizen_confirmation_count ?? 0}
              </div>
              <span className="text-[10px] text-gray-500">Resolved by staff, pending citizen check</span>
            </div>
            <div className="w-9 h-9 rounded-full bg-amber-100 flex items-center justify-center text-amber-700">
              <Clock className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-emerald-200 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-[11px] text-emerald-800 font-semibold uppercase tracking-wider block">Citizen Confirmed</span>
              <div className="text-2xl font-extrabold text-emerald-600 mt-0.5">
                {loading ? "..." : analytics?.citizen_confirmed_count ?? 0}
              </div>
              <span className="text-[10px] text-gray-500">Verified resolved by citizen</span>
            </div>
            <div className="w-9 h-9 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-700">
              <CheckCircle className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-red-200 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-[11px] text-red-800 font-semibold uppercase tracking-wider block">Disputed Resolutions</span>
              <div className="text-2xl font-extrabold text-red-600 mt-0.5">
                {loading ? "..." : analytics?.citizen_disputed_count ?? 0}
              </div>
              <span className="text-[10px] text-red-500 font-medium">Citizens disputed resolution</span>
            </div>
            <div className="w-9 h-9 rounded-full bg-red-100 flex items-center justify-center text-red-700">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-purple-200 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-[11px] text-purple-800 font-semibold uppercase tracking-wider block">Citizen Satisfaction</span>
              <div className="text-2xl font-extrabold text-purple-600 mt-0.5">
                {loading ? "..." : `${analytics?.avg_citizen_satisfaction ?? 0} / 5`}
              </div>
              <span className="text-[10px] text-gray-500">Based on {analytics?.total_feedback_count ?? 0} citizen ratings</span>
            </div>
            <div className="w-9 h-9 rounded-full bg-purple-100 flex items-center justify-center text-purple-700">
              <TrendingUp className="w-5 h-5" />
            </div>
          </div>
        </div>

        {/* AI-Generated Insights Panel */}
        {analytics?.ai_insights?.insights && (
          <div className="mb-6 bg-gradient-to-r from-amber-50/70 via-white to-orange-50/50 border border-amber-200/80 rounded-2xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-[#A94D37] flex items-center justify-center text-white shadow-sm">
                  <Sparkles className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-gray-900 tracking-tight">
                    AI Municipal Intelligence & Statistical Briefing
                  </h3>
                  <span className="text-[10px] text-gray-500">
                    {analytics.ai_insights.disclaimer || "Factual explanatory synthesis derived strictly from real database aggregates."}
                  </span>
                </div>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200 font-semibold uppercase">
                {analytics.ai_insights.generated_by === "gemini_ai" ? "Gemini Explanations" : "Deterministic Engine"}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {analytics.ai_insights.insights.map((ins: any, idx: number) => (
                <div key={idx} className="bg-white/90 p-3.5 rounded-xl border border-amber-100/90 shadow-sm">
                  <span className="text-[10px] font-bold uppercase text-[#A94D37] tracking-wider block mb-1">
                    {ins.title}
                  </span>
                  <p className="text-xs text-gray-600 leading-relaxed">{ins.description}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Charts Row: Trend & Breakdown */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* Daily Trend Line Chart */}
          <div className="lg:col-span-2 bg-white p-5 rounded-2xl border border-gray-200 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <BarChart2 className="w-4 h-4 text-[#A94D37]" />
                <h3 className="text-sm font-bold text-[#17191D]">Grievance Volume Trend</h3>
              </div>
              <span className="text-[11px] text-gray-400">Daily complaint incoming volume</span>
            </div>
            <div className="h-64 w-full">
              {analytics?.volume_trend && analytics.volume_trend.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={analytics.volume_trend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#6B7280" }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#6B7280" }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#17191D", borderRadius: 8, color: "#fff", border: "none", fontSize: 12 }}
                      itemStyle={{ color: "#fff" }}
                    />
                    <Line type="monotone" dataKey="count" name="Complaints" stroke="#A94D37" strokeWidth={2.5} dot={{ r: 3, fill: "#A94D37" }} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-xs text-gray-400">
                  No volume activity in selected date window.
                </div>
              )}
            </div>
          </div>

          {/* Category Distribution Pie Chart */}
          <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <PieChartIcon className="w-4 h-4 text-[#25845B]" />
                <h3 className="text-sm font-bold text-[#17191D]">Category Share</h3>
              </div>
              <span className="text-[11px] text-gray-400">Distribution</span>
            </div>
            <div className="h-64 w-full flex items-center justify-center">
              {analytics?.category_breakdown && analytics.category_breakdown.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={analytics.category_breakdown}
                      dataKey="count"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={75}
                      innerRadius={45}
                      paddingAngle={3}
                    >
                      {analytics.category_breakdown.map((_: any, index: number) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ backgroundColor: "#17191D", borderRadius: 8, color: "#fff", border: "none", fontSize: 12 }}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <span className="text-xs text-gray-400">No categories found.</span>
              )}
            </div>
          </div>
        </div>

        {/* Geospatial Intelligence & Hotspot Mapping Section (Task 15) */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 mb-8">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4 pb-3 border-b border-gray-100">
            <div>
              <div className="flex items-center gap-2">
                <MapPin className="w-4 h-4 text-[#A94D37]" />
                <h3 className="text-sm font-bold text-[#17191D]">
                  Location Intelligence & Civic Hotspot Mapping
                </h3>
              </div>
              <p className="text-[11px] text-gray-500 mt-0.5">
                Spatial clustering of verified GPS complaints (500m radius threshold). Address-only complaints are preserved in non-geolocated count.
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="px-2.5 py-1 rounded-lg bg-gray-100 font-semibold text-gray-700">
                📍 {locationData?.summary?.geolocated_complaints_count ?? 0} Geolocated
              </span>
              <span className="px-2.5 py-1 rounded-lg bg-amber-50 border border-amber-200 font-semibold text-amber-800">
                🔥 {locationData?.summary?.hotspot_count ?? 0} Hotspots
              </span>
              <span className="px-2.5 py-1 rounded-lg bg-blue-50 border border-blue-200 font-semibold text-blue-700">
                📄 {locationData?.summary?.without_gps_count ?? 0} Address Only
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Interactive Map Component */}
            <div className="lg:col-span-3">
              <LocationIntelligenceMap
                markers={locationData?.complaint_markers || []}
                hotspots={locationData?.hotspots || []}
                mapCenter={locationData?.map_center || null}
                onSelectComplaint={(c) => {
                  setSelectedMapComplaint(c);
                  setSelectedHotspot(null);
                }}
                onSelectHotspot={(hs) => {
                  setSelectedHotspot(hs);
                  setSelectedMapComplaint(null);
                }}
              />
            </div>

            {/* Side Detail Inspector Panel */}
            <div className="bg-[#F7F7F5] rounded-xl border border-gray-200 p-4 flex flex-col justify-between">
              <div>
                <h4 className="text-xs font-bold text-gray-800 mb-2 uppercase tracking-wider flex items-center justify-between">
                  <span>Geospatial Inspector</span>
                  {(selectedMapComplaint || selectedHotspot) && (
                    <button
                      onClick={() => {
                        setSelectedMapComplaint(null);
                        setSelectedHotspot(null);
                      }}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </h4>

                {selectedMapComplaint ? (
                  <div className="space-y-2.5 text-xs">
                    <div className="p-2.5 bg-white rounded-lg border border-gray-200">
                      <span className="font-mono font-bold text-[#A94D37] text-[11px] block">
                        {selectedMapComplaint.tracking_id}
                      </span>
                      <p className="font-semibold text-gray-900 mt-1">{selectedMapComplaint.title}</p>
                    </div>

                    <div className="text-[11px] space-y-1.5 text-gray-600 bg-white p-2.5 rounded-lg border border-gray-200">
                      <div>
                        <strong>Category:</strong> {selectedMapComplaint.category_name || "General"}
                      </div>
                      <div>
                        <strong>Department:</strong> {selectedMapComplaint.department_name || "Unassigned"}
                      </div>
                      <div>
                        <strong>Status:</strong>{" "}
                        <span className="capitalize font-semibold text-[#A94D37]">
                          {selectedMapComplaint.status}
                        </span>
                      </div>
                      <div>
                        <strong>Priority:</strong>{" "}
                        <span className="capitalize">{selectedMapComplaint.priority}</span>
                      </div>
                      <div>
                        <strong>Location:</strong> {selectedMapComplaint.address_preview}
                      </div>
                      <div>
                        <strong>Coordinates:</strong> {selectedMapComplaint.latitude.toFixed(5)}, {selectedMapComplaint.longitude.toFixed(5)}
                      </div>
                    </div>
                  </div>
                ) : selectedHotspot ? (
                  <div className="space-y-2.5 text-xs">
                    <div className="p-2.5 bg-amber-50 rounded-lg border border-amber-200 text-amber-900">
                      <div className="flex items-center gap-1 font-bold text-xs">
                        <Flame className="w-3.5 h-3.5 text-[#A94D37]" /> Hotspot Cluster {selectedHotspot.hotspot_id}
                      </div>
                      <p className="text-[11px] mt-1 text-amber-800">
                        {selectedHotspot.complaint_count} complaints clustered within {selectedHotspot.radius_meters}m radius.
                      </p>
                    </div>

                    <div className="text-[11px] space-y-1.5 text-gray-600 bg-white p-2.5 rounded-lg border border-gray-200">
                      <div>
                        <strong>Primary Concern:</strong> {selectedHotspot.primary_category}
                      </div>
                      <div>
                        <strong>Approx. Center:</strong> {selectedHotspot.approximate_latitude.toFixed(5)}, {selectedHotspot.approximate_longitude.toFixed(5)}
                      </div>
                      <div className="pt-1 border-t border-gray-100">
                        <strong>Associated Tickets:</strong>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {selectedHotspot.tracking_ids.map((tid: string) => (
                            <span key={tid} className="font-mono text-[9px] bg-gray-100 px-1.5 py-0.5 rounded text-gray-700">
                              {tid}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="py-8 text-center text-xs text-gray-400">
                    Click any marker or hotspot circle on the map to inspect incident details and clustered grievance tickets.
                  </div>
                )}
              </div>

              {/* Geographic Density Summary */}
              <div className="pt-3 border-t border-gray-200/80 text-[11px] text-gray-500">
                <span className="font-semibold text-gray-700 block mb-1">Density Benchmark:</span>
                {locationData?.summary?.geolocated_complaints_count > 0 ? (
                  <span>
                    {locationData?.summary?.geolocated_percentage}% of reported complaints have verified GPS coordinates.
                  </span>
                ) : (
                  <span>No GPS coordinates available in active filter window.</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Task 20: Predictive Civic Intelligence & Preventive Action Engine */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-8 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-gray-100">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-[#A94D37] to-[#8e3e2b] flex items-center justify-center text-white shadow-sm">
                <TrendingUp className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-base font-bold text-[#17191D] flex items-center gap-2">
                  Predictive Civic Intelligence & Preventive Actions
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200 font-semibold">
                    Statistical Forecast Engine
                  </span>
                </h3>
                <p className="text-xs text-gray-500">
                  Data-driven volume forecasts, recurring problem clusters, hotspot risk assessments, and targeted municipal interventions
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 font-medium">Horizon:</span>
              <select
                value={forecastHorizon}
                onChange={(e) => {
                  const val = parseInt(e.target.value, 10);
                  setForecastHorizon(val);
                  api.get(`/analytics/predictive/forecast/?horizon_days=${val}&${new URLSearchParams({
                    ...(dateFrom && { date_from: new Date(dateFrom).toISOString() }),
                    ...(dateTo && { date_to: new Date(dateTo).toISOString() }),
                    ...(selectedDept && { department: selectedDept }),
                    ...(selectedCat && { category: selectedCat }),
                  }).toString()}`).then((r) => setPredictiveForecast(r.data));
                }}
                className="text-xs border border-gray-300 rounded-lg px-2.5 py-1.5 bg-white font-medium"
              >
                <option value={7}>7-Day Forecast</option>
                <option value={14}>14-Day Forecast</option>
                <option value={21}>21-Day Forecast</option>
              </select>
            </div>
          </div>

          {/* Volume Forecast & Trend Chart */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-[#FBFBFA] p-4 rounded-xl border border-gray-200">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-bold text-gray-800">
                  Projected Complaint Inflow (Moving Average & Dampened Trend)
                </span>
                <span className="text-[10px] text-gray-500 font-mono">
                  {predictiveForecast?.status === "success"
                    ? `${predictiveForecast.historical_days_available} days observed`
                    : "Insufficient data"}
                </span>
              </div>

              {predictiveForecast?.status === "success" && predictiveForecast.predictions.length > 0 ? (
                <div className="h-60">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={predictiveForecast.predictions}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                      <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="#9CA3AF" />
                      <YAxis tick={{ fontSize: 10 }} stroke="#9CA3AF" />
                      <Tooltip
                        contentStyle={{ backgroundColor: "#17191D", borderRadius: "8px", color: "#fff", fontSize: "11px" }}
                        formatter={(val: any) => [`${val} tickets`, "Projected Inflow"]}
                      />
                      <Legend wrapperStyle={{ fontSize: "11px" }} />
                      <Line
                        type="monotone"
                        dataKey="predicted_count"
                        name="Projected Intake (Estimated)"
                        stroke="#A94D37"
                        strokeWidth={2.5}
                        strokeDasharray="4 4"
                        dot={{ r: 3, fill: "#A94D37" }}
                      />
                      <Line
                        type="monotone"
                        dataKey="upper_tolerance"
                        name="Upper Tolerance (+25%)"
                        stroke="#9CA3AF"
                        strokeWidth={1}
                        strokeDasharray="2 2"
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                  <p className="text-[10px] text-gray-400 mt-2 text-center italic">
                    * Projections represent statistical rolling estimates with a +/- 25% heuristic tolerance range (not calibrated statistical confidence intervals).
                  </p>
                </div>
              ) : (
                <div className="h-60 flex flex-col items-center justify-center text-center p-4">
                  <AlertCircle className="w-8 h-8 text-amber-500 mb-2" />
                  <p className="text-xs font-semibold text-gray-700">
                    {predictiveForecast?.message || "Insufficient historical data for a reliable statistical forecast."}
                  </p>
                  <p className="text-[11px] text-gray-400 mt-1 max-w-sm">
                    A minimum of 7 distinct days of complaint activity is required to generate reliable statistical intake estimates.
                  </p>
                </div>
              )}
            </div>

            {/* Recurring Problems Card */}
            <div className="bg-[#FBFBFA] p-4 rounded-xl border border-gray-200 flex flex-col">
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-gray-200">
                <span className="text-xs font-bold text-gray-800 flex items-center gap-1.5">
                  <Flame className="w-3.5 h-3.5 text-[#A94D37]" /> Persistent Issue Clusters
                </span>
                <span className="text-[10px] text-gray-400 font-mono">
                  {predictiveTrends?.recurring_problems?.length || 0} detected
                </span>
              </div>

              <div className="space-y-2.5 overflow-y-auto max-h-56 flex-1 text-xs">
                {predictiveTrends?.recurring_problems && predictiveTrends.recurring_problems.length > 0 ? (
                  predictiveTrends.recurring_problems.map((rp: any) => (
                    <div key={rp.problem_id} className="p-2.5 bg-white rounded-lg border border-gray-200">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-gray-800 text-[11px]">{rp.category_name}</span>
                        <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 font-mono">
                          {rp.total_complaint_count} reports
                        </span>
                      </div>
                      <p className="text-[10px] text-gray-500 mt-0.5 truncate">{rp.location_label}</p>
                      <div className="mt-1 text-[9px] text-gray-400 flex items-center justify-between border-t border-gray-100 pt-1">
                        <span>{rp.independent_incidents_count} incidents</span>
                        <div className="flex gap-1.5 font-semibold">
                          {rp.confirmed_duplicate_count > 0 && (
                            <span className="text-amber-700">{rp.confirmed_duplicate_count} confirmed</span>
                          )}
                          {rp.suspected_duplicate_count > 0 && (
                            <span className="text-purple-700">{rp.suspected_duplicate_count} suspected</span>
                          )}
                          {rp.confirmed_duplicate_count === 0 && rp.suspected_duplicate_count === 0 && (
                            <span className="text-gray-400">0 duplicates</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="py-8 text-center text-xs text-gray-400">
                    No recurring multi-complaint problems detected in current filter window.
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Civic Hotspot Risk Scores & Preventive Recommendations Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-2">
            {/* Hotspot Risk Scores */}
            <div className="border border-gray-200 rounded-xl p-4 bg-[#FBFBFA]">
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-gray-200">
                <span className="text-xs font-bold text-gray-800 flex items-center gap-1.5">
                  <ShieldAlert className="w-4 h-4 text-[#A94D37]" /> Civic Hotspot Risk Ranking
                </span>
                <span className="text-[10px] text-gray-400 font-mono">
                  Scale: 0-100 Risk Score
                </span>
              </div>

              <div className="space-y-3 overflow-y-auto max-h-72">
                {predictiveHotspots.length > 0 ? (
                  predictiveHotspots.map((hs: any) => (
                    <div key={hs.hotspot_id} className="p-3 bg-white rounded-xl border border-gray-200 text-xs shadow-sm">
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
                          Risk Score: {hs.risk_score} • {hs.risk_level}
                        </span>
                      </div>

                      <div className="text-[10px] text-gray-500 space-y-0.5 mt-1.5">
                        {hs.contributing_factors.map((f: string, idx: number) => (
                          <p key={idx}>• {f}</p>
                        ))}
                      </div>

                      <div className="mt-2 text-[10px] font-mono text-gray-400 bg-gray-50 px-2 py-1 rounded border border-gray-100">
                        Approx. Coordinates: {hs.latitude.toFixed(5)}, {hs.longitude.toFixed(5)}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="py-8 text-center text-xs text-gray-400">
                    No active high-density geographic risk hotspots detected.
                  </div>
                )}
              </div>
            </div>

            {/* Grounded Preventive Action Directives */}
            <div className="border border-gray-200 rounded-xl p-4 bg-[#FBFBFA]">
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-gray-200">
                <span className="text-xs font-bold text-gray-800 flex items-center gap-1.5">
                  <CheckCircle className="w-4 h-4 text-emerald-600" /> Preventive Action Recommendations
                </span>
                <span className="text-[10px] text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                  Data-Grounded Interventions
                </span>
              </div>

              <div className="space-y-3 overflow-y-auto max-h-72">
                {predictiveRecs.length > 0 ? (
                  predictiveRecs.map((rec: any) => (
                    <div key={rec.id} className="p-3 bg-white rounded-xl border border-emerald-100 shadow-sm text-xs space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-gray-900 text-[11px]">{rec.title}</span>
                        <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-gray-100 text-gray-600 uppercase">
                          {rec.category}
                        </span>
                      </div>
                      <p className="text-[11px] text-gray-700 leading-relaxed font-medium">
                        {rec.suggested_action}
                      </p>
                      <div className="pt-1 border-t border-gray-100 flex items-center justify-between text-[10px] text-gray-500">
                        <span>Supporting Metric: <strong>{rec.supporting_metric}</strong></span>
                        <span className="text-emerald-700 font-semibold">{rec.confidence_level}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="py-8 text-center text-xs text-gray-400">
                    No urgent preventive interventions required at this time.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Department Performance & SLA Benchmark */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 mb-8">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4 text-[#A94D37]" />
              <h3 className="text-sm font-bold text-[#17191D]">Department Performance & SLA Resolution</h3>
            </div>
            <span className="text-xs text-gray-400">Departmental resolution efficiency</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#F7F7F5] border-b border-gray-200 text-gray-600 font-semibold uppercase">
                <tr>
                  <th className="py-2.5 px-3">Department</th>
                  <th className="py-2.5 px-3">SLA Target</th>
                  <th className="py-2.5 px-3">Total Tickets</th>
                  <th className="py-2.5 px-3">Resolved</th>
                  <th className="py-2.5 px-3">In Field</th>
                  <th className="py-2.5 px-3">Pending</th>
                  <th className="py-2.5 px-3 text-right">Resolution Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {analytics?.department_performance && analytics.department_performance.length > 0 ? (
                  analytics.department_performance.map((dept: any, i: number) => (
                    <tr key={i} className="hover:bg-gray-50 transition">
                      <td className="py-3 px-3 font-semibold text-gray-900">{dept.name}</td>
                      <td className="py-3 px-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                          {dept.sla_hours ? `${dept.sla_hours}h SLA` : "N/A"}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-medium text-gray-700">{dept.total_complaints}</td>
                      <td className="py-3 px-3 font-medium text-[#25845B]">{dept.resolved_count}</td>
                      <td className="py-3 px-3 font-medium text-amber-600">{dept.in_progress_count}</td>
                      <td className="py-3 px-3 font-medium text-blue-600">{dept.pending_count}</td>
                      <td className="py-3 px-3 text-right">
                        <span className="font-bold text-gray-900">{dept.resolution_rate}%</span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-gray-400 italic">
                      No departmental metrics available for the current filter criteria.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Live Complaint Operations Table */}
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-gray-100 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-[#17191D]">All Civic Tickets</h2>
              <p className="text-[11px] text-gray-400">
                Showing {filteredComplaints.length} tickets matching active filters
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#F7F7F5] border-b border-gray-200 text-gray-600 font-semibold uppercase">
                <tr>
                  <th className="py-3 px-4">Ticket</th>
                  <th className="py-3 px-4">Citizen / Issue</th>
                  <th className="py-3 px-4">Department</th>
                  <th className="py-3 px-4">Assigned Staff</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredComplaints.length > 0 ? (
                  filteredComplaints.map((item) => (
                    <tr key={item.id} className="hover:bg-gray-50 transition">
                      <td className="py-3 px-4 font-mono font-bold text-[#A94D37]">
                        {item.tracking_id}
                        {item.ai_duplicate_suspect && (
                          <span className="block text-[10px] text-amber-600 font-sans font-bold">
                            ⚠️ Suspected Duplicate
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <p className="font-semibold text-gray-900 truncate max-w-xs">{item.title}</p>
                        <span className="text-[11px] text-gray-500">By {item.citizen_name} • {item.address}</span>
                      </td>
                      <td className="py-3 px-4 text-gray-700">
                        {item.department_name || "Unassigned"}
                      </td>
                      <td className="py-3 px-4">
                        {item.assigned_staff_name ? (
                          <span className="font-semibold text-gray-800">{item.assigned_staff_name}</span>
                        ) : (
                          <span className="text-gray-400 italic">None</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-gray-100 uppercase">
                          {item.status}
                        </span>
                        {item.resolution_verification_status === "citizen_disputed" && (
                          <span className="block mt-1 px-1.5 py-0.5 rounded text-[9px] font-bold bg-red-100 text-red-700 border border-red-200">
                            Disputed by Citizen
                          </span>
                        )}
                        {item.resolution_verification_status === "pending_citizen_confirmation" && (
                          <span className="block mt-1 px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-100 text-amber-700 border border-amber-200">
                            Awaiting Citizen Check
                          </span>
                        )}
                        {item.resolution_verification_status === "citizen_confirmed" && (
                          <span className="block mt-1 px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-100 text-emerald-700 border border-emerald-200">
                            Verified & Confirmed
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {item.resolution_verification_status === "citizen_disputed" && (
                            <button
                              onClick={() => {
                                setReviewingDispute(item);
                                setReviewAction("reopen");
                                setReviewNotes("");
                                setReviewMsg("");
                              }}
                              className="px-2.5 py-1 bg-red-600 hover:bg-red-700 text-white text-[11px] rounded font-semibold transition"
                            >
                              Review Dispute
                            </button>
                          )}
                          <button
                            onClick={() => openAssignmentModal(item)}
                            className="px-2.5 py-1 bg-[#17191D] hover:bg-black text-white text-[11px] rounded font-medium transition flex items-center gap-1"
                          >
                            <Users className="w-3 h-3" /> Assign Staff
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-gray-400 italic">
                      No complaints found matching selected filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Modal: Staff Assignment & AI Recommendation (Task 18) */}
        {assigningComplaint && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
            <div className="bg-white p-6 rounded-2xl max-w-lg w-full shadow-2xl border border-gray-200 max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between pb-3 border-b border-gray-100">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-[#A94D37] flex items-center justify-center text-white">
                    <Users className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-[#17191D]">
                      Assign Field Staff to Ticket
                    </h3>
                    <p className="text-[11px] text-gray-500">
                      Ticket <strong>{assigningComplaint.tracking_id}</strong> • {assigningComplaint.title}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => {
                    setAssigningComplaint(null);
                    setAssignError("");
                    setAssignSuccess("");
                    setRecommendation(null);
                  }}
                  className="p-1 hover:bg-gray-100 rounded-lg text-gray-400"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* AI Recommendation Card */}
              <div className="mt-4">
                {loadingRec ? (
                  <div className="p-4 bg-gray-50 border border-gray-200 rounded-xl text-center text-xs text-gray-500 animate-pulse">
                    Evaluating staff department compatibility, active workloads, and geographic proximity...
                  </div>
                ) : recommendation && recommendation.has_recommendation ? (
                  <div className="p-4 bg-gradient-to-r from-amber-50/80 via-white to-orange-50/60 border border-amber-200 rounded-xl shadow-sm">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-[#A94D37] flex items-center gap-1">
                        <Sparkles className="w-3.5 h-3.5" /> AI Recommended Officer
                      </span>
                      <span className="text-[10px] font-mono font-bold bg-amber-100 text-amber-800 px-2 py-0.5 rounded border border-amber-200">
                        Score: {recommendation.recommendation_score} / 1.0
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="text-xs font-bold text-gray-900">
                          {recommendation.recommended_staff_name}
                        </h4>
                        <div className="flex flex-wrap items-center gap-2 mt-1">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                            recommendation.department_match
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-gray-100 text-gray-700"
                          }`}>
                            {recommendation.department_match ? "✓ Department Match" : "Cross-Dept"}
                          </span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded font-semibold bg-blue-100 text-blue-800">
                            Active Workload: {recommendation.active_workload} tasks
                          </span>
                          {recommendation.distance_km !== null && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded font-semibold bg-purple-100 text-purple-800">
                              {recommendation.distance_km} km away
                            </span>
                          )}
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => setStaffId(String(recommendation.recommended_staff_id))}
                        className="px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white text-[11px] font-bold rounded-lg shadow-sm transition"
                      >
                        Select Top Pick
                      </button>
                    </div>

                    {/* Explanatory Reasons */}
                    <div className="mt-2.5 pt-2 border-t border-amber-100 text-[10px] text-gray-600 space-y-0.5">
                      {recommendation.recommendation_reasons.map((r: string, idx: number) => (
                        <p key={idx}>• {r}</p>
                      ))}
                    </div>

                    {/* Alternative Staff List */}
                    {recommendation.alternative_staff && recommendation.alternative_staff.length > 0 && (
                      <div className="mt-3 pt-2.5 border-t border-gray-100">
                        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-1.5">
                          Alternative Qualified Officers:
                        </span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                          {recommendation.alternative_staff.map((alt: any) => (
                            <button
                              key={alt.staff_id}
                              type="button"
                              onClick={() => setStaffId(String(alt.staff_id))}
                              className={`p-2 rounded-lg border text-left transition flex items-center justify-between ${
                                String(staffId) === String(alt.staff_id)
                                  ? "bg-amber-50 border-amber-400 text-amber-900"
                                  : "bg-white border-gray-200 text-gray-700 hover:bg-gray-50"
                              }`}
                            >
                              <div className="truncate">
                                <span className="font-bold text-[11px] block truncate">{alt.staff_name}</span>
                                <span className="text-[9px] text-gray-400">
                                  {alt.active_workload} active • {alt.department_name}
                                </span>
                              </div>
                              <span className="text-[10px] font-bold font-mono text-gray-500 shrink-0 ml-1">
                                {alt.recommendation_score}
                              </span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-3 bg-gray-50 border border-gray-200 rounded-xl text-xs text-gray-500">
                    No automated recommendation available. Please select from active municipal staff below.
                  </div>
                )}
              </div>

              {assignError && (
                <div className="mt-3 p-2.5 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                  {assignError}
                </div>
              )}

              {assignSuccess && (
                <div className="mt-3 p-2.5 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800">
                  {assignSuccess}
                </div>
              )}

              <form onSubmit={handleAssignStaff} className="mt-4 space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Confirmed Field Staff Assignment *
                  </label>
                  {staffMembers.length > 0 ? (
                    <select
                      value={staffId}
                      onChange={(e) => setStaffId(e.target.value)}
                      className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37] bg-white font-medium text-gray-800"
                    >
                      {staffMembers.map((staff) => (
                        <option key={staff.id} value={staff.id}>
                          {staff.first_name ? `${staff.first_name} ${staff.last_name} (${staff.username})` : staff.username} • {staff.department_name || staff.organization_name || "Municipal Field Unit"}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg text-xs text-gray-500">
                      No field staff accounts found in directory.
                    </div>
                  )}
                  <p className="text-[11px] text-gray-400 mt-1">
                    Human-in-the-loop guarantee: Assignment requires explicit administrative approval before notifications are dispatched.
                  </p>
                </div>

                <div className="flex justify-end gap-3 pt-3 border-t border-gray-100">
                  <button
                    type="button"
                    onClick={() => {
                      setAssigningComplaint(null);
                      setAssignError("");
                      setAssignSuccess("");
                      setRecommendation(null);
                    }}
                    className="px-4 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100 rounded-lg"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={assigning || staffMembers.length === 0}
                    className="px-4 py-2 text-xs font-semibold bg-[#A94D37] text-white rounded-lg shadow hover:bg-[#8e3e2b] disabled:opacity-50 flex items-center gap-1.5"
                  >
                    <CheckCircle className="w-3.5 h-3.5" />
                    {assigning ? "Assigning..." : "Approve & Dispatch Staff"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Modal: Dispute Review (Task 17) */}
        {reviewingDispute && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
            <div className="bg-white p-6 rounded-2xl max-w-lg w-full shadow-2xl border border-gray-200 max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between pb-3 border-b border-gray-100">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-red-600" />
                  <h3 className="text-base font-bold text-[#17191D]">
                    Supervisor Review: Disputed Resolution
                  </h3>
                </div>
                <button
                  onClick={() => setReviewingDispute(null)}
                  className="p-1 hover:bg-gray-100 rounded-lg text-gray-400"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="mt-3 text-xs space-y-3">
                <div className="p-3 bg-gray-50 rounded-xl border border-gray-200">
                  <span className="text-[10px] uppercase font-bold text-gray-400 block">Ticket Information</span>
                  <div className="font-mono font-bold text-sm text-[#A94D37] mt-0.5">
                    {reviewingDispute.tracking_id}
                  </div>
                  <p className="font-semibold text-gray-800 text-xs mt-1">{reviewingDispute.title}</p>
                  <p className="text-gray-500 text-[11px]">Location: {reviewingDispute.address}</p>
                  <p className="text-gray-500 text-[11px]">Assigned Staff: {reviewingDispute.assigned_staff_name || "Unassigned"}</p>
                </div>

                <div className="p-3 bg-red-50 rounded-xl border border-red-200">
                  <span className="text-[10px] uppercase font-bold text-red-700 block mb-1">Citizen Dispute Statement</span>
                  <p className="text-red-900 font-medium text-xs leading-relaxed">
                    &ldquo;{reviewingDispute.feedback?.dispute_reason || "Citizen indicated issue remains unresolved."}&rdquo;
                  </p>
                  {reviewingDispute.feedback?.rating && (
                    <span className="text-[10px] text-red-600 font-bold mt-1 block">
                      Citizen Score: {reviewingDispute.feedback.rating} / 5 Stars
                    </span>
                  )}
                </div>

                {reviewingDispute.resolution_notes && (
                  <div className="p-3 bg-green-50 rounded-xl border border-green-200">
                    <span className="text-[10px] uppercase font-bold text-green-800 block mb-1">Previous Staff Resolution Note</span>
                    <p className="text-green-900 text-xs">{reviewingDispute.resolution_notes}</p>
                  </div>
                )}

                {/* Evidence Comparison Preview */}
                {reviewingDispute.evidences && reviewingDispute.evidences.length > 0 && (
                  <div className="border border-gray-200 rounded-xl p-3 bg-gray-50">
                    <span className="text-[10px] font-bold text-gray-700 uppercase tracking-wider block mb-2">Attached Photographic Records</span>
                    <div className="grid grid-cols-2 gap-2">
                      {reviewingDispute.evidences.map((ev: any) => (
                        <div key={ev.id} className="border border-gray-200 rounded-lg overflow-hidden bg-white">
                          {ev.file_type === "image" && (
                            <img
                              src={ev.file.startsWith("http") ? ev.file : `http://127.0.0.1:8000${ev.file}`}
                              alt="Evidence"
                              className="w-full h-20 object-cover"
                            />
                          )}
                          <div className="p-1 text-[9px] text-gray-600 truncate font-medium">
                            {ev.is_resolution_proof ? "Staff Resolution Proof" : "Citizen Evidence"}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {reviewMsg && (
                  <div className={`p-2.5 rounded-lg text-xs font-medium ${reviewMsg.includes("Failed") ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-800"}`}>
                    {reviewMsg}
                  </div>
                )}

                <form onSubmit={handleAdminReviewDispute} className="space-y-3 pt-2 border-t border-gray-100">
                  <div>
                    <label className="block text-xs font-bold text-gray-800 mb-1">
                      Administrative Action
                    </label>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => setReviewAction("reopen")}
                        className={`p-2.5 rounded-xl border text-xs font-semibold text-left transition ${
                          reviewAction === "reopen"
                            ? "bg-amber-500 text-white border-amber-600 shadow-sm"
                            : "bg-white text-gray-700 border-gray-200 hover:bg-gray-50"
                        }`}
                      >
                        <span className="block font-bold">Reopen Ticket</span>
                        <span className={`text-[10px] block mt-0.5 ${reviewAction === "reopen" ? "text-amber-100" : "text-gray-400"}`}>
                          Send back to in_progress for further field action
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => setReviewAction("uphold")}
                        className={`p-2.5 rounded-xl border text-xs font-semibold text-left transition ${
                          reviewAction === "uphold"
                            ? "bg-emerald-600 text-white border-emerald-700 shadow-sm"
                            : "bg-white text-gray-700 border-gray-200 hover:bg-gray-50"
                        }`}
                      >
                        <span className="block font-bold">Uphold Resolution</span>
                        <span className={`text-[10px] block mt-0.5 ${reviewAction === "uphold" ? "text-emerald-100" : "text-gray-400"}`}>
                          Mark verified if dispute is invalid
                        </span>
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-gray-700 mb-1">
                      Supervisor / Admin Review Notes (Optional)
                    </label>
                    <textarea
                      rows={2}
                      value={reviewNotes}
                      onChange={(e) => setReviewNotes(e.target.value)}
                      placeholder="Add remarks explaining review rationale..."
                      className="w-full px-2.5 py-1.5 text-xs border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37] bg-white text-gray-800"
                    />
                  </div>

                  <div className="flex justify-end gap-2 pt-2 border-t border-gray-100">
                    <button
                      type="button"
                      onClick={() => setReviewingDispute(null)}
                      className="px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-100 rounded-lg"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={reviewSubmitting}
                      className="px-4 py-1.5 bg-[#A94D37] hover:bg-[#8e3e2b] text-white text-xs font-semibold rounded-lg shadow transition"
                    >
                      {reviewSubmitting ? "Processing..." : "Submit Review Decision"}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
