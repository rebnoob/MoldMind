"""Extract full B-Rep topology from an OpenCascade shape.

Produces a serializable topology dict with:
- Bodies (solids)
- Faces with surface type, params, orientation, adjacency
- Edges with curve type, params, face incidence, convexity
- Vertices with coordinates and edge incidence
- Stable IDs for cross-session reference
- Feature annotations from the DFM feature recognizer

The display mesh (GLB) is generated SEPARATELY from this data.
This module captures the CAD model; the mesh is just for rendering.
"""

import hashlib
import logging
import math
import numpy as np

logger = logging.getLogger(__name__)


def extract_topology(shape, face_infos: list, face_map: list[dict]) -> dict:
    """Extract complete B-Rep topology from an OCC shape.

    Args:
        shape: OpenCascade TopoDS_Shape
        face_infos: list of FaceInfo from face_analysis (with feature_type, mold_side)
        face_map: face_map from tessellator (for mesh mapping)

    Returns:
        dict: Complete topology structure (serializable to JSON)
    """
    from OCC.Core.TopExp import TopExp_Explorer, topexp
    from OCC.Core.TopAbs import (
        TopAbs_SOLID, TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX,
        TopAbs_FORWARD, TopAbs_REVERSED,
    )
    from OCC.Core.TopoDS import topods
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve
    from OCC.Core.GeomAbs import (
        GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere,
        GeomAbs_BSplineSurface, GeomAbs_Torus,
        GeomAbs_Line, GeomAbs_Circle, GeomAbs_Ellipse, GeomAbs_BSplineCurve,
    )
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape

    # --- Build topology maps ---
    # Map edges → adjacent faces
    edge_face_map = TopTools_IndexedDataMapOfShapeListOfShape()
    topexp.MapShapesAndAncestors(shape, TopAbs_EDGE, TopAbs_FACE, edge_face_map)

    # Map vertices → adjacent edges
    vert_edge_map = TopTools_IndexedDataMapOfShapeListOfShape()
    topexp.MapShapesAndAncestors(shape, TopAbs_VERTEX, TopAbs_EDGE, vert_edge_map)

    # --- Index all topology entities ---
    # We need stable ordering: use TopExp_Explorer which gives deterministic order

    # Index faces (same order as face_analysis)
    face_shapes = []
    face_shape_map = {}  # hash(face) → face_index
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    fidx = 0
    while exp.More():
        f = topods.Face(exp.Current())
        face_shapes.append(f)
        face_shape_map[f.__hash__()] = fidx
        fidx += 1
        exp.Next()

    # Index edges
    edge_shapes = []
    edge_shape_map = {}
    exp = TopExp_Explorer(shape, TopAbs_EDGE)
    eidx = 0
    while exp.More():
        e = topods.Edge(exp.Current())
        h = e.__hash__()
        if h not in edge_shape_map:  # Skip duplicate edges (shared between faces)
            edge_shapes.append(e)
            edge_shape_map[h] = eidx
            eidx += 1
        exp.Next()

    # Index vertices
    vert_shapes = []
    vert_shape_map = {}
    exp = TopExp_Explorer(shape, TopAbs_VERTEX)
    vidx = 0
    while exp.More():
        v = topods.Vertex(exp.Current())
        h = v.__hash__()
        if h not in vert_shape_map:
            vert_shapes.append(v)
            vert_shape_map[h] = vidx
            vidx += 1
        exp.Next()

    # --- Extract bodies ---
    bodies = []
    exp = TopExp_Explorer(shape, TopAbs_SOLID)
    body_idx = 0
    while exp.More():
        solid = topods.Solid(exp.Current())
        # Find faces belonging to this solid
        body_face_ids = []
        fexp = TopExp_Explorer(solid, TopAbs_FACE)
        while fexp.More():
            fh = topods.Face(fexp.Current()).__hash__()
            if fh in face_shape_map:
                body_face_ids.append(face_shape_map[fh])
            fexp.Next()

        # Volume
        props = GProp_GProps()
        brepgprop.VolumeProperties(solid, props)

        bodies.append({
            "id": body_idx,
            "face_ids": sorted(set(body_face_ids)),
            "volume_mm3": round(abs(props.Mass()), 2),
        })
        body_idx += 1
        exp.Next()

    # If no solids found (e.g., sheet body), create a single body with all faces
    if not bodies:
        bodies = [{"id": 0, "face_ids": list(range(len(face_shapes))), "volume_mm3": 0}]

    # --- Extract faces ---
    faces_data = []
    for fidx, face in enumerate(face_shapes):
        adaptor = BRepAdaptor_Surface(face)
        surf_type = adaptor.GetType()
        orientation = "forward" if face.Orientation() == TopAbs_FORWARD else "reversed"

        # Surface type and params
        stype, sparams = _extract_surface_params(adaptor, surf_type)

        # Face area
        props = GProp_GProps()
        brepgprop.SurfaceProperties(face, props)
        area = round(abs(props.Mass()), 4)

        # Edges of this face
        face_edge_ids = []
        eexp = TopExp_Explorer(face, TopAbs_EDGE)
        while eexp.More():
            eh = topods.Edge(eexp.Current()).__hash__()
            if eh in edge_shape_map:
                eid = edge_shape_map[eh]
                if eid not in face_edge_ids:
                    face_edge_ids.append(eid)
            eexp.Next()

        # Vertices of this face
        face_vertex_ids = []
        vexp = TopExp_Explorer(face, TopAbs_VERTEX)
        while vexp.More():
            vh = topods.Vertex(vexp.Current()).__hash__()
            if vh in vert_shape_map:
                vid = vert_shape_map[vh]
                if vid not in face_vertex_ids:
                    face_vertex_ids.append(vid)
            vexp.Next()

        # Adjacent faces (faces sharing an edge)
        adjacent_face_ids = set()
        for eid in face_edge_ids:
            edge = edge_shapes[eid]
            if edge_face_map.Contains(edge):
                adj_faces = edge_face_map.FindFromKey(edge)
                for af in adj_faces:
                    afh = af.__hash__()
                    if afh in face_shape_map and face_shape_map[afh] != fidx:
                        adjacent_face_ids.add(face_shape_map[afh])

        # Get centroid and normal from face_map (already computed by tessellator)
        centroid = [0, 0, 0]
        normal = [0, 0, 1]
        mesh_vert_start = 0
        mesh_vert_end = 0
        if fidx < len(face_map):
            fm = face_map[fidx]
            centroid = fm.get("centroid", centroid)
            normal = fm.get("normal", normal)
            mesh_vert_start = fm.get("vert_start", 0)
            mesh_vert_end = fm.get("vert_end", 0)

        # Stable ID: hash includes edge count + adj count + orientation for symmetry disambiguation
        stable_id = _make_face_stable_id(
            stype, sparams, area, centroid,
            edge_count=len(face_edge_ids),
            adj_count=len(adjacent_face_ids),
            orientation=orientation,
        )

        face_data = {
            "id": fidx,
            "stable_id": stable_id,
            "surface_type": stype,
            "surface_params": sparams,
            "area_mm2": area,
            "centroid": centroid,
            "normal": normal,
            "orientation": orientation,
            "vertex_ids": sorted(face_vertex_ids),
            "edge_ids": sorted(face_edge_ids),
            "adjacent_face_ids": sorted(adjacent_face_ids),
            "mesh_vert_start": mesh_vert_start,
            "mesh_vert_end": mesh_vert_end,
        }

        # Attach feature info if available
        if fidx < len(face_infos):
            fi = face_infos[fidx]
            face_data["feature_type"] = fi.feature_type
            face_data["mold_side"] = fi.mold_side

        faces_data.append(face_data)

    # --- Extract edges ---
    edges_data = []
    for eidx, edge in enumerate(edge_shapes):
        ctype, cparams, polyline = _extract_curve_params_and_polyline(edge)

        # Edge length
        props = GProp_GProps()
        brepgprop.LinearProperties(edge, props)
        length = round(abs(props.Mass()), 4)

        # Faces bounded by this edge
        edge_face_ids = []
        if edge_face_map.Contains(edge):
            adj = edge_face_map.FindFromKey(edge)
            for af in adj:
                afh = af.__hash__()
                if afh in face_shape_map:
                    edge_face_ids.append(face_shape_map[afh])

        # Vertices of this edge
        edge_vert_ids = []
        vexp = TopExp_Explorer(edge, TopAbs_VERTEX)
        while vexp.More():
            vh = topods.Vertex(vexp.Current()).__hash__()
            if vh in vert_shape_map:
                vid = vert_shape_map[vh]
                if vid not in edge_vert_ids:
                    edge_vert_ids.append(vid)
            vexp.Next()

        # Convexity: dihedral angle between adjacent face normals
        convexity = _compute_edge_convexity(edge_face_ids, faces_data)

        # Stable ID
        v_pts = [vert_shapes[vid] for vid in edge_vert_ids if vid < len(vert_shapes)]
        stable_id = _make_edge_stable_id(ctype, v_pts, length)

        edges_data.append({
            "id": eidx,
            "stable_id": stable_id,
            "curve_type": ctype,
            "curve_params": cparams,
            "polyline": polyline,  # Pre-tessellated for rendering/raycasting
            "length_mm": length,
            "face_ids": sorted(set(edge_face_ids)),
            "vertex_ids": sorted(edge_vert_ids),
            "convexity": convexity,
        })

    # --- Extract vertices ---
    vertices_data = []
    for vidx, vertex in enumerate(vert_shapes):
        pt = BRep_Tool.Pnt(vertex)

        # Edges connected to this vertex
        vert_edge_ids = []
        if vert_edge_map.Contains(vertex):
            adj = vert_edge_map.FindFromKey(vertex)
            for ae in adj:
                aeh = ae.__hash__()
                if aeh in edge_shape_map:
                    vert_edge_ids.append(edge_shape_map[aeh])

        vertices_data.append({
            "id": vidx,
            "point": [round(pt.X(), 6), round(pt.Y(), 6), round(pt.Z(), 6)],
            "edge_ids": sorted(set(vert_edge_ids)),
        })

    # --- Build features list from face_infos ---
    features = _build_feature_list(face_infos, faces_data)

    topology = {
        "bodies": bodies,
        "faces": faces_data,
        "edges": edges_data,
        "vertices": vertices_data,
        "features": features,
        "metadata": {
            "face_count": len(faces_data),
            "edge_count": len(edges_data),
            "vertex_count": len(vertices_data),
            "body_count": len(bodies),
            "feature_count": len(features),
        },
    }

    logger.info(
        f"Topology extracted: {len(faces_data)} faces, {len(edges_data)} edges, "
        f"{len(vertices_data)} vertices, {len(bodies)} bodies, {len(features)} features"
    )

    return topology


def serialize_brep(shape) -> bytes:
    """Serialize the OCC B-Rep shape to BREP text format.

    This preserves the exact CAD geometry so it can be reconstructed
    without re-importing the original STEP file.
    Use `deserialize_brep()` to reconstruct.
    """
    from OCC.Core.BRepTools import breptools
    brep_str = breptools.WriteToString(shape)
    return brep_str.encode("utf-8")


def deserialize_brep(data: bytes):
    """Reconstruct an OCC shape from serialized BREP data."""
    from OCC.Core.BRepTools import breptools
    from OCC.Core.TopoDS import TopoDS_Shape
    shape = TopoDS_Shape()
    breptools.ReadFromString(shape, data.decode("utf-8"))
    return shape


# --- Helper functions ---

_SURFACE_TYPE_MAP = {}  # Populated at import time


def _extract_surface_params(adaptor, surf_type) -> tuple[str, dict]:
    """Extract surface type string and geometric parameters."""
    from OCC.Core.GeomAbs import (
        GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone,
        GeomAbs_Sphere, GeomAbs_Torus, GeomAbs_BSplineSurface,
    )

    R = lambda v, d=4: round(v, d)

    if surf_type == GeomAbs_Plane:
        pln = adaptor.Plane()
        ax = pln.Axis().Direction()
        loc = pln.Location()
        d = ax.X() * loc.X() + ax.Y() * loc.Y() + ax.Z() * loc.Z()
        return "plane", {
            "normal": [R(ax.X()), R(ax.Y()), R(ax.Z())],
            "d": R(d),
        }
    elif surf_type == GeomAbs_Cylinder:
        cyl = adaptor.Cylinder()
        ax = cyl.Axis()
        return "cylinder", {
            "axis": [R(ax.Direction().X()), R(ax.Direction().Y()), R(ax.Direction().Z())],
            "origin": [R(ax.Location().X()), R(ax.Location().Y()), R(ax.Location().Z())],
            "radius": R(cyl.Radius()),
        }
    elif surf_type == GeomAbs_Cone:
        cone = adaptor.Cone()
        ax = cone.Axis()
        return "cone", {
            "axis": [R(ax.Direction().X()), R(ax.Direction().Y()), R(ax.Direction().Z())],
            "origin": [R(ax.Location().X()), R(ax.Location().Y()), R(ax.Location().Z())],
            "half_angle_deg": R(math.degrees(cone.SemiAngle())),
            "ref_radius": R(cone.RefRadius()),
        }
    elif surf_type == GeomAbs_Sphere:
        sph = adaptor.Sphere()
        c = sph.Location()
        return "sphere", {
            "center": [R(c.X()), R(c.Y()), R(c.Z())],
            "radius": R(sph.Radius()),
        }
    elif surf_type == GeomAbs_Torus:
        tor = adaptor.Torus()
        ax = tor.Axis()
        return "torus", {
            "axis": [R(ax.Direction().X()), R(ax.Direction().Y()), R(ax.Direction().Z())],
            "center": [R(ax.Location().X()), R(ax.Location().Y()), R(ax.Location().Z())],
            "major_radius": R(tor.MajorRadius()),
            "minor_radius": R(tor.MinorRadius()),
        }
    elif surf_type == GeomAbs_BSplineSurface:
        bs = adaptor.BSpline()
        return "bspline", {
            "u_degree": bs.UDegree(),
            "v_degree": bs.VDegree(),
            "num_u_poles": bs.NbUPoles(),
            "num_v_poles": bs.NbVPoles(),
        }
    else:
        return "other", {}


def _extract_curve_params_and_polyline(edge) -> tuple[str, dict, list]:
    """Extract edge curve type, parameters, AND a polyline for rendering.

    The polyline is a list of [x,y,z] points along the edge curve,
    suitable for Three.js LineSegments rendering and raycasting.
    Lines get 2 points, curves get ~24 points.
    """
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.GeomAbs import (
        GeomAbs_Line, GeomAbs_Circle, GeomAbs_Ellipse, GeomAbs_BSplineCurve,
    )

    R = lambda v, d=4: round(v, d)
    NUM_CURVE_POINTS = 24  # Tessellation density for curved edges

    try:
        adaptor = BRepAdaptor_Curve(edge)
        ctype = adaptor.GetType()
        u_first = adaptor.FirstParameter()
        u_last = adaptor.LastParameter()

        # Generate polyline by sampling the curve
        if ctype == GeomAbs_Line:
            p1 = adaptor.Value(u_first)
            p2 = adaptor.Value(u_last)
            polyline = [
                [R(p1.X()), R(p1.Y()), R(p1.Z())],
                [R(p2.X()), R(p2.Y()), R(p2.Z())],
            ]
            params = {"start": polyline[0], "end": polyline[1]}
            return "line", params, polyline

        elif ctype == GeomAbs_Circle:
            circ = adaptor.Circle()
            c = circ.Location()
            ax = circ.Axis().Direction()
            params = {
                "center": [R(c.X()), R(c.Y()), R(c.Z())],
                "axis": [R(ax.X()), R(ax.Y()), R(ax.Z())],
                "radius": R(circ.Radius()),
            }
        elif ctype == GeomAbs_Ellipse:
            ell = adaptor.Ellipse()
            c = ell.Location()
            params = {
                "center": [R(c.X()), R(c.Y()), R(c.Z())],
                "major_radius": R(ell.MajorRadius()),
                "minor_radius": R(ell.MinorRadius()),
            }
        elif ctype == GeomAbs_BSplineCurve:
            bs = adaptor.BSpline()
            params = {"degree": bs.Degree(), "num_poles": bs.NbPoles()}
        else:
            params = {}

        # Sample curve to polyline for non-line types
        polyline = []
        for i in range(NUM_CURVE_POINTS + 1):
            u = u_first + (u_last - u_first) * i / NUM_CURVE_POINTS
            pt = adaptor.Value(u)
            polyline.append([R(pt.X()), R(pt.Y()), R(pt.Z())])

        type_names = {
            GeomAbs_Circle: "circle",
            GeomAbs_Ellipse: "ellipse",
            GeomAbs_BSplineCurve: "bspline",
        }
        return type_names.get(ctype, "other"), params, polyline

    except Exception:
        return "other", {}, []


def _compute_edge_convexity(face_ids: list[int], faces_data: list[dict]) -> str:
    """Determine if an edge is convex, concave, or smooth based on adjacent face normals."""
    if len(face_ids) != 2:
        return "boundary"  # Edge on a boundary (only one face)

    f1 = faces_data[face_ids[0]] if face_ids[0] < len(faces_data) else None
    f2 = faces_data[face_ids[1]] if face_ids[1] < len(faces_data) else None
    if not f1 or not f2:
        return "unknown"

    n1 = np.array(f1["normal"])
    n2 = np.array(f2["normal"])
    dot = float(np.dot(n1, n2))

    if dot > 0.99:
        return "smooth"   # Normals nearly parallel → G1 continuous
    elif dot > 0.0:
        return "convex"   # Normals diverge → outside corner
    else:
        return "concave"  # Normals converge → inside corner


def _make_face_stable_id(stype: str, sparams: dict, area: float, centroid: list,
                         edge_count: int = 0, adj_count: int = 0,
                         orientation: str = "") -> str:
    """Create a stable face ID from geometry + topology signature.

    Includes edge count, adj count, and orientation to disambiguate
    symmetric faces that have the same surface params.
    """
    sig = f"{stype}_{area:.1f}_e{edge_count}_a{adj_count}_{orientation}"
    if centroid:
        sig += f"_c{centroid[0]:.1f},{centroid[1]:.1f},{centroid[2]:.1f}"
    if "normal" in sparams:
        n = sparams["normal"]
        sig += f"_n{n[0]:.2f},{n[1]:.2f},{n[2]:.2f}"
    elif "axis" in sparams:
        a = sparams["axis"]
        sig += f"_a{a[0]:.2f},{a[1]:.2f},{a[2]:.2f}"
    h = hashlib.md5(sig.encode()).hexdigest()[:12]
    return f"f_{h}"


def _make_edge_stable_id(ctype: str, vertices, length: float) -> str:
    """Create a stable edge ID from curve type + endpoints."""
    from OCC.Core.BRep import BRep_Tool
    sig = f"{ctype}_{length:.2f}"
    for v in vertices[:2]:
        pt = BRep_Tool.Pnt(v)
        sig += f"_{pt.X():.2f},{pt.Y():.2f},{pt.Z():.2f}"
    h = hashlib.md5(sig.encode()).hexdigest()[:12]
    return f"e_{h}"


def _build_feature_list(face_infos: list, faces_data: list[dict]) -> list[dict]:
    """Build feature list from face_infos, grouping faces by feature type."""
    from collections import defaultdict

    # Group faces by feature_type (excluding "other" and "parting")
    feature_groups = defaultdict(list)
    for fi in face_infos:
        if fi.feature_type in ("other", "parting", "fillet"):
            continue
        feature_groups[fi.feature_type].append(fi)

    features = []
    feat_id = 0

    for ftype, face_list in feature_groups.items():
        # For bosses/holes, try to group by proximity (same cylinder axis)
        if ftype in ("boss", "hole"):
            for fi in face_list:
                params = {}
                if fi.index < len(faces_data):
                    fd = faces_data[fi.index]
                    sp = fd.get("surface_params", {})
                    if "radius" in sp:
                        params["radius_mm"] = sp["radius"]
                    if "axis" in sp:
                        params["axis"] = sp["axis"]

                features.append({
                    "id": feat_id,
                    "type": ftype,
                    "face_ids": [fi.index],
                    "mold_side": fi.mold_side,
                    "draft_requirement_deg": fi.draft_requirement_deg,
                    "params": params,
                })
                feat_id += 1
        else:
            # Group all faces of same type into one feature
            features.append({
                "id": feat_id,
                "type": ftype,
                "face_ids": [fi.index for fi in face_list],
                "mold_side": face_list[0].mold_side if face_list else "unknown",
                "draft_requirement_deg": face_list[0].draft_requirement_deg if face_list else None,
                "params": {},
            })
            feat_id += 1

    return features
