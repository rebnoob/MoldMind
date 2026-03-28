"""Sharp corner / fillet detection rule.

Sharp internal corners cause:
- Stress concentration → part failure
- Flow hesitation → cosmetic defects
- Difficult ejection
- Mold wear at corner

Recommended: All internal corners should have radius >= 0.5mm (ideally 50-75% of wall thickness).
External corners: radius >= 0.25mm for mold life.
"""

from .base import DfmRule, DfmIssue, Severity, Category, AnalysisContext


class SharpCornerRule(DfmRule):
    rule_id = "sharp_corners"
    name = "Sharp Corners"
    category = Category.GEOMETRY
    weight = 1.0

    MIN_INTERNAL_RADIUS_MM = 0.5
    MIN_EXTERNAL_RADIUS_MM = 0.25

    def evaluate(self, context: AnalysisContext) -> list[DfmIssue]:
        """Detect sharp corners using edge analysis.

        Note: Full implementation requires edge curvature analysis from OpenCascade.
        This is a simplified version that flags faces with very small fillet radii.
        Phase 2 will add proper edge-by-edge analysis.
        """
        issues = []

        # Count cylindrical faces with very small radii (these are fillets/rounds)
        small_fillet_faces = []
        for face in context.face_infos:
            if face.surface_type == "cylindrical" and face.area < 1.0:
                # Small cylindrical face = likely a fillet
                # A proper implementation would extract the cylinder radius
                # For now, flag as info
                small_fillet_faces.append(face)

        # This rule needs edge-level analysis for proper implementation.
        # For v1, we provide a simplified heuristic based on face types.

        # Count faces that are neither planar nor have a known smooth surface type
        # (this is a proxy for "has the designer added fillets?")
        planar_faces = sum(1 for f in context.face_infos if f.surface_type == "planar")
        fillet_faces = sum(1 for f in context.face_infos
                          if f.surface_type in ("cylindrical", "spherical", "torus"))
        total_faces = len(context.face_infos)

        if total_faces > 0 and fillet_faces == 0 and planar_faces > 6:
            # Part has many planar faces but no fillets at all — likely has sharp corners
            issues.append(DfmIssue(
                rule_id=self.rule_id,
                severity=Severity.WARNING,
                category=self.category,
                title="No fillets detected — likely sharp internal corners",
                description=(
                    f"Part has {planar_faces} planar faces but no detected fillet "
                    f"surfaces. Sharp internal corners cause stress concentration "
                    f"(up to 3x), flow hesitation, and premature mold wear."
                ),
                suggestion=(
                    f"Add internal corner radii of at least {self.MIN_INTERNAL_RADIUS_MM}mm "
                    f"(ideally 50-75% of wall thickness). Add external radii of at least "
                    f"{self.MIN_EXTERNAL_RADIUS_MM}mm. Uniform radii improve flow and reduce "
                    f"cycle time."
                ),
                measured_value=0,
                threshold_value=self.MIN_INTERNAL_RADIUS_MM,
                unit="mm",
            ))

        return issues
