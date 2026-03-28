"""Wall thickness rules.

Two separate rules:
1. WallThicknessRule: Checks min/max absolute thickness
2. WallUniformityRule: Checks thickness variation (causes sink marks, warpage)

Key DFM principles:
- Too thin → short shots, flow hesitation
- Too thick → sink marks, voids, long cycle time, warpage
- Non-uniform → differential shrinkage → warpage
- Rib thickness should be 50-75% of adjacent wall
"""

from .base import DfmRule, DfmIssue, Severity, Category, AnalysisContext


class WallThicknessRule(DfmRule):
    rule_id = "wall_thickness"
    name = "Wall Thickness"
    category = Category.THICKNESS
    weight = 2.0

    def evaluate(self, context: AnalysisContext) -> list[DfmIssue]:
        issues = []
        ta = context.thickness_analysis

        if ta is None or not ta.samples:
            return issues

        mat = context.material

        # Check minimum thickness
        thin_samples = [s for s in ta.samples if s.thickness < mat.min_wall_thickness_mm]
        if thin_samples:
            min_t = min(s.thickness for s in thin_samples)
            affected_faces = list(set(s.face_index for s in thin_samples))
            issues.append(DfmIssue(
                rule_id=self.rule_id,
                severity=Severity.CRITICAL if min_t < mat.min_wall_thickness_mm * 0.5 else Severity.WARNING,
                category=self.category,
                title=f"Wall too thin ({min_t:.2f}mm)",
                description=(
                    f"Minimum wall thickness of {min_t:.2f}mm is below the "
                    f"recommended minimum of {mat.min_wall_thickness_mm}mm for "
                    f"{mat.name}. This may cause short shots, flow hesitation, "
                    f"or incomplete filling."
                ),
                suggestion=(
                    f"Increase wall thickness to at least {mat.min_wall_thickness_mm}mm. "
                    f"If thin features are intentional (ribs, snap fits), ensure they are "
                    f"within flow-length limits for the material."
                ),
                affected_faces=affected_faces,
                measured_value=min_t,
                threshold_value=mat.min_wall_thickness_mm,
                unit="mm",
            ))

        # Check maximum thickness
        thick_samples = [s for s in ta.samples if s.thickness > mat.max_wall_thickness_mm]
        if thick_samples:
            max_t = max(s.thickness for s in thick_samples)
            affected_faces = list(set(s.face_index for s in thick_samples))
            issues.append(DfmIssue(
                rule_id=self.rule_id,
                severity=Severity.WARNING,
                category=self.category,
                title=f"Wall too thick ({max_t:.2f}mm)",
                description=(
                    f"Maximum wall thickness of {max_t:.2f}mm exceeds the "
                    f"recommended maximum of {mat.max_wall_thickness_mm}mm for "
                    f"{mat.name}. Thick walls cause sink marks, internal voids, "
                    f"longer cycle times, and increased material cost."
                ),
                suggestion=(
                    f"Core out thick sections to achieve uniform {mat.min_wall_thickness_mm}-"
                    f"{mat.max_wall_thickness_mm}mm walls. Use ribs for structural "
                    f"strength instead of solid sections."
                ),
                affected_faces=affected_faces,
                measured_value=max_t,
                threshold_value=mat.max_wall_thickness_mm,
                unit="mm",
            ))

        return issues


class WallUniformityRule(DfmRule):
    rule_id = "wall_uniformity"
    name = "Wall Thickness Uniformity"
    category = Category.THICKNESS
    weight = 1.5

    VARIATION_WARNING_PCT = 25   # >25% variation
    VARIATION_CRITICAL_PCT = 50  # >50% variation

    def evaluate(self, context: AnalysisContext) -> list[DfmIssue]:
        issues = []
        ta = context.thickness_analysis

        if ta is None or not ta.samples or ta.mean_thickness == 0:
            return issues

        variation = ta.variation_pct

        if variation > self.VARIATION_CRITICAL_PCT:
            severity = Severity.CRITICAL
        elif variation > self.VARIATION_WARNING_PCT:
            severity = Severity.WARNING
        else:
            return issues  # Uniformity is acceptable

        issues.append(DfmIssue(
            rule_id=self.rule_id,
            severity=severity,
            category=self.category,
            title=f"Non-uniform wall thickness ({variation:.0f}% variation)",
            description=(
                f"Wall thickness varies from {ta.min_thickness:.2f}mm to "
                f"{ta.max_thickness:.2f}mm (mean: {ta.mean_thickness:.2f}mm, "
                f"variation: {variation:.0f}%). Non-uniform walls cause "
                f"differential shrinkage, warpage, and sink marks."
            ),
            suggestion=(
                f"Aim for uniform wall thickness within ±10% of nominal. "
                f"Use gradual transitions (3:1 taper ratio) where thickness "
                f"changes are necessary. Core out thick sections."
            ),
            measured_value=variation,
            threshold_value=self.VARIATION_WARNING_PCT,
            unit="%",
        ))

        return issues
