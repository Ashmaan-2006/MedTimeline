import type { Metadata } from "next";

import { SidebarNav } from "@/components/sidebar-nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "MedGraph AI",
  description: "Clinical timeline intelligence workspace for longitudinal patient records.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <aside className="sidebar" aria-label="Primary navigation">
            <div className="brand">
              <span className="brand-mark">MG</span>
              <span className="brand-title">MedGraph AI</span>
              <span className="brand-subtitle">Clinical timeline workspace</span>
            </div>
            <SidebarNav />
          </aside>
          <main className="main">
            <header className="topbar">
              <div>
                <span className="topbar-title">Patient Intelligence</span>
                <span className="topbar-subtitle">Timeline, retrieval, and cited clinical summaries</span>
              </div>
              <span className="topbar-status">MVP workspace</span>
            </header>
            <div className="content">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
