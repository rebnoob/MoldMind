"""Injection molding planning module.

Orchestrates three analysis stages:
1. Tooling assessment (mold type, side actions, cavity count)
2. Material recommendation (primary + 2 alternatives)
3. Pressure estimation (cavity pressure, clamp force, machine size)

All results include explicit assumptions, confidence levels, and limitations.
"""

from .tooling_assessment import assess_tooling
from .material_recommendation import recommend_material
from .pressure_estimation import estimate_pressure


def generate_molding_plan(
    face_infos: list,
    properties: dict,
    thickness_analysis,
    topology: dict | None = None,
) -> dict:
    """Generate a complete first-pass injection molding plan.

    Args:
        face_infos: FaceInfo list from face_analysis
        properties: Part properties from properties.py
        thickness_analysis: ThicknessAnalysis from wall_thickness
        topology: topology.json dict (optional)

    Returns:
        Complete molding plan with tooling, material, and pressure sections
    """
    # Stage 1: Tooling assessment
    tooling = assess_tooling(face_infos, properties, topology)

    # Stage 2: Material recommendation
    material = recommend_material(thickness_analysis, face_infos, properties)

    # Stage 3: Pressure estimation (uses recommended material)
    material_family = material["primary"].get("family", "ABS")
    pressure = estimate_pressure(
        face_infos, properties, thickness_analysis,
        material_family=material_family,
        pull_direction=tooling["pull_direction"],
    )

    # Overall confidence: min of all stages
    confidences = [tooling["confidence"], material["confidence"], pressure["confidence"]]
    confidence_order = {"low": 0, "medium": 1, "high": 2}
    overall_confidence = min(confidences, key=lambda c: confidence_order.get(c, 0))

    return {
        "tooling": tooling,
        "material": material,
        "pressure": pressure,
        "overall_confidence": overall_confidence,
        "summary": _build_summary(tooling, material, pressure),
    }


def _build_summary(tooling: dict, material: dict, pressure: dict) -> str:
    """One-paragraph human-readable summary of the molding plan."""
    parts = []

    # Tooling
    parts.append(
        f"This part is a {tooling['complexity_level']}-complexity molding candidate "
        f"requiring a {tooling['mold_type']} mold."
    )
    if tooling["cavity_recommendation"]["primary"] > 1:
        parts.append(
            f"Recommended {tooling['cavity_recommendation']['primary']}-cavity layout."
        )
    else:
        parts.append("Single-cavity mold recommended for initial production.")

    # Material
    parts.append(
        f"Recommended material: {material['primary']['name']} "
        f"({material['primary']['shrinkage_pct']}% shrinkage, "
        f"{material['primary']['melt_temp_c']}°C melt)."
    )

    # Pressure
    parts.append(
        f"Estimated clamp force: {pressure['clamp_force_tons']} tons "
        f"({pressure['machine_size_recommendation']} machine). "
        f"Shot weight: ~{pressure.get('volume_based', {}).get('shot_weight_total_g', '?')}g."
    )

    return " ".join(parts)
