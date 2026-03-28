"use client";

import { useCallback, useRef, useState } from "react";

interface FileUploaderProps {
  onUpload: (file: File) => void;
  state: "idle" | "uploading" | "processing" | "complete" | "error";
}

const ACCEPTED_EXTENSIONS = [".step", ".stp"];

export function FileUploader({ onUpload, state }: FileUploaderProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): string | null => {
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      return "Only STEP files (.step, .stp) are accepted.";
    }
    if (file.size > 100 * 1024 * 1024) {
      return "File is too large (max 100MB).";
    }
    return null;
  };

  const handleFile = useCallback(
    (file: File) => {
      const error = validateFile(file);
      if (error) {
        alert(error);
        return;
      }
      setSelectedFile(file);
    },
    []
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const isUploading = state === "uploading";

  return (
    <div className="space-y-4">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`
          border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition
          ${isDragOver ? "border-brand-500 bg-brand-50" : "border-gray-300 hover:border-gray-400"}
          ${isUploading ? "opacity-50 pointer-events-none" : ""}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".step,.stp,.STEP,.STP"
          onChange={handleChange}
          className="hidden"
        />
        <div className="flex flex-col items-center gap-2">
          <svg className="h-10 w-10 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <p className="text-sm text-gray-600">
            <span className="font-medium text-brand-600">Click to upload</span> or drag and drop
          </p>
          <p className="text-xs text-gray-400">STEP files (.step, .stp) up to 100MB</p>
        </div>
      </div>

      {selectedFile && state === "idle" && (
        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border">
          <div>
            <p className="font-medium text-sm text-gray-900">{selectedFile.name}</p>
            <p className="text-xs text-gray-500">
              {(selectedFile.size / (1024 * 1024)).toFixed(1)} MB
            </p>
          </div>
          <button
            onClick={() => onUpload(selectedFile)}
            className="px-4 py-2 bg-brand-600 text-white rounded-md text-sm font-medium hover:bg-brand-700"
          >
            Upload & Analyze
          </button>
        </div>
      )}

      {isUploading && (
        <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-lg border">
          <div className="animate-spin h-4 w-4 border-2 border-brand-600 border-t-transparent rounded-full" />
          <p className="text-sm text-gray-600">Uploading {selectedFile?.name}...</p>
        </div>
      )}
    </div>
  );
}
