"""Central DFM thresholds and configuration.

All tunable parameters in one place. Rules import from here
instead of hardcoding values.
"""


class TessellationConfig:
    """Display mesh generation settings.

    Why online viewers show indexed triangles:
    - GPUs only render triangles — even Onshape/Fusion tessellate B-Rep for display.
    - Indexed geometry is normal and efficient (shared vertices, smooth normals).
    - The visual quality depends on tessellation tolerance, not the rendering method.
    - B-Rep remains the source of truth for analysis; the mesh is purely for display.
    """
    LINEAR_DEFLECTION_MM = 0.01    # Max deviation of triangle from true surface (mm)
    ANGULAR_DEFLECTION_RAD = 0.1   # Max angle between adjacent triangle normals (rad ≈ 5.7°)
    ADAPTIVE_SCALE = 0.0005        # Deflection = min(LINEAR, part_size × this)
    DEFLECTION_FLOOR_MM = 0.002    # Never go finer than this (performance guard)
    EDGE_ANGLE_THRESHOLD_DEG = 15  # Angle for detecting sharp edges in viewer (degrees)


class DfmThresholds:
    # --- Draft Angle (per-feature thresholds) ---
    # Professional tools apply different draft rules per feature type.
    DRAFT_ZERO_DEG = 0.25              # Below this = functionally zero draft
    DRAFT_CAVITY_WALL_DEG = 1.0        # External main wall (cavity side)
    DRAFT_CORE_WALL_DEG = 0.5          # Internal main wall (core side)
    DRAFT_BOSS_DEG = 0.5               # Boss cylinder walls
    DRAFT_HOLE_DEG = 0.25              # Hole/pocket walls (minimum)
    DRAFT_RIB_DEG = 0.5                # Rib walls
    DRAFT_MIN_DEFAULT_DEG = 1.0        # Fallback for material override

    # --- Face Classification (% of total surface area) ---
    FACE_MAJOR_AREA_PCT = 2.0          # Face > 2% of total = main wall
    FACE_MINOR_AREA_PCT = 0.1          # Face < 0.1% = transition (skip)
    FACE_FILLET_AREA_PCT = 1.0         # Curved face < 1% = likely fillet (skip)

    # --- Wall Thickness ---
    WALL_THICKNESS_MAX_MM = 10.0   # Ray-cast cap: ignore hits beyond this (through-cavity)
    WALL_VARIATION_WARNING_PCT = 25
    WALL_VARIATION_CRITICAL_PCT = 50
    WALL_TRANSITION_RATIO = 2.0    # Flag if adjacent face thickness ratio exceeds this

    # --- Undercuts ---
    UNDERCUT_MIN_AREA_MM2 = 0.5    # Ignore undercut faces smaller than this
    UNDERCUT_CRITICAL_COUNT = 4    # >4 undercuts = CRITICAL
    UNDERCUT_COST_PER_ACTION = "$3,000–10,000"

    # --- Parting Line ---
    PARTING_STRAIGHT_PULL_GOOD = 0.85   # Ratio of moldable faces for PASS
    PARTING_STRAIGHT_PULL_REVIEW = 0.65 # Below this = FAIL
    PARTING_MAX_UNDERCUTS_GOOD = 2
    PARTING_MAX_UNDERCUTS_REVIEW = 4

    # --- Ribs & Bosses ---
    BOSS_MAX_RADIUS_MM = 10.0       # Cylinders smaller than this = likely boss
    BOSS_SINK_WALL_RATIO = 0.60     # Boss wall > 60% of nominal wall = sink risk
    RIB_MAX_AREA_RATIO = 0.20       # Rib face < 20% of largest face
    RIB_MAX_WALL_RATIO = 0.75       # Rib > 75% of adjacent wall = sink risk

    # --- Radii / Sharp Corners ---
    # Heuristic: only flag if strong signal (many planar, zero fillet faces)
    SHARP_CORNER_MIN_PLANAR_FACES = 8
    SHARP_CORNER_MIN_TOTAL_FACES = 12
    SHARP_CORNER_MIN_FILLET_AREA_MM2 = 5.0  # Small curved face = likely fillet

    # --- Scoring ---
    SCORE_CRITICAL_DEDUCTION = 15
    SCORE_WARNING_DEDUCTION = 7
    SCORE_INFO_DEDUCTION = 2
    VERDICT_FAIL_SCORE = 40
    VERDICT_REVIEW_SCORE = 70
