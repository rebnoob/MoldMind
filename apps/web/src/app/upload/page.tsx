"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { FileUploader } from "@/components/upload/file-uploader";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function UploadPage() {
  const router = useRouter();
  const [uploadState, setUploadState] = useState<
    "idle" | "uploading" | "error"
  >("idle");
  const [error, setError] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }

    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/projects/`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.status === 401 || res.status === 403) {
          localStorage.removeItem("token");
          localStorage.removeItem("user");
          router.push("/login");
          return;
        }
        if (!res.ok) {
          setError(`Server error (${res.status}). Is the API running?`);
          return;
        }
        const projects = await res.json();
        if (projects.length > 0) {
          setProjectId(projects[0].id);
        } else {
          const createRes = await fetch(`${API_URL}/api/projects/`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body: JSON.stringify({ name: "My Parts", description: "Default project" }),
          });
          if (!createRes.ok) {
            setError("Failed to create project");
            return;
          }
          const p = await createRes.json();
          setProjectId(p.id);
        }
      } catch (err) {
        setError(`Cannot connect to API at ${API_URL}. Is the server running?`);
      }
    })();
  }, [router]);

  const handleUpload = useCallback(async (file: File) => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    if (!projectId) { setError("No project available"); return; }

    setUploadState("uploading");
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("name", file.name.replace(/\.(step|stp)$/i, ""));
      formData.append("project_id", projectId);

      const res = await fetch(`${API_URL}/api/parts/upload`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (res.status === 401) { router.push("/login"); return; }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Upload failed");
      }

      // Upload succeeded — go straight to dashboard to watch progress
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setUploadState("error");
    }
  }, [projectId, router]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Upload Part</h1>
      <p className="text-gray-600 mb-8">
        Upload a STEP file (.step, .stp) to begin DFM analysis.
        Maximum file size: 100MB.
      </p>

      {!projectId && !error && (
        <div className="text-sm text-gray-400 mb-4">Setting up project...</div>
      )}

      <FileUploader onUpload={handleUpload} state={uploadState} />

      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
          {error}
        </div>
      )}
    </div>
  );
}
