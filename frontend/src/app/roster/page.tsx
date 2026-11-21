"use client";

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { api } from "@/lib/api";
import {
  Users,
  Building2,
  Mail,
  Phone,
  CheckCircle,
  Clock,
  Layers,
  MapPin,
  Sparkles,
  Search,
  Filter,
  UserCheck
} from "lucide-react";

export default function StaffRosterPage() {
  const [staffList, setStaffList] = useState<any[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedDept, setSelectedDept] = useState<string>("");

  useEffect(() => {
    fetchStaffAndMeta();
  }, []);

  const fetchStaffAndMeta = async () => {
    setLoading(true);
    try {
      const [staffRes, deptRes] = await Promise.all([
        api.get("/user/staff-list/"),
        api.get("/departments/")
      ]);
      setStaffList(staffRes.data || []);
      setDepartments(deptRes.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const filteredStaff = staffList.filter((staff) => {
    const matchesSearch =
      staff.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (staff.first_name && staff.first_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (staff.email && staff.email.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (staff.skills && staff.skills.toLowerCase().includes(searchQuery.toLowerCase()));

    const matchesDept = selectedDept ? String(staff.department) === String(selectedDept) : true;

    return matchesSearch && matchesDept;
  });

  return (
    <div className="flex flex-col min-h-screen bg-[#FAFAF9]">
      <Navbar />

      <main className="w-full px-3 sm:px-5 lg:px-6 py-6 flex-1">
        {/* Header Bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#DC2626] animate-pulse"></span>
              <h1 className="text-2xl font-bold text-[#17191D]">Municipal Field Staff Directory</h1>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Active field officers, department alignments, verified skills, and workload distribution
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-white border border-gray-200 text-gray-700 shadow-sm">
              Total Officers: <strong>{staffList.length}</strong>
            </span>
          </div>
        </div>

        {/* Filter / Search Bar */}
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm mb-6 flex flex-wrap items-center gap-4">
          <div className="flex-1 min-w-[240px] relative">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-3" />
            <input
              type="text"
              placeholder="Search by officer name, email, or verified skill..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#DC2626]"
            />
          </div>

          <div className="min-w-[200px]">
            <select
              value={selectedDept}
              onChange={(e) => setSelectedDept(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#DC2626] bg-white text-gray-700"
            >
              <option value="">All Municipal Departments</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Staff Cards Grid */}
        {loading ? (
          <div className="py-20 text-center text-xs text-gray-400">Loading municipal field staff roster...</div>
        ) : filteredStaff.length === 0 ? (
          <div className="py-20 text-center text-xs text-gray-400 bg-white rounded-2xl border border-gray-200">
            No field staff members found matching the current criteria.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {filteredStaff.map((staff) => (
              <div
                key={staff.id}
                className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 hover:border-gray-300 transition flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center font-bold text-gray-700 text-sm border border-gray-200">
                        {staff.username.slice(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <h3 className="font-bold text-sm text-[#17191D]">
                          {staff.first_name ? `${staff.first_name} ${staff.last_name || ""}` : staff.username}
                        </h3>
                        <span className="text-[10px] text-gray-400 font-mono">@{staff.username}</span>
                      </div>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-green-100 text-green-800 uppercase">
                      {staff.role}
                    </span>
                  </div>

                  <div className="space-y-2 text-xs text-gray-600 my-4 pt-2 border-t border-gray-100">
                    <div className="flex items-center gap-2">
                      <Building2 className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                      <span className="truncate">
                        {departments.find((d) => d.id === staff.department)?.name || "General Administration"}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Mail className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                      <span className="truncate">{staff.email || "No email provided"}</span>
                    </div>

                    {staff.phone_number && (
                      <div className="flex items-center gap-2">
                        <Phone className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                        <span>{staff.phone_number}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div>
                  {staff.skills ? (
                    <div className="pt-3 border-t border-gray-100">
                      <span className="text-[10px] text-gray-400 font-semibold uppercase block mb-1.5">
                        Verified Skills
                      </span>
                      <div className="flex flex-wrap gap-1">
                        {staff.skills.split(",").map((skill: string, idx: number) => (
                          <span
                            key={idx}
                            className="px-2 py-0.5 rounded bg-gray-100 text-gray-700 text-[10px] font-medium"
                          >
                            {skill.trim()}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="pt-3 border-t border-gray-100 text-[10px] text-gray-400 italic">
                      Standard field operative
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}
