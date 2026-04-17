import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "Second Brain — Spine",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body style={{ background: "#0f1419", color: "#e6e6e6", fontFamily: "system-ui, sans-serif", margin: 0 }}>
        {children}
      </body>
    </html>
  );
}
