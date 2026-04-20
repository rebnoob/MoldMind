"""3D fill-time field via voxelization + fast-marching (eikonal equation).

Mimics the "Melt Front Arrival Time" visualization from commercial molding
simulators (Moldex3D, Moldflow). Given a tessellated mesh, we:
  1. Voxelize the solid interior
  2. Pick a gate location (topmost voxel by default — user-configurable later)
  3. Solve the eikonal equation |∇T|·F = 1 from the gate via fast marching
  4. Project the 3D time field back onto each mesh vertex

The output is a per-vertex Float32Array (mm travel distance from gate, which is
proportional to fill time under uniform-speed assumption). Not as accurate as
true VOF Navier-Stokes, but 3× orders of magnitude faster and visually similar
for the purpose of showing how the cavity fills.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def compute_fill_time(
    vertices: np.ndarray | list[list[float]],
    indices: np.ndarray | list[int] | None = None,
    *,
    gate: str | tuple[float, float, float] = "top_z",
    max_grid: int = 128,
    pitch_mm: float | None = None,
    use_thickness_weighting: bool = True,
    couple_viscosity: bool = True,
    t_inj_c: float = 250.0,
    t_wall_c: float = 30.0,
    arrhenius_b: float = 1500.0,
    decay_frac: float = 0.65,
) -> dict[str, Any]:
    """Compute per-vertex melt-front arrival time on a 3D voxel grid.

    Physics model — simplified Hele-Shaw on voxels:

      ∇·(h² / (12η) · ∇P) = source       (Hele-Shaw)
      velocity ∝ h² / η                  (local flow speed scales with gap² / viscosity)
      T(r) = T_wall + (T_inj - T_wall)·exp(-r / L_decay)   (Arrhenius spatial decay)
      η(T) = η₀ · exp(B · (1/T - 1/T_ref))                 (Arrhenius viscosity)

    Boundary conditions:
      • Walls  → no-flow (enforced by the mask: skfmm never propagates outside)
      • Gate   → Dirichlet (phi = -1 at gate voxel, initial front)
      • Front  → free surface, implicit in the FMM propagation

    The FMM pass is run twice when viscosity coupling is on:
      pass 1: speed = h² / median(h²)                      (geometry-only)
      (estimate T(r) from pass-1 fill time, then η(T))
      pass 2: speed = h² / η(T)                            (geometry + viscosity)

    Args:
        vertices: flat mesh vertices, shape (3N, 3). Non-indexed as produced by
            services/geometry/src/tessellator.py.
        gate: "top_z"/"top_y"/"top_x" or explicit (x, y, z) mm.
        max_grid: longest-axis voxel count (controls cost).
        pitch_mm: voxel edge in mm (auto from bbox / max_grid if None).
        use_thickness_weighting: if False, fall back to pure geodesic eikonal (old behaviour).
        couple_viscosity: if True, iterate once with T-dependent viscosity.
        t_inj_c, t_wall_c: melt and wall temperatures (°C) for the T-coupling.
        arrhenius_b: η(T) = η₀ exp(B (1/T_K − 1/T_ref_K)); larger B = more T-sensitive.
        decay_frac: spatial decay length for T(r), relative to max fill distance.

    Returns:
        {
          vertex_fill_time: np.float32 (N,), per-vertex arrival "time" (mm, viscosity-weighted)
          max_time, voxel_grid, pitch_mm, gate_world, active_voxels, vertex_count,
          thickness_stats: {min, max, median} in mm
          passes: number of FMM iterations run
          physics: flags describing which terms are on
        }
    """
    import skfmm
    import trimesh
    import numpy.ma as ma

    verts = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
    n_verts = len(verts)
    if n_verts < 3:
        raise ValueError(f"Not enough vertices: {n_verts}")

    if indices is not None:
        idx_arr = np.asarray(indices, dtype=np.int64).reshape(-1)
        if idx_arr.size % 3 != 0:
            raise ValueError(f"indices length {idx_arr.size} not divisible by 3")
        faces = idx_arr.reshape(-1, 3)
    else:
        # Flat (non-indexed) mesh: 3 consecutive verts = 1 triangle
        if n_verts % 3 != 0:
            raise ValueError(
                f"No indices supplied and vertex count {n_verts} isn't a multiple of 3 "
                "(likely an indexed mesh — pass the indices array)"
            )
        faces = np.arange(n_verts, dtype=np.int64).reshape(-1, 3)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    bbox_size = mesh.bounds[1] - mesh.bounds[0]

    if pitch_mm is None:
        pitch_mm = float(bbox_size.max() / max_grid)
    pitch_mm = max(pitch_mm, 0.1)  # prevent absurdly small pitches → memory blowup

    logger.info(f"Voxelizing: bbox={bbox_size.tolist()}, pitch={pitch_mm:.3f}mm")
    vox = mesh.voxelized(pitch=pitch_mm)
    try:
        vox = vox.fill()  # flood-fill interior
    except Exception as e:
        logger.warning(f"Voxel fill failed ({e}); using surface-only voxels")
    matrix = np.asarray(vox.matrix, dtype=bool)
    # trimesh 4.x: origin = translation component of the voxel→world transform
    origin = np.asarray(vox.transform[:3, 3], dtype=np.float64)
    active = int(matrix.sum())
    if active < 20:
        raise RuntimeError(f"Voxelization produced only {active} filled cells — mesh likely non-watertight")
    logger.info(f"Voxel grid {matrix.shape}, {active} active ({100*matrix.mean():.1f}%)")

    # ── Pick gate ──
    filled_idx = np.argwhere(matrix)  # (M, 3) integer indices
    if isinstance(gate, str):
        if gate == "top_z":
            axis = 2
        elif gate == "top_y":
            axis = 1
        elif gate == "top_x":
            axis = 0
        else:
            raise ValueError(f"Unknown gate mode: {gate}")
        top_k = int(filled_idx[:, axis].max())
        at_top = filled_idx[filled_idx[:, axis] == top_k]
        gate_idx = tuple(int(x) for x in np.round(at_top.mean(axis=0)).astype(int))
        # Snap to an actual filled voxel near that centroid
        if not matrix[gate_idx]:
            diffs = at_top - np.array(gate_idx)
            nearest = at_top[np.argmin(np.sum(diffs ** 2, axis=1))]
            gate_idx = tuple(int(x) for x in nearest)
    else:
        gx, gy, gz = gate
        gate_idx = tuple(int(x) for x in np.floor((np.array([gx, gy, gz]) - origin) / pitch_mm))
        gate_idx = tuple(int(np.clip(c, 0, s - 1)) for c, s in zip(gate_idx, matrix.shape))
        if not matrix[gate_idx]:
            diffs = filled_idx - np.array(gate_idx)
            nearest = filled_idx[np.argmin(np.sum(diffs ** 2, axis=1))]
            gate_idx = tuple(int(x) for x in nearest)

    # ── Local gap thickness from 3D distance transform of the interior ──
    # For a slab of thickness h, the EDT inside ranges from 0 (at wall) to h/2 (mid-plane),
    # so 2·EDT is a natural proxy for local wall thickness. Ribs get small values,
    # thick bosses get large values — exactly what Hele-Shaw wants.
    from scipy.ndimage import distance_transform_edt
    edt_vox = distance_transform_edt(matrix)          # voxel units, 0 at wall
    local_h_mm = 2.0 * edt_vox * pitch_mm             # approximate local gap in mm
    # Clip to avoid zero/huge values destabilising the FMM speed field
    h_inside = local_h_mm[matrix]
    h_median = float(np.median(h_inside))
    h_min_cap = max(pitch_mm, 0.1 * h_median)
    h_max_cap = max(4.0 * h_median, h_min_cap * 10)
    local_h_clipped = np.clip(local_h_mm, h_min_cap, h_max_cap)
    thickness_stats = {
        "min_mm": float(h_inside.min()),
        "max_mm": float(h_inside.max()),
        "median_mm": h_median,
    }
    logger.info(
        f"Local thickness: min={thickness_stats['min_mm']:.2f}  "
        f"median={h_median:.2f}  max={thickness_stats['max_mm']:.2f} mm "
        f"(clipped to [{h_min_cap:.2f}, {h_max_cap:.2f}])"
    )

    # ── Speed field (Hele-Shaw: v ∝ h²) ──
    # Normalise so max speed = 1 → travel_time output is in mm
    phi = np.ones(matrix.shape, dtype=np.float64)
    phi[gate_idx] = -1.0
    phi_ma = ma.MaskedArray(phi, mask=~matrix)

    passes = 0

    def _run_fmm_with_speed(speed_field: np.ndarray) -> np.ma.MaskedArray:
        nonlocal passes
        s = speed_field.copy()
        # Outside the mask, speed is irrelevant (masked). Inside, must be strictly > 0.
        s[~matrix] = 1.0  # placeholder, will be masked anyway
        s[matrix] = np.clip(s[matrix], 1e-3, None)
        s[matrix] = s[matrix] / s[matrix].max()  # normalise: max speed = 1
        speed_ma = ma.MaskedArray(s, mask=~matrix)
        passes += 1
        return skfmm.travel_time(phi_ma, speed=speed_ma, dx=pitch_mm)

    if use_thickness_weighting:
        speed_geom = local_h_clipped ** 2
        logger.info(f"FMM pass 1/1 — geometry-weighted speed (v ∝ h²)")
        travel = _run_fmm_with_speed(speed_geom)

        if couple_viscosity:
            # Temperature from preliminary fill time (spatial Arrhenius decay).
            # decay length = decay_frac × max fill-time; use the preliminary result.
            ft1 = np.asarray(travel.filled(0.0), dtype=np.float64)
            ft1_max = float(np.ma.max(travel))
            if ft1_max > 0:
                decay_len = max(ft1_max * decay_frac, 1e-6)
                T_C = t_wall_c + (t_inj_c - t_wall_c) * np.exp(-ft1 / decay_len)
                T_K = T_C + 273.15
                T_ref_K = t_inj_c + 273.15
                eta_rel = np.exp(arrhenius_b * (1.0 / T_K - 1.0 / T_ref_K))
                # Viscosity increases in cold regions → lowers speed there
                speed_visc = speed_geom / np.clip(eta_rel, 1e-3, 1e6)
                logger.info(
                    f"FMM pass 2/2 — viscosity-coupled  "
                    f"(T range {float(T_C[matrix].min()):.0f}..{float(T_C[matrix].max()):.0f} °C, "
                    f"η/η₀ range {float(eta_rel[matrix].min()):.2f}..{float(eta_rel[matrix].max()):.2f})"
                )
                travel = _run_fmm_with_speed(speed_visc)
    else:
        # Old behaviour: pure geodesic distance (uniform speed = 1)
        logger.info("FMM — uniform speed (eikonal only, no physics)")
        travel = skfmm.distance(phi_ma, dx=pitch_mm)
        passes = 1

    max_dist = float(np.ma.max(travel))
    dist_arr = np.asarray(travel.filled(max_dist * 1.2), dtype=np.float32)

    # ── Project to vertices ──
    idx = np.floor((verts - origin) / pitch_mm).astype(np.int32)
    idx = np.clip(idx, 0, np.array(matrix.shape) - 1)
    vertex_fill_time = dist_arr[idx[:, 0], idx[:, 1], idx[:, 2]].astype(np.float32)

    gate_world = {
        "x": float(origin[0] + (gate_idx[0] + 0.5) * pitch_mm),
        "y": float(origin[1] + (gate_idx[1] + 0.5) * pitch_mm),
        "z": float(origin[2] + (gate_idx[2] + 0.5) * pitch_mm),
    }

    return {
        "vertex_fill_time": vertex_fill_time,
        "max_time": max_dist,
        "voxel_grid": list(matrix.shape),
        "pitch_mm": pitch_mm,
        "gate_world": gate_world,
        "active_voxels": active,
        "vertex_count": n_verts,
        "thickness_stats": thickness_stats,
        "passes": passes,
        "physics": {
            "thickness_weighted": use_thickness_weighting,
            "viscosity_coupled": use_thickness_weighting and couple_viscosity,
            "t_inj_c": t_inj_c,
            "t_wall_c": t_wall_c,
            "arrhenius_b": arrhenius_b,
            "decay_frac": decay_frac,
        },
    }
