"""Wall thickness analysis using ray-casting approach.

Casts rays inward from the outer surface to find the opposite wall.
Properly handles face orientation (Forward/Reversed) to determine
the true outward normal direction.
"""

import logging
import time
import numpy as np

logger = logging.getLogger(__name__)


class ThicknessResult:
    """Wall thickness measurement at a sample point."""
    def __init__(self, point: list[float], thickness: float, face_index: int):
        self.point = point
        self.thickness = thickness
        self.face_index = face_index


class ThicknessAnalysis:
    """Aggregated wall thickness analysis results."""
    def __init__(self, samples: list[ThicknessResult]):
        self.samples = samples
        thicknesses = [s.thickness for s in samples if s.thickness > 0]
        self.min_thickness = min(thicknesses) if thicknesses else 0
        self.max_thickness = max(thicknesses) if thicknesses else 0
        self.mean_thickness = float(np.mean(thicknesses)) if thicknesses else 0
        self.std_thickness = float(np.std(thicknesses)) if thicknesses else 0
        self.uniformity = 1.0 - (self.std_thickness / self.mean_thickness) if self.mean_thickness > 0 else 0

    @property
    def variation_pct(self) -> float:
        if self.mean_thickness == 0:
            return 0
        return (self.max_thickness - self.min_thickness) / self.mean_thickness * 100


def analyze_wall_thickness(shape, num_samples: int = 200, time_limit_s: float = 15.0) -> ThicknessAnalysis:
    """Analyze wall thickness by ray-casting inward from each face.

    For each sample point on the surface:
    1. Compute outward normal (accounting for face orientation)
    2. Cast a ray INWARD (opposite to outward normal)
    3. Find first intersection with the shape = opposite wall
    4. Distance = wall thickness at that point
    """
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.BRepIntCurveSurface import BRepIntCurveSurface_Inter
    from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Lin, gp_Vec
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.TopoDS import topods

    t_start = time.time()

    # Collect faces with areas and orientation
    total_area = 0
    faces = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    face_idx = 0
    while explorer.More():
        face = topods.Face(explorer.Current())
        props = GProp_GProps()
        brepgprop.SurfaceProperties(face, props)
        area = abs(props.Mass())
        is_reversed = (face.Orientation() == TopAbs_REVERSED)
        faces.append((face, area, face_idx, is_reversed))
        total_area += area
        face_idx += 1
        explorer.Next()

    if not faces or total_area == 0:
        return ThicknessAnalysis([])

    results = []

    for face, area, fidx, is_reversed in faces:
        if time.time() - t_start > time_limit_s:
            logger.info(f"Wall thickness: time limit after {len(results)} samples")
            break

        # Proportional samples per face, min 1, max 6
        n = max(1, min(6, int(num_samples * area / total_area)))
        adaptor = BRepAdaptor_Surface(face)
        u_min, u_max = adaptor.FirstUParameter(), adaptor.LastUParameter()
        v_min, v_max = adaptor.FirstVParameter(), adaptor.LastVParameter()

        n_u = max(1, int(np.sqrt(n)))
        n_v = max(1, n // n_u)

        for i in range(n_u):
            for j in range(n_v):
                if time.time() - t_start > time_limit_s:
                    break

                u = u_min + (u_max - u_min) * (i + 0.5) / n_u
                v = v_min + (v_max - v_min) * (j + 0.5) / n_v

                try:
                    du, dv = gp_Vec(), gp_Vec()
                    p = gp_Pnt()
                    adaptor.D1(u, v, p, du, dv)
                    normal_vec = du.Crossed(dv)

                    if normal_vec.Magnitude() < 1e-10:
                        continue

                    normal_vec.Normalize()

                    # Flip for reversed faces to get TRUE outward normal
                    if is_reversed:
                        normal_vec.Reverse()

                    # Ray direction = INWARD (opposite to outward normal)
                    inward_dir = gp_Dir(
                        -normal_vec.X(), -normal_vec.Y(), -normal_vec.Z()
                    )

                    # Start point: slightly OUTSIDE the surface (along outward normal)
                    # so we don't self-intersect with the face we're sampling from
                    start = gp_Pnt(
                        p.X() + normal_vec.X() * 0.01,
                        p.Y() + normal_vec.Y() * 0.01,
                        p.Z() + normal_vec.Z() * 0.01,
                    )

                    ray = gp_Lin(start, inward_dir)

                    intersector = BRepIntCurveSurface_Inter()
                    intersector.Init(shape, ray, 1e-6)

                    min_dist = float("inf")
                    while intersector.More():
                        hit_pnt = intersector.Pnt()
                        dist = start.Distance(hit_pnt)
                        # Skip self-intersections (< 0.05mm) and
                        # through-cavity rays (> 10mm — not a real wall for typical injection molding)
                        if 0.05 < dist < 10.0:
                            min_dist = min(min_dist, dist)
                            break  # Take first valid hit
                        intersector.Next()

                    if min_dist < float("inf"):
                        results.append(ThicknessResult(
                            point=[p.X(), p.Y(), p.Z()],
                            thickness=min_dist,
                            face_index=fidx,
                        ))
                except Exception:
                    continue

    elapsed = time.time() - t_start
    if results:
        logger.info(f"Wall thickness: {len(results)} samples in {elapsed:.1f}s, "
                     f"min={min(r.thickness for r in results):.2f}mm, "
                     f"max={max(r.thickness for r in results):.2f}mm")
    else:
        logger.info(f"Wall thickness: no valid samples in {elapsed:.1f}s")

    return ThicknessAnalysis(results)
