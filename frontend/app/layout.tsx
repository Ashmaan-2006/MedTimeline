import type { Metadata } from "next";
import { Geist, Geist_Mono, Newsreader } from "next/font/google";

import { Logo } from "@/components/logo";
import { SidebarNav } from "@/components/sidebar-nav";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  display: "swap",
});

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
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${newsreader.variable}`}
    >
      <body>
        <div className="app-shell">
          <header className="site-header">
            <div className="site-header-bar">
              <div className="brand">
                <Logo className="brand-mark" />
                <span className="brand-title">MedGraph</span>
                <span className="brand-subtitle">Clinical timeline workspace</span>
              </div>
              <SidebarNav />
              <span className="topbar-status">MVP workspace</span>
            </div>
          </header>
          <main className="main">
            <div className="content">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
