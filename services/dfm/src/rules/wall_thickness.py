"""Wall thickness checks — bulk-surface only.

Filters thickness samples to major_wall and minor_wall faces.
Fillets, transitions, and other minor geometry are excluded
so they don't pollute min/max/variation metrics.
"""

from collections import defaultdict
from .base import DfmRule, DfmIssue, Severity, Category, AnalysisContext
from ..dfm_config import DfmThresholds as T

# Face classes considered "real walls" for thickness analysis
_WALL_CLASSES = {"major_wall", "minor_wall"}


def _wall_face_indices(context: AnalysisContext) -> set[int]:
    """Return face indices that are major or minor walls."""
    return {f.index for f in context.face_infos if f.face_class in _WALL_CLASSES}


class WallThicknessRule(DfmRule):
    """Check absolute wall thickness on major surfaces only."""
    rule_id = "wall_thickness"
    name = "Wall Thickness"
    category = Category.THICKNESS
    weight = 2.0

    def evaluate(self, context: AnalysisContext) -> list[DfmIssue]:
        issues = []
        ta = context.thickness_analysis
        if ta is None or not ta.samples:
            return issues

        wall_faces = _wall_face_indices(context)
        # Filter samples to wall faces only
        samples = [s for s in ta.samples if s.face_index in wall_faces]
        if not samples:
            return issues

        mat = context.material

        thin = [s for s in samples if s.thickness < mat.min_wall_thickness_mm]
        if thin:
            min_t = min(s.thickness for s in thin)
            faces = sorted(set(s.face_index for s in thin))
            issues.append(DfmIssue(
                rule_id=self.rule_id,
                severity=Severity.CRITICAL if min_t < mat.min_wall_thickness_mm * 0.5 else Severity.WARNING,
                category=self.category,
                title=f"Thin wall ({min_t:.2f} mm)",
                description=(
                    f"Min wall {min_t:.2f} mm on major surfaces < recommended "
                    f"{mat.min_wall_thickness_mm} mm for {mat.name}."
                ),
                suggestion=f"Increase to ≥ {mat.min_wall_thickness_mm} mm.",
                affected_faces=faces,
                measured_value=min_t,
                threshold_value=mat.min_wall_thickness_mm,
                unit="mm",
            ))

        thick = [s for s in samples if s.thickness > mat.max_wall_thickness_mm]
        if thick:
            max_t = max(s.thickness for s in thick)
            faces = sorted(set(s.face_index for s in thick))
            issues.append(DfmIssue(
                rule_id=self.rule_id,
                severity=Severity.WARNING,
                category=self.category,
                title=f"Thick wall ({max_t:.2f} mm)",
                description=(
                    f"Max wall {max_t:.2f} mm on major surfaces > recommended "
                    f"{mat.max_wall_thickness_mm} mm."
                ),
                suggestion="Core out thick sections; use ribs for strength.",
                affected_faces=faces,
                measured_value=max_t,
                threshold_value=mat.max_wall_thickness_mm,
                unit="mm",
            ))

        return issues


class WallUniformityRule(DfmRule):
    """Check wall thickness variation across major surfaces only."""
    rule_id = "wall_uniformity"
    name = "Wall Uniformity"
    category = Category.THICKNESS
    weight = 1.5

    def evaluate(self, context: AnalysisContext) -> list[DfmIssue]:
        issues = []
        ta = context.thickness_analysis
        if ta is None or not ta.samples:
            return issues

        wall_faces = _wall_face_indices(context)
        samples = [s for s in ta.samples if s.face_index in wall_faces]
        thicknesses = [s.thickness for s in samples if s.thickness > 0]
        if len(thicknesses) < 3:
            return issues

        import numpy as np
        min_t = min(thicknesses)
        max_t = max(thicknesses)
        mean_t = float(np.mean(thicknesses))
        if mean_t == 0:
            return issues

        var = (max_t - min_t) / mean_t * 100
        if var < T.WALL_VARIATION_WARNING_PCT:
            return issues

        severity = Severity.CRITICAL if var > T.WALL_VARIATION_CRITICAL_PCT else Severity.WARNING

        issues.append(DfmIssue(
            rule_id=self.rule_id,
            severity=severity,
            category=self.category,
            title=f"Non-uniform wall ({var:.0f}% variation)",
            description=(
                f"Major-surface thickness ranges from {min_t:.2f} to {max_t:.2f} mm "
                f"(mean {mean_t:.2f} mm). Differential shrinkage causes warpage."
            ),
            suggestion="Aim for ±10% of nominal. Use gradual 3:1 taper transitions.",
            measured_value=var,
            threshold_value=T.WALL_VARIATION_WARNING_PCT,
            unit="%",
        ))
        return issues


class WallTransitionRule(DfmRule):
    """Detect abrupt thick-to-thin transitions between major surfaces."""
    rule_id = "wall_transition"
    name = "Thickness Transitions"
    category = Category.THICKNESS
    weight = 1.0

    def evaluate(self, context: AnalysisContext) -> list[DfmIssue]:
        issues = []
        ta = context.thickness_analysis
        if ta is None or len(ta.samples) < 5:
            return issues

        wall_faces = _wall_face_indices(context)
        samples = [s for s in ta.samples if s.face_index in wall_faces]
        if len(samples) < 5:
            return issues

        # Per-face average thickness (major surfaces only)
        face_samples = defaultdict(list)
        for s in samples:
            face_samples[s.face_index].append(s.thickness)

        if len(face_samples) < 2:
            return issues

        import numpy as np
        all_t = [s.thickness for s in samples]
        nominal = float(np.mean(all_t))
        if nominal == 0:
            return issues

        transition_faces = []
        for fidx, thicknesses in face_samples.items():
            avg = sum(thicknesses) / len(thicknesses)
            ratio = max(avg / nominal, nominal / avg)
            if ratio > T.WALL_TRANSITION_RATIO:
                transition_faces.append(fidx)

        if transition_faces:
            issues.append(DfmIssue(
                rule_id=self.rule_id,
                severity=Severity.WARNING,
                category=self.category,
                title=f"Abrupt thickness transition ({len(transition_faces)} region(s))",
                description=(
                    f"{len(transition_faces)} major surface(s) have local thickness "
                    f"> {T.WALL_TRANSITION_RATIO:.0f}× the nominal {nominal:.2f} mm."
                ),
                suggestion="Use gradual tapers (3:1 ratio) between thick and thin sections.",
                affected_faces=sorted(transition_faces),
                measured_value=T.WALL_TRANSITION_RATIO,
                threshold_value=T.WALL_TRANSITION_RATIO,
                unit="×",
            ))

        return issues
