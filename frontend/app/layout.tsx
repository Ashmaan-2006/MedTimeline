import type { Metadata } from "next";
import Link from "next/link";

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
              <span className="brand-title">MedGraph AI</span>
              <span className="brand-subtitle">Clinical timeline workspace</span>
            </div>
            <nav>
              <ul className="nav-list">
                <li>
                  <Link className="nav-item nav-item-active" href="/">
                    Patients
                  </Link>
                </li>
                <li>
                  <Link className="nav-item" href="/">
                    Documents
                  </Link>
                </li>
                <li>
                  <Link className="nav-item" href="/">
                    Timeline
                  </Link>
                </li>
              </ul>
            </nav>
          </aside>
          <main className="main">
            <header className="topbar">
              <span className="topbar-title">Patient Intelligence</span>
              <span className="topbar-status">MVP workspace</span>
            </header>
            <div className="content">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
