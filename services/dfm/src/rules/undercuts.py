"""Undercut detection — bulk surfaces only.

Only reports undercuts on major_wall and minor_wall faces.
Tiny fillet/transition faces that happen to oppose the pull direction
are excluded — they're usually CAD artifacts, not real undercuts.
"""

from .base import DfmRule, DfmIssue, Severity, Category, AnalysisContext
from ..dfm_config import DfmThresholds as T

_RELEVANT_CLASSES = {"major_wall", "minor_wall", "undercut"}


class UndercutRule(DfmRule):
    rule_id = "undercut"
    name = "Undercuts"
    category = Category.UNDERCUT
    weight = 2.5

    def evaluate(self, context: AnalysisContext) -> list[DfmIssue]:
        issues = []

        # Only consider undercut faces that are significant surfaces
        undercut_faces = [
            f for f in context.face_infos
            if f.is_undercut
            and f.area >= T.UNDERCUT_MIN_AREA_MM2
            and f.face_class in _RELEVANT_CLASSES
        ]

        if not undercut_faces:
            return issues

        total_area = sum(f.area for f in context.face_infos if f.face_class in _RELEVANT_CLASSES)
        uc_area = sum(f.area for f in undercut_faces)
        area_pct = (uc_area / total_area * 100) if total_area > 0 else 0

        severity = Severity.CRITICAL if len(undercut_faces) > T.UNDERCUT_CRITICAL_COUNT else Severity.WARNING

        # Direction summary
        directions = []
        for f in undercut_faces:
            if f.normal:
                dirs = []
                if abs(f.normal[0]) > 0.3:
                    dirs.append("X+" if f.normal[0] > 0 else "X-")
                if abs(f.normal[1]) > 0.3:
                    dirs.append("Y+" if f.normal[1] > 0 else "Y-")
                if abs(f.normal[2]) > 0.3:
                    dirs.append("Z+" if f.normal[2] > 0 else "Z-")
                if dirs:
                    directions.append("/".join(dirs))
        dir_summary = ", ".join(sorted(set(directions))) if directions else "various"

        # Count excluded minor undercuts for transparency
        excluded = sum(1 for f in context.face_infos
                       if f.is_undercut and f.face_class not in _RELEVANT_CLASSES)

        desc = (
            f"{len(undercut_faces)} significant undercut face(s) "
            f"({uc_area:.1f} mm², {area_pct:.1f}% of surface). "
            f"Direction(s): {dir_summary}. "
            f"Each needs a side action ({T.UNDERCUT_COST_PER_ACTION})."
        )
        if excluded > 0:
            desc += f" ({excluded} minor fillet/transition faces excluded.)"

        issues.append(DfmIssue(
            rule_id=self.rule_id,
            severity=severity,
            category=self.category,
            title=f"{len(undercut_faces)} undercut(s) detected",
            description=desc,
            suggestion=(
                "Options: (1) Change pull direction. "
                "(2) Redesign features. "
                "(3) Accept side actions if required."
            ),
            affected_faces=[f.index for f in undercut_faces],
            measured_value=len(undercut_faces),
            threshold_value=0,
            unit="count",
        ))

        return issues
