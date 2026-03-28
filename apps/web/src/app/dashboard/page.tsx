"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Part {
  id: string;
  name: string;
  filename: string;
  status: string;
  error_message: string | null;
  moldability_score: number | null;
  issue_counts: { critical: number; warning: number; info: number } | null;
  created_at: string;
  file_size_bytes: number | null;
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-gray-400">--</span>;
  const color =
    score >= 80 ? "text-green-700 bg-green-50" :
    score >= 60 ? "text-amber-700 bg-amber-50" :
    "text-red-700 bg-red-50";
  return <span className={`text-sm font-bold px-2 py-0.5 rounded ${color}`}>{score}</span>;
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "analyzed":
      return <span className="text-xs font-medium text-green-700 bg-green-50 px-2 py-0.5 rounded">Analyzed</span>;
    case "processing":
    case "uploaded":
      return (
        <span className="text-xs font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded flex items-center gap-1.5 w-fit">
          <span className="animate-spin h-3 w-3 border border-blue-600 border-t-transparent rounded-full" />
          {status === "processing" ? "Analyzing..." : "Queued"}
        </span>
      );
    case "error":
      return <span className="text-xs font-medium text-red-700 bg-red-50 px-2 py-0.5 rounded">Error</span>;
    default:
      return <span className="text-xs text-gray-400">{status}</span>;
  }
}

export default function DashboardPage() {
  const router = useRouter();
  const [parts, setParts] = useState<Part[]>([]);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchParts = async () => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }

    try {
      const res = await fetch(`${API_URL}/api/parts/all`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401 || res.status === 403) {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        router.push("/login");
        return;
      }
      if (res.ok) {
        const data = await res.json();
        setParts(data);

        // Stop polling if all parts are in terminal state
        const hasPending = data.some((p: Part) =>
          p.status === "processing" || p.status === "uploaded"
        );
        if (!hasPending && intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        // Start polling if there are pending parts
        if (hasPending && !intervalRef.current) {
          intervalRef.current = setInterval(fetchParts, 2000);
        }
      }
    } catch {
      // Silently retry on next interval
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchParts();
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-16 text-center text-gray-400">
        Loading parts...
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Parts</h1>
          <p className="text-sm text-gray-500">
            {parts.length} part{parts.length !== 1 ? "s" : ""}
          </p>
        </div>
        <a
          href="/upload"
          className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
        >
          Upload Part
        </a>
      </div>

      {parts.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-gray-300 rounded-lg">
          <p className="text-gray-500 mb-3">No parts yet</p>
          <a href="/upload" className="text-brand-600 font-medium text-sm hover:text-brand-700">
            Upload a STEP file to get started
          </a>
        </div>
      ) : (
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-4 py-3">Part</th>
                <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-4 py-3">Status</th>
                <th className="text-center text-xs font-medium text-gray-500 uppercase tracking-wide px-4 py-3">Score</th>
                <th className="text-center text-xs font-medium text-gray-500 uppercase tracking-wide px-4 py-3">Issues</th>
                <th className="text-right text-xs font-medium text-gray-500 uppercase tracking-wide px-4 py-3">Uploaded</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {parts.map((part) => (
                <tr
                  key={part.id}
                  className={`hover:bg-gray-50 ${part.status === "analyzed" ? "cursor-pointer" : ""}`}
                  onClick={() => {
                    if (part.status === "analyzed") router.push(`/analysis/${part.id}`);
                  }}
                >
                  <td className="px-4 py-3">
                    <p className="text-sm font-medium text-gray-900">{part.name}</p>
                    <p className="text-xs text-gray-400">{part.filename}</p>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={part.status} />
                    {part.status === "error" && part.error_message && (
                      <p className="text-xs text-red-500 mt-1 max-w-[200px] truncate" title={part.error_message}>
                        {part.error_message}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center"><ScoreBadge score={part.moldability_score} /></td>
                  <td className="px-4 py-3 text-center">
                    {part.issue_counts ? (
                      <div className="flex items-center justify-center gap-2 text-xs">
                        {part.issue_counts.critical > 0 && <span className="text-red-600">{part.issue_counts.critical}C</span>}
                        {part.issue_counts.warning > 0 && <span className="text-amber-600">{part.issue_counts.warning}W</span>}
                        {part.issue_counts.info > 0 && <span className="text-blue-600">{part.issue_counts.info}I</span>}
                      </div>
                    ) : (
                      <span className="text-xs text-gray-400">--</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-xs text-gray-500">
                    {new Date(part.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
