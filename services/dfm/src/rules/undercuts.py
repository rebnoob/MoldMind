"""Undercut detection rule.

Undercuts are features that prevent the part from being ejected in the pull direction.
They require side actions (sliders, lifters) which add cost and complexity.

Classification:
- Simple undercut: Can be resolved with a slider or lifter
- Complex undercut: May require collapsible cores or multi-stage ejection
- Through-hole perpendicular to pull: Standard side action
"""

from .base import DfmRule, DfmIssue, Severity, Category, AnalysisContext


class UndercutRule(DfmRule):
    rule_id = "undercut"
    name = "Undercut Detection"
    category = Category.UNDERCUT
    weight = 2.5  # Undercuts significantly impact tooling cost

    # Area threshold: ignore very small undercut faces (likely artifacts)
    MIN_FACE_AREA_MM2 = 0.5

    def evaluate(self, context: AnalysisContext) -> list[DfmIssue]:
        issues = []

        undercut_faces = [
            f for f in context.face_infos
            if f.is_undercut and f.area >= self.MIN_FACE_AREA_MM2
        ]

        if not undercut_faces:
            return issues

        total_undercut_area = sum(f.area for f in undercut_faces)
        total_part_area = sum(f.area for f in context.face_infos)
        area_pct = (total_undercut_area / total_part_area * 100) if total_part_area > 0 else 0

        # Many undercuts = complex tooling
        if len(undercut_faces) > 4:
            severity = Severity.CRITICAL
        elif len(undercut_faces) > 1:
            severity = Severity.WARNING
        else:
            severity = Severity.WARNING

        issues.append(DfmIssue(
            rule_id=self.rule_id,
            severity=severity,
            category=self.category,
            title=f"{len(undercut_faces)} undercut(s) detected",
            description=(
                f"Found {len(undercut_faces)} face(s) that form undercuts "
                f"relative to the current pull direction "
                f"({context.pull_direction}). "
                f"Total undercut area: {total_undercut_area:.1f}mm² "
                f"({area_pct:.1f}% of total surface). "
                f"Each undercut requires a side action (slider or lifter), "
                f"increasing mold cost by ~$2,000-$10,000+ per action."
            ),
            suggestion=(
                f"Consider: (1) Changing the pull direction to eliminate some undercuts. "
                f"(2) Redesigning features to remove undercuts where possible "
                f"(e.g., use snap fits that flex, or add shutoffs). "
                f"(3) If undercuts are required, ensure they are accessible "
                f"for standard slider mechanisms."
            ),
            affected_faces=[f.index for f in undercut_faces],
            measured_value=len(undercut_faces),
            threshold_value=0,
            unit="count",
        ))

        return issues
