"use client";

import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
import { Bell, CheckCheck, Clock, FileText } from "lucide-react";
import Link from "next/link";

interface NotificationItem {
  id: number;
  title: string;
  message: string;
  complaint?: number | null;
  is_read: boolean;
  created_at: string;
}

export default function NotificationBell() {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const fetchNotifications = async () => {
    try {
      const token = localStorage.getItem("token");
      if (!token) return;
      const res = await api.get("/notifications/");
      const data: NotificationItem[] = res.data?.results || res.data || [];
      setNotifications(data);
      setUnreadCount(data.filter((n) => !n.is_read).length);
    } catch {
      // silently skip if not logged in
    }
  };

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 20000); // Poll every 20s
    return () => clearInterval(interval);
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const markAllAsRead = async () => {
    try {
      await api.post("/notifications/mark_all_read/");
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.error(err);
    }
  };

  const markSingleAsRead = async (id: number) => {
    try {
      await api.post(`/notifications/${id}/mark_as_read/`);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-gray-300 hover:text-white hover:bg-gray-800 rounded-lg transition"
        title="Notifications"
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 flex h-4 w-4 items-center justify-center rounded-full bg-[#A94D37] text-[9px] font-bold text-white shadow-sm ring-2 ring-[#17191D]">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-white text-gray-900 rounded-xl shadow-2xl border border-gray-200 z-50 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
          <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-[#17191D]">Notifications</span>
              {unreadCount > 0 && (
                <span className="text-[10px] bg-[#A94D37]/10 text-[#A94D37] font-bold px-2 py-0.5 rounded-full">
                  {unreadCount} new
                </span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                onClick={markAllAsRead}
                className="text-[11px] text-[#A94D37] hover:underline flex items-center gap-1 font-medium"
              >
                <CheckCheck className="w-3.5 h-3.5" /> Mark all read
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto divide-y divide-gray-100">
            {notifications.length === 0 ? (
              <div className="py-8 text-center text-xs text-gray-400">
                <Bell className="w-8 h-8 text-gray-300 mx-auto mb-2 stroke-[1.5]" />
                No notifications yet
              </div>
            ) : (
              notifications.map((item) => (
                <div
                  key={item.id}
                  onClick={() => !item.is_read && markSingleAsRead(item.id)}
                  className={`p-3 text-xs transition cursor-pointer hover:bg-gray-50 ${
                    !item.is_read ? "bg-amber-50/40 font-medium" : "text-gray-600"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className={`font-semibold text-xs ${!item.is_read ? "text-[#17191D]" : "text-gray-700"}`}>
                      {item.title}
                    </p>
                    <span className="text-[10px] text-gray-400 shrink-0 flex items-center gap-0.5">
                      <Clock className="w-3 h-3" />
                      {new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                  <p className="text-[11px] text-gray-600 mt-1 leading-snug">{item.message}</p>
                </div>
              ))
            )}
          </div>

          <div className="p-2 bg-gray-50 text-center border-t border-gray-100">
            <span className="text-[11px] text-gray-500">
              Real-time updates delivered to your Gmail &amp; Dashboard
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
