"""First-pass injection pressure and clamp force estimation.

This is NOT a flow simulation. It uses industry-standard heuristics:
- Projected area = X × Y bounding box footprint (simple, conservative)
- Flow ratio method (flow length / wall thickness)
- Material viscosity factors
- Volume-based shot weight, fill time, and packing estimates

Results are suitable for machine selection and initial quoting.
"""

import math
import numpy as np

# Base cavity pressure by material family (MPa) at flow ratio = 100
MATERIAL_BASE_PRESSURE = {
    "ABS": 35, "PP": 25, "PA": 45, "PC": 55, "POM": 35,
    "PE": 25, "PS": 25, "PBT": 40, "TPU": 30, "PMMA": 40,
    "Generic": 35,
}

# Viscosity factor: multiplier on base pressure
MATERIAL_VISCOSITY_FACTOR = {
    "ABS": 1.0, "PP": 0.8, "PA": 1.2, "PC": 1.4, "POM": 0.9,
    "PE": 0.7, "PS": 0.7, "PBT": 1.1, "TPU": 0.9, "PMMA": 1.1,
    "Generic": 1.0,
}

# Material density (g/cm³) for shot weight calculation
MATERIAL_DENSITY = {
    "ABS": 1.05, "PP": 0.91, "PA": 1.14, "PC": 1.20, "POM": 1.41,
    "PE": 0.95, "PS": 1.05, "PBT": 1.31, "TPU": 1.12, "PMMA": 1.18,
    "Generic": 1.05,
}


def estimate_pressure(
    face_infos: list,
    properties: dict,
    thickness_analysis,
    material_family: str = "ABS",
    pull_direction: list[float] | None = None,
) -> dict:
    """Estimate injection molding pressure and clamp force.

    Projected area = X × Y bounding box footprint (parting plane perpendicular to pull).
    Pressure and force calculations use part volume for shot weight and fill time.
    """
    pull = np.array(pull_direction or [0, 0, 1], dtype=float)
    pull = pull / np.linalg.norm(pull)

    dims = properties.get("dimensions", {"x": 0, "y": 0, "z": 0})
    volume = properties.get("volume_mm3", 0)

    dx = dims.get("x", 0)
    dy = dims.get("y", 0)
    dz = dims.get("z", 0)

    # --- Nominal wall thickness ---
    nominal_wall = 2.0
    if thickness_analysis and thickness_analysis.mean_thickness > 0:
        nominal_wall = thickness_analysis.mean_thickness

    # --- Projected area (actual surface projection onto parting plane) ---
    # Sum each face's contribution: face_area × |cos(angle between normal and pull)|
    # This gives the TRUE silhouette area, not the bounding box.
    # Faces perpendicular to pull (walls) contribute ~0.
    # Faces parallel to pull (top/bottom) contribute their full area.
    # Divide by 2 because top and bottom both project (only one side counts for clamp).
    projected_area_raw = 0.0
    for f in face_infos:
        if f.normal is None:
            continue
        n = np.array(f.normal)
        dot = abs(float(np.dot(n, pull)))
        projected_area_raw += f.area * dot
    projected_area = projected_area_raw / 2.0

    # Volume-based cross-check: volume / depth = average cross-section
    # This catches cases where projected area seems too high or too low
    pull_depth = abs(pull[0]) * dx + abs(pull[1]) * dy + abs(pull[2]) * dz
    if pull_depth > 0:
        volume_cross_section = volume / pull_depth
    else:
        volume_cross_section = projected_area

    # Use the smaller of face-projection and volume-cross-section as a conservative bound
    # (projected area should never exceed volume/depth for a solid part)
    if volume_cross_section > 0 and projected_area > volume_cross_section * 1.5:
        projected_area = volume_cross_section  # Volume-based is more conservative

    # Determine perpendicular dimensions for flow length
    perp_dims = []
    if abs(pull[0]) > 0.5:
        perp_dims = [dy, dz]
    elif abs(pull[1]) > 0.5:
        perp_dims = [dx, dz]
    else:
        perp_dims = [dx, dy]

    # --- Flow length ---
    # Longest dimension in the parting plane / 2 (center-gated)
    max_perp = max(perp_dims) if perp_dims else max(dx, dy)
    flow_length = max_perp / 2.0

    # --- Flow ratio ---
    flow_ratio = flow_length / nominal_wall if nominal_wall > 0 else 100

    # --- Cavity pressure ---
    base_pressure = MATERIAL_BASE_PRESSURE.get(material_family, 35)
    viscosity = MATERIAL_VISCOSITY_FACTOR.get(material_family, 1.0)
    flow_ratio_adjustment = max(0, (flow_ratio - 100) / 10)
    cavity_pressure = round((base_pressure + flow_ratio_adjustment) * viscosity, 1)

    # --- Injection pressure (2× cavity for runner/gate/nozzle losses) ---
    injection_pressure = round(cavity_pressure * 2.0, 1)

    # --- Clamp force ---
    # F (tons) = projected_area_cm² × cavity_pressure_MPa / 10 × safety factor
    projected_area_cm2 = projected_area / 100.0
    clamp_force = round(projected_area_cm2 * cavity_pressure / 10.0 * 1.1, 1)

    # --- Volume-based calculations ---
    density = MATERIAL_DENSITY.get(material_family, 1.05)
    volume_cm3 = volume / 1000.0

    # Shot weight (part only)
    shot_weight_part = round(volume_cm3 * density, 2)
    # Runner/sprue adds ~10-20% for cold runner
    runner_factor = 1.15
    shot_weight_total = round(shot_weight_part * runner_factor, 2)

    # Fill time estimate: volume / (injection rate)
    # Typical injection rate: 50-200 cm³/s depending on machine size
    # Estimate based on wall thickness: thinner walls need faster fill
    if nominal_wall < 1.5:
        fill_rate_cm3s = 150  # Fast fill for thin walls
    elif nominal_wall < 3.0:
        fill_rate_cm3s = 100  # Medium fill
    else:
        fill_rate_cm3s = 60   # Slow fill for thick walls
    fill_time_s = round(volume_cm3 / fill_rate_cm3s, 2)
    fill_time_s = max(fill_time_s, 0.3)  # Minimum 0.3s

    # Packing pressure: typically 50-80% of injection pressure
    packing_pressure = round(injection_pressure * 0.6, 1)

    # Packing time estimate: based on wall thickness (thicker = longer pack)
    packing_time_s = round(nominal_wall * 1.5, 1)  # ~1.5s per mm of wall

    # Cooling time estimate: proportional to wall² (heat transfer)
    cooling_time_s = round(nominal_wall ** 2 * 1.2, 1)  # ~1.2s per mm² of wall

    # Total cycle time
    cycle_time_s = round(fill_time_s + packing_time_s + cooling_time_s + 3.0, 1)  # +3s for open/close/eject

    # --- Machine size ---
    if clamp_force <= 30:
        machine = "25-50 ton"
    elif clamp_force <= 80:
        machine = "50-100 ton"
    elif clamp_force <= 200:
        machine = "100-250 ton"
    elif clamp_force <= 500:
        machine = "250-500 ton"
    else:
        machine = f"500+ ton"

    # Required shot capacity (machine barrel must hold at least this)
    min_barrel_cm3 = round(shot_weight_total / density * 1.3, 1)  # 30% headroom

    return {
        "projected_area_mm2": round(projected_area, 1),
        "projected_area_method": "Face-projected silhouette area (capped by volume/depth cross-check)",
        "volume_cross_section_mm2": round(volume_cross_section, 1),
        "nominal_wall_mm": round(nominal_wall, 2),
        "flow_length_mm": round(flow_length, 1),
        "flow_ratio": round(flow_ratio, 1),
        "cavity_pressure_mpa": cavity_pressure,
        "injection_pressure_mpa": injection_pressure,
        "packing_pressure_mpa": packing_pressure,
        "clamp_force_tons": clamp_force,
        "machine_size_recommendation": machine,
        "volume_based": {
            "part_volume_cm3": round(volume_cm3, 2),
            "shot_weight_part_g": shot_weight_part,
            "shot_weight_total_g": shot_weight_total,
            "runner_overhead_pct": round((runner_factor - 1) * 100, 0),
            "fill_time_s": fill_time_s,
            "packing_time_s": packing_time_s,
            "cooling_time_s": cooling_time_s,
            "cycle_time_s": cycle_time_s,
            "fill_rate_cm3s": fill_rate_cm3s,
            "min_barrel_capacity_cm3": min_barrel_cm3,
            "material_density_gcm3": density,
        },
        "material_used": material_family,
        "method": "Heuristic: face-projected silhouette area + volume cross-check, flow-ratio + viscosity factor",
        "assumptions": [
            f"Material: {material_family} (density {density} g/cm³)",
            f"Projected area: {projected_area:.0f} mm² (face projection, volume cross-check: {volume_cross_section:.0f} mm²)",
            "Single gate, center-fed",
            "Cold runner (~15% overhead)",
            f"Fill rate: {fill_rate_cm3s} cm³/s (based on {nominal_wall:.1f}mm wall)",
            "10% safety margin on clamp force",
            "Packing: 60% of injection pressure",
        ],
        "confidence": "low",
        "limitations": [
            "Not a flow simulation — no melt-front tracking or shear-thinning",
            "Projected area uses face normal projection — accurate for convex shapes, approximate for concave",
            "Gate location assumed at center, not optimized",
            "Cycle time is approximate — actual depends on cooling circuit design",
        ],
    }
