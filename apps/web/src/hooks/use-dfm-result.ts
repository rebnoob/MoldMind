"use client";

import { useState, useEffect } from "react";

interface DfmIssue {
  id: string;
  rule_id: string;
  severity: "critical" | "warning" | "info";
  category: string;
  title: string;
  description: string;
  suggestion: string | null;
  affected_faces: number[] | null;
  measured_value: number | null;
  threshold_value: number | null;
  unit: string | null;
}

interface DfmResult {
  moldability_score: number;
  pull_direction: number[];
  summary: { critical: number; warning: number; info: number };
  issues: DfmIssue[];
}

export function useDfmResult(partId: string) {
  const [result, setResult] = useState<DfmResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchResult() {
      try {
        const token = localStorage.getItem("token");
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/api/analysis/dfm/${partId}/latest`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );

        if (!res.ok) {
          if (res.status === 404) {
            setResult(null);
            return;
          }
          throw new Error("Failed to fetch DFM result");
        }

        const data = await res.json();
        setResult(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }

    fetchResult();
  }, [partId]);

  return { result, loading, error };
}
