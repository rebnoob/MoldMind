export default function Home() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-16">
      <h1 className="text-4xl font-bold text-gray-900 mb-4">
        Manufacturing Intelligence for Injection Molding
      </h1>
      <p className="text-lg text-gray-600 mb-8 max-w-2xl">
        Upload a STEP file. Get an instant moldability audit with scored issues,
        fix suggestions, and 3D visualization — in seconds, not hours.
      </p>

      <div className="flex gap-4 mb-16">
        <a
          href="/upload"
          className="px-6 py-3 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 transition"
        >
          Upload Part
        </a>
        <a
          href="/dashboard"
          className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition"
        >
          View Dashboard
        </a>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="p-6 border border-gray-200 rounded-lg">
          <h3 className="font-semibold text-gray-900 mb-2">DFM Analysis</h3>
          <p className="text-sm text-gray-600">
            Automated draft angle, wall thickness, undercut, and geometry checks
            with per-face issue highlighting.
          </p>
        </div>
        <div className="p-6 border border-gray-200 rounded-lg">
          <h3 className="font-semibold text-gray-900 mb-2">Moldability Score</h3>
          <p className="text-sm text-gray-600">
            Composite 0-100 score based on weighted rule evaluation. Calibrated
            against expert reviews.
          </p>
        </div>
        <div className="p-6 border border-gray-200 rounded-lg">
          <h3 className="font-semibold text-gray-900 mb-2">Actionable Fixes</h3>
          <p className="text-sm text-gray-600">
            Every issue includes a specific, inspectable suggestion with
            measured values and thresholds.
          </p>
        </div>
      </div>
    </div>
  );
}
