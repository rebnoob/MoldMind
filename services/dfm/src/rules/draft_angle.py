"""Feature-based draft angle check.

Groups faces by feature_type and applies per-feature draft thresholds:
- Main walls (cavity): 1.0°   → CRITICAL if missing
- Main walls (core):   0.5°   → WARNING if missing
- Bosses:              0.5°   → WARNING
- Holes:               0.25°  → WARNING
- Ribs:                0.5°   → WARNING
- Fillets, parting:    skipped

This matches how a mold engineer reviews a part: each feature type
has its own draft requirement based on where it sits in the mold.
"""

from collections import defaultdict
from .base import DfmRule, DfmIssue, Severity, Category, AnalysisContext
from ..dfm_config import DfmThresholds as T

# Feature types that need draft checks (others are skipped)
_DRAFT_FEATURES = {"main_wall", "boss", "hole", "rib", "minor_feature"}

# Human-readable names for reporting
_FEATURE_NAMES = {
    "main_wall": "main wall",
    "boss": "boss",
    "hole": "hole/pocket",
    "rib": "rib",
    "minor_feature": "minor feature",
}


class DraftAngleRule(DfmRule):
    rule_id = "draft_angle"
    name = "Draft Angle"
    category = Category.DRAFT
    weight = 2.0

    def evaluate(self, context: AnalysisContext) -> list[DfmIssue]:
        issues = []
        pd = context.pull_direction
        pull_str = f"[{pd[0]:.1f}, {pd[1]:.1f}, {pd[2]:.1f}]"

        # Group faces by feature type
        by_feature: dict[str, list] = defaultdict(list)
        skipped = 0

        for face in context.face_infos:
            if face.draft_angle_deg is None:
                skipped += 1
                continue
            if face.feature_type not in _DRAFT_FEATURES:
                skipped += 1
                continue
            by_feature[face.feature_type].append(face)

        # Check each feature group against its own threshold
        for feature_type, faces in by_feature.items():
            failing = []
            for f in faces:
                req = f.draft_requirement_deg
                if req is None:
                    continue
                if f.draft_angle_deg < req:
                    failing.append(f)

            if not failing:
                continue

            # Determine severity based on feature type and how bad the draft is
            zero_draft = [f for f in failing if f.draft_angle_deg < T.DRAFT_ZERO_DEG]
            low_draft = [f for f in failing if f.draft_angle_deg >= T.DRAFT_ZERO_DEG]

            name = _FEATURE_NAMES.get(feature_type, feature_type)
            req_deg = failing[0].draft_requirement_deg or 1.0

            # Group by mold side for better reporting
            cavity_faces = [f for f in failing if f.mold_side == "cavity"]
            core_faces = [f for f in failing if f.mold_side == "core"]
            other_faces = [f for f in failing if f.mold_side not in ("cavity", "core")]

            if zero_draft:
                # CRITICAL for main walls, WARNING for features
                severity = Severity.CRITICAL if feature_type == "main_wall" else Severity.WARNING
                worst = min(f.draft_angle_deg for f in zero_draft)

                side_info = ""
                if cavity_faces and not core_faces:
                    side_info = " (cavity side)"
                elif core_faces and not cavity_faces:
                    side_info = " (core side)"
                elif cavity_faces and core_faces:
                    side_info = f" ({len(cavity_faces)} cavity, {len(core_faces)} core)"

                issues.append(DfmIssue(
                    rule_id=self.rule_id,
                    severity=severity,
                    category=self.category,
                    title=f"No draft on {len(zero_draft)} {name}(s){side_info}",
                    description=(
                        f"{len(zero_draft)} {name} face(s) have < {T.DRAFT_ZERO_DEG}° draft "
                        f"(pull {pull_str}). Minimum for {name}: {req_deg}°. "
                        f"Part will stick in the {'cavity' if cavity_faces else 'core' if core_faces else 'mold'}."
                    ),
                    suggestion=f"Add ≥ {req_deg}° draft to {name} surfaces.",
                    affected_faces=[f.index for f in zero_draft],
                    measured_value=worst,
                    threshold_value=req_deg,
                    unit="°",
                    metadata={
                        "feature_type": feature_type,
                        "mold_sides": {"cavity": len(cavity_faces), "core": len(core_faces), "other": len(other_faces)},
                        "skipped_faces": skipped,
                    },
                ))

            if low_draft:
                issues.append(DfmIssue(
                    rule_id=self.rule_id,
                    severity=Severity.WARNING,
                    category=self.category,
                    title=f"Low draft on {len(low_draft)} {name}(s)",
                    description=(
                        f"{len(low_draft)} {name} face(s) have draft "
                        f"{min(f.draft_angle_deg for f in low_draft):.1f}–"
                        f"{max(f.draft_angle_deg for f in low_draft):.1f}° "
                        f"(recommended ≥ {req_deg}° for {name})."
                    ),
                    suggestion=f"Increase draft to ≥ {req_deg}°.",
                    affected_faces=[f.index for f in low_draft],
                    measured_value=min(f.draft_angle_deg for f in low_draft),
                    threshold_value=req_deg,
                    unit="°",
                    metadata={"feature_type": feature_type},
                ))

        return issues
