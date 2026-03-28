"""Tessellate OpenCascade B-Rep shapes to high-quality display meshes.

Architecture note:
- The B-Rep shape (exact CAD geometry) is the source of truth for analysis.
- This module generates a DISPLAY mesh only — for GPU rendering in the browser.
- Indexed geometry with per-face vertex groups preserves both smooth shading
  (shared vertices within faces) and face-level selection (separate between faces).
- Tessellation quality is controlled by linear + angular deflection tolerances.
  Tighter tolerances → more triangles → smoother curves → larger files.
"""

import logging
import struct
import json
import numpy as np

logger = logging.getLogger(__name__)


def tessellate_shape(shape, deflection: float = None, angular_deflection: float = None) -> dict:
    """Tessellate a B-Rep shape into an indexed triangle mesh.

    Args:
        shape: OpenCascade TopoDS_Shape (B-Rep, exact geometry)
        deflection: Max chord height deviation (mm). None = use config default.
        angular_deflection: Max angle between adjacent normals (rad). None = use config.

    Returns:
        dict with vertices, normals, indices, face_map, and tessellation metadata.
    """
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.TopoDS import topods
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib

    # Load config defaults
    from services.dfm.src.dfm_config import TessellationConfig as TC
    if deflection is None:
        deflection = TC.LINEAR_DEFLECTION_MM
    if angular_deflection is None:
        angular_deflection = TC.ANGULAR_DEFLECTION_RAD

    # Adaptive deflection: scale with part size, but respect floor
    bbox = Bnd_Box()
    brepbndlib.Add(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    max_dim = max(xmax - xmin, ymax - ymin, zmax - zmin)

    adaptive_deflection = min(deflection, max_dim * TC.ADAPTIVE_SCALE)
    adaptive_deflection = max(adaptive_deflection, TC.DEFLECTION_FLOOR_MM)

    # Tessellate the B-Rep shape
    mesh = BRepMesh_IncrementalMesh(shape, adaptive_deflection, False, angular_deflection, True)
    mesh.Perform()
    if not mesh.IsDone():
        raise RuntimeError("Tessellation failed")

    all_vertices = []
    all_normals = []
    all_indices = []
    face_map = []
    vertex_offset = 0
    normals_from_occ = True  # Track whether OCC provided normals

    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    face_index = 0

    while explorer.More():
        face = topods.Face(explorer.Current())
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation(face, location)

        if triangulation is None:
            explorer.Next()
            face_index += 1
            continue

        is_reversed = (face.Orientation() == TopAbs_REVERSED)
        nb_nodes = triangulation.NbNodes()
        nb_tris = triangulation.NbTriangles()

        vert_start = vertex_offset
        idx_start = len(all_indices)

        # Extract shared nodes (positions) for this face
        for i in range(1, nb_nodes + 1):
            node = triangulation.Node(i)
            if not location.IsIdentity():
                node = node.Transformed(location.Transformation())
            all_vertices.append([node.X(), node.Y(), node.Z()])

        # Extract per-node normals from OCC (smooth shading)
        has_normals = triangulation.HasNormals()
        if has_normals:
            for i in range(1, nb_nodes + 1):
                n = triangulation.Normal(i)
                if not location.IsIdentity():
                    n = n.Transformed(location.Transformation())
                nx, ny, nz = n.X(), n.Y(), n.Z()
                if is_reversed:
                    nx, ny, nz = -nx, -ny, -nz
                all_normals.append([nx, ny, nz])
        else:
            # Fallback: accumulate face normals at shared vertices (Gouraud)
            normals_from_occ = False
            face_normals = [[0.0, 0.0, 0.0] for _ in range(nb_nodes)]
            for i in range(1, nb_tris + 1):
                tri = triangulation.Triangle(i)
                n1, n2, n3 = tri.Get()
                i1, i2, i3 = n1 - 1, n2 - 1, n3 - 1
                v0 = np.array(all_vertices[vertex_offset + i1])
                v1 = np.array(all_vertices[vertex_offset + i2])
                v2 = np.array(all_vertices[vertex_offset + i3])
                fn = np.cross(v1 - v0, v2 - v0)
                for idx in [i1, i2, i3]:
                    face_normals[idx][0] += fn[0]
                    face_normals[idx][1] += fn[1]
                    face_normals[idx][2] += fn[2]
            for fn in face_normals:
                length = (fn[0]**2 + fn[1]**2 + fn[2]**2) ** 0.5
                if length > 0:
                    fn[0] /= length; fn[1] /= length; fn[2] /= length
                if is_reversed:
                    fn[0] = -fn[0]; fn[1] = -fn[1]; fn[2] = -fn[2]
            all_normals.extend(face_normals)

        # Triangle indices (referencing global vertex buffer)
        for i in range(1, nb_tris + 1):
            tri = triangulation.Triangle(i)
            n1, n2, n3 = tri.Get()
            if is_reversed:
                n1, n2, n3 = n1, n3, n2
            all_indices.extend([
                n1 - 1 + vertex_offset,
                n2 - 1 + vertex_offset,
                n3 - 1 + vertex_offset,
            ])

        vert_end = vertex_offset + nb_nodes
        idx_end = len(all_indices)

        # Centroid and average normal for annotations
        face_verts = np.array(all_vertices[vert_start:vert_end], dtype=np.float32)
        face_norms = np.array(all_normals[vert_start:vert_end], dtype=np.float32)
        centroid = face_verts.mean(axis=0).tolist() if len(face_verts) > 0 else [0, 0, 0]
        avg_normal = face_norms.mean(axis=0)
        n_len = float(np.linalg.norm(avg_normal))
        avg_normal = (avg_normal / n_len).tolist() if n_len > 0 else [0, 0, 1]

        face_map.append({
            "face_index": face_index,
            "vert_start": vert_start,
            "vert_end": vert_end,
            "idx_start": idx_start,
            "idx_end": idx_end,
            "centroid": [round(c, 4) for c in centroid],
            "normal": [round(n, 4) for n in avg_normal],
        })

        vertex_offset = vert_end
        face_index += 1
        explorer.Next()

    vertices = np.array(all_vertices, dtype=np.float32)
    normals = np.array(all_normals, dtype=np.float32)
    indices = np.array(all_indices, dtype=np.uint32)

    # Normalize all normals
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    lengths = np.where(lengths == 0, 1, lengths)
    normals = (normals / lengths).astype(np.float32)

    num_tris = len(indices) // 3
    logger.info(
        f"Tessellated: {len(vertices)} verts, {num_tris} tris, {face_index} faces, "
        f"deflection={adaptive_deflection:.4f}mm, angular={angular_deflection:.2f}rad"
    )

    return {
        "vertices": vertices,
        "normals": normals,
        "indices": indices,
        "face_map": face_map,
        "tess_metadata": {
            "brep_available": True,
            "linear_deflection_mm": round(adaptive_deflection, 4),
            "angular_deflection_rad": round(angular_deflection, 2),
            "vertex_count": len(vertices),
            "triangle_count": num_tris,
            "face_count": face_index,
            "normals_from_occ": normals_from_occ,
            "part_max_dimension_mm": round(max_dim, 2),
        },
    }


def mesh_to_glb(vertices: np.ndarray, normals: np.ndarray, indices: np.ndarray = None) -> bytes:
    """Convert indexed mesh to GLB (binary glTF 2.0).

    Builds GLB manually with proper index buffer for smooth shading.
    Uses PBR material with doubleSided rendering.
    """
    num_verts = len(vertices)
    v_min = vertices.min(axis=0).tolist()
    v_max = vertices.max(axis=0).tolist()

    pos_bytes = vertices.astype(np.float32).tobytes()
    norm_bytes = normals.astype(np.float32).tobytes()

    has_indices = indices is not None and len(indices) > 0
    idx_bytes = indices.astype(np.uint32).tobytes() if has_indices else b''
    num_indices = len(indices) if has_indices else 0

    bin_data = pos_bytes + norm_bytes + idx_bytes
    while len(bin_data) % 4 != 0:
        bin_data += b'\x00'

    buffer_views = [
        {"buffer": 0, "byteOffset": 0, "byteLength": len(pos_bytes), "target": 34962},
        {"buffer": 0, "byteOffset": len(pos_bytes), "byteLength": len(norm_bytes), "target": 34962},
    ]
    accessors = [
        {"bufferView": 0, "componentType": 5126, "count": num_verts, "type": "VEC3", "min": v_min, "max": v_max},
        {"bufferView": 1, "componentType": 5126, "count": num_verts, "type": "VEC3"},
    ]
    primitive = {"attributes": {"POSITION": 0, "NORMAL": 1}, "mode": 4, "material": 0}

    if has_indices:
        buffer_views.append({
            "buffer": 0,
            "byteOffset": len(pos_bytes) + len(norm_bytes),
            "byteLength": len(idx_bytes),
            "target": 34963,
        })
        accessors.append({"bufferView": 2, "componentType": 5125, "count": num_indices, "type": "SCALAR"})
        primitive["indices"] = 2

    gltf = {
        "asset": {"version": "2.0", "generator": "MoldMind"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [primitive]}],
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(bin_data)}],
        "materials": [{
            "pbrMetallicRoughness": {
                "baseColorFactor": [0.78, 0.80, 0.83, 1.0],
                "metallicFactor": 0.08,
                "roughnessFactor": 0.4,
            },
            "doubleSided": True,
        }],
    }

    json_str = json.dumps(gltf, separators=(',', ':'))
    json_bytes = json_str.encode('utf-8')
    while len(json_bytes) % 4 != 0:
        json_bytes += b' '

    total_length = 12 + 8 + len(json_bytes) + 8 + len(bin_data)
    glb = bytearray()
    glb += struct.pack('<I', 0x46546C67)
    glb += struct.pack('<I', 2)
    glb += struct.pack('<I', total_length)
    glb += struct.pack('<I', len(json_bytes))
    glb += struct.pack('<I', 0x4E4F534A)
    glb += json_bytes
    glb += struct.pack('<I', len(bin_data))
    glb += struct.pack('<I', 0x004E4942)
    glb += bin_data
    return bytes(glb)
