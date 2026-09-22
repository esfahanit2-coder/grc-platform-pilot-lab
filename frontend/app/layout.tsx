import type { Metadata } from "next";
import "./globals.css";
import "./design-system.css";
import "./operations.css";
import "./dashboard.css";
import WorkQuickNav from "./work-quick-nav";

export const metadata: Metadata = {
  title: "GRC Platform",
  description: "Sovereign, framework-agnostic GRC platform",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fa" dir="rtl">
      <body>
        {children}
        <WorkQuickNav />
      </body>
    </html>
  );
}
