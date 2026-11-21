"use client";

import { useEffect, useState, useMemo } from "react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { api } from "@/lib/api";
import {
  CheckCircle,
  Camera,
  Upload,
  AlertCircle,
  Clock,
  MapPin,
  AlertTriangle,
  History,
  Layers,
  ArrowRight
} from "lucide-react";

export default function StaffPage() {
  const [complaints, setComplaints] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTask, setActiveTask] = useState<any>(null);
  const [statusVal, setStatusVal] = useState("in_progress");
  const [notesVal, setNotesVal] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [proofPreview, setProofPreview] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState("");

  useEffect(() => {
    loadStaffTasks();
  }, []);

  const loadStaffTasks = () => {
    setLoading(true);
    api.get("/complaints/")
      .then((res) => setComplaints(res.data))
      .catch((err) => console.log(err))
      .finally(() => setLoading(false));
  };

  const handleUpdateProgress = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTask) return;

    setSubmitting(true);
    setStatusMsg("");
    try {
      // 1. If proof file is selected, upload to /evidence/ with is_resolution_proof=true
      if (proofFile) {
        const formData = new FormData();
        formData.append("complaint", activeTask.id);
        formData.append("file", proofFile);
        formData.append("file_type", "image");
        formData.append("is_resolution_proof", "true");

        await api.post("/evidence/", formData, {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        });
      }

      // 2. Update complaint status
      await api.post(`/complaints/${activeTask.id}/update_status/`, {
        status: statusVal,
        notes: notesVal,
      });

      setActiveTask(null);
      setNotesVal("");
      setProofFile(null);
      setProofPreview(null);
      loadStaffTasks();
    } catch (err: any) {
      setStatusMsg(err.response?.data?.error || "Failed to update task status.");
    } finally {
      setSubmitting(false);
    }
  };

  const activeWorkloadCount = useMemo(() => {
    return complaints.filter((c) => ["assigned", "in_progress", "escalated"].includes(c.status)).length;
  }, [complaints]);

  const resolvedCount = useMemo(() => {
    return complaints.filter((c) => ["resolved", "verified"].includes(c.status)).length;
  }, [complaints]);

  const overdueCount = useMemo(() => {
    return complaints.filter((c) => c.sla_info?.is_overdue).length;
  }, [complaints]);

  const getPriorityBadge = (priority: string) => {
    const styles: Record<string, string> = {
      urgent: "bg-red-100 text-red-800 border-red-200",
      high: "bg-orange-100 text-orange-800 border-orange-200",
      medium: "bg-blue-100 text-blue-800 border-blue-200",
      low: "bg-gray-100 text-gray-700 border-gray-200",
    };
    return (
      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${styles[priority] || "bg-gray-100 text-gray-700"}`}>
        {priority}
      </span>
    );
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      assigned: "bg-purple-100 text-purple-800",
      in_progress: "bg-amber-100 text-amber-800",
      resolved: "bg-emerald-100 text-emerald-800",
      verified: "bg-teal-100 text-teal-800",
      escalated: "bg-red-100 text-red-800",
    };
    return (
      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${styles[status] || "bg-gray-100 text-gray-700"}`}>
        {status.replace("_", " ")}
      </span>
    );
  };

  return (
    <div className="flex flex-col min-h-screen bg-[#FAFAF9]">
      <Navbar />
      <div className="w-full px-3 sm:px-5 lg:px-6 py-6 flex-1">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[#17191D]">Field Officer Workspace</h1>
            <p className="text-xs text-gray-500 mt-1">
              Real-time assigned grievances, SLA timelines, and resolution proof submission
            </p>
          </div>
          <button
            onClick={loadStaffTasks}
            className="px-3 py-1.5 bg-white border border-gray-200 hover:bg-gray-50 text-xs font-semibold rounded-lg shadow-sm text-gray-700"
          >
            Refresh Tasks
          </button>
        </div>

        {/* Staff Workload & SLA KPI Row (Task 18) */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wider block">Total Assigned</span>
              <div className="text-2xl font-extrabold text-[#17191D] mt-0.5">{complaints.length}</div>
              <span className="text-[10px] text-gray-400">All-time lifetime tickets</span>
            </div>
            <div className="w-9 h-9 rounded-full bg-gray-100 flex items-center justify-center text-gray-700">
              <Layers className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-amber-200 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-[11px] text-amber-800 font-semibold uppercase tracking-wider block">Active Workload</span>
              <div className="text-2xl font-extrabold text-amber-600 mt-0.5">{activeWorkloadCount}</div>
              <span className="text-[10px] text-amber-600">Tasks requiring field action</span>
            </div>
            <div className="w-9 h-9 rounded-full bg-amber-100 flex items-center justify-center text-amber-700">
              <Clock className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-red-200 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-[11px] text-red-800 font-semibold uppercase tracking-wider block">SLA Overdue</span>
              <div className="text-2xl font-extrabold text-red-600 mt-0.5">{overdueCount}</div>
              <span className="text-[10px] text-red-500">Exceeded municipal deadline</span>
            </div>
            <div className="w-9 h-9 rounded-full bg-red-100 flex items-center justify-center text-red-700">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>

          <div className="bg-white p-4 rounded-xl border border-emerald-200 shadow-sm flex items-center justify-between">
            <div>
              <span className="text-[11px] text-emerald-800 font-semibold uppercase tracking-wider block">Completed</span>
              <div className="text-2xl font-extrabold text-[#25845B] mt-0.5">{resolvedCount}</div>
              <span className="text-[10px] text-gray-500">Resolved & verified work</span>
            </div>
            <div className="w-9 h-9 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-700">
              <CheckCircle className="w-5 h-5" />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-sm font-bold text-[#17191D]">Assigned Tasks</h2>
              <span className="text-xs text-gray-400">{complaints.length} tickets</span>
            </div>

            {loading ? (
              <div className="p-8 text-center text-xs text-gray-400">Loading tasks...</div>
            ) : complaints.length === 0 ? (
              <div className="p-12 text-center text-gray-500 text-xs">
                No active tasks assigned to your account.
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {complaints.map((c) => (
                  <div key={c.id} className="p-4 hover:bg-gray-50 transition flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-bold text-[#DC2626]">{c.tracking_id}</span>
                        {getStatusBadge(c.status)}
                        {getPriorityBadge(c.priority)}
                        {c.sla_info?.is_overdue && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-red-600 text-white animate-pulse">
                            Overdue
                          </span>
                        )}
                      </div>
                      <h4 className="font-bold text-sm text-gray-900">{c.title}</h4>
                      
                      <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500 pt-0.5">
                        <span className="flex items-center gap-1 text-gray-600">
                          <MapPin className="w-3.5 h-3.5 text-gray-400" />
                          {c.address} {c.ward_or_zone ? `(${c.ward_or_zone})` : ""}
                        </span>
                        {c.latitude && c.longitude && (
                          <span className="font-mono text-[10px] text-gray-400 bg-gray-100 px-1.5 py-0.2 rounded">
                            GPS: {Number(c.latitude).toFixed(4)}, {Number(c.longitude).toFixed(4)}
                          </span>
                        )}
                      </div>

                      {/* SLA Progress Bar / Target */}
                      {c.sla_info?.sla_deadline && (
                        <div className="text-[11px] text-gray-500 pt-0.5 flex items-center gap-1.5">
                          <Clock className="w-3 h-3 text-gray-400" />
                          <span>
                            SLA Target: <strong>{new Date(c.sla_info.sla_deadline).toLocaleString()}</strong>
                          </span>
                          {c.sla_info.remaining_seconds !== null && c.sla_info.remaining_seconds > 0 && (
                            <span className="text-emerald-700 font-semibold">
                              ({Math.round(c.sla_info.remaining_seconds / 3600)}h remaining)
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => {
                        setActiveTask(c);
                        setStatusVal(c.status);
                        setNotesVal(c.resolution_notes || "");
                      }}
                      className="px-3.5 py-1.5 bg-[#DC2626] hover:bg-[#B91C1C] text-white text-xs font-semibold rounded-lg shadow-sm shrink-0 self-start sm:self-center transition"
                    >
                      Update Task
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Action Pane with History & Proof */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 h-fit space-y-4">
            <h3 className="text-sm font-bold text-[#17191D] pb-3 border-b border-gray-100">
              Submit Resolution Evidence & Notes
            </h3>

            {activeTask ? (
              <div className="space-y-4">
                <div className="p-3 bg-gray-50 rounded-xl text-xs border border-gray-200">
                  <span className="text-gray-400 block font-medium">Active Ticket:</span>
                  <p className="font-bold text-gray-900 mt-0.5">{activeTask.tracking_id} — {activeTask.title}</p>
                  <p className="text-[11px] text-gray-600 mt-1">Location: {activeTask.address}</p>
                  {activeTask.description && (
                    <p className="text-[11px] text-gray-500 mt-1 bg-white p-2 rounded border border-gray-100">
                      &ldquo;{activeTask.description}&rdquo;
                    </p>
                  )}
                </div>

                <form onSubmit={handleUpdateProgress} className="space-y-3.5">
                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1">Update Status</label>
                    <select
                      value={statusVal}
                      onChange={(e) => setStatusVal(e.target.value)}
                      className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-none focus:border-[#DC2626] bg-white font-medium"
                    >
                      <option value="in_progress">In Progress</option>
                      <option value="resolved">Resolved (Work Completed)</option>
                      <option value="escalated">Escalate to Senior Officer</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1">Field Notes / Work Summary *</label>
                    <textarea
                      rows={3}
                      required
                      placeholder="Describe field actions taken (e.g., cleared 2 tons of debris, repaired broken pipeline segment)..."
                      value={notesVal}
                      onChange={(e) => setNotesVal(e.target.value)}
                      className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-none focus:border-[#DC2626] bg-white text-gray-800"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1">
                      Upload Resolution Proof (Photo)
                    </label>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          const f = e.target.files[0];
                          setProofFile(f);
                          setProofPreview(URL.createObjectURL(f));
                        }
                      }}
                      className="w-full text-xs text-gray-500 file:mr-2 file:py-1 file:px-2 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200"
                    />
                    {proofPreview && (
                      <div className="mt-2 flex items-center gap-2 p-2 bg-gray-50 rounded border">
                        <img src={proofPreview} alt="Proof" className="w-12 h-12 object-cover rounded" />
                        <span className="text-[11px] text-gray-600 truncate">{proofFile?.name}</span>
                      </div>
                    )}
                  </div>

                  {statusMsg && (
                    <div className="p-2.5 bg-red-50 border border-red-200 text-xs text-red-700 rounded-lg">
                      {statusMsg}
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={submitting}
                    className="w-full py-2 bg-[#25845B] hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg shadow transition flex items-center justify-center gap-1.5"
                  >
                    <CheckCircle className="w-4 h-4" />
                    {submitting ? "Updating & Uploading..." : "Commit Status & Notify Citizen"}
                  </button>
                </form>

                {/* Complaint History / Timeline (Task 18) */}
                {activeTask.timeline && activeTask.timeline.length > 0 && (
                  <div className="pt-3 border-t border-gray-100">
                    <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-2 flex items-center gap-1">
                      <History className="w-3 h-3 text-[#DC2626]" /> Ticket Audit History
                    </span>
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {activeTask.timeline.map((tl: any, i: number) => (
                        <div key={i} className="text-[11px] flex items-start gap-2 border-l-2 border-[#DC2626] pl-2 py-0.5">
                          <div>
                            <span className="font-semibold text-gray-800 block">{tl.action}</span>
                            {tl.details && <span className="text-gray-500 text-[10px] block">{tl.details}</span>}
                            <span className="text-[9px] text-gray-400">{new Date(tl.created_at).toLocaleString()}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="py-12 text-center text-xs text-gray-400">
                Select a task on the left to review location, timeline, and submit field resolution notes.
              </div>
            )}
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}
