"""Sharp corners and abrupt section transitions.

Heuristic approach: detects likely missing fillets by analyzing the ratio
of planar faces to small curved faces (fillets). Does NOT perform
edge-level curvature analysis (deferred to Phase 2).

Conservative: only flags when the signal is strong.
"""

from .base import DfmRule, DfmIssue, Severity, Category, AnalysisContext
from ..dfm_config import DfmThresholds as T


class RadiiTransitionsRule(DfmRule):
    rule_id = "radii_transitions"
    name = "Radii & Transitions"
    category = Category.GEOMETRY
    weight = 0.5  # Low weight — heuristic-based

    def evaluate(self, context: AnalysisContext) -> list[DfmIssue]:
        issues = []
        faces = context.face_infos

        total = len(faces)
        if total < T.SHARP_CORNER_MIN_TOTAL_FACES:
            return issues  # Too few faces to assess

        planar = sum(1 for f in faces if f.surface_type == "planar")
        # Small curved faces are likely fillets or rounds
        fillet_like = sum(
            1 for f in faces
            if f.surface_type in ("cylindrical", "spherical", "torus")
            and f.area < T.SHARP_CORNER_MIN_FILLET_AREA_MM2
        )

        if planar >= T.SHARP_CORNER_MIN_PLANAR_FACES and fillet_like == 0:
            # Strong signal: many flat faces, zero small rounds
            issues.append(DfmIssue(
                rule_id=self.rule_id,
                severity=Severity.INFO,
                category=self.category,
                title="No fillets detected (heuristic)",
                description=(
                    f"Part has {planar} planar faces and no detected fillet surfaces. "
                    f"Sharp internal corners cause ~3× stress concentration, "
                    f"flow hesitation, and premature mold wear. "
                    f"(Note: this is a heuristic check — edge-level analysis not yet implemented.)"
                ),
                suggestion=(
                    "Add internal radii ≥ 0.5 mm (ideally 50–75% of wall thickness). "
                    "External radii ≥ 0.25 mm for mold life."
                ),
                measured_value=0,
                threshold_value=0.5,
                unit="mm",
            ))

        return issues
