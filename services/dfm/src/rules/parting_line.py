"""Parting-line feasibility — area-weighted, bulk surfaces only.

Uses face_class to focus on major/minor walls. Tiny fillets and
transition faces are excluded from the moldability ratio so they
don't artificially lower the score.
"""

from .base import DfmRule, DfmIssue, Severity, Category, AnalysisContext
from ..dfm_config import DfmThresholds as T

# Face classes that count toward the moldability ratio
_SIGNIFICANT = {"major_wall", "minor_wall", "parting", "undercut"}


class PartingLineRule(DfmRule):
    rule_id = "parting_line"
    name = "Parting Line Feasibility"
    category = Category.PARTING
    weight = 1.5

    def evaluate(self, context: AnalysisContext) -> list[DfmIssue]:
        issues = []
        faces = context.face_infos

        if not faces:
            return issues

        # Only consider significant faces (ignore fillets, transitions, other)
        sig_faces = [f for f in faces if f.face_class in _SIGNIFICANT]
        if not sig_faces:
            return issues

        total_area = sum(f.area for f in sig_faces)
        if total_area == 0:
            return issues

        parting_area = sum(f.area for f in sig_faces if f.face_class == "parting")
        wall_area = sum(f.area for f in sig_faces if f.face_class in ("major_wall", "minor_wall"))
        undercut_area = sum(f.area for f in sig_faces if f.face_class == "undercut")
        undercut_count = sum(1 for f in sig_faces if f.face_class == "undercut")

        moldable_area = parting_area + wall_area
        ratio = moldable_area / total_area if total_area > 0 else 0

        excluded = len(faces) - len(sig_faces)

        if ratio >= T.PARTING_STRAIGHT_PULL_GOOD and undercut_count <= T.PARTING_MAX_UNDERCUTS_GOOD:
            severity = Severity.INFO
            title = "Straight-pull moldable"
            desc = (
                f"{ratio:.0%} of significant surface area is moldable in a straight pull. "
                f"Good candidate for a simple 2-plate mold."
            )
        elif ratio >= T.PARTING_STRAIGHT_PULL_REVIEW or undercut_count <= T.PARTING_MAX_UNDERCUTS_REVIEW:
            severity = Severity.WARNING
            title = f"Needs review — {undercut_count} undercut(s)"
            desc = (
                f"{ratio:.0%} moldable, {undercut_count} undercut(s) "
                f"({undercut_area:.0f} mm²). May need side action(s)."
            )
        else:
            severity = Severity.CRITICAL
            title = f"Complex mold — {undercut_count} undercut(s)"
            desc = (
                f"Only {ratio:.0%} of significant area is straight-pull moldable "
                f"with {undercut_count} undercut(s)."
            )

        if excluded > 0:
            desc += f" ({excluded} fillet/transition faces excluded from ratio.)"

        undercut_face_indices = [f.index for f in sig_faces if f.face_class == "undercut"]

        issues.append(DfmIssue(
            rule_id=self.rule_id,
            severity=severity,
            category=self.category,
            title=title,
            description=desc,
            suggestion=(
                "To improve: (1) Change pull direction. "
                "(2) Eliminate undercuts. "
                "(3) Confirm side actions are feasible."
            ),
            affected_faces=undercut_face_indices if undercut_face_indices else None,
            measured_value=round(ratio * 100, 1),
            threshold_value=round(T.PARTING_STRAIGHT_PULL_GOOD * 100, 1),
            unit="%",
            metadata={"undercuts": undercut_count, "excluded_faces": excluded},
        ))

        return issues
