"""First-pass tooling and cavity assessment for injection molding.

Uses existing topology and face analysis data to estimate:
- Pull direction feasibility
- Parting line quality
- Undercut count and side action needs
- Mold type (2-plate, 3-plate, hot runner)
- Cavity count recommendation

All outputs are labeled with assumptions and confidence levels.
"""

import math
import numpy as np
from collections import defaultdict


def assess_tooling(face_infos: list, properties: dict, topology: dict | None = None) -> dict:
    """Assess mold tooling requirements from geometry data.

    Args:
        face_infos: List of FaceInfo objects (from face_analysis)
        properties: Part properties dict (volume, bbox, dimensions)
        topology: topology.json data (optional, for feature details)

    Returns:
        Structured tooling assessment dict
    """
    dims = properties.get("dimensions", {"x": 0, "y": 0, "z": 0})
    volume = properties.get("volume_mm3", 0)
    bbox = properties.get("bounding_box", {"min": [0, 0, 0], "max": [0, 0, 0]})

    # --- Pull direction analysis ---
    pull = [0, 0, 1]  # Default Z+
    parting_area = sum(f.area for f in face_infos if f.is_parting_face)
    total_area = sum(f.area for f in face_infos)
    parting_ratio = parting_area / total_area if total_area > 0 else 0

    pull_confidence = "high" if parting_ratio > 0.25 else "medium" if parting_ratio > 0.1 else "low"

    # --- Undercut analysis ---
    undercut_faces = [f for f in face_infos if f.is_undercut and f.area > 0.5]
    undercut_count = len(undercut_faces)

    # Group undercuts by direction to determine side action count
    # Each unique direction = 1 side action mechanism
    side_action_directions = defaultdict(list)
    for f in undercut_faces:
        if f.normal:
            # Quantize direction to group nearby normals
            key = (
                round(f.normal[0] / 0.3) * 0.3,
                round(f.normal[1] / 0.3) * 0.3,
                round(f.normal[2] / 0.3) * 0.3,
            )
            side_action_directions[key].append(f.index)

    side_actions_needed = len(side_action_directions)

    # --- Parting feasibility ---
    wall_faces = sum(1 for f in face_infos if f.feature_type in ("main_wall", "minor_feature", "boss", "hole", "rib"))
    parting_faces = sum(1 for f in face_infos if f.is_parting_face)
    moldable_count = wall_faces + parting_faces
    moldable_ratio = moldable_count / len(face_infos) if face_infos else 0

    if moldable_ratio > 0.85 and undercut_count <= 2:
        parting_feasibility = "good"
    elif moldable_ratio > 0.65 or undercut_count <= 4:
        parting_feasibility = "challenging"
    else:
        parting_feasibility = "complex"

    # --- Mold type ---
    if side_actions_needed == 0 and parting_feasibility == "good":
        mold_type = "2-plate"
    elif side_actions_needed <= 2:
        mold_type = f"2-plate with {side_actions_needed} side action(s)"
    elif side_actions_needed <= 4:
        mold_type = "3-plate or 2-plate with multiple actions"
    else:
        mold_type = "Complex (hot runner or multi-stage recommended)"

    # --- Complexity level ---
    feature_count = 0
    if topology and "features" in topology:
        feature_count = len(topology["features"])

    if side_actions_needed == 0 and feature_count <= 5:
        complexity = "simple"
    elif side_actions_needed <= 2 and feature_count <= 15:
        complexity = "moderate"
    else:
        complexity = "complex"

    # --- Cavity recommendation ---
    max_dim = max(dims.get("x", 0), dims.get("y", 0), dims.get("z", 0))
    envelope_area = dims.get("x", 0) * dims.get("y", 0)  # footprint in parting plane

    # Cavity count heuristic:
    # Small parts (<50mm) with no side actions → multi-cavity candidate
    # Each side action must replicate per cavity → limits count
    if max_dim < 50 and side_actions_needed == 0 and complexity == "simple":
        primary_cavities = 4
        multi_max = 8
        cavity_notes = "Small, simple part — 4-8 cavities recommended for production"
    elif max_dim < 100 and side_actions_needed <= 1 and complexity != "complex":
        primary_cavities = 2
        multi_max = 4
        cavity_notes = "Medium part — 2-4 cavities feasible; side actions limit count"
    elif max_dim < 200 and side_actions_needed == 0:
        primary_cavities = 1
        multi_max = 2
        cavity_notes = "Larger part — 1-2 cavities; consider 2 only for high volume (>100K/yr)"
    else:
        primary_cavities = 1
        multi_max = 1
        cavity_notes = "Large or complex part — single cavity recommended"

    # --- Mold component breakdown ---
    # Estimate the number of mold parts/components needed
    boss_count = sum(1 for f in face_infos if f.feature_type == "boss")
    hole_count = sum(1 for f in face_infos if f.feature_type == "hole")

    mold_components = {
        "cavity_plate": 1,
        "core_plate": 1,
        "sliders": side_actions_needed,
        "lifters": 0,  # Would need more advanced undercut analysis to distinguish from sliders
        "core_pins": hole_count,  # Each hole typically needs a core pin
        "ejector_pins": max(4, boss_count + 2),  # Minimum 4 + 1 per boss
        "sprue_bushing": 1,
        "runner_system": 1 if primary_cavities <= 2 else 2,  # Hot runner manifold for higher cavity
        "cooling_channels": 2,  # Minimum: 1 per mold half
        "guide_pins": 4,  # Standard
        "return_pins": 4,  # Standard
        "mold_base": 1,
    }
    total_mold_parts = sum(mold_components.values())

    # Estimate for multi-cavity: some components multiply
    if primary_cavities > 1:
        multi_cavity_components = dict(mold_components)
        multi_cavity_components["sliders"] *= primary_cavities
        multi_cavity_components["core_pins"] *= primary_cavities
        multi_cavity_components["ejector_pins"] *= primary_cavities
        multi_cavity_components["cooling_channels"] = primary_cavities * 2
        total_multi_parts = sum(multi_cavity_components.values())
    else:
        multi_cavity_components = None
        total_multi_parts = total_mold_parts

    assumptions = [
        f"Pull direction Z+ (auto-detected, parting ratio {parting_ratio:.0%})",
        "Production volume unknown — defaulting to medium (10K-50K/yr)",
        "Standard mold base assumed",
    ]

    return {
        "pull_direction": pull,
        "pull_direction_confidence": pull_confidence,
        "parting_feasibility": parting_feasibility,
        "parting_ratio": round(moldable_ratio, 3),
        "undercut_count": undercut_count,
        "undercut_faces": [f.index for f in undercut_faces],
        "side_actions_needed": side_actions_needed,
        "side_action_directions": {
            str(k): v for k, v in side_action_directions.items()
        },
        "mold_type": mold_type,
        "complexity_level": complexity,
        "feature_count": feature_count,
        "cavity_recommendation": {
            "primary": primary_cavities,
            "multi_cavity_max": multi_max,
            "rationale": f"Part envelope {dims.get('x', 0):.0f}×{dims.get('y', 0):.0f}×{dims.get('z', 0):.0f}mm, "
                         f"{complexity} complexity, {side_actions_needed} side action(s)",
            "notes": cavity_notes,
        },
        "mold_components": mold_components,
        "total_mold_parts": total_mold_parts,
        "multi_cavity_components": multi_cavity_components,
        "total_multi_cavity_parts": total_multi_parts,
        "part_envelope_mm": {
            "x": round(dims.get("x", 0), 1),
            "y": round(dims.get("y", 0), 1),
            "z": round(dims.get("z", 0), 1),
        },
        "part_volume_mm3": round(volume, 1),
        "assumptions": assumptions,
        "confidence": "medium" if parting_feasibility != "complex" else "low",
    }
