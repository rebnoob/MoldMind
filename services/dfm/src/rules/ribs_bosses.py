"""Rib and boss feature detection — bulk surfaces only.

Only considers major_wall and minor_wall faces for boss/rib candidates.
Fillets, transitions, and other tiny geometry are excluded.
"""

import math
from .base import DfmRule, DfmIssue, Severity, Category, AnalysisContext
from ..dfm_config import DfmThresholds as T

_WALL_CLASSES = {"major_wall", "minor_wall"}


class RibsBossesRule(DfmRule):
    rule_id = "ribs_bosses"
    name = "Ribs & Bosses"
    category = Category.RIB_BOSS
    weight = 1.0

    def evaluate(self, context: AnalysisContext) -> list[DfmIssue]:
        issues = []
        faces = context.face_infos
        ta = context.thickness_analysis

        if not faces:
            return issues

        # --- Boss detection: cylindrical major/minor wall faces ---
        boss_faces = [
            f for f in faces
            if f.surface_type == "cylindrical"
            and not f.is_undercut
            and not f.is_parting_face
            and f.face_class in _WALL_CLASSES
            and f.draft_angle_deg is not None
        ]

        if boss_faces and ta and ta.mean_thickness > 0:
            nominal = ta.mean_thickness
            sink_risk_bosses = []

            for f in boss_faces:
                est_height = nominal * 2
                est_radius = f.area / (2 * math.pi * est_height) if est_height > 0 else 0
                if est_radius < T.BOSS_MAX_RADIUS_MM and est_radius > nominal * T.BOSS_SINK_WALL_RATIO:
                    sink_risk_bosses.append(f)

            if sink_risk_bosses:
                issues.append(DfmIssue(
                    rule_id=self.rule_id,
                    severity=Severity.WARNING,
                    category=self.category,
                    title=f"{len(sink_risk_bosses)} boss(es) — possible sink risk",
                    description=(
                        f"{len(sink_risk_bosses)} cylindrical feature(s) may cause sink marks. "
                        f"Estimated radius > {T.BOSS_SINK_WALL_RATIO:.0%} of nominal wall "
                        f"({ta.mean_thickness:.2f} mm). (Heuristic.)"
                    ),
                    suggestion="Core out boss centers. Boss wall should be 50–60% of adjacent wall.",
                    affected_faces=[f.index for f in sink_risk_bosses],
                    measured_value=len(sink_risk_bosses),
                    threshold_value=0,
                    unit="count",
                ))

        # --- Rib detection: narrow planar wall faces (major/minor only) ---
        wall_faces = [f for f in faces if f.face_class in _WALL_CLASSES]
        if len(wall_faces) > 4:
            max_area = max(f.area for f in wall_faces)
            rib_threshold = max_area * T.RIB_MAX_AREA_RATIO

            rib_candidates = [
                f for f in wall_faces
                if f.surface_type == "planar"
                and not f.is_parting_face
                and not f.is_undercut
                and f.draft_angle_deg is not None
                and 0 < f.area < rib_threshold
                and f.area > 1.0  # ignore sub-1mm² faces
            ]

            if rib_candidates and ta and ta.mean_thickness > 0:
                issues.append(DfmIssue(
                    rule_id=self.rule_id,
                    severity=Severity.INFO,
                    category=self.category,
                    title=f"{len(rib_candidates)} possible rib feature(s)",
                    description=(
                        f"{len(rib_candidates)} narrow wall face(s) may be ribs. "
                        f"Rib thickness should be 50–75% of adjacent wall "
                        f"({ta.mean_thickness * 0.5:.2f}–{ta.mean_thickness * 0.75:.2f} mm). "
                        f"(Heuristic.)"
                    ),
                    suggestion="Ensure rib base ≤ 75% of wall. Add draft 0.5–1°/side. Fillet junctions ≥ 0.5 mm.",
                    affected_faces=[f.index for f in rib_candidates],
                    measured_value=len(rib_candidates),
                    threshold_value=0,
                    unit="count",
                ))

        return issues
