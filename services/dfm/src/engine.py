"""DFM Analysis Engine.

Orchestrates geometry analysis and rule evaluation to produce
a complete moldability assessment.
"""

import logging
import time
from dataclasses import dataclass

from .rules import ALL_RULES, DfmIssue, Severity, AnalysisContext, MaterialParams

logger = logging.getLogger(__name__)


@dataclass
class DfmAnalysisResult:
    """Complete DFM analysis output."""
    moldability_score: int          # 0-100 (100 = perfectly moldable)
    verdict: str                    # PASS / REVIEW / FAIL
    verdict_summary: str            # One-sentence human-readable summary
    pull_direction: list[float]
    issues: list[DfmIssue]
    summary: dict                   # {critical: N, warning: N, info: N}
    metadata: dict                  # timing, rule versions, etc.


class DfmEngine:
    """Main DFM analysis engine.

    Usage:
        engine = DfmEngine(material_id="abs_generic")
        result = engine.analyze(shape, pull_direction=[0, 0, 1])
    """

    def __init__(self, material_params: MaterialParams | None = None):
        self.material = material_params or MaterialParams()
        self.rules = [rule_cls() for rule_cls in ALL_RULES]

    def analyze(self, shape, pull_direction: list[float]) -> DfmAnalysisResult:
        """Run full DFM analysis on a shape.

        Args:
            shape: OpenCascade TopoDS_Shape
            pull_direction: Mold pull direction [x, y, z]

        Returns:
            DfmAnalysisResult with score, issues, and metadata
        """
        start_time = time.time()

        # Step 1: Geometry analysis
        logger.info("Running face analysis...")
        from services.geometry.src.face_analysis import analyze_faces
        face_infos = analyze_faces(shape, pull_direction)

        logger.info("Running wall thickness analysis...")
        from services.geometry.src.wall_thickness import analyze_wall_thickness
        thickness = analyze_wall_thickness(shape)

        # Step 2: Build analysis context
        context = AnalysisContext(
            face_infos=face_infos,
            thickness_analysis=thickness,
            pull_direction=pull_direction,
            material=self.material,
            shape=shape,
        )

        # Step 3: Evaluate all rules
        all_issues = []
        rule_timings = {}

        for rule in self.rules:
            rule_start = time.time()
            try:
                issues = rule.evaluate(context)
                all_issues.extend(issues)
                rule_timings[rule.rule_id] = time.time() - rule_start
            except Exception as e:
                logger.error(f"Rule {rule.rule_id} failed: {e}")
                rule_timings[rule.rule_id] = -1  # Mark as failed

        # Step 4: Compute moldability score
        score = self._compute_score(all_issues)

        # Step 5: Build summary
        summary = {
            "critical": sum(1 for i in all_issues if i.severity == Severity.CRITICAL),
            "warning": sum(1 for i in all_issues if i.severity == Severity.WARNING),
            "info": sum(1 for i in all_issues if i.severity == Severity.INFO),
            "total_faces": len(face_infos),
            "faces_with_issues": len(set(
                f for i in all_issues if i.affected_faces for f in i.affected_faces
            )),
        }

        total_time = time.time() - start_time
        metadata = {
            "analysis_time_s": round(total_time, 2),
            "rule_timings": rule_timings,
            "rules_evaluated": len(self.rules),
            "engine_version": "0.1.0",
        }

        logger.info(
            f"DFM analysis complete: score={score}, "
            f"issues={summary['critical']}C/{summary['warning']}W/{summary['info']}I, "
            f"time={total_time:.1f}s"
        )

        verdict, verdict_summary = self._compute_verdict(score, summary)

        return DfmAnalysisResult(
            moldability_score=score,
            verdict=verdict,
            verdict_summary=verdict_summary,
            pull_direction=pull_direction,
            issues=all_issues,
            summary=summary,
            metadata=metadata,
        )

    def analyze_mock(self, part_id: str, pull_direction: list[float]) -> DfmAnalysisResult:
        """Run DFM analysis using mock geometry data (no OpenCascade required).

        Uses seeded random geometry so each part_id gets consistent but unique results.
        The DFM rules evaluation is real — only the geometry input is mocked.
        """
        start_time = time.time()

        from services.geometry.src.mock_geometry import mock_analyze_faces, mock_analyze_wall_thickness

        logger.info(f"Running mock face analysis for part {part_id}...")
        face_infos = mock_analyze_faces(part_id, pull_direction)

        logger.info(f"Running mock wall thickness for part {part_id}...")
        thickness = mock_analyze_wall_thickness(part_id)

        context = AnalysisContext(
            face_infos=face_infos,
            thickness_analysis=thickness,
            pull_direction=pull_direction,
            material=self.material,
            shape=None,
        )

        all_issues = []
        rule_timings = {}

        for rule in self.rules:
            rule_start = time.time()
            try:
                issues = rule.evaluate(context)
                all_issues.extend(issues)
                rule_timings[rule.rule_id] = time.time() - rule_start
            except Exception as e:
                logger.error(f"Rule {rule.rule_id} failed: {e}")
                rule_timings[rule.rule_id] = -1

        score = self._compute_score(all_issues)

        summary = {
            "critical": sum(1 for i in all_issues if i.severity == Severity.CRITICAL),
            "warning": sum(1 for i in all_issues if i.severity == Severity.WARNING),
            "info": sum(1 for i in all_issues if i.severity == Severity.INFO),
            "total_faces": len(face_infos),
            "faces_with_issues": len(set(
                f for i in all_issues if i.affected_faces for f in i.affected_faces
            )),
        }

        total_time = time.time() - start_time
        metadata = {
            "analysis_time_s": round(total_time, 2),
            "rule_timings": rule_timings,
            "rules_evaluated": len(self.rules),
            "engine_version": "0.1.0-mock",
            "mock": True,
        }

        logger.info(
            f"Mock DFM analysis complete: score={score}, "
            f"issues={summary['critical']}C/{summary['warning']}W/{summary['info']}I"
        )

        verdict, verdict_summary = self._compute_verdict(score, summary)

        return DfmAnalysisResult(
            moldability_score=score,
            verdict=verdict,
            verdict_summary=verdict_summary,
            pull_direction=pull_direction,
            issues=all_issues,
            summary=summary,
            metadata=metadata,
        )

    def _compute_score(self, issues: list[DfmIssue]) -> int:
        """Compute composite moldability score from issues.

        Scoring approach:
        - Start at 100
        - Deduct points based on severity and rule weight
        - Critical issues: heavy deduction
        - Warnings: moderate deduction
        - Info: minimal deduction
        - Floor at 0
        """
        score = 100.0

        # Build weight lookup
        rule_weights = {rule.rule_id: rule.weight for rule in self.rules}

        for issue in issues:
            weight = rule_weights.get(issue.rule_id, 1.0)

            if issue.severity == Severity.CRITICAL:
                score -= 15 * weight
            elif issue.severity == Severity.WARNING:
                score -= 7 * weight
            elif issue.severity == Severity.INFO:
                score -= 2 * weight

        return max(0, min(100, round(score)))

    @staticmethod
    def _compute_verdict(score: int, summary: dict) -> tuple[str, str]:
        """Determine overall PASS / REVIEW / FAIL verdict.

        Returns (verdict, summary_text).
        """
        from .dfm_config import DfmThresholds as T

        crits = summary.get("critical", 0)
        warns = summary.get("warning", 0)

        if crits > 0 or score < T.VERDICT_FAIL_SCORE:
            verdict = "FAIL"
            summary_text = (
                f"Part has {crits} critical issue(s) that must be resolved before molding."
            )
        elif warns > 0 or score < T.VERDICT_REVIEW_SCORE:
            verdict = "REVIEW"
            summary_text = (
                f"Part is likely moldable but has {warns} issue(s) to review."
            )
        else:
            verdict = "PASS"
            summary_text = "Part appears to be a good injection molding candidate."

        return verdict, summary_text
