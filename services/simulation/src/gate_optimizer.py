"""Gate-position optimization for injection molding fill.

Implements the heuristic from the user's note (see
llm_wiki_for_physics/wiki/sources/optimal_gate_position_note.md):

  • Symmetric parts → evaluate the centres of the 3 principal planes (XY/XZ/YZ).
  • Asymmetric parts → evaluate candidates along axis-parallel lines through
    the centre of mass.

Each candidate is scored with a fast (lower-resolution) run of compute_fill_time;
the best one wins. The winning gate can then be re-evaluated at full resolution
for the final visualisation.

Objective: minimise `max(vertex_fill_time)`. Lower = more balanced fill path.
See wiki/concepts/gate_optimization.md for the full rationale.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import numpy as np

from .fill_time import compute_fill_time

logger = logging.getLogger(__name__)

Strategy = Literal["symmetric_centers", "com_axes", "exhaustive_xy_grid"]


def _bbox_and_com(vertices: np.ndarray, indices: np.ndarray | None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (bbox_min, bbox_max, centre_of_mass) in mm.

    Centre of mass is approximated from the triangle barycenters weighted by
    triangle area. Close enough for gate-placement heuristics without needing
    a full volume integral.
    """
    v = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
    bbox_min = v.min(axis=0)
    bbox_max = v.max(axis=0)
    if indices is None:
        if len(v) % 3 != 0:
            # Fall back to vertex centroid
            return bbox_min, bbox_max, v.mean(axis=0)
        tris = v.reshape(-1, 3, 3)
    else:
        idx = np.asarray(indices, dtype=np.int64).reshape(-1, 3)
        tris = v[idx]  # (T, 3, 3)
    centroids = tris.mean(axis=1)                                    # (T, 3)
    edge1 = tris[:, 1] - tris[:, 0]
    edge2 = tris[:, 2] - tris[:, 0]
    areas = 0.5 * np.linalg.norm(np.cross(edge1, edge2), axis=1)     # (T,)
    total = float(areas.sum())
    if total <= 0:
        return bbox_min, bbox_max, v.mean(axis=0)
    com = (centroids * areas[:, None]).sum(axis=0) / total
    return bbox_min, bbox_max, com


def _symmetric_candidates(bbox_min: np.ndarray, bbox_max: np.ndarray) -> list[tuple[str, tuple[float, float, float]]]:
    cx, cy, cz = (bbox_min + bbox_max) / 2
    return [
        ("xy_center", (float(cx), float(cy), float(bbox_max[2]))),
        ("xz_center", (float(cx), float(bbox_max[1]), float(cz))),
        ("yz_center", (float(bbox_max[0]), float(cy), float(cz))),
    ]


def _com_axis_candidates(bbox_min: np.ndarray, bbox_max: np.ndarray, com: np.ndarray) -> list[tuple[str, tuple[float, float, float]]]:
    extent = bbox_max - bbox_min
    alphas = (-0.35, 0.0, 0.35)
    out: list[tuple[str, tuple[float, float, float]]] = []
    for axis_idx, axis_name in enumerate("xyz"):
        for a in alphas:
            pos = com.copy()
            pos[axis_idx] = com[axis_idx] + a * extent[axis_idx]
            # Clip to bbox (shrunk slightly so the gate stays strictly inside)
            pos[axis_idx] = float(np.clip(pos[axis_idx], bbox_min[axis_idx] + 0.01 * extent[axis_idx], bbox_max[axis_idx] - 0.01 * extent[axis_idx]))
            out.append((f"com_{axis_name}{'+' if a>0 else '-' if a<0 else '0'}", tuple(float(x) for x in pos)))
    return out


def _xy_grid_candidates(bbox_min: np.ndarray, bbox_max: np.ndarray, n: int = 5) -> list[tuple[str, tuple[float, float, float]]]:
    xs = np.linspace(bbox_min[0], bbox_max[0], n + 2)[1:-1]   # drop the corners
    ys = np.linspace(bbox_min[1], bbox_max[1], n + 2)[1:-1]
    z_top = float(bbox_max[2])
    out: list[tuple[str, tuple[float, float, float]]] = []
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            out.append((f"xy_grid_{i}_{j}", (float(x), float(y), z_top)))
    return out


def optimize_gate(
    vertices: np.ndarray | list[list[float]],
    indices: np.ndarray | list[int] | None = None,
    *,
    strategy: Strategy = "symmetric_centers",
    max_grid: int = 64,
    objective: Literal["max_time", "uniformity"] = "max_time",
    include_current_best_refine: bool = False,
) -> dict[str, Any]:
    """Rank candidate gate positions.

    Args:
        vertices, indices: tessellated mesh from services/geometry/src/tessellator
        strategy: "symmetric_centers" (3 candidates; fastest),
                  "com_axes" (9 candidates on axis lines through the COM),
                  "exhaustive_xy_grid" (25 candidates on a 5×5 grid on the XY face — slowest).
        max_grid: voxel-grid size for each evaluation. 64 runs ~0.5 s/candidate;
                  the final render at 96 can be re-run on the winner if desired.
        objective: "max_time" (minimise the longest flow path), or
                   "uniformity" (minimise stdev/mean of the fill-time field).

    Returns:
        {
          strategy: str,
          objective: str,
          n_candidates: int,
          best: {label, gate_xyz, score, fill_meta (sans vertex_fill_time)},
          ranked: [ {label, gate_xyz, score}, ... ]  # sorted ascending (best first)
        }
    """
    v_arr = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
    bbox_min, bbox_max, com = _bbox_and_com(v_arr, indices)

    if strategy == "symmetric_centers":
        candidates = _symmetric_candidates(bbox_min, bbox_max)
    elif strategy == "com_axes":
        candidates = _com_axis_candidates(bbox_min, bbox_max, com)
    elif strategy == "exhaustive_xy_grid":
        candidates = _xy_grid_candidates(bbox_min, bbox_max, n=5)
    else:
        raise ValueError(f"Unknown strategy: {strategy!r}")

    logger.info(
        f"Gate optimizer: strategy={strategy}  candidates={len(candidates)}  "
        f"bbox=({bbox_min.tolist()} -> {bbox_max.tolist()})  com={com.tolist()}"
    )

    ranked: list[dict[str, Any]] = []
    for label, gate_xyz in candidates:
        try:
            result = compute_fill_time(
                v_arr, indices,
                gate=gate_xyz,
                max_grid=max_grid,
                couple_viscosity=False,  # skip pass 2 during the search — just geometry
            )
        except Exception as e:
            logger.warning(f"candidate {label} failed: {e}")
            ranked.append({"label": label, "gate_xyz": list(gate_xyz), "score": float("inf"), "error": str(e)})
            continue

        vft = result["vertex_fill_time"]
        if objective == "max_time":
            score = float(result["max_time"])
        elif objective == "uniformity":
            mean = float(vft.mean())
            score = float(vft.std() / max(mean, 1e-9))
        else:
            raise ValueError(f"Unknown objective: {objective}")

        meta = {k: v for k, v in result.items() if k != "vertex_fill_time"}
        ranked.append({
            "label": label,
            "gate_xyz": [float(c) for c in gate_xyz],
            "score": score,
            "max_time": float(result["max_time"]),
            "active_voxels": int(result["active_voxels"]),
            "grid": list(result["voxel_grid"]),
            "pitch_mm": float(result["pitch_mm"]),
            "thickness_median_mm": float(meta["thickness_stats"]["median_mm"]),
        })

    ranked.sort(key=lambda r: r["score"])
    best = ranked[0] if ranked else None
    return {
        "strategy": strategy,
        "objective": objective,
        "n_candidates": len(candidates),
        "bbox_min_mm": bbox_min.tolist(),
        "bbox_max_mm": bbox_max.tolist(),
        "centre_of_mass_mm": com.tolist(),
        "best": best,
        "ranked": ranked,
    }
