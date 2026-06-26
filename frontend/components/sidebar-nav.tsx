"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  {
    href: "/",
    label: "Patients",
    match: (pathname: string) => pathname === "/" || pathname.startsWith("/patients"),
  },
  { href: "/", label: "Documents", match: () => false },
  { href: "/", label: "Timeline", match: () => false },
  {
    href: "/admin/evals",
    label: "Evaluations",
    match: (pathname: string) => pathname.startsWith("/admin/evals"),
  },
];

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Primary navigation">
      <span className="nav-section-label">Workspace</span>
      <ul className="nav-list">
        {NAV_ITEMS.map((item) => {
          const isActive = item.match(pathname);
          return (
            <li key={item.label}>
              <Link
                aria-current={isActive ? "page" : undefined}
                className={`nav-item ${isActive ? "nav-item-active" : ""}`}
                href={item.href}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
