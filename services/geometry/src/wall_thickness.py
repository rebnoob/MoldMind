"""Wall thickness analysis using ray-casting approach.

For each point on the outer surface, cast a ray inward along the surface normal.
The distance to the opposite wall is the local wall thickness.

This is an approximate method but works well for most injection molded parts.
More accurate methods (medial axis transform) are deferred to Phase 2.
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)


class ThicknessResult:
    """Wall thickness measurement at a sample point."""

    def __init__(self, point: list[float], thickness: float, face_index: int):
        self.point = point          # [x, y, z] sample location
        self.thickness = thickness  # mm
        self.face_index = face_index


class ThicknessAnalysis:
    """Aggregated wall thickness analysis results."""

    def __init__(self, samples: list[ThicknessResult]):
        self.samples = samples
        thicknesses = [s.thickness for s in samples if s.thickness > 0]
        self.min_thickness = min(thicknesses) if thicknesses else 0
        self.max_thickness = max(thicknesses) if thicknesses else 0
        self.mean_thickness = np.mean(thicknesses) if thicknesses else 0
        self.std_thickness = np.std(thicknesses) if thicknesses else 0
        self.uniformity = 1.0 - (self.std_thickness / self.mean_thickness) if self.mean_thickness > 0 else 0

    @property
    def variation_pct(self) -> float:
        """Percentage variation: (max - min) / mean * 100."""
        if self.mean_thickness == 0:
            return 0
        return (self.max_thickness - self.min_thickness) / self.mean_thickness * 100


def analyze_wall_thickness(shape, num_samples: int = 500) -> ThicknessAnalysis:
    """Analyze wall thickness by ray-casting from surface sample points.

    Strategy:
    1. Sample points on each face (using UV parametrization)
    2. At each point, cast a ray inward (opposite to surface normal)
    3. Find intersection with opposite wall
    4. Distance = wall thickness at that point

    Args:
        shape: OpenCascade TopoDS_Shape
        num_samples: Approximate number of sample points across entire part

    Returns:
        ThicknessAnalysis with per-point measurements and statistics
    """
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
    from OCC.Core.BRepIntCurveSurface import BRepIntCurveSurface_Inter
    from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Lin
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.BRepGProp import brepgprop

    # Calculate total surface area for proportional sampling
    total_area = 0
    faces = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    face_idx = 0
    while explorer.More():
        face = explorer.Current()
        props = GProp_GProps()
        brepgprop.SurfaceProperties(face, props)
        area = abs(props.Mass())
        faces.append((face, area, face_idx))
        total_area += area
        face_idx += 1
        explorer.Next()

    results = []

    for face, area, fidx in faces:
        # Proportional number of samples per face
        n = max(1, int(num_samples * area / total_area))
        adaptor = BRepAdaptor_Surface(face)
        u_min, u_max = adaptor.FirstUParameter(), adaptor.LastUParameter()
        v_min, v_max = adaptor.FirstVParameter(), adaptor.LastVParameter()

        # Sample on a grid within UV bounds
        n_u = max(1, int(np.sqrt(n)))
        n_v = max(1, n // n_u)

        for i in range(n_u):
            for j in range(n_v):
                u = u_min + (u_max - u_min) * (i + 0.5) / n_u
                v = v_min + (v_max - v_min) * (j + 0.5) / n_v

                # Get point and normal at (u, v)
                try:
                    pnt = adaptor.Value(u, v)
                    # Get surface normal via D1
                    from OCC.Core.gp import gp_Vec
                    du, dv = gp_Vec(), gp_Vec()
                    p = gp_Pnt()
                    adaptor.D1(u, v, p, du, dv)
                    normal_vec = du.Crossed(dv)

                    if normal_vec.Magnitude() < 1e-10:
                        continue

                    normal_vec.Normalize()

                    # Cast ray inward (opposite to outward normal)
                    ray_dir = gp_Dir(-normal_vec.X(), -normal_vec.Y(), -normal_vec.Z())
                    # Offset start point slightly along normal to avoid self-intersection
                    start = gp_Pnt(
                        pnt.X() + normal_vec.X() * 0.001,
                        pnt.Y() + normal_vec.Y() * 0.001,
                        pnt.Z() + normal_vec.Z() * 0.001,
                    )
                    ray = gp_Lin(start, ray_dir)

                    # Intersect ray with shape
                    intersector = BRepIntCurveSurface_Inter()
                    intersector.Init(shape, ray, 1e-6)

                    min_dist = float("inf")
                    while intersector.More():
                        hit_pnt = intersector.Pnt()
                        dist = start.Distance(hit_pnt)
                        if dist > 0.01:  # Ignore very close hits (same face)
                            min_dist = min(min_dist, dist)
                        intersector.Next()

                    if min_dist < float("inf"):
                        results.append(ThicknessResult(
                            point=[pnt.X(), pnt.Y(), pnt.Z()],
                            thickness=min_dist,
                            face_index=fidx,
                        ))

                except Exception:
                    continue  # Skip problematic sample points

    logger.info(f"Wall thickness: {len(results)} samples, "
                f"min={min(r.thickness for r in results):.2f}mm, "
                f"max={max(r.thickness for r in results):.2f}mm" if results else
                "Wall thickness: no valid samples")

    return ThicknessAnalysis(results)
