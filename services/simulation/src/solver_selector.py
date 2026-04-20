"""Adaptive fluid-solver recommendation for injection-molding parts.

Given part geometry features, picks the cheapest solver that still captures
the physics. Philosophy:

  • Don't solve full 3D Navier-Stokes on a 0.5 mm shell — Hele-Shaw is exact to
    a few percent at ~1000× the speed.
  • Don't run Hele-Shaw on a chunky 30 mm hub with undercuts — the gap-averaged
    approximation breaks and you need 3D VOF to predict weld lines / air traps.
  • Everything in between is a spectrum: thickness-weighted FMM (cheap-ish 3D),
    Stokes 3D (no inertia), full VOF (the real thing).

The selector returns a RECOMMENDATION — the caller is free to override. The
reasoning block is the important part for user trust.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Literal

SolverID = Literal["hele_shaw_2d", "fmm_3d", "stokes_3d", "vof_3d"]


# --- Solver registry ---------------------------------------------------------
# `available` tracks whether the solver is actually wired up in this repo today.
# Flip to True as each one lands.

SOLVERS: dict[SolverID, dict[str, Any]] = {
    "hele_shaw_2d": {
        "name": "Hele-Shaw 2D (mid-plane)",
        "available": False,
        "runtime_estimate": "1–3 s",
        "where": "removed — previously services/simulation/src/hele_shaw.py",
        "physics": [
            "2D Poisson pressure: ∇·(h³/12η · ∇P) = source",
            "Gap-averaged velocity (parabolic across h)",
            "Arrhenius η(T), density ρ(P,T)",
        ],
    },
    "fmm_3d": {
        "name": "Thickness-weighted FMM 3D",
        "available": True,
        "runtime_estimate": "2–5 s",
        "where": "services/simulation/src/fill_time.py → 3D viewer",
        "physics": [
            "Eikonal fast-marching on a voxel grid",
            "Speed ∝ h² / η(T), h from 3D distance transform",
            "Two-pass viscosity coupling (geometry → T → η → speed)",
        ],
    },
    "stokes_3d": {
        "name": "Stokes 3D (incompressible, no inertia)",
        "available": False,
        "runtime_estimate": "2–5 min",
        "where": "not implemented — would use icoFoam with inertia dropped",
        "physics": [
            "3D ∇·(η·∇u) = ∇p, ∇·u = 0",
            "Inertial (u·∇)u dropped since Re ≪ 1",
            "Single-phase pseudo-steady fill",
        ],
    },
    "vof_3d": {
        "name": "Full 3D VOF Navier-Stokes",
        "available": False,  # container ready, runner still a stub
        "runtime_estimate": "20–60 min",
        "where": "services/simulation/src/openfoam_runner.py (container ready, pipeline stub)",
        "physics": [
            "3D incompressible NS (though inertia ≈ 0 for polymers)",
            "VOF α-field: ∂α/∂t + ∇·(α u) = 0  — tracks melt/air interface",
            "Cross-WLF viscosity η(T, γ̇)",
            "Energy equation with mold wall heat transfer + viscous heating",
        ],
    },
}


# --- Polymer melt reference numbers (ABS-ish defaults) -----------------------
# These are used to compute Re so the user sees an honest number, even though
# for polymers Re is basically always ≪ 1 and Stokes holds.
_REF_RHO = 1000.0     # kg/m³  (typical thermoplastic)
_REF_VEL = 0.1        # m/s    (typical injection velocity at gate area)
_REF_ETA = 1000.0     # Pa·s   (melt viscosity at injection temp)


# --- Decision thresholds -----------------------------------------------------
# Tuned so that shell parts → Hele-Shaw, chunky parts → VOF, ribs / moderate →
# FMM 3D. These match the common Moldflow / Moldex3D triage.

THRESH_SHELL_ASPECT = 0.05        # h/L below this → pure shell → 2D Hele-Shaw
THRESH_THICK_ASPECT = 0.20        # above this → need 3D
THRESH_CHUNKY_ASPECT = 0.30       # above this → VOF region
THRESH_MANY_UNDERCUTS = 3         # any undercuts → can't use pure 2D Hele-Shaw
THRESH_CONSERVATIVE_BUMP = True    # if uncertain, prefer the richer solver


@dataclass
class PartFeatures:
    """Inputs the selector needs. Caller (API endpoint) is responsible for
    pulling these from fill_time.json + molding_plan.json + part DB row."""
    median_thickness_mm: float
    min_thickness_mm: float
    max_thickness_mm: float
    flow_length_mm: float
    volume_mm3: float
    undercut_count: int = 0
    parting_ratio: float | None = None       # 0..1, fraction moldable without side actions
    face_count: int | None = None
    # optional diagnostic labels from the DFM layer
    has_3d_features: bool = False            # ribs/bosses/hubs present?


def _compute_reynolds(median_thickness_mm: float) -> float:
    L_m = median_thickness_mm * 1e-3
    return _REF_RHO * _REF_VEL * L_m / _REF_ETA


def select_solver(features: PartFeatures) -> dict[str, Any]:
    """Pick the right solver for this part. Returns a rich dict intended for
    both programmatic use (caller checks `solver`) and UI display (`reasoning`,
    `derived`, `alternatives`)."""

    h = features.median_thickness_mm
    L = max(features.flow_length_mm, 1e-6)
    aspect = h / L
    Re = _compute_reynolds(h)

    derived = {
        "aspect_ratio_h_over_L": round(aspect, 4),
        "reynolds_number": round(Re, 5),
        "stokes_regime": Re < 1.0,
        "median_thickness_mm": round(h, 3),
        "flow_length_mm": round(features.flow_length_mm, 1),
        "thickness_range_mm": [round(features.min_thickness_mm, 2), round(features.max_thickness_mm, 2)],
        "thickness_uniformity": round(features.min_thickness_mm / max(features.max_thickness_mm, 1e-6), 3),
        "undercut_count": features.undercut_count,
    }

    # ── Decision tree ────────────────────────────────────────────────────────
    reasoning_lines: list[str] = []
    ignores: list[str] = []
    chosen: SolverID
    confidence: str

    if features.undercut_count >= THRESH_MANY_UNDERCUTS or aspect >= THRESH_CHUNKY_ASPECT:
        chosen = "vof_3d"
        confidence = "high_accuracy"
        reasoning_lines = [
            f"aspect h/L = {aspect:.3f} ≥ {THRESH_CHUNKY_ASPECT} (chunky)" if aspect >= THRESH_CHUNKY_ASPECT
            else f"{features.undercut_count} undercuts ≥ {THRESH_MANY_UNDERCUTS}",
            f"Re = {Re:.1e} — inertia negligible, but 3D geometry demands full resolution",
            "Weld lines, air traps, and complex 3D fronts require VOF tracking",
        ]
        ignores = ["nothing major — this is the ground truth"]

    elif aspect >= THRESH_THICK_ASPECT or features.undercut_count > 0 or features.has_3d_features:
        chosen = "fmm_3d"
        confidence = "medium"
        triggers = []
        if aspect >= THRESH_THICK_ASPECT:
            triggers.append(f"aspect h/L = {aspect:.3f} ≥ {THRESH_THICK_ASPECT} — moderately 3D, gap-averaging starts losing accuracy")
        if features.undercut_count > 0:
            triggers.append(f"{features.undercut_count} undercut(s) — 2D Hele-Shaw can't represent flow around side cores")
        if features.has_3d_features:
            triggers.append("3D features (ribs/bosses/hubs) flagged — local thickness weighting matters")
        reasoning_lines = triggers + [
            f"thickness varies {features.min_thickness_mm:.1f}–{features.max_thickness_mm:.1f} mm (local h² weighting used)",
            f"Re = {Re:.1e} ≪ 1 — Stokes regime, no inertia term needed",
        ]
        ignores = [
            "true mass transport (front advances on geodesic, not via momentum)",
            "weld-line prediction (can't resolve front merging)",
            "non-isothermal density changes",
        ]

    elif aspect < THRESH_SHELL_ASPECT and features.undercut_count == 0 and not features.has_3d_features:
        chosen = "hele_shaw_2d"
        confidence = "high"
        reasoning_lines = [
            f"aspect h/L = {aspect:.3f} < {THRESH_SHELL_ASPECT} → pure shell, gap-averaging is exact to ~5%",
            "no undercuts and no 3D features flagged",
            f"Re = {Re:.1e} ≪ 1 — Stokes assumption holds, parabolic velocity profile is analytical",
            "2D mid-plane pressure solve is ~1000× cheaper than VOF for the same answer",
        ]
        ignores = [
            "velocity variation across the gap (assumed parabolic)",
            "3D corner flow at T-junctions and gates",
        ]

    else:
        # aspect ~0.05 to 0.2 with no 3D features — borderline shell / 2.5D
        chosen = "fmm_3d"
        confidence = "medium"
        reasoning_lines = [
            f"aspect h/L = {aspect:.3f} in borderline shell / 2.5D range",
            "FMM 3D captures thickness variations that 2D Hele-Shaw would average out",
            "much cheaper than VOF and good enough for gate placement / cold-spot mapping",
        ]
        ignores = ["weld-line prediction", "true 3D corner flow"]

    # ── Build "alternatives" list so user can override with full context ─────
    def _other(sid: SolverID) -> dict[str, Any]:
        s = SOLVERS[sid]
        tradeoff = {
            "hele_shaw_2d": "cheapest, only valid on pure shells",
            "fmm_3d": "3D visual but eikonal front (not true flow)",
            "stokes_3d": "real 3D flow, no free surface (single-phase)",
            "vof_3d": "ground truth but 600× slower than Hele-Shaw",
        }[sid]
        return {
            "solver": sid,
            "name": s["name"],
            "available": s["available"],
            "runtime_estimate": s["runtime_estimate"],
            "tradeoff": tradeoff,
        }

    recommended_meta = SOLVERS[chosen]

    return {
        "recommended": chosen,
        "name": recommended_meta["name"],
        "available": recommended_meta["available"],
        "confidence": confidence,
        "runtime_estimate": recommended_meta["runtime_estimate"],
        "reasoning": reasoning_lines,
        "ignores": ignores,
        "physics": recommended_meta["physics"],
        "derived": derived,
        "alternatives": [_other(sid) for sid in SOLVERS if sid != chosen],
        "thresholds_applied": {
            "shell_aspect": THRESH_SHELL_ASPECT,
            "thick_aspect": THRESH_THICK_ASPECT,
            "chunky_aspect": THRESH_CHUNKY_ASPECT,
            "many_undercuts": THRESH_MANY_UNDERCUTS,
        },
        "inputs": asdict(features),
    }
