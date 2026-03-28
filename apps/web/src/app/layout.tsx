import type { Metadata } from "next";
import "./globals.css";
import { NavBar } from "@/components/layout/nav-bar";

export const metadata: Metadata = {
  title: "MoldMind — Manufacturing Intelligence",
  description: "Convert part geometry into optimized, editable mold design workflows",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white">
        <NavBar />
        <main>{children}</main>
      </body>
    </html>
  );
}
