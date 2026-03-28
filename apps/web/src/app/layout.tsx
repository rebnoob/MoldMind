import type { Metadata } from "next";
import "./globals.css";

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
        <nav className="border-b border-gray-200 bg-white">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="flex h-14 items-center justify-between">
              <div className="flex items-center gap-8">
                <a href="/" className="text-lg font-semibold text-brand-900">
                  MoldMind
                </a>
                <div className="hidden sm:flex gap-6">
                  <a href="/dashboard" className="text-sm text-gray-600 hover:text-gray-900">
                    Dashboard
                  </a>
                  <a href="/upload" className="text-sm text-gray-600 hover:text-gray-900">
                    Upload
                  </a>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-xs text-gray-400">v0.1.0</span>
              </div>
            </div>
          </div>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}
