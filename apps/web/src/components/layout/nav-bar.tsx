"use client";

import { useEffect, useState } from "react";

export function NavBar() {
  const [user, setUser] = useState<{ name: string } | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("user");
    if (stored) {
      try { setUser(JSON.parse(stored)); } catch {}
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    window.location.href = "/login";
  };

  return (
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
            {user ? (
              <div className="flex items-center gap-3">
                <span className="text-sm text-gray-600">{user.name}</span>
                <button
                  onClick={handleLogout}
                  className="text-xs text-gray-400 hover:text-gray-600"
                >
                  Logout
                </button>
              </div>
            ) : (
              <a href="/login" className="text-sm text-brand-600 font-medium">
                Sign in
              </a>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
