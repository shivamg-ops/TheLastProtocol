import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "JANSAHAYAK AI — From Voice to Resolution",
  description: "AI-powered multilingual citizen grievance and municipal resolution platform.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-[#F7F7F5] text-[#17191D]">{children}</body>
    </html>
  );
}
