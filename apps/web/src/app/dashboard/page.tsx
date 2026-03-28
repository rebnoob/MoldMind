"use client";

// Mock data — replace with API calls
const MOCK_PARTS = [
  {
    id: "1",
    name: "Housing Cover",
    filename: "housing_cover_v3.step",
    status: "analyzed",
    score: 62,
    issues: { critical: 2, warning: 3, info: 1 },
    created_at: "2024-01-15T10:30:00Z",
  },
  {
    id: "2",
    name: "Clip Assembly",
    filename: "clip_assy_rev2.step",
    status: "analyzed",
    score: 85,
    issues: { critical: 0, warning: 2, info: 1 },
    created_at: "2024-01-14T14:20:00Z",
  },
  {
    id: "3",
    name: "Connector Body",
    filename: "connector_body.stp",
    status: "processing",
    score: null,
    issues: null,
    created_at: "2024-01-15T11:00:00Z",
  },
];

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-gray-400">—</span>;

  const color =
    score >= 80 ? "text-green-700 bg-green-50" :
    score >= 60 ? "text-amber-700 bg-amber-50" :
    "text-red-700 bg-red-50";

  return (
    <span className={`text-sm font-bold px-2 py-0.5 rounded ${color}`}>
      {score}
    </span>
  );
}

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Parts</h1>
          <p className="text-sm text-gray-500">
            {MOCK_PARTS.length} parts in this project
          </p>
        </div>
        <a
          href="/upload"
          className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
        >
          Upload Part
        </a>
      </div>

      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-4 py-3">
                Part
              </th>
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-4 py-3">
                Status
              </th>
              <th className="text-center text-xs font-medium text-gray-500 uppercase tracking-wide px-4 py-3">
                Score
              </th>
              <th className="text-center text-xs font-medium text-gray-500 uppercase tracking-wide px-4 py-3">
                Issues
              </th>
              <th className="text-right text-xs font-medium text-gray-500 uppercase tracking-wide px-4 py-3">
                Uploaded
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {MOCK_PARTS.map((part) => (
              <tr key={part.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <a href={`/analysis/${part.id}`} className="block">
                    <p className="text-sm font-medium text-gray-900 hover:text-brand-600">
                      {part.name}
                    </p>
                    <p className="text-xs text-gray-400">{part.filename}</p>
                  </a>
                </td>
                <td className="px-4 py-3">
                  {part.status === "analyzed" ? (
                    <span className="text-xs font-medium text-green-700 bg-green-50 px-2 py-0.5 rounded">
                      Analyzed
                    </span>
                  ) : (
                    <span className="text-xs font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded flex items-center gap-1 w-fit">
                      <span className="animate-spin h-3 w-3 border border-blue-600 border-t-transparent rounded-full" />
                      Processing
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-center">
                  <ScoreBadge score={part.score} />
                </td>
                <td className="px-4 py-3 text-center">
                  {part.issues ? (
                    <div className="flex items-center justify-center gap-2 text-xs">
                      {part.issues.critical > 0 && (
                        <span className="text-red-600">{part.issues.critical}C</span>
                      )}
                      {part.issues.warning > 0 && (
                        <span className="text-amber-600">{part.issues.warning}W</span>
                      )}
                      {part.issues.info > 0 && (
                        <span className="text-blue-600">{part.issues.info}I</span>
                      )}
                    </div>
                  ) : (
                    <span className="text-xs text-gray-400">—</span>
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
    </div>
  );
}
