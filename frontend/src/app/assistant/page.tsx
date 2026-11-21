"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import { api } from "@/lib/api";
import {
  Send,
  Sparkles,
  Bot,
  User,
  ArrowRight,
  HelpCircle,
  FileText,
  Clock,
  CheckCircle,
  ShieldAlert,
  AlertTriangle,
  RotateCcw
} from "lucide-react";

interface Message {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: string;
  language?: string;
  intent?: string;
  related_complaint?: any;
  suggested_actions?: string[];
  sources?: string[];
  requires_human_support?: boolean;
}

const SUGGESTED_QUESTIONS = [
  "How do I file a civic complaint?",
  "Meri complaint ka status kya hai?",
  "How can I report a water pipeline burst?",
  "What does 'submitted' status mean?",
  "How do I dispute an unresolved complaint?",
  "What photo evidence should I upload?"
];

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome-1",
      sender: "assistant",
      text: "Namaste! I am your JanSahayak Civic Knowledge Assistant. I can help you understand municipal complaint procedures, explain grievance statuses and SLA deadlines, or look up your filed complaints.",
      timestamp: "Just now",
      suggested_actions: ["Ask how to register a complaint", "Check status of your tracking code"],
      sources: ["JanSahayak Civic Operating Guidance"]
    }
  ]);
  const [inputValue, setInputValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState("auto");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputValue).trim();
    if (!text || loading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: text,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    setLoading(true);

    try {
      const res = await api.post("/assistant/chat/", {
        message: text,
        language: selectedLanguage
      });

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        sender: "assistant",
        text: res.data.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        language: res.data.language,
        intent: res.data.intent,
        related_complaint: res.data.related_complaint,
        suggested_actions: res.data.suggested_actions,
        sources: res.data.sources,
        requires_human_support: res.data.requires_human_support
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      const errorMsg =
        err.response?.data?.error ||
        "I encountered a temporary problem contacting civic services. Please try again or visit the /report page directly.";

      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          sender: "assistant",
          text: errorMsg,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          sources: ["System Gateway"]
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([
      {
        id: "welcome-reset",
        sender: "assistant",
        text: "Chat cleared. What civic question can I help you with today?",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        suggested_actions: ["How do I file a complaint?", "Check my complaint status"],
        sources: ["JanSahayak Civic Operating Guidance"]
      }
    ]);
  };

  return (
    <div className="flex flex-col min-h-screen bg-[#FAFAF9]">
      <Navbar />

      <main className="max-w-4xl mx-auto px-4 py-6 w-full flex-1 flex flex-col">
        {/* Header Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4 pb-3 border-b border-gray-200">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#A94D37] to-[#8e3e2b] flex items-center justify-center text-white shadow-md">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-base font-bold text-[#17191D] flex items-center gap-1.5">
                Civic Knowledge & Grievance Assistant
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-mono font-semibold">
                  Multilingual AI
                </span>
              </h1>
              <p className="text-[11px] text-gray-500">
                Ask questions about municipal procedures, SLA targets, or your personal complaint records
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value)}
              className="text-xs border border-gray-300 rounded-lg px-2.5 py-1.5 bg-white text-gray-700 focus:outline-none focus:border-[#A94D37]"
            >
              <option value="auto">Auto Language</option>
              <option value="en">English</option>
              <option value="hi">हिंदी (Hindi)</option>
              <option value="hinglish">Hinglish</option>
            </select>

            <button
              onClick={clearChat}
              className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition"
              title="Reset Chat"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Suggested Question Chips */}
        <div className="mb-4 flex flex-wrap gap-1.5">
          {SUGGESTED_QUESTIONS.map((q, idx) => (
            <button
              key={idx}
              onClick={() => handleSendMessage(q)}
              className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-white hover:bg-amber-50 text-gray-700 hover:text-[#A94D37] border border-gray-200 hover:border-amber-300 transition shadow-sm text-left"
            >
              {q}
            </button>
          ))}
        </div>

        {/* Chat History Box */}
        <div className="flex-1 bg-white rounded-2xl border border-gray-200 shadow-sm p-4 overflow-y-auto min-h-[440px] max-h-[600px] space-y-4">
          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex gap-3 ${m.sender === "user" ? "justify-end" : "justify-start"}`}
            >
              {m.sender === "assistant" && (
                <div className="w-8 h-8 rounded-lg bg-amber-100 text-[#A94D37] flex items-center justify-center shrink-0 mt-0.5">
                  <Bot className="w-4 h-4" />
                </div>
              )}

              <div
                className={`max-w-[85%] sm:max-w-[75%] rounded-2xl p-3.5 text-xs ${
                  m.sender === "user"
                    ? "bg-[#17191D] text-white rounded-tr-none"
                    : "bg-gray-50 border border-gray-200 text-gray-800 rounded-tl-none space-y-2.5"
                }`}
              >
                <p className="whitespace-pre-line leading-relaxed">{m.text}</p>

                {/* Related Complaint Card */}
                {m.related_complaint && (
                  <div className="mt-2.5 p-3 bg-white rounded-xl border border-amber-200 shadow-sm text-[11px] space-y-1.5 text-gray-800">
                    <div className="flex items-center justify-between pb-1 border-b border-gray-100">
                      <span className="font-mono font-bold text-[#A94D37]">
                        {m.related_complaint.tracking_id}
                      </span>
                      <span className="px-2 py-0.5 rounded font-bold uppercase text-[9px] bg-gray-100 text-gray-700">
                        {m.related_complaint.status}
                      </span>
                    </div>
                    <p className="font-semibold">{m.related_complaint.title}</p>
                    <div className="text-[10px] text-gray-500 space-y-0.5">
                      <p>Department: <strong>{m.related_complaint.department}</strong></p>
                      <p>Assigned Staff: <strong>{m.related_complaint.assigned_staff}</strong></p>
                      <p>Filed On: {m.related_complaint.created_at}</p>
                      {m.related_complaint.is_overdue && (
                        <p className="text-red-600 font-bold">⚠️ Flagged Overdue under Municipal SLA</p>
                      )}
                    </div>
                    <div className="pt-1.5 flex justify-end">
                      <Link
                        href="/citizen"
                        className="text-[10px] text-[#A94D37] hover:underline font-bold flex items-center gap-1"
                      >
                        Inspect in Citizen Portal <ArrowRight className="w-3 h-3" />
                      </Link>
                    </div>
                  </div>
                )}

                {/* Suggested Action Buttons */}
                {m.suggested_actions && m.suggested_actions.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-gray-200/60 flex flex-wrap gap-1.5">
                    {m.suggested_actions.map((act, i) => {
                      if (act.includes("/report")) {
                        return (
                          <Link
                            key={i}
                            href="/report"
                            className="px-2.5 py-1 bg-[#A94D37] hover:bg-[#8e3e2b] text-white text-[10px] font-semibold rounded-lg shadow-sm transition inline-flex items-center gap-1"
                          >
                            <FileText className="w-3 h-3" /> File Grievance Now
                          </Link>
                        );
                      }
                      if (act.includes("/citizen")) {
                        return (
                          <Link
                            key={i}
                            href="/citizen"
                            className="px-2.5 py-1 bg-white hover:bg-gray-100 border border-gray-300 text-gray-800 text-[10px] font-semibold rounded-lg shadow-sm transition inline-flex items-center gap-1"
                          >
                            <CheckCircle className="w-3 h-3" /> Open Citizen Portal
                          </Link>
                        );
                      }
                      return (
                        <button
                          key={i}
                          onClick={() => handleSendMessage(act)}
                          className="px-2.5 py-1 bg-white hover:bg-gray-100 border border-gray-300 text-gray-700 text-[10px] font-medium rounded-lg transition"
                        >
                          {act}
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* Sources & Disclaimers */}
                {m.sources && m.sources.length > 0 && (
                  <div className="pt-1 text-[9px] text-gray-400 font-mono">
                    Verified Source: {m.sources.join(", ")}
                  </div>
                )}

                <div
                  className={`text-[9px] mt-1 text-right ${
                    m.sender === "user" ? "text-gray-400" : "text-gray-400"
                  }`}
                >
                  {m.timestamp}
                </div>
              </div>

              {m.sender === "user" && (
                <div className="w-8 h-8 rounded-lg bg-gray-200 text-gray-700 flex items-center justify-center shrink-0 mt-0.5">
                  <User className="w-4 h-4" />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-3 justify-start">
              <div className="w-8 h-8 rounded-lg bg-amber-100 text-[#A94D37] flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 animate-pulse" />
              </div>
              <div className="bg-gray-50 border border-gray-200 rounded-2xl rounded-tl-none p-3.5 text-xs text-gray-500 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[#A94D37] animate-bounce"></span>
                <span className="w-2 h-2 rounded-full bg-[#A94D37] animate-bounce [animation-delay:0.2s]"></span>
                <span className="w-2 h-2 rounded-full bg-[#A94D37] animate-bounce [animation-delay:0.4s]"></span>
                <span className="text-[11px] ml-1">Consulting civic knowledge base...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Message Input Box */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="mt-3 flex items-center gap-2"
        >
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Type your question in English, हिंदी, or Hinglish (e.g. 'Status of JSH-12345678' or 'Kaise report kare?')..."
            className="flex-1 px-4 py-2.5 text-xs bg-white border border-gray-300 rounded-xl focus:outline-none focus:border-[#A94D37] text-gray-800 shadow-sm"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !inputValue.trim()}
            className="px-4 py-2.5 bg-[#A94D37] hover:bg-[#8e3e2b] disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow transition flex items-center gap-1.5 shrink-0"
          >
            <Send className="w-3.5 h-3.5" /> Send
          </button>
        </form>

        <p className="text-[10px] text-gray-400 text-center mt-2">
          JanSahayak AI provides municipal guidance based on verified city codes. For emergency fire or medical assistance, dial national emergency numbers directly.
        </p>
      </main>

      <Footer />
    </div>
  );
}

