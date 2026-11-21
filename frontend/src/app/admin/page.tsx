"use client";

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { api } from "@/lib/api";

export default function AdminPage() {
  const [analytics, setAnalytics] = useState<any>(null);
  const [complaints, setComplaints] = useState<any[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [staffMembers, setStaffMembers] = useState<any[]>([]);
  const [assigningComplaint, setAssigningComplaint] = useState<any>(null);
  const [staffId, setStaffId] = useState("");
  const [assignError, setAssignError] = useState("");
  const [assignSuccess, setAssignSuccess] = useState("");
  const [assigning, setAssigning] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [resAnalytics, resComplaints, resDepts, resStaff] = await Promise.all([
        api.get("/analytics/summary/"),
        api.get("/complaints/"),
        api.get("/departments/"),
        api.get("/user/staff-list/"),
      ]);
      setAnalytics(resAnalytics.data);
      setComplaints(resComplaints.data);
      setDepartments(resDepts.data);
      setStaffMembers(resStaff.data);
      if (resStaff.data.length > 0 && !staffId) {
        setStaffId(String(resStaff.data[0].id));
      }
    } catch (err) {
      console.error(err);
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
      loadData();
    } catch (err: any) {
      const msg = err.response?.data?.error || "Error assigning staff. Ensure staff user exists.";
      setAssignError(msg);
    } finally {
      setAssigning(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full flex-1">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#A94D37] animate-pulse"></span>
              <h1 className="text-2xl font-bold text-[#17191D]">AI Command & Administration Centre</h1>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Real-time municipal grievance triage, duplicate prevention, and department resolution SLAs
            </p>
          </div>
          <button
            onClick={loadData}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-800 text-xs font-semibold rounded-lg transition"
          >
            Refresh Live Feeds
          </button>
        </div>

        {/* Live Metrics Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-[#17191D] text-white p-5 rounded-xl border border-gray-800 shadow">
            <span className="text-xs text-gray-400 font-medium">Total Complaints</span>
            <div className="text-3xl font-extrabold text-white mt-1">
              {analytics?.total_complaints || complaints.length}
            </div>
          </div>
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
            <span className="text-xs text-gray-500 font-medium">Pending Triage / Assign</span>
            <div className="text-3xl font-extrabold text-blue-600 mt-1">
              {analytics?.pending_complaints || 0}
            </div>
          </div>
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
            <span className="text-xs text-gray-500 font-medium">Active In Field</span>
            <div className="text-3xl font-extrabold text-amber-600 mt-1">
              {analytics?.in_progress_complaints || 0}
            </div>
          </div>
          <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm">
            <span className="text-xs text-gray-500 font-medium">Resolution Rate</span>
            <div className="text-3xl font-extrabold text-[#25845B] mt-1">
              {analytics?.resolution_rate || 0}%
            </div>
          </div>
        </div>

        {/* Department SLAs and Live Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-sm font-bold text-[#17191D]">All Civic Tickets</h2>
              <span className="text-xs text-gray-400">{complaints.length} tickets</span>
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
                  {complaints.map((item) => (
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
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => setAssigningComplaint(item)}
                          className="px-2.5 py-1 bg-[#17191D] hover:bg-black text-white text-[11px] rounded font-medium transition"
                        >
                          Dispatch Staff
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Department Breakdown Column */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 h-fit">
            <h3 className="text-sm font-bold text-[#17191D] pb-3 border-b border-gray-100">
              Department Performance & SLAs
            </h3>
            <div className="mt-4 space-y-4">
              {departments.map((dept) => (
                <div key={dept.id} className="p-3 rounded-lg bg-[#F7F7F5] border border-gray-200">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-bold text-xs text-[#17191D]">{dept.name}</span>
                    <span className="text-[10px] font-bold text-[#A94D37] bg-white px-2 py-0.5 rounded border border-gray-200">
                      SLA: {dept.sla_hours}h
                    </span>
                  </div>
                  <p className="text-[11px] text-gray-500 line-clamp-2">{dept.description}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Modal: Staff Assignment */}
        {assigningComplaint && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
            <div className="bg-white p-6 rounded-2xl max-w-md w-full shadow-2xl border border-gray-200">
              <h3 className="text-base font-bold text-[#17191D]">
                Assign Field Staff to Ticket
              </h3>
              <p className="text-xs text-gray-500 mt-1">
                Ticket: <strong>{assigningComplaint.tracking_id}</strong> — {assigningComplaint.title}
              </p>

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
                    Select Field Staff Member
                  </label>
                  {staffMembers.length > 0 ? (
                    <select
                      value={staffId}
                      onChange={(e) => setStaffId(e.target.value)}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:border-[#A94D37] bg-white"
                    >
                      {staffMembers.map((staff) => (
                        <option key={staff.id} value={staff.id}>
                          {staff.first_name ? `${staff.first_name} ${staff.last_name} (${staff.username})` : staff.username} • {staff.organization_name || "Municipal Field Unit"}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg text-xs text-gray-500">
                      No field staff accounts found in directory.
                    </div>
                  )}
                  <p className="text-[11px] text-gray-400 mt-1">
                    Only verified municipal field officers and active staff are available for assignment.
                  </p>
                </div>

                <div className="flex justify-end gap-3 pt-3 border-t border-gray-100">
                  <button
                    type="button"
                    onClick={() => {
                      setAssigningComplaint(null);
                      setAssignError("");
                      setAssignSuccess("");
                    }}
                    className="px-4 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100 rounded-lg"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={assigning || staffMembers.length === 0}
                    className="px-4 py-2 text-xs font-semibold bg-[#A94D37] text-white rounded-lg shadow hover:bg-[#8e3e2b] disabled:opacity-50"
                  >
                    {assigning ? "Assigning..." : "Confirm Assignment"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
