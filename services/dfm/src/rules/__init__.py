from .base import DfmRule, DfmIssue, Severity, Category, AnalysisContext, MaterialParams
from .draft_angle import DraftAngleRule
from .wall_thickness import WallThicknessRule, WallUniformityRule, WallTransitionRule
from .undercuts import UndercutRule
from .radii_transitions import RadiiTransitionsRule
from .parting_line import PartingLineRule
from .ribs_bosses import RibsBossesRule

ALL_RULES: list[type[DfmRule]] = [
    DraftAngleRule,
    WallThicknessRule,
    WallUniformityRule,
    WallTransitionRule,
    UndercutRule,
    RadiiTransitionsRule,
    PartingLineRule,
    RibsBossesRule,
]

__all__ = ["DfmRule", "DfmIssue", "Severity", "Category", "AnalysisContext", "MaterialParams", "ALL_RULES"]
