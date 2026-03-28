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

interface IssuePanelProps {
  issues: DfmIssue[];
  selectedIssueId: string | null;
  onSelectIssue: (id: string) => void;
}

const SEVERITY_STYLES = {
  critical: {
    border: "border-red-200",
    bg: "bg-red-50",
    badge: "bg-red-100 text-red-800",
    dot: "bg-red-500",
  },
  warning: {
    border: "border-amber-200",
    bg: "bg-amber-50",
    badge: "bg-amber-100 text-amber-800",
    dot: "bg-amber-500",
  },
  info: {
    border: "border-blue-200",
    bg: "bg-blue-50",
    badge: "bg-blue-100 text-blue-800",
    dot: "bg-blue-500",
  },
};

const CATEGORY_LABELS: Record<string, string> = {
  draft: "Draft Angle",
  thickness: "Wall Thickness",
  undercut: "Undercuts",
  geometry: "Geometry",
  gate: "Gating",
  ejection: "Ejection",
  cooling: "Cooling",
};

export function IssuePanel({ issues, selectedIssueId, onSelectIssue }: IssuePanelProps) {
  const grouped = {
    critical: issues.filter((i) => i.severity === "critical"),
    warning: issues.filter((i) => i.severity === "warning"),
    info: issues.filter((i) => i.severity === "info"),
  };

  return (
    <div className="p-4">
      <h2 className="text-lg font-semibold text-gray-900 mb-1">DFM Issues</h2>
      <p className="text-sm text-gray-500 mb-4">
        {issues.length} issue{issues.length !== 1 ? "s" : ""} found.
        Click to highlight on model.
      </p>

      <div className="space-y-6">
        {(["critical", "warning", "info"] as const).map((severity) => {
          const group = grouped[severity];
          if (group.length === 0) return null;
          const styles = SEVERITY_STYLES[severity];

          return (
            <div key={severity}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`w-2 h-2 rounded-full ${styles.dot}`} />
                <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                  {severity} ({group.length})
                </span>
              </div>

              <div className="space-y-2">
                {group.map((issue) => (
                  <IssueCard
                    key={issue.id}
                    issue={issue}
                    isSelected={issue.id === selectedIssueId}
                    onSelect={() => onSelectIssue(issue.id)}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function IssueCard({
  issue,
  isSelected,
  onSelect,
}: {
  issue: DfmIssue;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const styles = SEVERITY_STYLES[issue.severity];

  return (
    <button
      onClick={onSelect}
      className={`
        w-full text-left p-3 rounded-lg border transition
        ${isSelected ? `${styles.border} ${styles.bg} ring-2 ring-offset-1 ring-brand-500` : "border-gray-200 hover:border-gray-300"}
      `}
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <h3 className="text-sm font-medium text-gray-900">{issue.title}</h3>
        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${styles.badge}`}>
          {CATEGORY_LABELS[issue.category] || issue.category}
        </span>
      </div>

      <p className="text-xs text-gray-600 mb-2 line-clamp-2">{issue.description}</p>

      {issue.measured_value != null && issue.threshold_value != null && (
        <div className="flex items-center gap-3 text-xs">
          <span className="text-gray-500">
            Measured: <span className="font-mono font-medium text-gray-700">{issue.measured_value}{issue.unit}</span>
          </span>
          <span className="text-gray-500">
            Threshold: <span className="font-mono font-medium text-gray-700">{issue.threshold_value}{issue.unit}</span>
          </span>
        </div>
      )}

      {isSelected && issue.suggestion && (
        <div className="mt-2 pt-2 border-t border-gray-200">
          <p className="text-xs text-gray-500 font-medium mb-0.5">Suggestion</p>
          <p className="text-xs text-gray-700">{issue.suggestion}</p>
        </div>
      )}

      {issue.affected_faces && (
        <div className="mt-1 text-[10px] text-gray-400">
          {issue.affected_faces.length} face{issue.affected_faces.length !== 1 ? "s" : ""} affected
        </div>
      )}
    </button>
  );
}
