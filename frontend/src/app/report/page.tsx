"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { api } from "@/lib/api";
import {
  Mic,
  MicOff,
  Send,
  Camera,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  RotateCcw,
  User,
  Bot,
  HelpCircle,
} from "lucide-react";

interface ChatMessage {
  id: string;
  sender: "user" | "ai";
  text: string;
  time: string;
  imagePreview?: string;
  diagnosis?: any;
}

export default function InteractiveChatReportPage() {
  const router = useRouter();

  // Multi-turn conversation messages
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [hasUsedVoice, setHasUsedVoice] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [attachedEvidenceFile, setAttachedEvidenceFile] = useState<File | null>(null);
  const [evidencePreview, setEvidencePreview] = useState<string | null>(null);

  // Active AI Diagnostic state & Editable Draft
  const [currentDiagnosis, setCurrentDiagnosis] = useState<any>(null);
  const [categories, setCategories] = useState<any[]>([]);

  const [selectedLanguage, setSelectedLanguage] = useState<string>("hi-IN"); // hi-IN, mr-IN, en-IN
  const [confirmedByCitizen, setConfirmedByCitizen] = useState<boolean>(false);

  // Draft Confirmation Form States
  const [draftTitle, setDraftTitle] = useState("");
  const [draftDescription, setDraftDescription] = useState("");
  const [draftCategory, setDraftCategory] = useState<any>("");
  const [draftPriority, setDraftPriority] = useState("medium");
  const [draftAddress, setDraftAddress] = useState("");
  const [draftWard, setDraftWard] = useState("");
  const [draftDuration, setDraftDuration] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [evidenceStatus, setEvidenceStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [successTicket, setSuccessTicket] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);

  // Initial welcome greeting
  useEffect(() => {
    api
      .get("/categories/")
      .then((res) => setCategories(res.data))
      .catch((err) => console.log(err));

    setMessages([
      {
        id: "msg-0",
        sender: "ai",
        text: "Namaste! Main JanSahayak AI hoon. Aap apni nagrik samasya (Garbage, Road Pothole, Water leakage, Streetlight, Sewage) bolkar (Hindi/Marathi/English) ya likhkar bata sakte hain. Sath hi photo bhi upload kar sakte hain.",
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // ignore
        }
      }
    };
  }, []);

  // Auto-scroll chat to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, analyzing]);

  // Handle Photo selection
  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedImage(file);
      setAttachedEvidenceFile(file);
      const url = URL.createObjectURL(file);
      setImagePreviewUrl(url);
      setEvidencePreview(url);
    }
  };

  // Robust Multilingual Web Speech API Implementation
  const toggleVoiceRecording = () => {
    setSpeechError(null);

    // If currently listening, manually stop
    if (isListening) {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // ignore
        }
      }
      setIsListening(false);
      return;
    }

    if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
      setSpeechError("Speech recognition is not supported in this browser. Please use Google Chrome or Edge.");
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    const recognition = new SpeechRecognition();
    recognition.continuous = true; // KEEP RECORDING until user stops or finishes speaking
    recognition.interimResults = true; // Show live interim words as they speak
    recognition.maxAlternatives = 1;
    recognition.lang = selectedLanguage; // Configurable: Hindi (hi-IN), Marathi (mr-IN), or English/Hinglish (en-IN)

    let finalTranscript = "";

    recognition.onstart = () => {
      setIsListening(true);
      setSpeechError(null);
    };

    recognition.onresult = (event: any) => {
      let interimTranscript = "";
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const transcriptPart = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcriptPart + " ";
        } else {
          interimTranscript += transcriptPart;
        }
      }

      const activeText = finalTranscript + interimTranscript;
      if (activeText.trim()) {
        setInputText(activeText);
        setHasUsedVoice(true);
      }
    };

    recognition.onerror = (event: any) => {
      console.warn("Speech recognition error:", event.error);
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setSpeechError("Microphone permission denied. Please allow microphone access in your browser address bar.");
      } else if (event.error === "no-speech") {
        // Just brief silence, don't crash
      } else {
        setSpeechError(`Voice input error: ${event.error}`);
      }
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    try {
      recognition.start();
      recognitionRef.current = recognition;
    } catch (err: any) {
      console.error("Recognition start failed:", err);
      setIsListening(false);
    }
  };

  // Send message to AI Assistant
  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();

    // If recording is active, stop it before sending
    if (isListening && recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
      setIsListening(false);
    }

    const textToSend = inputText.trim();
    if (!textToSend && !selectedImage) return;

    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      sender: "user",
      text: textToSend || "(Uploaded Photo Evidence)",
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      imagePreview: imagePreviewUrl || undefined,
    };

    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInputText("");
    setSelectedImage(null);
    setImagePreviewUrl(null);
    setAnalyzing(true);

    try {
      const conversationHistory = newMessages.map((m) => ({
        sender: m.sender,
        text: m.text,
      }));

      const res = await api.post("/ai/process_text/", {
        text: textToSend || "Uploaded photo of civic grievance",
        history: conversationHistory,
      });

      const diagnosis = res.data;
      setCurrentDiagnosis(diagnosis);

      // Populate draft fields
      if (diagnosis.title) setDraftTitle(diagnosis.title);
      if (diagnosis.summary) setDraftDescription(diagnosis.summary);
      if (diagnosis.priority) setDraftPriority(diagnosis.priority);
      if (diagnosis.matched_category_id) {
        setDraftCategory(diagnosis.matched_category_id);
      } else if (categories.length > 0) {
        setDraftCategory(categories[0].id);
      }
      if (diagnosis.location_extracted) setDraftAddress(diagnosis.location_extracted);
      if (diagnosis.ward_extracted) setDraftWard(diagnosis.ward_extracted);
      if (diagnosis.duration_extracted) setDraftDuration(diagnosis.duration_extracted);

      const aiReplyMsg: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        sender: "ai",
        text: diagnosis.assistant_reply || "Maine aapki samasya note kar li hai.",
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        diagnosis: diagnosis,
      };

      setMessages((prev) => [...prev, aiReplyMsg]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-err-${Date.now()}`,
          sender: "ai",
          text: "Maaf kijiye, server connect karne me samasya aayi. Kripya punah prayas karein.",
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleResetChat = () => {
    if (isListening && recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
      setIsListening(false);
    }
    setCurrentDiagnosis(null);
    setInputText("");
    setSelectedImage(null);
    setImagePreviewUrl(null);
    setSuccessTicket(null);
    setMessages([
      {
        id: "msg-0",
        sender: "ai",
        text: "Chat reset kar di gayi hai. Aap nayi samasya bata sakte hain.",
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);
  };

  const handleSubmitComplaint = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = localStorage.getItem("token");
    if (!token) {
      alert("Please sign in or use demo login to register complaint.");
      router.push("/login");
      return;
    }

    // Task 16: Require explicit citizen confirmation before submitting
    if (!confirmedByCitizen) {
      alert("Please check the confirmation box to verify that your complaint draft details are accurate.");
      return;
    }

    // Task 7: Enforce ready_to_submit check before complaint creation
    if (currentDiagnosis && currentDiagnosis.ready_to_submit === false) {
      const clarifyText = currentDiagnosis.clarification_question ||
        (currentDiagnosis.missing_information && currentDiagnosis.missing_information.length > 0
          ? `Please provide: ${currentDiagnosis.missing_information.join(", ")}`
          : "Complaint cannot be submitted yet as essential location or grievance details are missing.");
      alert(`Cannot submit complaint yet:\n${clarifyText}`);
      return;
    }

    if (!draftAddress || draftAddress.trim().length < 3 || draftAddress.toLowerCase() === "reported location") {
      alert("Please specify the exact street, landmark, or location before submitting.");
      return;
    }

    setSubmitting(true);
    setEvidenceStatus("idle");
    try {
      const payload = {
        title: draftTitle,
        description: draftDescription,
        category: draftCategory,
        priority: draftPriority,
        address: draftAddress.trim(),
        ward_or_zone: draftWard,
        duration_of_issue: draftDuration,
        detected_language: currentDiagnosis?.detected_language || "en",
        original_input_mode: hasUsedVoice ? "voice" : "text",
      };

      const res = await api.post("/complaints/", payload);
      const createdComplaint = res.data;

      // Upload evidence file if attached
      if (attachedEvidenceFile && createdComplaint?.id) {
        setEvidenceStatus("uploading");
        try {
          const fileExt = attachedEvidenceFile.name.split(".").pop()?.toLowerCase() || "";
          let fileType = "document";
          if (["jpg", "jpeg", "png", "webp"].includes(fileExt)) {
            fileType = "image";
          } else if (["mp4", "mov", "avi"].includes(fileExt)) {
            fileType = "video";
          } else if (["mp3", "wav", "ogg", "m4a"].includes(fileExt)) {
            fileType = "audio";
          }

          const formData = new FormData();
          formData.append("complaint", createdComplaint.id);
          formData.append("file", attachedEvidenceFile);
          formData.append("file_type", fileType);

          await api.post("/evidence/", formData, {
            headers: {
              "Content-Type": "multipart/form-data",
            },
          });
          setEvidenceStatus("success");
        } catch (uploadErr) {
          console.error("Evidence upload failed:", uploadErr);
          setEvidenceStatus("error");
        }
      }

      setSuccessTicket(createdComplaint.tracking_id);
    } catch (err) {
      console.error(err);
      alert("Failed to submit complaint. Ensure backend is running and you are logged in.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-[#F7F7F5]">
      <Navbar />

      <main className="w-full px-3 sm:px-5 lg:px-6 py-6 flex-1">
        {/* Header Bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#DC2626]/10 text-xs font-bold text-[#DC2626] uppercase">
              <Sparkles className="w-3.5 h-3.5" /> AI Multilingual Civic Assistant
            </div>
            <h1 className="text-2xl font-bold text-[#17191D] mt-1">Interactive Voice & Chat Assistant</h1>
            <p className="text-xs text-gray-500">
              Speak or chat naturally in Hindi, Marathi, Hinglish, or English with photo evidence.
            </p>
          </div>

          <button
            onClick={handleResetChat}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-gray-100 border border-gray-200 text-xs font-semibold text-gray-700 rounded-lg shadow-sm transition"
          >
            <RotateCcw className="w-3.5 h-3.5" /> New Conversation
          </button>
        </div>

        {speechError && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 text-red-600" />
            <span>{speechError}</span>
          </div>
        )}

        {successTicket ? (
          <div className="bg-white p-8 rounded-2xl border border-green-200 shadow-xl text-center max-w-xl mx-auto">
            <div className="w-16 h-16 bg-green-100 text-[#25845B] rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <h2 className="text-2xl font-bold text-[#17191D]">Ticket Successfully Created!</h2>
            <p className="text-gray-600 text-sm mt-2">Your municipal tracking ticket ID is:</p>
            <div className="my-4 inline-block bg-gray-100 border border-gray-300 px-6 py-2.5 rounded-lg text-lg font-mono font-bold text-[#DC2626]">
              {successTicket}
            </div>

            {evidenceStatus === "success" && (
              <div className="mb-4 p-2.5 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-center justify-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-[#25845B]" />
                <span>Photo evidence securely uploaded and linked to ticket.</span>
              </div>
            )}

            {evidenceStatus === "error" && (
              <div className="mb-4 p-2.5 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 flex items-center justify-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                <span>Complaint registered, but photo evidence upload encountered a network issue.</span>
              </div>
            )}
            <p className="text-xs text-gray-500 max-w-md mx-auto mb-6">
              The ticket is assigned to the respective department with SLA tracking. You can monitor live field updates in your Citizen Portal.
            </p>
            <div className="flex justify-center gap-4">
              <button
                onClick={handleResetChat}
                className="px-5 py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-800 text-xs font-medium rounded-lg"
              >
                Report Another Problem
              </button>
              <button
                onClick={() => router.push("/citizen")}
                className="px-5 py-2.5 bg-[#DC2626] hover:bg-[#B91C1C] text-white text-xs font-medium rounded-lg shadow"
              >
                Go to Citizen Dashboard
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left 7 Columns: Chat Window */}
            <div className="lg:col-span-7 flex flex-col bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden h-[620px]">
              {/* Chat Status Header */}
              <div className="p-3.5 px-5 bg-[#17191D] text-white flex items-center justify-between border-b border-gray-800">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-[#DC2626] flex items-center justify-center font-bold text-white text-xs">
                    JS
                  </div>
                  <div>
                    <h3 className="text-xs font-bold leading-tight">JanSahayak Citizen Assistant</h3>
                    <div className="flex items-center gap-1.5 text-[10px] text-gray-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#25845B]"></span> Online • Multilingual (HI/MR/EN)
                    </div>
                  </div>
                </div>

                {currentDiagnosis?.detected_language && (
                  <span className="text-[10px] bg-gray-800 border border-gray-700 px-2 py-0.5 rounded text-[#DC2626] font-bold uppercase">
                    Lang: {currentDiagnosis.detected_language}
                  </span>
                )}
              </div>

              {/* Message Feed */}
              <div className="flex-1 p-4 overflow-y-auto space-y-4 bg-[#F7F7F5]">
                {messages.map((m) => (
                  <div
                    key={m.id}
                    className={`flex gap-2.5 max-w-[85%] ${
                      m.sender === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
                    }`}
                  >
                    <div
                      className={`w-7 h-7 rounded-full flex items-center justify-center text-xs shrink-0 ${
                        m.sender === "user" ? "bg-[#17191D] text-white" : "bg-[#DC2626] text-white"
                      }`}
                    >
                      {m.sender === "user" ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
                    </div>

                    <div>
                      <div
                        className={`p-3.5 rounded-2xl text-xs leading-relaxed shadow-sm ${
                          m.sender === "user"
                            ? "bg-[#17191D] text-white rounded-tr-none"
                            : "bg-white text-gray-800 border border-gray-200 rounded-tl-none"
                        }`}
                      >
                        {m.imagePreview && (
                          <div className="mb-2 rounded-lg overflow-hidden border border-gray-700">
                            <img src={m.imagePreview} alt="Uploaded evidence" className="max-h-48 w-full object-cover" />
                          </div>
                        )}
                        <p className="whitespace-pre-wrap">{m.text}</p>
                      </div>
                      <span className="text-[10px] text-gray-400 mt-1 block px-1">{m.time}</span>
                    </div>
                  </div>
                ))}

                {analyzing && (
                  <div className="flex gap-2.5 mr-auto max-w-[80%] items-center">
                    <div className="w-7 h-7 rounded-full bg-[#DC2626] text-white flex items-center justify-center text-xs">
                      <Bot className="w-3.5 h-3.5" />
                    </div>
                    <div className="p-3 bg-white border border-gray-200 rounded-2xl rounded-tl-none text-xs text-gray-500 flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-[#DC2626] animate-ping"></span>
                      AI is analyzing grievance & extracting location...
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Image Preview Bar if chosen */}
              {imagePreviewUrl && (
                <div className="p-2 px-4 bg-gray-50 border-t border-gray-200 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <img src={imagePreviewUrl} alt="Preview" className="w-8 h-8 rounded object-cover border" />
                    <span className="text-gray-600 truncate max-w-xs">{selectedImage?.name}</span>
                  </div>
                  <button
                    onClick={() => {
                      setSelectedImage(null);
                      setImagePreviewUrl(null);
                    }}
                    className="text-red-500 hover:text-red-700 text-xs font-semibold"
                  >
                    Remove
                  </button>
                </div>
              )}

              {/* Live Speech Recognition Banner when active */}
              {isListening && (
                <div className="px-4 py-2 bg-red-50 border-t border-red-200 flex items-center justify-between text-xs text-red-700">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-600 animate-ping"></span>
                    <span className="font-semibold">Microphone Live — Speak in Hindi, Marathi or English...</span>
                  </div>
                  <button
                    type="button"
                    onClick={toggleVoiceRecording}
                    className="px-2 py-0.5 bg-red-600 text-white rounded text-[11px] font-bold"
                  >
                    Done Speaking
                  </button>
                </div>
              )}

              {/* Chat Input Controls */}
              <form onSubmit={handleSendMessage} className="p-3 bg-white border-t border-gray-200 flex items-center gap-2">
                <input
                  type="file"
                  accept="image/*,video/*"
                  ref={fileInputRef}
                  onChange={handleImageChange}
                  className="hidden"
                />

                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="p-2 text-gray-500 hover:text-[#DC2626] hover:bg-gray-100 rounded-lg transition"
                  title="Upload Photo / Video Evidence"
                >
                  <Camera className="w-5 h-5" />
                </button>

                {/* Speech Input Language Selector */}
                <select
                  value={selectedLanguage}
                  onChange={(e) => setSelectedLanguage(e.target.value)}
                  className="px-1.5 py-1 text-[11px] font-semibold bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded-lg text-gray-700 focus:outline-none focus:border-[#DC2626]"
                  title="Select voice recognition language"
                >
                  <option value="hi-IN">हिन्दी / Hinglish</option>
                  <option value="mr-IN">मराठी (Marathi)</option>
                  <option value="en-IN">English (India)</option>
                </select>

                <button
                  type="button"
                  onClick={toggleVoiceRecording}
                  className={`p-2.5 rounded-xl transition ${
                    isListening
                      ? "bg-red-500 text-white shadow-lg animate-pulse"
                      : "text-gray-600 hover:text-[#DC2626] hover:bg-gray-100"
                  }`}
                  title={isListening ? "Stop Recording" : `Record Speech (${selectedLanguage})`}
                >
                  {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                </button>

                <input
                  type="text"
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  placeholder={
                    isListening
                      ? "Listening to voice input... speak clearly..."
                      : "Type problem or speak via mic (e.g. 'Hamare gali me kachra pada hai')..."
                  }
                  className="flex-1 px-3.5 py-2.5 text-xs bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:border-[#DC2626] focus:bg-white"
                />

                <button
                  type="submit"
                  disabled={analyzing || (!inputText.trim() && !selectedImage)}
                  className="p-2.5 bg-[#DC2626] hover:bg-[#B91C1C] text-white rounded-xl shadow transition disabled:opacity-50"
                >
                  <Send className="w-4 h-4" />
                </button>
              </form>
            </div>

            {/* Right 5 Columns: AI Diagnostic & Live Confirmation Card */}
            <div className="lg:col-span-5 flex flex-col gap-4">
              {currentDiagnosis ? (
                <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm">
                  <div className="flex items-center justify-between pb-3 border-b border-gray-100">
                    <h3 className="text-sm font-bold text-[#17191D] flex items-center gap-1.5">
                      <Sparkles className="w-4 h-4 text-[#DC2626]" /> Structured Complaint Preview
                    </h3>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                        currentDiagnosis.priority === "urgent"
                          ? "bg-red-100 text-red-700"
                          : "bg-blue-100 text-blue-700"
                      }`}
                    >
                      {draftPriority}
                    </span>
                  </div>

                    {/* Clarification / Missing Info Alert */}
                    {currentDiagnosis.ready_to_submit === false && (
                      <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900 flex items-start gap-2">
                        <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                        <div>
                          <strong className="block font-semibold">Missing Essential Details Before Submission:</strong>
                          {currentDiagnosis.clarification_question && (
                            <p className="mt-1 text-amber-800 italic">"{currentDiagnosis.clarification_question}"</p>
                          )}
                          {currentDiagnosis.missing_information && currentDiagnosis.missing_information.length > 0 && (
                            <ul className="list-disc ml-4 mt-1 space-y-0.5 text-[11px] text-amber-700">
                              {currentDiagnosis.missing_information.map((item: string, idx: number) => (
                                <li key={idx}>{item}</li>
                              ))}
                            </ul>
                          )}
                          <p className="mt-2 text-[10px] text-amber-600">
                            Please type or speak the missing details on the left, or edit the address field directly below.
                          </p>
                        </div>
                      </div>
                    )}

                  {/* Editable Review Form */}
                  <form onSubmit={handleSubmitComplaint} className="mt-4 space-y-3 text-xs">
                    <div>
                      <label className="block text-[11px] font-semibold text-gray-700 mb-1">Title</label>
                      <input
                        type="text"
                        required
                        value={draftTitle}
                        onChange={(e) => setDraftTitle(e.target.value)}
                        className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:border-[#DC2626]"
                      />
                    </div>

                    <div>
                      <label className="block text-[11px] font-semibold text-gray-700 mb-1">Problem Summary</label>
                      <textarea
                        rows={2}
                        required
                        value={draftDescription}
                        onChange={(e) => setDraftDescription(e.target.value)}
                        className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:border-[#DC2626]"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[11px] font-semibold text-gray-700 mb-1">Category</label>
                        <select
                          value={draftCategory}
                          onChange={(e) => setDraftCategory(e.target.value)}
                          className="w-full px-2 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:border-[#DC2626]"
                        >
                          {categories.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-[11px] font-semibold text-gray-700 mb-1">Priority</label>
                        <select
                          value={draftPriority}
                          onChange={(e) => setDraftPriority(e.target.value)}
                          className="w-full px-2 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:border-[#DC2626]"
                        >
                          <option value="low">Low</option>
                          <option value="medium">Medium</option>
                          <option value="high">High</option>
                          <option value="urgent">Urgent</option>
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="block text-[11px] font-semibold text-gray-700 mb-1">
                        Exact Location / Landmark *
                      </label>
                      <input
                        type="text"
                        required
                        placeholder="e.g. Near Shiv Mandir, Main Road"
                        value={draftAddress}
                        onChange={(e) => setDraftAddress(e.target.value)}
                        className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:border-[#DC2626]"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[11px] font-semibold text-gray-700 mb-1">Ward / Zone</label>
                        <input
                          type="text"
                          placeholder="e.g. Ward 12"
                          value={draftWard}
                          onChange={(e) => setDraftWard(e.target.value)}
                          className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:border-[#DC2626]"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-semibold text-gray-700 mb-1">Duration</label>
                        <input
                          type="text"
                          placeholder="e.g. 3 days"
                          value={draftDuration}
                          onChange={(e) => setDraftDuration(e.target.value)}
                          className="w-full px-2.5 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:border-[#DC2626]"
                        />
                      </div>
                    </div>

                    {evidencePreview && (
                      <div className="p-2.5 bg-gray-50 border border-gray-200 rounded-lg flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <img src={evidencePreview} alt="Attached" className="w-9 h-9 rounded object-cover border border-gray-300" />
                          <div>
                            <span className="text-[11px] font-semibold text-gray-800 block">Photo Evidence Attached</span>
                            <span className="text-[10px] text-gray-500">Will be uploaded with ticket</span>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            setAttachedEvidenceFile(null);
                            setEvidencePreview(null);
                          }}
                          className="text-[10px] text-red-600 font-bold hover:underline"
                        >
                          Remove
                        </button>
                      </div>
                    )}

                    {/* Explicit Citizen Confirmation Checkbox (Requirement 6) */}
                    <div className="pt-2 border-t border-gray-100">
                      <label className="flex items-start gap-2 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={confirmedByCitizen}
                          onChange={(e) => setConfirmedByCitizen(e.target.checked)}
                          className="mt-0.5 rounded border-gray-300 text-[#DC2626] focus:ring-[#DC2626]"
                        />
                        <span className="text-[11px] text-gray-700 leading-tight">
                          I have verified that the problem description and location are accurate, and I confirm the submission of this complaint.
                        </span>
                      </label>
                    </div>

                    <button
                      type="submit"
                      disabled={submitting || !confirmedByCitizen}
                      className="w-full py-2.5 bg-[#DC2626] hover:bg-[#B91C1C] disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-medium text-xs rounded-xl shadow transition flex items-center justify-center gap-1.5 mt-2"
                    >
                      {submitting ? "Submitting Ticket & Uploading Evidence..." : "Confirm & Submit Complaint"} <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </form>
                </div>
              ) : (
                <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm text-center text-xs text-gray-500 flex flex-col items-center justify-center h-full min-h-[300px]">
                  <HelpCircle className="w-10 h-10 text-gray-300 mb-2" />
                  <h4 className="font-bold text-gray-700 text-sm">Complaint Draft Preview</h4>
                  <p className="max-w-xs mt-1 text-[11px] text-gray-400">
                    Start chatting or speak on the left. The AI will extract the category, ward, and urgency, and present an editable ticket here for your final confirmation.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
}
