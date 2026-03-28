interface ScoreCardProps {
  score: number;
  summary: {
    critical: number;
    warning: number;
    info: number;
    verdict?: string;
    verdict_summary?: string;
  };
}

function getScoreColor(score: number): string {
  if (score >= 80) return "text-green-600";
  if (score >= 60) return "text-amber-600";
  return "text-red-600";
}

const VERDICT_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  PASS: { bg: "bg-green-100 border-green-300", text: "text-green-800", label: "PASS" },
  REVIEW: { bg: "bg-amber-100 border-amber-300", text: "text-amber-800", label: "REVIEW" },
  FAIL: { bg: "bg-red-100 border-red-300", text: "text-red-800", label: "FAIL" },
};

export function ScoreCard({ score, summary }: ScoreCardProps) {
  const verdict = summary.verdict || (score >= 70 ? "PASS" : score >= 40 ? "REVIEW" : "FAIL");
  const vs = VERDICT_STYLES[verdict] || VERDICT_STYLES.REVIEW;

  return (
    <div className="bg-white/95 backdrop-blur-sm border border-gray-200 rounded-lg p-4 shadow-sm min-w-[220px]">
      {/* Verdict badge */}
      <div className={`inline-flex items-center px-2.5 py-1 rounded border text-xs font-bold mb-2 ${vs.bg} ${vs.text}`}>
        {vs.label}
      </div>

      <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
        Moldability Score
      </div>
      <div className="flex items-baseline gap-2 mb-2">
        <span className={`text-3xl font-bold ${getScoreColor(score)}`}>{score}</span>
        <span className="text-sm text-gray-500">/ 100</span>
      </div>

      {summary.verdict_summary && (
        <p className="text-[11px] text-gray-500 mb-2 leading-tight">{summary.verdict_summary}</p>
      )}

      <div className="flex gap-3 text-xs">
        {summary.critical > 0 && (
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-500" />
            {summary.critical} critical
          </span>
        )}
        {summary.warning > 0 && (
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            {summary.warning} warning
          </span>
        )}
        {summary.info > 0 && (
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-blue-500" />
            {summary.info} info
          </span>
        )}
      </div>
    </div>
  );
}
