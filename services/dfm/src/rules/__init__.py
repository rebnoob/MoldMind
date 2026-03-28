from .base import DfmRule, DfmIssue, Severity, Category
from .draft_angle import DraftAngleRule
from .wall_thickness import WallThicknessRule, WallUniformityRule
from .undercuts import UndercutRule
from .sharp_corners import SharpCornerRule

ALL_RULES: list[type[DfmRule]] = [
    DraftAngleRule,
    WallThicknessRule,
    WallUniformityRule,
    UndercutRule,
    SharpCornerRule,
]

__all__ = ["DfmRule", "DfmIssue", "Severity", "Category", "ALL_RULES"]
