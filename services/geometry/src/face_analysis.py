"""Analyze individual B-Rep faces: normals, draft angles, surface types."""

import logging
import math
import numpy as np

logger = logging.getLogger(__name__)


class FaceInfo:
    """Analysis results for a single B-Rep face."""

    def __init__(self, index: int, surface_type: str, area: float,
                 normal: list[float] | None, draft_angle_deg: float | None,
                 is_undercut: bool):
        self.index = index
        self.surface_type = surface_type  # planar, cylindrical, conical, spherical, bspline, other
        self.area = area                  # mm²
        self.normal = normal              # average normal vector [x,y,z] (None for curved)
        self.draft_angle_deg = draft_angle_deg  # angle relative to pull direction
        self.is_undercut = is_undercut


def analyze_faces(shape, pull_direction: list[float]) -> list[FaceInfo]:
    """Analyze all faces of a shape relative to a pull direction.

    Args:
        shape: OpenCascade TopoDS_Shape
        pull_direction: Unit vector [x, y, z] for mold pull direction

    Returns:
        List of FaceInfo objects, one per B-Rep face
    """
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import (
        GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone,
        GeomAbs_Sphere, GeomAbs_BSplineSurface, GeomAbs_Torus,
    )
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.gp import gp_Dir, gp_Vec

    pull = np.array(pull_direction, dtype=np.float64)
    pull = pull / np.linalg.norm(pull)
    pull_dir = gp_Dir(float(pull[0]), float(pull[1]), float(pull[2]))

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
        face = explorer.Current()
        adaptor = BRepAdaptor_Surface(face)
        surf_type_enum = adaptor.GetType()
        surface_type = surface_type_map.get(surf_type_enum, "other")

        # Face area
        props = GProp_GProps()
        brepgprop.SurfaceProperties(face, props)
        area = abs(props.Mass())

        # Draft angle analysis
        normal = None
        draft_angle = None
        is_undercut = False

        if surface_type == "planar":
            # Planar face: single normal
            plane = adaptor.Plane()
            n = plane.Axis().Direction()
            normal = [n.X(), n.Y(), n.Z()]
            norm_vec = np.array(normal)

            # Draft angle = 90° - angle between normal and pull direction
            cos_angle = abs(np.dot(norm_vec, pull))
            angle_from_pull = math.degrees(math.acos(min(cos_angle, 1.0)))
            draft_angle = 90.0 - angle_from_pull

            # Undercut: face normal points away from pull AND face is not perpendicular
            dot = np.dot(norm_vec, pull)
            if dot < -0.01 and abs(draft_angle) > 5.0:
                is_undercut = True

        elif surface_type == "cylindrical":
            # Cylindrical face: draft angle is angle between cylinder axis and pull
            cyl = adaptor.Cylinder()
            axis = cyl.Axis().Direction()
            axis_vec = np.array([axis.X(), axis.Y(), axis.Z()])

            cos_angle = abs(np.dot(axis_vec, pull))
            angle_from_pull = math.degrees(math.acos(min(cos_angle, 1.0)))

            # For cylinders, if axis is parallel to pull → 0° draft (bad for molding)
            # If axis is perpendicular to pull → the cylinder wall has draft
            draft_angle = angle_from_pull  # Simplified; actual draft depends on position
            normal = [axis.X(), axis.Y(), axis.Z()]

        results.append(FaceInfo(
            index=face_idx,
            surface_type=surface_type,
            area=area,
            normal=normal,
            draft_angle_deg=draft_angle,
            is_undercut=is_undercut,
        ))

        face_idx += 1
        explorer.Next()

    logger.info(f"Analyzed {face_idx} faces. Undercuts: {sum(1 for f in results if f.is_undercut)}")
    return results
