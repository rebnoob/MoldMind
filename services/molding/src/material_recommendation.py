"""Material recommendation for injection molding.

Selects 1 primary + 2 alternative materials based on:
- Wall thickness compatibility
- Shrinkage (lower = better for dimensional parts)
- Ease of molding (lower melt temp = easier)
- Feature complexity (ribs/bosses → prefer low shrinkage)

When product requirements are unknown, recommendations are conservative
and clearly labeled as assumptions.
"""

# Material database (matches db/seeds/materials.sql)
# Structured for scoring without needing DB access at analysis time.
MATERIALS = [
    {"id": "abs_generic", "name": "ABS (Generic)", "family": "ABS",
     "min_wall": 0.75, "max_wall": 3.5, "draft": 1.0, "shrinkage": 0.5,
     "melt_temp": 230, "mold_temp": 60, "cost_rank": 3, "flow_rank": 3,
     "notes": "General-purpose, good surface finish, low shrinkage"},
    {"id": "pp_generic", "name": "Polypropylene (Generic)", "family": "PP",
     "min_wall": 0.65, "max_wall": 3.8, "draft": 1.5, "shrinkage": 1.5,
     "melt_temp": 230, "mold_temp": 40, "cost_rank": 1, "flow_rank": 2,
     "notes": "Lowest cost, living hinge capable, higher shrinkage"},
    {"id": "pa6_generic", "name": "Nylon 6 (Generic)", "family": "PA",
     "min_wall": 0.45, "max_wall": 3.0, "draft": 0.5, "shrinkage": 1.2,
     "melt_temp": 260, "mold_temp": 80, "cost_rank": 5, "flow_rank": 4,
     "notes": "High strength, hygroscopic, needs drying"},
    {"id": "pc_generic", "name": "Polycarbonate (Generic)", "family": "PC",
     "min_wall": 1.0, "max_wall": 3.8, "draft": 1.0, "shrinkage": 0.6,
     "melt_temp": 300, "mold_temp": 90, "cost_rank": 6, "flow_rank": 5,
     "notes": "High impact, optically clear, tight tolerances"},
    {"id": "pom_generic", "name": "Acetal/POM (Generic)", "family": "POM",
     "min_wall": 0.75, "max_wall": 3.0, "draft": 0.5, "shrinkage": 2.0,
     "melt_temp": 210, "mold_temp": 90, "cost_rank": 4, "flow_rank": 3,
     "notes": "Low friction, dimensional stability, higher shrinkage"},
    {"id": "ps_generic", "name": "Polystyrene (Generic)", "family": "PS",
     "min_wall": 0.75, "max_wall": 4.0, "draft": 1.0, "shrinkage": 0.4,
     "melt_temp": 220, "mold_temp": 40, "cost_rank": 1, "flow_rank": 1,
     "notes": "Lowest cost, easy flow, brittle"},
    {"id": "pe_hdpe", "name": "HDPE", "family": "PE",
     "min_wall": 0.75, "max_wall": 4.0, "draft": 1.5, "shrinkage": 2.5,
     "melt_temp": 230, "mold_temp": 40, "cost_rank": 1, "flow_rank": 2,
     "notes": "Chemical resistant, high shrinkage, flexible"},
    {"id": "abs_pc", "name": "ABS/PC Blend", "family": "ABS",
     "min_wall": 0.75, "max_wall": 3.5, "draft": 1.0, "shrinkage": 0.5,
     "melt_temp": 260, "mold_temp": 80, "cost_rank": 5, "flow_rank": 4,
     "notes": "Higher impact than ABS, good for enclosures"},
    {"id": "pbt_generic", "name": "PBT (Generic)", "family": "PBT",
     "min_wall": 0.75, "max_wall": 3.0, "draft": 0.5, "shrinkage": 1.5,
     "melt_temp": 260, "mold_temp": 70, "cost_rank": 4, "flow_rank": 4,
     "notes": "Good electrical properties, chemical resistant"},
]


def recommend_material(
    thickness_analysis,
    face_infos: list,
    properties: dict,
) -> dict:
    """Recommend injection molding material based on part geometry.

    Args:
        thickness_analysis: ThicknessAnalysis object (min, max, mean)
        face_infos: List of FaceInfo (for feature types)
        properties: Part properties (volume, etc.)

    Returns:
        Material recommendation with primary + 2 alternatives
    """
    nominal_wall = thickness_analysis.mean_thickness if thickness_analysis else 2.0
    min_wall = thickness_analysis.min_thickness if thickness_analysis else 1.0
    max_wall = thickness_analysis.max_thickness if thickness_analysis else 3.0
    volume = properties.get("volume_mm3", 0)

    # Feature analysis
    has_ribs = any(f.feature_type == "rib" for f in face_infos)
    has_bosses = any(f.feature_type == "boss" for f in face_infos)
    has_thin_walls = min_wall < 1.0

    # --- Filter by wall thickness compatibility ---
    compatible = []
    eliminated = []
    for mat in MATERIALS:
        if nominal_wall < mat["min_wall"] * 0.8:
            eliminated.append({"id": mat["id"], "reason": f"Nominal wall {nominal_wall:.1f}mm below min {mat['min_wall']}mm"})
        elif nominal_wall > mat["max_wall"] * 1.2:
            eliminated.append({"id": mat["id"], "reason": f"Nominal wall {nominal_wall:.1f}mm above max {mat['max_wall']}mm"})
        else:
            compatible.append(mat)

    if not compatible:
        # Fallback: use all materials if nothing matches
        compatible = list(MATERIALS)
        eliminated = []

    # --- Score each compatible material ---
    scored = []
    for mat in compatible:
        score = 100.0

        # Shrinkage: lower is better (especially with ribs/bosses → sink marks)
        shrinkage_penalty = mat["shrinkage"] * 10  # 0.4% → 4pts, 2.5% → 25pts
        if has_ribs or has_bosses:
            shrinkage_penalty *= 1.5  # Extra penalty for features prone to sink
        score -= shrinkage_penalty

        # Ease of molding: lower melt temp = easier processing
        melt_penalty = max(0, (mat["melt_temp"] - 220) / 10)  # 220°C baseline
        score -= melt_penalty

        # Cost: lower rank = cheaper
        score -= mat["cost_rank"] * 3

        # Flow: lower rank = better flow (important for thin walls)
        if has_thin_walls:
            score -= mat["flow_rank"] * 4
        else:
            score -= mat["flow_rank"] * 2

        # Wall thickness fit: closer to center of range = better
        mid = (mat["min_wall"] + mat["max_wall"]) / 2
        fit = 1.0 - abs(nominal_wall - mid) / (mat["max_wall"] - mat["min_wall"])
        score += fit * 10

        scored.append((score, mat))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Build result
    primary = scored[0][1] if scored else MATERIALS[0]
    alts = [s[1] for s in scored[1:3]]

    def mat_rationale(mat, is_primary=False):
        reasons = []
        if nominal_wall >= mat["min_wall"] and nominal_wall <= mat["max_wall"]:
            reasons.append(f"compatible with {nominal_wall:.1f}mm wall")
        reasons.append(f"{mat['shrinkage']}% shrinkage")
        if mat["cost_rank"] <= 2:
            reasons.append("low cost")
        elif mat["cost_rank"] >= 5:
            reasons.append("higher cost")
        if mat["flow_rank"] <= 2:
            reasons.append("excellent flow")
        if mat.get("notes"):
            reasons.append(mat["notes"].split(",")[0].strip().lower())
        return "; ".join(reasons)

    assumptions = [
        "No temperature or chemical resistance requirements specified",
        "No regulatory requirements (FDA, UL) specified",
        "Cost optimization not primary — balanced recommendation",
    ]
    if has_ribs:
        assumptions.append("Part has ribs — low-shrinkage materials preferred to reduce sink marks")
    if has_bosses:
        assumptions.append("Part has bosses — low-shrinkage materials preferred")

    return {
        "primary": {
            "id": primary["id"],
            "name": primary["name"],
            "family": primary["family"],
            "shrinkage_pct": primary["shrinkage"],
            "melt_temp_c": primary["melt_temp"],
            "mold_temp_c": primary["mold_temp"],
            "rationale": mat_rationale(primary, True),
        },
        "alternatives": [
            {
                "id": m["id"],
                "name": m["name"],
                "family": m["family"],
                "rationale": mat_rationale(m),
            }
            for m in alts
        ],
        "selection_criteria": {
            "nominal_wall_mm": round(nominal_wall, 2),
            "min_wall_mm": round(min_wall, 2),
            "max_wall_mm": round(max_wall, 2),
            "has_ribs": has_ribs,
            "has_bosses": has_bosses,
            "has_thin_walls": has_thin_walls,
            "compatible_count": len(compatible),
            "eliminated_count": len(eliminated),
        },
        "assumptions": assumptions,
        "confidence": "low" if not thickness_analysis else "medium",
    }
