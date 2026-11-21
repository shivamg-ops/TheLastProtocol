"use client";

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { api } from "@/lib/api";
import { CheckCircle } from "lucide-react";

export default function StaffPage() {
  const [complaints, setComplaints] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTask, setActiveTask] = useState<any>(null);
  const [statusVal, setStatusVal] = useState("in_progress");
  const [notesVal, setNotesVal] = useState("");
  const [submitting, setSubmitting] = useState(false);

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
    try {
      await api.post(`/complaints/${activeTask.id}/update_status/`, {
        status: statusVal,
        notes: notesVal,
      });
      setActiveTask(null);
      setNotesVal("");
      loadStaffTasks();
    } catch (err: any) {
      alert(err.response?.data?.error || "Failed to update task status.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full flex-1">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-[#17191D]">Staff Resolution Workspace</h1>
          <p className="text-xs text-gray-500 mt-1">Field tasks assigned to your municipal unit</p>
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
                  <div key={c.id} className="p-4 hover:bg-gray-50 transition flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-[#A94D37]">{c.tracking_id}</span>
                        <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-gray-100">
                          {c.status}
                        </span>
                      </div>
                      <h4 className="font-bold text-sm text-gray-900 mt-1">{c.title}</h4>
                      <p className="text-xs text-gray-500 mt-0.5">Location: {c.address} • {c.ward_or_zone}</p>
                    </div>

                    <button
                      onClick={() => {
                        setActiveTask(c);
                        setStatusVal(c.status);
                      }}
                      className="px-3 py-1.5 bg-[#A94D37] hover:bg-[#8e3e2b] text-white text-xs font-semibold rounded-lg shadow-sm"
                    >
                      Update Progress
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Action Pane */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 h-fit">
            <h3 className="text-sm font-bold text-[#17191D] pb-3 border-b border-gray-100">
              Submit Resolution Evidence & Notes
            </h3>

            {activeTask ? (
              <form onSubmit={handleUpdateProgress} className="mt-4 space-y-4">
                <div className="p-3 bg-gray-50 rounded-lg text-xs">
                  <span className="text-gray-400">Current Task:</span>
                  <p className="font-bold text-gray-800">{activeTask.tracking_id} — {activeTask.title}</p>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Status</label>
                  <select
                    value={statusVal}
                    onChange={(e) => setStatusVal(e.target.value)}
                    className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37]"
                  >
                    <option value="in_progress">In Progress</option>
                    <option value="resolved">Resolved (Work Completed)</option>
                    <option value="escalated">Escalate to Senior Officer</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">Field Notes / Work Summary</label>
                  <textarea
                    rows={4}
                    required
                    placeholder="Describe actions taken (e.g., cleared 2 tons of debris, repaired broken pipeline segment)..."
                    value={notesVal}
                    onChange={(e) => setNotesVal(e.target.value)}
                    className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37]"
                  />
                </div>

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full py-2 bg-[#25845B] hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg shadow transition flex items-center justify-center gap-1.5"
                >
                  <CheckCircle className="w-4 h-4" />
                  {submitting ? "Updating..." : "Commit Status & Notify Citizen"}
                </button>
              </form>
            ) : (
              <div className="py-12 text-center text-xs text-gray-400">
                Select a task on the left to submit field resolution notes.
              </div>
            )}
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}
