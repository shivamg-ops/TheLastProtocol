"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { api } from "@/lib/api";
import { Eye, Plus, FileText, Star, CheckCircle, AlertTriangle, XCircle, ArrowRightLeft, Camera } from "lucide-react";

export default function CitizenDashboard() {
  const [complaints, setComplaints] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedComplaint, setSelectedComplaint] = useState<any>(null);
  
  // Feedback & Resolution Verification States (Task 17)
  const [rating, setRating] = useState(5);
  const [feedbackNotes, setFeedbackNotes] = useState("");
  const [satisfaction, setSatisfaction] = useState(true);
  const [isDispute, setIsDispute] = useState(false);
  const [disputeReason, setDisputeReason] = useState("");
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState("");
  const [disputeProofFile, setDisputeProofFile] = useState<File | null>(null);

  useEffect(() => {
    fetchComplaints();
  }, []);

  const fetchComplaints = () => {
    setLoading(true);
    api.get("/complaints/")
      .then((res) => {
        setComplaints(res.data);
        if (selectedComplaint) {
          const updated = res.data.find((c: any) => c.id === selectedComplaint.id);
          if (updated) setSelectedComplaint(updated);
        }
      })
      .catch((err) => console.log(err))
      .finally(() => setLoading(false));
  };

  const handleFeedbackSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedComplaint) return;
    setSubmittingFeedback(true);
    setFeedbackMsg("");

    try {
      // 1. Submit resolution verification / dispute feedback
      await api.post(`/complaints/${selectedComplaint.id}/submit_feedback/`, {
        rating: rating,
        feedback_text: feedbackNotes,
        resolution_satisfaction: satisfaction && !isDispute,
        is_disputed: isDispute,
        dispute_reason: disputeReason,
      });

      // 2. If citizen attached additional dispute proof photo, upload as evidence
      if (isDispute && disputeProofFile) {
        const formData = new FormData();
        formData.append("complaint", selectedComplaint.id);
        formData.append("file", disputeProofFile);
        formData.append("file_type", "image");
        await api.post("/evidence/", formData, {
          headers: { "Content-Type": "multipart/form-data" }
        });
      }

      setFeedbackMsg(
        isDispute
          ? "Dispute logged successfully. The ticket has been flagged for supervisor review."
          : "Resolution confirmed! Thank you for verifying municipal service delivery."
      );
      fetchComplaints();
    } catch (err: any) {
      setFeedbackMsg(err.response?.data?.error || "Failed to submit verification.");
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      submitted: "bg-blue-50 text-blue-700 border-blue-200",
      assigned: "bg-purple-50 text-purple-700 border-purple-200",
      in_progress: "bg-amber-50 text-amber-700 border-amber-200",
      resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
      verified: "bg-teal-50 text-teal-700 border-teal-200",
      escalated: "bg-red-50 text-red-700 border-red-200",
      rejected: "bg-gray-50 text-gray-700 border-gray-200",
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
      <div className="w-full px-3 sm:px-5 lg:px-6 py-6 flex-1">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-bold text-[#17191D]">Citizen Grievance Portal</h1>
            <p className="text-xs text-gray-500 mt-1">Track your filed complaints and resolution verification</p>
          </div>
          <Link
            href="/report"
            className="px-4 py-2 bg-[#DC2626] hover:bg-[#B91C1C] text-white text-xs font-semibold rounded-lg shadow transition flex items-center gap-1.5"
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
                  className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 bg-[#DC2626] text-white text-xs font-semibold rounded-lg"
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
                        <td className="py-3 px-4 font-mono font-bold text-[#DC2626]">
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
                  <div className="font-mono font-bold text-sm text-[#DC2626]">
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

                {/* Before & After Evidence Comparison Section (Task 17) */}
                <div className="pt-3 border-t border-gray-100">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-bold text-gray-700 flex items-center gap-1.5">
                      <ArrowRightLeft className="w-3.5 h-3.5 text-[#DC2626]" /> Resolution Verification Evidence
                    </h4>
                    <span className="text-[10px] text-gray-400 font-mono">Before vs After Comparison</span>
                  </div>

                  {(() => {
                    const beforeEvidence = selectedComplaint.evidences?.find((ev: any) => !ev.is_resolution_proof && ev.file_type === "image");
                    const afterEvidence = selectedComplaint.evidences?.find((ev: any) => ev.is_resolution_proof && ev.file_type === "image");

                    return (
                      <div className="grid grid-cols-2 gap-3 mb-3">
                        {/* Before Evidence */}
                        <div className="border border-gray-200 rounded-xl overflow-hidden bg-gray-50 flex flex-col">
                          <div className="p-1.5 bg-gray-100 border-b border-gray-200 flex items-center justify-between">
                            <span className="text-[10px] font-bold text-gray-700 uppercase tracking-wider">Before (Reported)</span>
                            <span className="text-[9px] px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 font-medium">Citizen</span>
                          </div>
                          {beforeEvidence ? (
                            <img
                              src={beforeEvidence.file.startsWith("http") ? beforeEvidence.file : `http://127.0.0.1:8000${beforeEvidence.file}`}
                              alt="Before Complaint Evidence"
                              className="w-full h-28 object-cover cursor-pointer hover:opacity-90 transition"
                              onClick={() => window.open(beforeEvidence.file.startsWith("http") ? beforeEvidence.file : `http://127.0.0.1:8000${beforeEvidence.file}`, "_blank")}
                            />
                          ) : (
                            <div className="h-28 flex flex-col items-center justify-center p-3 text-center bg-gray-50">
                              <Camera className="w-5 h-5 text-gray-300 mb-1" />
                              <span className="text-[10px] text-gray-400">Original evidence photo unavailable</span>
                            </div>
                          )}
                          <div className="p-1.5 text-[10px] text-gray-500 bg-white border-t border-gray-100">
                            {beforeEvidence ? `Uploaded by ${beforeEvidence.uploaded_by_name || "Citizen"}` : "No initial photo filed"}
                          </div>
                        </div>

                        {/* After Evidence */}
                        <div className="border border-emerald-200 rounded-xl overflow-hidden bg-emerald-50/30 flex flex-col">
                          <div className="p-1.5 bg-emerald-100/60 border-b border-emerald-200 flex items-center justify-between">
                            <span className="text-[10px] font-bold text-emerald-900 uppercase tracking-wider">After (Resolution)</span>
                            <span className="text-[9px] px-1.5 py-0.2 rounded bg-emerald-200 text-emerald-900 font-medium">Staff Proof</span>
                          </div>
                          {afterEvidence ? (
                            <img
                              src={afterEvidence.file.startsWith("http") ? afterEvidence.file : `http://127.0.0.1:8000${afterEvidence.file}`}
                              alt="After Resolution Proof"
                              className="w-full h-28 object-cover cursor-pointer hover:opacity-90 transition"
                              onClick={() => window.open(afterEvidence.file.startsWith("http") ? afterEvidence.file : `http://127.0.0.1:8000${afterEvidence.file}`, "_blank")}
                            />
                          ) : (
                            <div className="h-28 flex flex-col items-center justify-center p-3 text-center bg-gray-50">
                              <Camera className="w-5 h-5 text-gray-300 mb-1" />
                              <span className="text-[10px] text-amber-700 font-medium">Resolution proof photo unavailable</span>
                            </div>
                          )}
                          <div className="p-1.5 text-[10px] text-gray-500 bg-white border-t border-emerald-100">
                            {afterEvidence ? `Proof by ${afterEvidence.uploaded_by_name || "Field Officer"}` : "Staff did not upload photo"}
                          </div>
                        </div>
                      </div>
                    );
                  })()}
                </div>

                {/* Citizen Resolution Verification & Rating Section (Task 17) */}
                {(selectedComplaint.status === "resolved" || selectedComplaint.status === "verified" || selectedComplaint.resolution_verification_status === "citizen_disputed") && (
                  <div className="pt-3 border-t border-gray-100">
                    <h4 className="font-bold text-gray-700 mb-2 flex items-center gap-1.5">
                      <Star className="w-3.5 h-3.5 text-amber-500 fill-amber-500" /> Citizen Trust & Verification
                    </h4>

                    {selectedComplaint.feedback ? (
                      <div className={`p-3 rounded-lg border ${selectedComplaint.feedback.is_disputed ? "bg-red-50 border-red-200 text-red-900" : "bg-emerald-50 border-emerald-200 text-emerald-900"}`}>
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-1">
                            {[1, 2, 3, 4, 5].map((star) => (
                              <Star
                                key={star}
                                className={`w-3.5 h-3.5 ${
                                  star <= selectedComplaint.feedback.rating
                                    ? "text-amber-500 fill-amber-500"
                                    : "text-gray-300"
                                }`}
                              />
                            ))}
                            <span className="font-bold text-xs ml-1">
                              {selectedComplaint.feedback.rating}/5 Stars
                            </span>
                          </div>
                          <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${selectedComplaint.feedback.is_disputed ? "bg-red-200 text-red-800" : "bg-emerald-200 text-emerald-800"}`}>
                            {selectedComplaint.feedback.is_disputed ? "Disputed by Citizen" : "Verified & Confirmed"}
                          </span>
                        </div>

                        {selectedComplaint.feedback.feedback_text && (
                          <p className="text-[11px] text-gray-700 mt-1 italic">
                            &ldquo;{selectedComplaint.feedback.feedback_text}&rdquo;
                          </p>
                        )}

                        {selectedComplaint.feedback.dispute_reason && (
                          <div className="mt-2 p-2 bg-white rounded border border-red-100 text-[11px] text-red-800">
                            <strong>Dispute Reason:</strong> {selectedComplaint.feedback.dispute_reason}
                          </div>
                        )}
                      </div>
                    ) : (
                      <form onSubmit={handleFeedbackSubmit} className="space-y-3 bg-gray-50 p-3 rounded-xl border border-gray-200">
                        {feedbackMsg && (
                          <div className="p-2 bg-blue-50 border border-blue-200 rounded text-[11px] text-blue-800">
                            {feedbackMsg}
                          </div>
                        )}

                        {/* Action Choice: Confirm or Dispute */}
                        <div>
                          <label className="block text-[11px] font-semibold text-gray-700 mb-1.5">
                            Did the municipal authority resolve your grievance?
                          </label>
                          <div className="grid grid-cols-2 gap-2">
                            <button
                              type="button"
                              onClick={() => { setIsDispute(false); setSatisfaction(true); }}
                              className={`p-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 border transition ${
                                !isDispute
                                  ? "bg-emerald-600 text-white border-emerald-600 shadow-sm"
                                  : "bg-white text-gray-700 border-gray-300 hover:bg-gray-100"
                              }`}
                            >
                              <CheckCircle className="w-3.5 h-3.5" /> Yes, Confirmed
                            </button>
                            <button
                              type="button"
                              onClick={() => { setIsDispute(true); setSatisfaction(false); }}
                              className={`p-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 border transition ${
                                isDispute
                                  ? "bg-red-600 text-white border-red-600 shadow-sm"
                                  : "bg-white text-gray-700 border-gray-300 hover:bg-gray-100"
                              }`}
                            >
                              <XCircle className="w-3.5 h-3.5" /> No, Dispute Work
                            </button>
                          </div>
                        </div>

                        {/* Star Rating */}
                        <div>
                          <label className="block text-[11px] font-semibold text-gray-700 mb-1">
                            {isDispute ? "Dissatisfaction Rating" : "Rate Resolution Quality"}
                          </label>
                          <div className="flex items-center gap-2">
                            {[1, 2, 3, 4, 5].map((s) => (
                              <button
                                key={s}
                                type="button"
                                onClick={() => setRating(s)}
                                className="p-1 focus:outline-none"
                              >
                                <Star
                                  className={`w-5 h-5 ${
                                    s <= rating
                                      ? "text-amber-500 fill-amber-500"
                                      : "text-gray-300"
                                  }`}
                                />
                              </button>
                            ))}
                            <span className="text-xs font-bold text-gray-700 ml-1">{rating} Stars</span>
                          </div>
                        </div>

                        {/* If Disputing, show Dispute Reason & Photo Upload */}
                        {isDispute ? (
                          <>
                            <div>
                              <label className="block text-[11px] font-semibold text-red-700 mb-1">
                                Why is this resolution incomplete or incorrect? *
                              </label>
                              <textarea
                                rows={2}
                                required
                                placeholder="Explain what is still broken or unresolved (e.g., 'Only half the garbage was cleared', 'Pothole still open')."
                                value={disputeReason}
                                onChange={(e) => setDisputeReason(e.target.value)}
                                className="w-full px-2.5 py-1.5 text-xs border border-red-300 rounded-lg focus:outline-none focus:border-red-500 bg-white"
                              />
                            </div>
                            <div>
                              <label className="block text-[11px] font-semibold text-gray-700 mb-1">
                                Attach Photo Proof of Unresolved Issue (Optional)
                              </label>
                              <input
                                type="file"
                                accept="image/*"
                                onChange={(e) => setDisputeProofFile(e.target.files ? e.target.files[0] : null)}
                                className="w-full text-[11px] text-gray-500 file:mr-2 file:py-1 file:px-2 file:rounded file:border-0 file:text-[10px] file:font-semibold file:bg-gray-200 file:text-gray-700 hover:file:bg-gray-300"
                              />
                            </div>
                          </>
                        ) : (
                          <div>
                            <label className="block text-[11px] font-semibold text-gray-700 mb-1">Feedback Comments (Optional)</label>
                            <textarea
                              rows={2}
                              placeholder="Was the issue resolved satisfactorily? e.g. 'Pothole filled and road leveled nicely.'"
                              value={feedbackNotes}
                              onChange={(e) => setFeedbackNotes(e.target.value)}
                              className="w-full px-2.5 py-1.5 text-xs border border-gray-300 rounded-lg focus:outline-none focus:border-[#DC2626] bg-white"
                            />
                          </div>
                        )}

                        <button
                          type="submit"
                          disabled={submittingFeedback}
                          className={`w-full py-2 text-white text-xs font-semibold rounded-lg shadow transition flex items-center justify-center gap-1.5 ${
                            isDispute
                              ? "bg-red-600 hover:bg-red-700"
                              : "bg-[#25845B] hover:bg-emerald-700"
                          }`}
                        >
                          {submittingFeedback ? (
                            "Submitting..."
                          ) : isDispute ? (
                            <>
                              <AlertTriangle className="w-3.5 h-3.5" /> Submit Dispute & Request Review
                            </>
                          ) : (
                            <>
                              <CheckCircle className="w-3.5 h-3.5" /> Confirm Resolution & Submit
                            </>
                          )}
                        </button>
                      </form>
                    )}
                  </div>
                )}

                {/* Timeline */}
                <div className="pt-3 border-t border-gray-100">
                  <h4 className="font-bold text-gray-700 mb-2">Audit History</h4>
                  <div className="space-y-3">
                    {selectedComplaint.timeline && selectedComplaint.timeline.length > 0 ? (
                      selectedComplaint.timeline.map((tl: any, i: number) => (
                        <div key={i} className="flex gap-2.5 items-start">
                          <div className="w-2 h-2 rounded-full bg-[#DC2626] mt-1 shrink-0"></div>
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
