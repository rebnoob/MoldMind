"""Ceramic insert feasibility analysis for injection molding.

Evaluates whether a part is a GO, CAUTION, or NO-GO candidate for
molding with ceramic inserts in a metal mold base.

This is NOT a pass/fail on injection pressure alone.
It evaluates geometry, structural loads, thermal cycling, insert
manufacturability, integration, and business viability.

Ceramic insert properties assumed (typical alumina/zirconia):
- Compressive strength: ~2500 MPa (excellent)
- Tensile strength: ~250 MPa (poor — 10× weaker than compression)
- Fracture toughness: ~4 MPa·√m (very low — brittle)
- Thermal conductivity: ~25 W/mK (lower than steel at ~50 W/mK)
- Max service temp: ~1600°C (not a limit for plastics)
- Thermal expansion: ~8 µm/m·°C (lower than steel at ~12 µm/m·°C)
"""

import math
from dataclasses import dataclass, field


@dataclass
class Check:
    """Single checklist item result."""
    name: str
    category: str
    status: str  # "pass", "caution", "fail", "unknown"
    severity: str  # "low", "medium", "high", "critical"
    finding: str  # What was found
    risk: str  # Why it matters for ceramic
    recommendation: str = ""
    value: float | str | None = None
    threshold: float | str | None = None


@dataclass
class CeramicFeasibility:
    """Complete ceramic insert feasibility result."""
    rating: str  # "GO", "CAUTION", "NO-GO"
    confidence: str  # "low", "medium", "high"
    summary: str
    checks: list[Check] = field(default_factory=list)
    top_risks: list[str] = field(default_factory=list)
    missing_inputs: list[str] = field(default_factory=list)
    could_improve: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)


def analyze_ceramic_feasibility(
    face_infos: list,
    properties: dict,
    thickness_analysis,
    topology: dict | None,
    molding_plan: dict | None,
) -> dict:
    """Run full ceramic insert feasibility analysis.

    Returns serializable dict with GO/CAUTION/NO-GO rating and detailed checklist.
    """
    checks: list[Check] = []
    missing = []
    assumptions = [
        "Ceramic material: alumina (Al₂O₃) or zirconia-toughened alumina",
        "Compressive strength ~2500 MPa, tensile ~250 MPa, fracture toughness ~4 MPa·√m",
        "Insert mounted in steel mold base with full backing support",
        "No production volume specified — defaulting to prototype/low-volume (<1000 shots)",
        "No cosmetic requirements specified — defaulting to non-cosmetic",
        "No specific resin specified — using molding plan material recommendation",
    ]

    # Extract data
    dims = properties.get("dimensions", {"x": 0, "y": 0, "z": 0})
    volume = properties.get("volume_mm3", 0)
    bbox = properties.get("bounding_box", {"min": [0,0,0], "max": [0,0,0]})
    max_dim = max(dims.get("x", 0), dims.get("y", 0), dims.get("z", 0))
    min_dim = min(d for d in [dims.get("x", 1e9), dims.get("y", 1e9), dims.get("z", 1e9)] if d > 0)

    nom_wall = thickness_analysis.mean_thickness if thickness_analysis else 2.0
    min_wall = thickness_analysis.min_thickness if thickness_analysis else 1.0
    max_wall = thickness_analysis.max_thickness if thickness_analysis else 4.0
    wall_var = thickness_analysis.variation_pct if thickness_analysis else 0

    tooling = molding_plan.get("tooling", {}) if molding_plan else {}
    pressure = molding_plan.get("pressure", {}) if molding_plan else {}
    material = molding_plan.get("material", {}) if molding_plan else {}

    proj_area = pressure.get("projected_area_mm2", 0)
    cavity_p = pressure.get("cavity_pressure_mpa", 35)
    melt_temp = material.get("primary", {}).get("melt_temp_c", 230)
    mold_temp = material.get("primary", {}).get("mold_temp_c", 60)
    side_actions = tooling.get("side_actions_needed", 0)
    undercut_count = tooling.get("undercut_count", 0)
    parting_feas = tooling.get("parting_feasibility", "unknown")
    complexity = tooling.get("complexity_level", "unknown")

    # Feature counts
    feature_types = {}
    for f in face_infos:
        ft = getattr(f, "feature_type", "other")
        feature_types[ft] = feature_types.get(ft, 0) + 1

    boss_count = feature_types.get("boss", 0)
    hole_count = feature_types.get("hole", 0)
    rib_count = feature_types.get("rib", 0)
    fillet_count = feature_types.get("fillet", 0)

    # Edge analysis
    concave_edges = 0
    if topology:
        concave_edges = sum(1 for e in topology.get("edges", []) if e.get("convexity") == "concave")

    # ========================================================
    # 1. PART GEOMETRY SCREEN
    # ========================================================

    # Part size
    if max_dim > 300:
        checks.append(Check("Part size", "geometry", "fail", "critical",
            f"Max dimension {max_dim:.0f}mm exceeds typical ceramic insert range",
            "Large ceramic inserts are expensive, fragile to handle, and hard to support uniformly",
            "Consider ceramic only for small/medium features, not full-size cavity"))
    elif max_dim > 150:
        checks.append(Check("Part size", "geometry", "caution", "medium",
            f"Max dimension {max_dim:.0f}mm — medium-sized for ceramic insert",
            "Larger inserts have higher thermal mass and more risk of uneven support",
            value=max_dim, threshold=150))
    else:
        checks.append(Check("Part size", "geometry", "pass", "low",
            f"Max dimension {max_dim:.0f}mm — suitable for ceramic insert",
            "Small parts are good candidates — insert is compact and well-supported",
            value=max_dim, threshold=150))

    # Projected area
    if proj_area > 10000:
        checks.append(Check("Projected area", "geometry", "fail", "critical",
            f"Projected area {proj_area:.0f}mm² creates high total load on insert",
            "Ceramic can handle high compressive stress but large area = high total force = mounting risk"))
    elif proj_area > 5000:
        checks.append(Check("Projected area", "geometry", "caution", "medium",
            f"Projected area {proj_area:.0f}mm² — moderate total load",
            "Ensure full backing support behind insert; no unsupported spans",
            value=proj_area, threshold=5000))
    else:
        checks.append(Check("Projected area", "geometry", "pass", "low",
            f"Projected area {proj_area:.0f}mm² — manageable for ceramic insert",
            "", value=proj_area, threshold=5000))

    # Wall thickness
    if min_wall < 0.5:
        checks.append(Check("Thin walls", "geometry", "fail", "critical",
            f"Min wall {min_wall:.2f}mm — very thin sections create high-speed fill with thermal shock",
            "Thin walls require fast fill → high injection speed → high shear → thermal shock on insert surface"))
    elif min_wall < 1.0:
        checks.append(Check("Thin walls", "geometry", "caution", "medium",
            f"Min wall {min_wall:.2f}mm — thin sections may need fast fill",
            "Fast fill increases thermal cycling severity on ceramic surface",
            value=min_wall, threshold=1.0))
    else:
        checks.append(Check("Thin walls", "geometry", "pass", "low",
            f"Min wall {min_wall:.2f}mm — standard thickness",
            "", value=min_wall, threshold=1.0))

    # Thick sections
    if max_wall > 6:
        checks.append(Check("Thick sections", "geometry", "caution", "medium",
            f"Max wall {max_wall:.2f}mm — thick sections retain heat, creating hot spots on insert",
            "Hot spots cause localized thermal expansion → stress concentration in ceramic"))
    else:
        checks.append(Check("Thick sections", "geometry", "pass", "low",
            f"Max wall {max_wall:.2f}mm — acceptable", "", value=max_wall, threshold=6))

    # Wall transitions
    if wall_var > 50:
        checks.append(Check("Wall transitions", "geometry", "caution", "high",
            f"Wall thickness varies {wall_var:.0f}% — abrupt transitions create differential thermal load",
            "Ceramic inserts are sensitive to thermal gradients; abrupt transitions = hot/cold interface = stress"))
    elif wall_var > 25:
        checks.append(Check("Wall transitions", "geometry", "caution", "medium",
            f"Wall thickness varies {wall_var:.0f}% — moderate variation",
            "Monitor for differential cooling effects on ceramic surface",
            value=wall_var, threshold=25))
    else:
        checks.append(Check("Wall transitions", "geometry", "pass", "low",
            f"Wall thickness varies {wall_var:.0f}% — uniform", "", value=wall_var, threshold=25))

    # Sharp internal corners (concave edges)
    if concave_edges > 20:
        checks.append(Check("Internal corners", "geometry", "caution", "high",
            f"{concave_edges} concave edges — many internal corners = stress concentrators in ceramic",
            "Ceramic has very low fracture toughness; internal corners act as crack initiation sites",
            "Add generous radii (≥0.5mm) at all internal corners"))
    elif concave_edges > 5:
        checks.append(Check("Internal corners", "geometry", "caution", "medium",
            f"{concave_edges} concave edges — some internal corners to review",
            "Each sharp internal corner is a potential crack initiation site in ceramic",
            value=concave_edges, threshold=5))
    else:
        checks.append(Check("Internal corners", "geometry", "pass", "low",
            f"{concave_edges} concave edges — few internal corners", ""))

    # Bosses
    if boss_count > 3:
        checks.append(Check("Bosses", "geometry", "caution", "high",
            f"{boss_count} bosses — each creates a concentrated load point during ejection",
            "Boss pins in ceramic are fragile; they create localized bending stress at base",
            "Consider steel boss pins inserted through ceramic insert"))
    elif boss_count > 0:
        checks.append(Check("Bosses", "geometry", "caution", "medium",
            f"{boss_count} boss(es) — review ejection loads at boss locations",
            "Boss features in ceramic need careful backing support"))
    else:
        checks.append(Check("Bosses", "geometry", "pass", "low", "No bosses", ""))

    # Holes / slots
    if hole_count > 5:
        checks.append(Check("Holes/slots", "geometry", "fail", "critical",
            f"{hole_count} holes — many openings weaken the ceramic insert structurally",
            "Each hole in the ceramic insert removes material, creating thin sections and stress risers",
            "Use steel core pins through the ceramic insert instead of ceramic holes"))
    elif hole_count > 0:
        checks.append(Check("Holes/slots", "geometry", "caution", "medium",
            f"{hole_count} hole(s) — each hole weakens ceramic locally",
            "Consider steel inserts for core pins rather than ceramic-on-ceramic",
            value=hole_count, threshold=5))
    else:
        checks.append(Check("Holes/slots", "geometry", "pass", "low", "No holes", ""))

    # Ribs
    if rib_count > 0:
        checks.append(Check("Deep ribs", "geometry", "caution", "high",
            f"{rib_count} rib feature(s) — ribs create thin, deep slots in the insert",
            "Thin rib slots in ceramic are extremely fragile; they concentrate bending stress and chip easily",
            "Limit rib depth to <3× wall thickness; add generous draft"))

    # ========================================================
    # 2. MOLDABILITY / TOOLING SCREEN
    # ========================================================

    checks.append(Check("Parting line", "tooling",
        "pass" if parting_feas == "good" else "caution" if parting_feas == "challenging" else "fail",
        "low" if parting_feas == "good" else "medium" if parting_feas == "challenging" else "high",
        f"Parting feasibility: {parting_feas}",
        "Complex parting lines create thin ceramic shutoff edges that chip easily"))

    if side_actions > 0:
        checks.append(Check("Side actions", "tooling", "caution" if side_actions <= 2 else "fail",
            "high" if side_actions > 2 else "medium",
            f"{side_actions} side action(s) needed",
            "Side actions create local concentrated loads on ceramic edges; each action point is a chip risk",
            "Use steel side-action components interfacing with ceramic cavity insert"))
    else:
        checks.append(Check("Side actions", "tooling", "pass", "low", "No side actions needed", ""))

    if undercut_count > 0:
        checks.append(Check("Undercuts", "tooling", "caution", "medium",
            f"{undercut_count} undercut(s)",
            "Undercut regions require mechanical action against the insert surface",
            value=undercut_count))

    # Ejection
    checks.append(Check("Ejection strategy", "tooling", "caution", "medium",
        "Ejection loads act on ceramic surface — review pin layout",
        "Ejector pins push directly against the insert; concentrated point loads on brittle ceramic = chip risk",
        "Use large-diameter ejector pins and distribute force evenly; avoid pins near thin sections"))

    # ========================================================
    # 3. STRUCTURAL SCREEN
    # ========================================================

    # Total cavity force
    total_force_kn = proj_area * cavity_p / 1000  # mm² × MPa = N → kN
    checks.append(Check("Cavity force", "structural",
        "pass" if total_force_kn < 50 else "caution" if total_force_kn < 200 else "fail",
        "low" if total_force_kn < 50 else "medium" if total_force_kn < 200 else "critical",
        f"Total cavity force: {total_force_kn:.0f} kN ({cavity_p:.0f} MPa × {proj_area:.0f} mm²)",
        "Ceramic handles compression well but total force determines required backing support quality",
        value=total_force_kn, threshold=200))

    # Average compressive stress on insert (assuming full backing)
    avg_stress = cavity_p  # With full backing, stress ≈ cavity pressure
    checks.append(Check("Avg compressive stress", "structural", "pass", "low",
        f"Average compressive stress ~{avg_stress:.0f} MPa (cavity pressure, fully backed)",
        "Well below ceramic compressive strength of 2500 MPa — bulk compression is not the failure mode",
        "The real risk is LOCAL bending, tension, and edge chipping — not average compression"))

    # Local bending risk
    part_depth = dims.get("z", 0)  # Depth in pull direction
    if part_depth > 30 and boss_count + hole_count > 0:
        checks.append(Check("Local bending risk", "structural", "caution", "high",
            f"Part depth {part_depth:.0f}mm with {boss_count + hole_count} boss/hole features",
            "Deep features create cantilever-like loading on ceramic walls → local bending → tensile failure",
            "Ensure all deep features have full steel backing behind ceramic insert"))
    elif part_depth > 50:
        checks.append(Check("Local bending risk", "structural", "caution", "medium",
            f"Part depth {part_depth:.0f}mm — deep cavity may create bending moments on insert walls",
            "Deep inserts need full peripheral support to prevent bending"))
    else:
        checks.append(Check("Local bending risk", "structural", "pass", "low",
            f"Part depth {part_depth:.0f}mm — shallow cavity, low bending risk", ""))

    # Edge chipping risk
    checks.append(Check("Edge chipping risk", "structural",
        "caution" if concave_edges > 3 or side_actions > 0 else "pass",
        "high" if concave_edges > 10 or side_actions > 1 else "medium",
        "Ceramic edges chip under impact or concentrated loads",
        "Every mold closure cycle impacts the parting line edges; ceramic is brittle at edges",
        "Add chamfers on all ceramic edges; use steel inserts at high-wear parting line areas"))

    # ========================================================
    # 4. THERMAL SCREEN
    # ========================================================

    thermal_delta = melt_temp - mold_temp
    checks.append(Check("Thermal gradient", "thermal",
        "pass" if thermal_delta < 200 else "caution" if thermal_delta < 300 else "fail",
        "low" if thermal_delta < 200 else "medium" if thermal_delta < 300 else "high",
        f"ΔT = {thermal_delta}°C (melt {melt_temp}°C → mold {mold_temp}°C)",
        "High thermal gradients cause thermal shock in brittle ceramics; each cycle = stress cycle",
        value=thermal_delta, threshold=250))

    if melt_temp > 280:
        checks.append(Check("High melt temp", "thermal", "caution", "high",
            f"Melt temperature {melt_temp}°C — high-temp resins are more aggressive on insert surface",
            "High-temp materials (PC, PA) create more severe thermal cycling"))
    else:
        checks.append(Check("Melt temperature", "thermal", "pass", "low",
            f"Melt temperature {melt_temp}°C — standard range", ""))

    checks.append(Check("Thermal conductivity", "thermal", "caution", "medium",
        "Ceramic thermal conductivity ~25 W/mK vs steel ~50 W/mK",
        "Slower heat extraction → longer cycle time and potential hot spots",
        "Expect 15-30% longer cycle times compared to steel tooling"))

    # ========================================================
    # 5. INSERT-TO-BASE INTEGRATION
    # ========================================================

    checks.append(Check("Thermal expansion mismatch", "integration", "caution", "medium",
        "Ceramic CTE ~8 µm/m·°C vs steel ~12 µm/m·°C",
        "At mold operating temperature, steel expands more than ceramic → gap at edges → potential flash",
        "Design pocket with thermal expansion tolerance; use interference fit at room temp"))

    if max_dim > 100:
        checks.append(Check("Insert mounting", "integration", "caution", "high",
            f"Insert size {max_dim:.0f}mm — large inserts need precise pocket fit",
            "Large ceramic inserts are hard to retain securely without stress concentrations at clamp points"))
    else:
        checks.append(Check("Insert mounting", "integration", "pass", "low",
            f"Insert size {max_dim:.0f}mm — standard insert mounting feasible", ""))

    checks.append(Check("Backing support", "integration", "caution", "high",
        "Full backing behind all loaded regions is REQUIRED for ceramic inserts",
        "Any unsupported span creates bending → tensile stress → crack → catastrophic failure",
        "No air gaps, no unsupported overhangs, no cantilevered ceramic features"))

    # ========================================================
    # 6. MANUFACTURING THE INSERT
    # ========================================================

    face_count = properties.get("face_count", 0)
    if face_count > 100:
        checks.append(Check("Geometric complexity", "manufacturing", "caution", "high",
            f"{face_count} B-Rep faces — complex geometry increases sintering distortion risk",
            "Ceramic inserts are sintered and shrink ~15-20%; complex shapes distort non-uniformly"))
    else:
        checks.append(Check("Geometric complexity", "manufacturing", "pass", "low",
            f"{face_count} B-Rep faces — manageable complexity", ""))

    checks.append(Check("Sintering shrinkage", "manufacturing", "caution", "medium",
        "Ceramic shrinks ~15-20% during sintering — all dimensions must be oversized",
        "Anisotropic shrinkage can cause distortion; critical dimensions may not hold ±0.1mm",
        "Expect ±0.5% dimensional variation; plan for post-sintering grinding on critical surfaces"))

    if fillet_count == 0 and concave_edges > 5:
        checks.append(Check("Post-processing", "manufacturing", "caution", "medium",
            "No fillets detected — sharp corners need post-sintering grinding or polishing",
            "Sharp edges in green ceramic chip during handling and firing"))

    # ========================================================
    # 7. PROCESS / MATERIAL SCREEN
    # ========================================================

    mat_name = material.get("primary", {}).get("name", "Unknown")
    checks.append(Check("Resin compatibility", "process",
        "pass" if melt_temp < 260 else "caution",
        "low" if melt_temp < 260 else "medium",
        f"Material: {mat_name} (melt {melt_temp}°C)",
        "Low-melt resins (ABS, PP, PS) are gentler on ceramic; high-temp resins (PC, PA) are more aggressive"))

    if cavity_p > 80:
        checks.append(Check("Injection pressure", "process", "caution", "high",
            f"Cavity pressure {cavity_p:.0f} MPa — high pressure increases structural load",
            "While ceramic handles compression, high pressure intensifies edge/corner/thin-section risks"))
    else:
        checks.append(Check("Injection pressure", "process", "pass", "low",
            f"Cavity pressure {cavity_p:.0f} MPa — within typical range for ceramic", ""))

    # ========================================================
    # 8. TOOL LIFE / BUSINESS SCREEN
    # ========================================================

    checks.append(Check("Prototype feasibility", "business", "pass", "low",
        "Ceramic inserts are well-suited for prototype runs (<100 shots)",
        "Low tooling cost, fast turnaround; acceptable for functional prototyping"))

    checks.append(Check("Low-volume feasibility", "business",
        "caution" if complexity != "complex" else "fail",
        "medium" if complexity != "complex" else "high",
        f"Low-volume (100-1000 shots): {'feasible with care' if complexity != 'complex' else 'risky for complex parts'}",
        "Ceramic inserts typically last 500-5000 shots depending on geometry and material"))

    checks.append(Check("Production feasibility", "business", "fail", "critical",
        "Ceramic inserts are NOT suitable for production volumes (>5000 shots)",
        "Insert wear, chipping, and thermal fatigue make ceramic uneconomic for production",
        "For production: use steel or pre-hardened steel tooling"))

    # ========================================================
    # 9. DECISION LOGIC
    # ========================================================

    fail_count = sum(1 for c in checks if c.status == "fail")
    caution_high = sum(1 for c in checks if c.status == "caution" and c.severity in ("high", "critical"))
    caution_count = sum(1 for c in checks if c.status == "caution")
    pass_count = sum(1 for c in checks if c.status == "pass")

    if fail_count >= 2 or (fail_count >= 1 and caution_high >= 3):
        rating = "NO-GO"
        summary = (
            f"This part has {fail_count} critical failure(s) and {caution_high} high-severity cautions. "
            f"Ceramic inserts are not recommended without significant design changes."
        )
    elif fail_count >= 1 or caution_high >= 3:
        rating = "CAUTION"
        summary = (
            f"Ceramic inserts are possible but risky. {fail_count} failure(s) and {caution_high} high-severity cautions "
            f"require mitigation. Recommended only for prototype/low-volume with steel backing at risk areas."
        )
    elif caution_count > pass_count:
        rating = "CAUTION"
        summary = (
            f"Geometry is workable but {caution_count} caution items need review. "
            f"Recommended for prototype runs with careful insert design and full backing support."
        )
    else:
        rating = "GO"
        summary = (
            f"Part geometry and process conditions are compatible with ceramic inserts. "
            f"{pass_count} checks pass, {caution_count} cautions. Suitable for prototype and low-volume production."
        )

    # Top risks
    top_risks = [
        c.finding + " — " + c.risk
        for c in sorted(checks, key=lambda c: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(c.severity, 4))
        if c.status in ("fail", "caution") and c.severity in ("critical", "high")
    ][:5]

    # Missing inputs
    missing = [
        "Production volume (assumed prototype/low-volume)",
        "Cosmetic surface requirements (assumed non-cosmetic)",
        "Specific resin grade (using molding plan recommendation)",
        "Insert material grade (assumed alumina or ZTA)",
        "Exact gate location and runner design",
    ]

    # What could improve the rating
    could_improve = []
    if rating == "NO-GO":
        could_improve = [
            "Redesign to reduce/eliminate holes and slots (use steel core pins instead)",
            "Reduce part size or split into smaller insert regions",
            "Add generous radii to all internal corners (≥1mm)",
            "Simplify parting line to avoid thin shutoff edges",
            "Use ceramic only for cavity surface with full steel backing structure",
        ]
    elif rating == "CAUTION":
        could_improve = [
            "Add full steel backing behind all loaded ceramic surfaces",
            "Use steel inserts for boss pins, core pins, and side-action interfaces",
            "Add radii to all sharp corners in the insert design",
            "Choose a low-melt-temp resin (ABS, PP) to reduce thermal shock",
            "Limit to <500 shots for initial trials",
        ]

    confidence = "medium" if molding_plan else "low"

    return {
        "rating": rating,
        "confidence": confidence,
        "summary": summary,
        "checks": [
            {
                "name": c.name,
                "category": c.category,
                "status": c.status,
                "severity": c.severity,
                "finding": c.finding,
                "risk": c.risk,
                "recommendation": c.recommendation,
                "value": c.value,
                "threshold": c.threshold,
            }
            for c in checks
        ],
        "statistics": {
            "total_checks": len(checks),
            "pass": pass_count,
            "caution": caution_count,
            "fail": fail_count,
            "caution_high": caution_high,
        },
        "top_risks": top_risks,
        "missing_inputs": missing,
        "could_improve": could_improve,
        "assumptions": assumptions,
    }
