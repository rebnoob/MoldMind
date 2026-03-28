"use client";

import { useState } from "react";
import { PartViewer } from "@/components/viewer/part-viewer";
import { IssuePanel } from "@/components/dfm/issue-panel";
import { ScoreCard } from "@/components/dfm/score-card";
import { useDfmResult } from "@/hooks/use-dfm-result";

// Mock data for development — replaced by API calls when backend is connected
const MOCK_RESULT = {
  moldability_score: 62,
  pull_direction: [0, 0, 1],
  summary: { critical: 2, warning: 3, info: 1 },
  issues: [
    {
      id: "1",
      rule_id: "draft_angle",
      severity: "critical" as const,
      category: "draft",
      title: "Zero draft on 4 face(s)",
      description:
        "4 face(s) have essentially no draft angle (< 0.25°). These faces will lock the part in the mold, preventing ejection without damage.",
      suggestion:
        "Add at least 1.0° of draft to all faces parallel to the pull direction.",
      affected_faces: [3, 7, 12, 15],
      measured_value: 0.1,
      threshold_value: 1.0,
      unit: "degrees",
    },
    {
      id: "2",
      rule_id: "wall_thickness",
      severity: "critical" as const,
      category: "thickness",
      title: "Wall too thin (0.4mm)",
      description:
        "Minimum wall thickness of 0.40mm is below the recommended minimum of 0.80mm. This may cause short shots or flow hesitation.",
      suggestion: "Increase wall thickness to at least 0.80mm.",
      affected_faces: [20, 21],
      measured_value: 0.4,
      threshold_value: 0.8,
      unit: "mm",
    },
    {
      id: "3",
      rule_id: "undercut",
      severity: "warning" as const,
      category: "undercut",
      title: "2 undercut(s) detected",
      description:
        "Found 2 face(s) that form undercuts relative to the current pull direction. Each undercut requires a side action, increasing mold cost by ~$2,000-$10,000+.",
      suggestion:
        "Consider changing pull direction or redesigning features to remove undercuts.",
      affected_faces: [8, 9],
      measured_value: 2,
      threshold_value: 0,
      unit: "count",
    },
    {
      id: "4",
      rule_id: "wall_uniformity",
      severity: "warning" as const,
      category: "thickness",
      title: "Non-uniform wall thickness (38% variation)",
      description:
        "Wall thickness varies from 0.8mm to 3.2mm (mean: 1.8mm). Non-uniform walls cause differential shrinkage and warpage.",
      suggestion:
        "Aim for uniform wall thickness within ±10% of nominal. Use gradual transitions.",
      affected_faces: null,
      measured_value: 38,
      threshold_value: 25,
      unit: "%",
    },
    {
      id: "5",
      rule_id: "draft_angle",
      severity: "warning" as const,
      category: "draft",
      title: "Insufficient draft on 6 face(s)",
      description:
        "6 face(s) have draft angle below 1.0° for ABS. This may cause ejection difficulty and surface marks.",
      suggestion: "Increase draft angle to at least 1.0°. Consider 2.0° for better quality.",
      affected_faces: [4, 5, 10, 11, 16, 17],
      measured_value: 0.5,
      threshold_value: 1.0,
      unit: "degrees",
    },
    {
      id: "6",
      rule_id: "sharp_corners",
      severity: "info" as const,
      category: "geometry",
      title: "No fillets detected — likely sharp internal corners",
      description:
        "Part has 24 planar faces but no detected fillet surfaces. Sharp internal corners cause stress concentration.",
      suggestion: "Add internal corner radii of at least 0.5mm.",
      affected_faces: null,
      measured_value: 0,
      threshold_value: 0.5,
      unit: "mm",
    },
  ],
};

export default function AnalysisPage({
  params,
}: {
  params: { partId: string };
}) {
  const [highlightedFaces, setHighlightedFaces] = useState<number[]>([]);
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null);

  // In production, use: const { result, loading } = useDfmResult(params.partId);
  const result = MOCK_RESULT;

  const handleIssueSelect = (issueId: string) => {
    setSelectedIssueId(issueId);
    const issue = result.issues.find((i) => i.id === issueId);
    setHighlightedFaces(issue?.affected_faces || []);
  };

  return (
    <div className="h-[calc(100vh-56px)] flex">
      {/* Left: 3D Viewer */}
      <div className="flex-1 relative">
        <PartViewer
          meshUrl={null} // TODO: load from API
          highlightedFaces={highlightedFaces}
          pullDirection={result.pull_direction}
        />
        <div className="absolute top-4 left-4">
          <ScoreCard
            score={result.moldability_score}
            summary={result.summary}
          />
        </div>
      </div>

      {/* Right: Issue Panel */}
      <div className="w-[420px] border-l border-gray-200 overflow-y-auto">
        <IssuePanel
          issues={result.issues}
          selectedIssueId={selectedIssueId}
          onSelectIssue={handleIssueSelect}
        />
      </div>
    </div>
  );
}
