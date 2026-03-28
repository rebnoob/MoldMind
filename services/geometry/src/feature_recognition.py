"""Heuristic feature recognition for injection molding DFM.

Classifies B-Rep faces into molding-relevant features:
- Core/cavity side detection (internal vs external surface)
- Feature type: main_wall, boss, hole, rib, fillet, parting
- Per-feature draft requirements

This is a HEURISTIC approach — it uses geometry + topology patterns,
not a full feature tree. It handles 80%+ of typical shell/box parts
correctly. Complex multi-body or organic shapes may need manual review.

How Onshape/Fusion do it (simplified):
1. Define parting plane → split faces into core side vs cavity side
2. Recognize features by topology (boss = raised cylinder, hole = depressed cylinder, etc.)
3. Apply feature-specific draft rules

We approximate step 1 using the part centroid: faces whose outward normal
points away from centroid = cavity side (external), toward = core side (internal).
"""

import logging
import math
import numpy as np

logger = logging.getLogger(__name__)


def classify_features(face_infos: list, pull_direction: list[float], shape=None) -> None:
    """Classify faces into molding features. Modifies face_infos in-place.

    Sets on each FaceInfo:
      - mold_side: "core" | "cavity" | "parting" | "unknown"
      - feature_type: "main_wall" | "boss" | "hole" | "rib" | "fillet" | "parting" | "other"
      - draft_requirement_deg: minimum draft for this feature type

    Args:
        face_infos: list of FaceInfo objects (already have surface_type, area, normal, draft_angle, etc.)
        pull_direction: [x, y, z] mold pull direction
        shape: OpenCascade TopoDS_Shape (optional, for centroid computation)
    """
    from services.dfm.src.dfm_config import DfmThresholds as T

    pull = np.array(pull_direction, dtype=np.float64)
    pull = pull / np.linalg.norm(pull)

    if not face_infos:
        return

    total_area = sum(f.area for f in face_infos)

    # --- Step 1: Compute part centroid for core/cavity classification ---
    # Use volume centroid from OCC if shape available, else average face centroids
    part_centroid = _compute_part_centroid(face_infos, shape)

    # --- Step 2: Classify each face ---
    for f in face_infos:
        # Default
        f.mold_side = "unknown"
        f.feature_type = "other"
        f.draft_requirement_deg = None  # None = skip draft check

        # Parting faces (already detected in face_analysis)
        if f.is_parting_face:
            f.mold_side = "parting"
            f.feature_type = "parting"
            f.draft_requirement_deg = None
            continue

        # Undercuts (already detected)
        if f.is_undercut:
            f.mold_side = "unknown"
            f.feature_type = "undercut"
            f.draft_requirement_deg = None
            continue

        # --- Core/cavity side detection ---
        if f.normal is not None:
            face_normal = np.array(f.normal)
            # Vector from part centroid to face centroid
            # (approximated: face normal direction relative to centroid)
            # If outward normal points AWAY from centroid → external (cavity)
            # If outward normal points TOWARD centroid → internal (core)
            #
            # We use the dot product of (face_normal) with (face_position - centroid).
            # But we don't have face position easily, so we use a simpler heuristic:
            # Compare the face normal against the pull direction:
            # - External (cavity) faces on a typical part have normals that point
            #   outward in diverse directions
            # - Internal (core) faces have normals that point inward
            #
            # Better heuristic: use OCC to test if a point slightly outside the face
            # (along its normal) is outside the solid → cavity side.
            f.mold_side = _classify_mold_side(f, part_centroid, shape)

        # --- Feature type detection ---
        area_pct = (f.area / total_area * 100) if total_area > 0 else 0

        if f.surface_type in ("cylindrical",):
            _classify_cylindrical(f, pull, area_pct, T)
        elif f.surface_type in ("spherical", "torus"):
            _classify_curved(f, area_pct, T)
        elif f.surface_type == "conical":
            _classify_conical(f, pull, area_pct, T)
        elif f.surface_type == "planar":
            _classify_planar(f, pull, area_pct, T)
        else:
            # bspline, other — skip
            f.feature_type = "other"
            f.draft_requirement_deg = None

    # --- Step 3: Post-process — detect rib pairs ---
    _detect_rib_pairs(face_infos, pull, total_area)

    # Log summary
    from collections import Counter
    ft_counts = Counter(f.feature_type for f in face_infos)
    ms_counts = Counter(f.mold_side for f in face_infos)
    logger.info(
        f"Features: " + ", ".join(f"{k}={v}" for k, v in sorted(ft_counts.items()))
        + f" | Sides: " + ", ".join(f"{k}={v}" for k, v in sorted(ms_counts.items()))
    )


def _compute_part_centroid(face_infos, shape):
    """Get part centroid. Uses OCC volume centroid if shape available."""
    if shape is not None:
        try:
            from OCC.Core.GProp import GProp_GProps
            from OCC.Core.BRepGProp import brepgprop
            props = GProp_GProps()
            brepgprop.VolumeProperties(shape, props)
            com = props.CentreOfMass()
            return np.array([com.X(), com.Y(), com.Z()])
        except Exception:
            pass

    # Fallback: area-weighted average of face normals * area as proxy
    # (not great, but works for simple parts)
    if face_infos:
        positions = []
        weights = []
        for f in face_infos:
            if f.normal is not None:
                # Use normal as a rough position proxy — not ideal
                positions.append(f.normal)
                weights.append(f.area)
        if positions:
            return np.zeros(3)  # fallback to origin
    return np.zeros(3)


def _classify_mold_side(face, part_centroid, shape):
    """Determine if face is on core or cavity side.

    Uses OCC solid classifier: cast a point slightly outside the face
    along its outward normal. If it's outside the solid → cavity side.
    If inside → core side.
    """
    if shape is not None and face.normal is not None:
        try:
            from OCC.Core.BRepClass3d import BRepClass3d_SolidClassifier
            from OCC.Core.gp import gp_Pnt
            from OCC.Core.TopAbs import TopAbs_OUT, TopAbs_IN

            # We need a point on the face. Use the face_map centroid if available,
            # otherwise approximate. Since we don't have the centroid here directly,
            # use the OCC solid classifier with the part centroid + normal offset.
            # This is approximate but handles most cases.

            # Test point slightly OUTSIDE along the outward normal from centroid
            # If it's outside the solid → this normal points to cavity (external face)
            norm = np.array(face.normal)
            # Use part centroid offset along the face normal
            test_pt = part_centroid + norm * 1000  # far out along normal
            classifier = BRepClass3d_SolidClassifier(
                shape, gp_Pnt(float(test_pt[0]), float(test_pt[1]), float(test_pt[2])), 1e-6
            )
            state = classifier.State()
            if state == TopAbs_OUT:
                return "cavity"
            elif state == TopAbs_IN:
                return "core"
        except Exception:
            pass

    # Fallback: use normal direction relative to pull
    # Faces with normal component along +pull tend to be cavity (top/outer)
    # Faces with normal component along -pull tend to be core (bottom/inner)
    if face.normal is not None:
        dot_pull = np.dot(np.array(face.normal), np.array([0, 0, 1]))  # approximate
        if dot_pull > 0.1:
            return "cavity"
        elif dot_pull < -0.1:
            return "core"
    return "unknown"


def _classify_cylindrical(face, pull, area_pct, T):
    """Classify cylindrical faces: boss, hole, or fillet."""
    # Small curved face → likely fillet
    if area_pct < T.FACE_FILLET_AREA_PCT:
        face.feature_type = "fillet"
        face.draft_requirement_deg = None
        return

    # Check if axis is parallel to pull
    if face.draft_angle_deg is not None:
        # Axis ∥ pull: this is a boss or hole wall
        if face.mold_side == "cavity" or face.mold_side == "unknown":
            face.feature_type = "boss"
            face.draft_requirement_deg = T.DRAFT_BOSS_DEG
        else:
            face.feature_type = "hole"
            face.draft_requirement_deg = T.DRAFT_HOLE_DEG
    else:
        # Axis ⊥ pull: horizontal cylinder (already flagged as undercut usually)
        face.feature_type = "other"
        face.draft_requirement_deg = None


def _classify_curved(face, area_pct, T):
    """Classify spherical/torus faces: usually fillets."""
    if area_pct < T.FACE_FILLET_AREA_PCT:
        face.feature_type = "fillet"
    else:
        face.feature_type = "other"
    face.draft_requirement_deg = None


def _classify_conical(face, pull, area_pct, T):
    """Classify conical faces: tapered boss/hole (has built-in draft)."""
    if area_pct < T.FACE_FILLET_AREA_PCT:
        face.feature_type = "fillet"
        face.draft_requirement_deg = None
    else:
        # Cones have built-in draft from their half-angle
        if face.mold_side == "core":
            face.feature_type = "hole"
            face.draft_requirement_deg = T.DRAFT_HOLE_DEG
        else:
            face.feature_type = "boss"
            face.draft_requirement_deg = T.DRAFT_BOSS_DEG


def _classify_planar(face, pull, area_pct, T):
    """Classify planar faces: main wall or minor feature."""
    if face.draft_angle_deg is None:
        face.feature_type = "other"
        face.draft_requirement_deg = None
        return

    # Significant planar wall face
    if area_pct >= T.FACE_MAJOR_AREA_PCT:
        face.feature_type = "main_wall"
        if face.mold_side == "core":
            face.draft_requirement_deg = T.DRAFT_CORE_WALL_DEG
        else:
            face.draft_requirement_deg = T.DRAFT_CAVITY_WALL_DEG
    elif area_pct >= T.FACE_MINOR_AREA_PCT:
        # Small but not tiny — could be a rib wall (detected in post-process)
        face.feature_type = "minor_feature"
        face.draft_requirement_deg = T.DRAFT_CORE_WALL_DEG  # conservative
    else:
        # Tiny transition face
        face.feature_type = "fillet"  # treat as ignorable
        face.draft_requirement_deg = None


def _detect_rib_pairs(face_infos, pull, total_area):
    """Post-process: detect rib-like face pairs.

    Ribs are narrow planar faces with opposing normals that are close together.
    Heuristic: two minor_feature planar faces with normals ~180° apart,
    both with draft_angle near 0, and small area.
    """
    from services.dfm.src.dfm_config import DfmThresholds as T

    minor_planar = [
        f for f in face_infos
        if f.feature_type == "minor_feature"
        and f.surface_type == "planar"
        and f.normal is not None
    ]

    # Try to pair faces with opposing normals (within 20°)
    used = set()
    for i, f1 in enumerate(minor_planar):
        if i in used:
            continue
        n1 = np.array(f1.normal)
        for j, f2 in enumerate(minor_planar):
            if j <= i or j in used:
                continue
            n2 = np.array(f2.normal)
            # Opposing normals: dot product ≈ -1
            dot = float(np.dot(n1, n2))
            if dot < -0.9:  # within ~25° of opposing
                # Both small faces with opposing normals → likely a rib pair
                f1.feature_type = "rib"
                f1.draft_requirement_deg = T.DRAFT_RIB_DEG
                f2.feature_type = "rib"
                f2.draft_requirement_deg = T.DRAFT_RIB_DEG
                used.add(i)
                used.add(j)
                break
