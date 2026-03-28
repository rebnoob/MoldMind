"""Draft angle analysis rule.

Draft angle is the angle between a mold face and the pull direction.
Insufficient draft causes:
- Part sticking in the mold
- Ejection marks / surface damage
- Increased cycle time
- Mold wear

Industry standards:
- Minimum 0.5° for smooth untextured surfaces
- Minimum 1.0° general purpose
- Minimum 1.5°+ per 0.001" texture depth (textured surfaces need more)
- 2-3° is ideal for most applications
"""

from .base import DfmRule, DfmIssue, Severity, Category, AnalysisContext


class DraftAngleRule(DfmRule):
    rule_id = "draft_angle"
    name = "Draft Angle"
    category = Category.DRAFT
    weight = 2.0  # High impact rule

    # Thresholds (degrees)
    CRITICAL_THRESHOLD = 0.25  # Essentially zero draft
    WARNING_THRESHOLD_FACTOR = 1.0  # Factor of material's recommended draft

    def evaluate(self, context: AnalysisContext) -> list[DfmIssue]:
        issues = []
        min_draft = context.material.recommended_draft_deg

        zero_draft_faces = []
        low_draft_faces = []

        for face in context.face_infos:
            if face.draft_angle_deg is None:
                continue  # Skip faces where draft couldn't be computed (freeform)

            if face.surface_type == "planar":
                # Faces perpendicular to pull direction (top/bottom) don't need draft
                if abs(face.draft_angle_deg) > 85:
                    continue

            if abs(face.draft_angle_deg) < self.CRITICAL_THRESHOLD:
                zero_draft_faces.append(face)
            elif abs(face.draft_angle_deg) < min_draft:
                low_draft_faces.append(face)

        if zero_draft_faces:
            issues.append(DfmIssue(
                rule_id=self.rule_id,
                severity=Severity.CRITICAL,
                category=self.category,
                title=f"Zero draft on {len(zero_draft_faces)} face(s)",
                description=(
                    f"{len(zero_draft_faces)} face(s) have essentially no draft angle "
                    f"(< {self.CRITICAL_THRESHOLD}°). These faces will lock the part in "
                    f"the mold, preventing ejection without damage."
                ),
                suggestion=(
                    f"Add at least {min_draft}° of draft to all faces parallel to the "
                    f"pull direction. For textured surfaces, add additional draft "
                    f"(~1.5° per 0.001\" texture depth)."
                ),
                affected_faces=[f.index for f in zero_draft_faces],
                measured_value=min(f.draft_angle_deg for f in zero_draft_faces),
                threshold_value=min_draft,
                unit="degrees",
            ))

        if low_draft_faces:
            issues.append(DfmIssue(
                rule_id=self.rule_id,
                severity=Severity.WARNING,
                category=self.category,
                title=f"Insufficient draft on {len(low_draft_faces)} face(s)",
                description=(
                    f"{len(low_draft_faces)} face(s) have draft angle below the "
                    f"recommended minimum of {min_draft}° for {context.material.name}. "
                    f"This may cause ejection difficulty and surface marks."
                ),
                suggestion=(
                    f"Increase draft angle to at least {min_draft}°. "
                    f"Consider {min_draft * 2}° for better mold life and part quality."
                ),
                affected_faces=[f.index for f in low_draft_faces],
                measured_value=min(f.draft_angle_deg for f in low_draft_faces),
                threshold_value=min_draft,
                unit="degrees",
            ))

        return issues
