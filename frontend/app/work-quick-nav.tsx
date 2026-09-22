"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function WorkQuickNav() {
  const pathname = usePathname();
  if (pathname.startsWith("/login") || pathname.startsWith("/mfa")) return null;
  if (pathname === "/work") return null;

  return (
    <div
      style={{
        position: "fixed",
        left: 18,
        bottom: 18,
        zIndex: 60,
      }}
    >
      <Link
        href="/work"
        className="primary"
        style={{ display: "inline-block", textDecoration: "none", boxShadow: "0 8px 24px #10243b26" }}
      >
        ☑ کارهای من
      </Link>
    </div>
  );
}
