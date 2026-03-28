"""Tessellate OpenCascade B-Rep shapes to triangle meshes for web viewing.

Outputs indexed triangle mesh data suitable for Three.js BufferGeometry
or GLB export.
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)


def tessellate_shape(shape, deflection: float = 0.1, angular_deflection: float = 0.5) -> dict:
    """Tessellate a B-Rep shape into an indexed triangle mesh.

    Args:
        shape: OpenCascade TopoDS_Shape
        deflection: Linear deflection (chord height) in model units.
                    Smaller = finer mesh. 0.1mm is good for typical parts.
        angular_deflection: Angular deflection in radians.

    Returns:
        dict with:
            - vertices: np.ndarray (N, 3) float32
            - normals: np.ndarray (N, 3) float32
            - indices: np.ndarray (M, 3) uint32 — triangle face indices
            - face_map: list[dict] — maps each triangle range to an OCC face index
                        [{face_index: int, tri_start: int, tri_end: int}, ...]
    """
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.TopLoc import TopLoc_Location

    # Perform tessellation
    mesh = BRepMesh_IncrementalMesh(shape, deflection, False, angular_deflection, True)
    mesh.Perform()

    if not mesh.IsDone():
        raise RuntimeError("Tessellation failed")

    all_vertices = []
    all_normals = []
    all_indices = []
    face_map = []
    vertex_offset = 0

    # Iterate over each B-Rep face
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    face_index = 0

    while explorer.More():
        face = explorer.Current()
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation(face, location)

        if triangulation is None:
            explorer.Next()
            face_index += 1
            continue

        # Extract vertices
        nb_nodes = triangulation.NbNodes()
        nb_tris = triangulation.NbTriangles()

        tri_start = len(all_indices)

        for i in range(1, nb_nodes + 1):
            node = triangulation.Node(i)
            # Apply location transformation
            if not location.IsIdentity():
                node = node.Transformed(location.Transformation())
            all_vertices.append([node.X(), node.Y(), node.Z()])

        # Extract triangles
        for i in range(1, nb_tris + 1):
            tri = triangulation.Triangle(i)
            n1, n2, n3 = tri.Get()
            # Convert to 0-based indexing with vertex offset
            all_indices.append([
                n1 - 1 + vertex_offset,
                n2 - 1 + vertex_offset,
                n3 - 1 + vertex_offset,
            ])

        face_map.append({
            "face_index": face_index,
            "tri_start": tri_start,
            "tri_end": len(all_indices),
        })

        vertex_offset += nb_nodes
        face_index += 1
        explorer.Next()

    vertices = np.array(all_vertices, dtype=np.float32)
    indices = np.array(all_indices, dtype=np.uint32)

    # Compute per-vertex normals from face normals
    normals = _compute_vertex_normals(vertices, indices)

    logger.info(f"Tessellated: {len(vertices)} vertices, {len(indices)} triangles, {face_index} faces")

    return {
        "vertices": vertices,
        "normals": normals,
        "indices": indices,
        "face_map": face_map,
    }


def _compute_vertex_normals(vertices: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Compute smooth per-vertex normals by averaging face normals."""
    normals = np.zeros_like(vertices)

    for tri in indices:
        v0, v1, v2 = vertices[tri[0]], vertices[tri[1]], vertices[tri[2]]
        edge1 = v1 - v0
        edge2 = v2 - v0
        face_normal = np.cross(edge1, edge2)
        normals[tri[0]] += face_normal
        normals[tri[1]] += face_normal
        normals[tri[2]] += face_normal

    # Normalize
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    lengths = np.where(lengths == 0, 1, lengths)  # Avoid division by zero
    normals = normals / lengths

    return normals.astype(np.float32)


def mesh_to_glb(vertices: np.ndarray, normals: np.ndarray, indices: np.ndarray) -> bytes:
    """Convert mesh data to GLB (binary glTF) format for web viewing.

    Uses trimesh for GLB export.
    """
    import trimesh

    mesh = trimesh.Trimesh(
        vertices=vertices,
        faces=indices,
        vertex_normals=normals,
    )
    return mesh.export(file_type="glb")
