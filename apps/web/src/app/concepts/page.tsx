"use client";

/**
 * Mold Concept Review Page (Phase 2)
 *
 * Will display:
 * - Suggested parting line on 3D model
 * - Mold architecture recommendation (2-plate vs 3-plate)
 * - Gate type and location
 * - Slider/lifter concepts
 * - Mold base selection
 * - Side-by-side concept comparison
 */

export default function ConceptsPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-16 text-center">
      <div className="inline-flex items-center gap-2 px-3 py-1 bg-blue-50 border border-blue-200 rounded-full text-xs text-blue-700 font-medium mb-4">
        Phase 2
      </div>
      <h1 className="text-2xl font-bold text-gray-900 mb-3">
        Mold Concept Generation
      </h1>
      <p className="text-gray-600 max-w-lg mx-auto mb-8">
        Automatic parting line suggestion, mold architecture recommendation,
        gate selection, and slider/lifter concepts — generated from your
        validated part geometry.
      </p>
      <div className="grid grid-cols-2 gap-4 max-w-md mx-auto text-left">
        <div className="p-4 border border-gray-200 rounded-lg">
          <p className="text-sm font-medium text-gray-900">Parting Line</p>
          <p className="text-xs text-gray-500">Geometry-based suggestion</p>
        </div>
        <div className="p-4 border border-gray-200 rounded-lg">
          <p className="text-sm font-medium text-gray-900">Gate Location</p>
          <p className="text-xs text-gray-500">Flow-length optimized</p>
        </div>
        <div className="p-4 border border-gray-200 rounded-lg">
          <p className="text-sm font-medium text-gray-900">Mold Type</p>
          <p className="text-xs text-gray-500">2-plate / 3-plate / hot runner</p>
        </div>
        <div className="p-4 border border-gray-200 rounded-lg">
          <p className="text-sm font-medium text-gray-900">Side Actions</p>
          <p className="text-xs text-gray-500">Slider & lifter concepts</p>
        </div>
      </div>
    </div>
  );
}
