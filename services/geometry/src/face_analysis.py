"""Analyze individual B-Rep faces: normals, draft angles, surface types.

Draft angle convention for injection molding:
- Pull direction = direction the part is ejected from the mold (typically Z+)
- Draft angle = angle between the face wall and the pull axis
  - 0° = wall exactly parallel to pull (no draft, bad)
  - 2° = slight taper (good)
  - 90° = face perpendicular to pull (top/bottom, doesn't need draft)
- Undercut = feature that prevents ejection in the pull direction
"""

import logging
import math
import numpy as np

logger = logging.getLogger(__name__)


class FaceInfo:
    """Analysis results for a single B-Rep face."""

    def __init__(self, index: int, surface_type: str, area: float,
                 normal: list[float] | None, draft_angle_deg: float | None,
                 is_undercut: bool, is_parting_face: bool = False):
        self.index = index
        self.surface_type = surface_type  # planar, cylindrical, conical, spherical, bspline, other
        self.area = area                  # mm²
        self.normal = normal              # outward normal vector [x,y,z]
        self.draft_angle_deg = draft_angle_deg  # angle of wall from pull axis (0=no draft)
        self.is_undercut = is_undercut
        self.is_parting_face = is_parting_face

        # Set by feature_recognition.classify_features():
        self.mold_side: str = "unknown"       # "core" | "cavity" | "parting" | "unknown"
        self.feature_type: str = "other"      # "main_wall" | "boss" | "hole" | "rib" | "fillet" | "parting" | "undercut" | "minor_feature" | "other"
        self.draft_requirement_deg: float | None = None  # feature-specific min draft

        # Legacy compat — face_class maps from feature_type
    @property
    def face_class(self) -> str:
        """Legacy accessor: maps feature_type to the old face_class values."""
        mapping = {
            "main_wall": "major_wall",
            "boss": "major_wall",
            "hole": "minor_wall",
            "rib": "minor_wall",
            "minor_feature": "minor_wall",
            "fillet": "fillet",
            "parting": "parting",
            "undercut": "undercut",
        }
        return mapping.get(self.feature_type, "other")


def analyze_faces(shape, pull_direction: list[float]) -> list[FaceInfo]:
    """Analyze all faces of a shape relative to a pull direction.

    Args:
        shape: OpenCascade TopoDS_Shape
        pull_direction: Unit vector [x, y, z] for mold pull direction

    Returns:
        List of FaceInfo objects, one per B-Rep face
    """
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.TopoDS import topods
    from OCC.Core.GeomAbs import (
        GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone,
        GeomAbs_Sphere, GeomAbs_BSplineSurface, GeomAbs_Torus,
    )
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.BRepGProp import brepgprop

    pull = np.array(pull_direction, dtype=np.float64)
    pull = pull / np.linalg.norm(pull)

    results = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    face_idx = 0

    surface_type_map = {
        GeomAbs_Plane: "planar",
        GeomAbs_Cylinder: "cylindrical",
        GeomAbs_Cone: "conical",
        GeomAbs_Sphere: "spherical",
        GeomAbs_BSplineSurface: "bspline",
        GeomAbs_Torus: "torus",
    }

    while explorer.More():
        face = topods.Face(explorer.Current())
        adaptor = BRepAdaptor_Surface(face)
        surf_type_enum = adaptor.GetType()
        surface_type = surface_type_map.get(surf_type_enum, "other")
        is_reversed = (face.Orientation() == TopAbs_REVERSED)

        # Face area
        props = GProp_GProps()
        brepgprop.SurfaceProperties(face, props)
        area = abs(props.Mass())

        normal = None
        draft_angle = None
        is_undercut = False
        is_parting_face = False

        if surface_type == "planar":
            plane = adaptor.Plane()
            n = plane.Axis().Direction()
            norm_vec = np.array([n.X(), n.Y(), n.Z()])

            # Flip normal for reversed faces to get TRUE outward normal
            if is_reversed:
                norm_vec = -norm_vec

            normal = norm_vec.tolist()

            # Signed dot product: how much the outward normal aligns with pull
            # +1 = normal points same as pull (top face)
            # -1 = normal points opposite pull (bottom face)
            #  0 = normal perpendicular to pull (vertical wall)
            dot = float(np.dot(norm_vec, pull))

            # Draft angle = angle between the wall and the pull axis
            # = asin(|dot|) — measures how far the face tilts from being parallel to pull
            draft_angle = math.degrees(math.asin(min(abs(dot), 1.0)))

            # Parting faces: nearly perpendicular to pull (top/bottom of part)
            # These don't need draft — they're the faces the mold halves press against
            if abs(dot) > 0.85:  # within ~32° of pull axis
                is_parting_face = True
                draft_angle = None  # not applicable

            # Undercut detection: face's outward normal has a significant component
            # opposing the pull direction, AND the face is not a parting face.
            # This means the mold can't release this face during ejection.
            elif dot < -0.05 and not is_parting_face:
                is_undercut = True

        elif surface_type == "cylindrical":
            cyl = adaptor.Cylinder()
            axis = cyl.Axis().Direction()
            axis_vec = np.array([axis.X(), axis.Y(), axis.Z()])

            # For a cylinder, the relevant question is: is the axis parallel to pull?
            # If axis ∥ pull: cylindrical wall is perpendicular to pull = no draft on cylinder walls
            #   (think: a vertical hole or boss — the walls have 0° draft)
            # If axis ⊥ pull: cylinder is a horizontal feature (through-hole = potential undercut)
            axis_dot_pull = abs(float(np.dot(axis_vec, pull)))

            if axis_dot_pull > 0.85:
                # Axis parallel to pull: cylindrical wall needs draft
                # Perfect cylinder = 0° draft (walls are exactly parallel to pull)
                # A cone would have positive draft
                draft_angle = 0.0  # Cylinders inherently have 0 draft
                normal = axis_vec.tolist()
            else:
                # Axis perpendicular or angled to pull: could be undercut (side hole)
                draft_angle = None  # complex, skip for now
                normal = axis_vec.tolist()
                if axis_dot_pull < 0.3:
                    is_undercut = True  # Side hole / horizontal cylinder

        elif surface_type == "conical":
            # Cones have built-in draft (the half-angle)
            cone = adaptor.Cone()
            half_angle = math.degrees(cone.SemiAngle())
            axis = cone.Axis().Direction()
            axis_vec = np.array([axis.X(), axis.Y(), axis.Z()])
            axis_dot_pull = abs(float(np.dot(axis_vec, pull)))

            if axis_dot_pull > 0.85:
                draft_angle = abs(half_angle)  # Cone half-angle IS the draft
            else:
                draft_angle = None
            normal = axis_vec.tolist()

        else:
            # Freeform surfaces (bspline, sphere, torus): skip draft analysis
            normal = None
            draft_angle = None
            is_undercut = False

        results.append(FaceInfo(
            index=face_idx,
            surface_type=surface_type,
            area=area,
            normal=normal,
            draft_angle_deg=draft_angle,
            is_undercut=is_undercut,
            is_parting_face=is_parting_face,
        ))

        face_idx += 1
        explorer.Next()

    # --- Feature recognition pass ---
    # Classify faces into molding features (main_wall, boss, hole, rib, fillet, etc.)
    # and determine core/cavity side. This replaces the old area-% classification.
    from services.geometry.src.feature_recognition import classify_features
    classify_features(results, pull_direction, shape)

    logger.info(f"Analyzed {face_idx} faces")

    return results
