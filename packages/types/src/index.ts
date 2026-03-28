// Shared types between frontend and API contracts

export type Severity = "critical" | "warning" | "info";

export type DfmCategory =
  | "draft"
  | "thickness"
  | "undercut"
  | "geometry"
  | "gate"
  | "ejection"
  | "cooling";

export interface BoundingBox {
  min: [number, number, number];
  max: [number, number, number];
}

export interface Part {
  id: string;
  project_id: string;
  name: string;
  filename: string;
  file_size_bytes: number | null;
  units: string;
  status: "uploaded" | "processing" | "ready" | "error";
  bounding_box: BoundingBox | null;
  face_count: number | null;
  volume_mm3: number | null;
  surface_area_mm2: number | null;
  mesh_url: string | null;
  created_at: string;
}

export interface DfmIssue {
  id: string;
  rule_id: string;
  severity: Severity;
  category: DfmCategory;
  title: string;
  description: string;
  suggestion: string | null;
  affected_faces: number[] | null;
  affected_region: BoundingBox | null;
  measured_value: number | null;
  threshold_value: number | null;
  unit: string | null;
}

export interface DfmResult {
  id: string;
  job_id: string;
  part_id: string;
  moldability_score: number;
  pull_direction: [number, number, number];
  summary: {
    critical: number;
    warning: number;
    info: number;
    total_faces: number;
    faces_with_issues: number;
  };
  issues: DfmIssue[];
  created_at: string;
}

export interface AnalysisJob {
  id: string;
  part_id: string;
  job_type: "dfm_analysis" | "mold_concept";
  status: "queued" | "processing" | "completed" | "failed";
  progress: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface Material {
  id: string;
  name: string;
  family: string;
  min_wall_thickness_mm: number;
  max_wall_thickness_mm: number;
  recommended_draft_deg: number;
  shrinkage_pct: number;
}
