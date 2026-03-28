"use client";

import { useState, useCallback } from "react";
import { FileUploader } from "@/components/upload/file-uploader";

export default function UploadPage() {
  const [uploadState, setUploadState] = useState<
    "idle" | "uploading" | "processing" | "complete" | "error"
  >("idle");
  const [partId, setPartId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = useCallback(async (file: File) => {
    setUploadState("uploading");
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("name", file.name.replace(/\.(step|stp)$/i, ""));
      formData.append("project_id", "00000000-0000-0000-0000-000000000000"); // TODO: project selector

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/parts/upload`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Upload failed");
      }

      const part = await res.json();
      setPartId(part.id);
      setUploadState("processing");

      // TODO: Poll for processing status, then redirect to analysis
      // For now, just mark complete
      setUploadState("complete");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setUploadState("error");
    }
  }, []);

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Upload Part</h1>
      <p className="text-gray-600 mb-8">
        Upload a STEP file (.step, .stp) to begin DFM analysis.
        Maximum file size: 100MB.
      </p>

      <FileUploader onUpload={handleUpload} state={uploadState} />

      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
          {error}
        </div>
      )}

      {uploadState === "processing" && (
        <div className="mt-6 p-6 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center gap-3">
            <div className="animate-spin h-5 w-5 border-2 border-blue-600 border-t-transparent rounded-full" />
            <div>
              <p className="font-medium text-blue-900">Processing geometry...</p>
              <p className="text-sm text-blue-700">
                Parsing STEP file, tessellating mesh, extracting properties.
              </p>
            </div>
          </div>
        </div>
      )}

      {uploadState === "complete" && partId && (
        <div className="mt-6 p-6 bg-green-50 border border-green-200 rounded-lg">
          <p className="font-medium text-green-900 mb-2">Part uploaded successfully</p>
          <div className="flex gap-3">
            <a
              href={`/analysis/${partId}`}
              className="px-4 py-2 bg-brand-600 text-white rounded-md text-sm font-medium hover:bg-brand-700"
            >
              Run DFM Analysis
            </a>
            <a
              href={`/analysis/${partId}`}
              className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-50"
            >
              View Part
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
