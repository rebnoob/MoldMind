"""Base classes for DFM rules.

Every rule follows the same contract:
1. Receives geometry analysis data (face info, thickness data, etc.)
2. Evaluates conditions
3. Returns zero or more DfmIssue objects

Rules are deterministic, explainable, and configurable per material.
"""

from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


class Severity(str, Enum):
    CRITICAL = "critical"  # Will prevent successful molding
    WARNING = "warning"    # Will cause quality issues or increase cost
    INFO = "info"          # Suggestion for improvement


class Category(str, Enum):
    DRAFT = "draft"
    THICKNESS = "thickness"
    UNDERCUT = "undercut"
    GEOMETRY = "geometry"
    GATE = "gate"
    EJECTION = "ejection"
    COOLING = "cooling"


@dataclass
class DfmIssue:
    """A single DFM issue found by a rule."""
    rule_id: str
    severity: Severity
    category: Category
    title: str
    description: str
    suggestion: str | None = None
    affected_faces: list[int] | None = None
    affected_region: dict | None = None  # bounding box
    measured_value: float | None = None
    threshold_value: float | None = None
    unit: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class MaterialParams:
    """Material-specific parameters for DFM rules."""
    min_wall_thickness_mm: float = 0.8
    max_wall_thickness_mm: float = 4.0
    recommended_draft_deg: float = 1.0
    shrinkage_pct: float = 1.0
    name: str = "Generic Thermoplastic"

    @classmethod
    def from_dict(cls, data: dict) -> "MaterialParams":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class DfmRule(ABC):
    """Base class for all DFM rules."""

    rule_id: str  # Unique identifier, e.g., "draft_angle"
    name: str     # Human-readable name
    category: Category
    weight: float = 1.0  # Weight in composite score (higher = more impact)

    @abstractmethod
    def evaluate(self, context: "AnalysisContext") -> list[DfmIssue]:
        """Evaluate this rule and return any issues found."""
        ...


@dataclass
class AnalysisContext:
    """All data available to DFM rules during evaluation.

    Populated by the DFM engine before rules are evaluated.
    """
    # Geometry analysis results (from geometry service)
    face_infos: list = field(default_factory=list)  # list[FaceInfo]
    thickness_analysis: object | None = None         # ThicknessAnalysis
    # edge_infos: list = field(default_factory=list)

    # Parameters
    pull_direction: list[float] = field(default_factory=lambda: [0, 0, 1])
    material: MaterialParams = field(default_factory=MaterialParams)

    # Raw shape reference (for rules that need direct geometry access)
    shape: object | None = None
