"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { api } from "@/lib/api";
import { Eye, Plus, FileText } from "lucide-react";

export default function CitizenDashboard() {
  const [complaints, setComplaints] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedComplaint, setSelectedComplaint] = useState<any>(null);

  useEffect(() => {
    fetchComplaints();
  }, []);

  const fetchComplaints = () => {
    setLoading(true);
    api.get("/complaints/")
      .then((res) => {
        setComplaints(res.data);
      })
      .catch((err) => console.log(err))
      .finally(() => setLoading(false));
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      submitted: "bg-blue-50 text-blue-700 border-blue-200",
      assigned: "bg-purple-50 text-purple-700 border-purple-200",
      in_progress: "bg-amber-50 text-amber-700 border-amber-200",
      resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
      escalated: "bg-red-50 text-red-700 border-red-200",
    };
    return (
      <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border capitalize ${styles[status] || "bg-gray-50 text-gray-700"}`}>
        {status.replace('_', ' ')}
      </span>
    );
  };

  return (
    <div className="flex flex-col min-h-screen">
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full flex-1">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-bold text-[#17191D]">Citizen Grievance Portal</h1>
            <p className="text-xs text-gray-500 mt-1">Track your filed complaints and resolution verification</p>
          </div>
          <Link
            href="/report"
            className="px-4 py-2 bg-[#A94D37] hover:bg-[#8e3e2b] text-white text-xs font-semibold rounded-lg shadow transition flex items-center gap-1.5"
          >
            <Plus className="w-4 h-4" /> File New Complaint
          </Link>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
            <span className="text-xs text-gray-500 font-medium">Total Reported</span>
            <div className="text-2xl font-bold text-[#17191D] mt-1">{complaints.length}</div>
          </div>
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
            <span className="text-xs text-gray-500 font-medium">In Resolution</span>
            <div className="text-2xl font-bold text-amber-600 mt-1">
              {complaints.filter((c) => ['assigned', 'in_progress'].includes(c.status)).length}
            </div>
          </div>
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
            <span className="text-xs text-gray-500 font-medium">Successfully Resolved</span>
            <div className="text-2xl font-bold text-[#25845B] mt-1">
              {complaints.filter((c) => c.status === 'resolved').length}
            </div>
          </div>
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
            <span className="text-xs text-gray-500 font-medium">Pending Review</span>
            <div className="text-2xl font-bold text-blue-600 mt-1">
              {complaints.filter((c) => c.status === 'submitted').length}
            </div>
          </div>
        </div>

        {/* Complaints Table & Details */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-sm font-bold text-[#17191D]">My Complaints</h2>
              <span className="text-xs text-gray-400">{complaints.length} items</span>
            </div>

            {loading ? (
              <div className="p-8 text-center text-xs text-gray-400">Loading complaints...</div>
            ) : complaints.length === 0 ? (
              <div className="p-12 text-center">
                <FileText className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                <h3 className="text-sm font-bold text-gray-700">No complaints reported yet</h3>
                <p className="text-xs text-gray-400 mt-1">Report road, garbage, water or streetlight issues using AI.</p>
                <Link
                  href="/report"
                  className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 bg-[#A94D37] text-white text-xs font-semibold rounded-lg"
                >
                  <Plus className="w-4 h-4" /> Report Problem
                </Link>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#F7F7F5] border-b border-gray-200 text-gray-600 font-semibold uppercase">
                    <tr>
                      <th className="py-3 px-4">Tracking ID</th>
                      <th className="py-3 px-4">Title & Category</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Priority</th>
                      <th className="py-3 px-4">Date</th>
                      <th className="py-3 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {complaints.map((item) => (
                      <tr key={item.id} className="hover:bg-gray-50 transition">
                        <td className="py-3 px-4 font-mono font-bold text-[#A94D37]">
                          {item.tracking_id}
                        </td>
                        <td className="py-3 px-4">
                          <p className="font-semibold text-gray-900 truncate max-w-xs">{item.title}</p>
                          <span className="text-[11px] text-gray-500">{item.category_name || "General"}</span>
                        </td>
                        <td className="py-3 px-4">{getStatusBadge(item.status)}</td>
                        <td className="py-3 px-4">
                          <span className="uppercase text-[10px] font-bold tracking-wider px-2 py-0.5 rounded bg-gray-100">
                            {item.priority}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-gray-500">
                          {new Date(item.created_at).toLocaleDateString()}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => setSelectedComplaint(item)}
                            className="p-1.5 hover:bg-gray-200 rounded text-gray-600 transition"
                            title="View Timeline"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Timeline / Detail Pane */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 h-fit">
            <h3 className="text-sm font-bold text-[#17191D] pb-3 border-b border-gray-100">
              Complaint Detail & Activity
            </h3>
            {selectedComplaint ? (
              <div className="mt-4 space-y-4 text-xs">
                <div>
                  <span className="text-gray-400">Tracking Code:</span>
                  <div className="font-mono font-bold text-sm text-[#A94D37]">
                    {selectedComplaint.tracking_id}
                  </div>
                </div>

                <div>
                  <span className="text-gray-400">Title:</span>
                  <p className="font-semibold text-gray-800">{selectedComplaint.title}</p>
                </div>

                <div>
                  <span className="text-gray-400">Department:</span>
                  <p className="font-semibold text-gray-800">{selectedComplaint.department_name || "Assigned"}</p>
                </div>

                <div>
                  <span className="text-gray-400">Assigned Staff:</span>
                  <p className="font-semibold text-gray-800">{selectedComplaint.assigned_staff_name || "Pending Assignment"}</p>
                </div>

                <div>
                  <span className="text-gray-400">Location:</span>
                  <p className="text-gray-700">{selectedComplaint.address}</p>
                </div>

                {selectedComplaint.resolution_notes && (
                  <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                    <span className="font-bold text-green-900 block mb-1">Resolution Note by Staff:</span>
                    <p className="text-green-800">{selectedComplaint.resolution_notes}</p>
                  </div>
                )}

                {/* Timeline */}
                <div className="pt-3 border-t border-gray-100">
                  <h4 className="font-bold text-gray-700 mb-2">Audit History</h4>
                  <div className="space-y-3">
                    {selectedComplaint.timeline && selectedComplaint.timeline.length > 0 ? (
                      selectedComplaint.timeline.map((tl: any, i: number) => (
                        <div key={i} className="flex gap-2.5 items-start">
                          <div className="w-2 h-2 rounded-full bg-[#A94D37] mt-1 shrink-0"></div>
                          <div>
                            <p className="font-semibold text-gray-900">{tl.action}</p>
                            <p className="text-[11px] text-gray-500">{tl.details}</p>
                            <span className="text-[10px] text-gray-400">{new Date(tl.created_at).toLocaleString()}</span>
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="text-gray-400 italic">No timeline entries yet.</p>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-12 text-center text-xs text-gray-400">
                Click the eye icon on any complaint to inspect its timeline and resolution proof.
              </div>
            )}
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
}
