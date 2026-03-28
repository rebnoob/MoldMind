interface ScoreCardProps {
  score: number;
  summary: { critical: number; warning: number; info: number };
}

function getScoreColor(score: number): string {
  if (score >= 80) return "text-green-600";
  if (score >= 60) return "text-amber-600";
  return "text-red-600";
}

function getScoreLabel(score: number): string {
  if (score >= 90) return "Excellent";
  if (score >= 80) return "Good";
  if (score >= 60) return "Fair";
  if (score >= 40) return "Poor";
  return "Critical";
}

export function ScoreCard({ score, summary }: ScoreCardProps) {
  return (
    <div className="bg-white/95 backdrop-blur-sm border border-gray-200 rounded-lg p-4 shadow-sm min-w-[200px]">
      <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
        Moldability Score
      </div>
      <div className="flex items-baseline gap-2 mb-3">
        <span className={`text-3xl font-bold ${getScoreColor(score)}`}>
          {score}
        </span>
        <span className="text-sm text-gray-500">/ 100</span>
        <span className={`text-sm font-medium ${getScoreColor(score)}`}>
          {getScoreLabel(score)}
        </span>
      </div>
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
