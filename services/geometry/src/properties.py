"""Extract geometric properties from OpenCascade shapes."""

import logging

logger = logging.getLogger(__name__)


def extract_properties(shape) -> dict:
    """Extract basic geometric properties from a B-Rep shape.

    Returns:
        dict with volume_mm3, surface_area_mm2, bounding_box, face_count, edge_count
    """
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE

    # Volume and surface area
    volume_props = GProp_GProps()
    brepgprop.VolumeProperties(shape, volume_props)
    volume = volume_props.Mass()

    surface_props = GProp_GProps()
    brepgprop.SurfaceProperties(shape, surface_props)
    surface_area = surface_props.Mass()

    # Bounding box
    bbox = Bnd_Box()
    brepbndlib.Add(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

    # Count faces and edges
    face_count = 0
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face_count += 1
        explorer.Next()

    edge_count = 0
    explorer = TopExp_Explorer(shape, TopAbs_EDGE)
    while explorer.More():
        edge_count += 1
        explorer.Next()

    # Center of mass
    com = volume_props.CentreOfMass()

    result = {
        "volume_mm3": abs(volume),
        "surface_area_mm2": abs(surface_area),
        "bounding_box": {
            "min": [xmin, ymin, zmin],
            "max": [xmax, ymax, zmax],
        },
        "dimensions": {
            "x": xmax - xmin,
            "y": ymax - ymin,
            "z": zmax - zmin,
        },
        "center_of_mass": [com.X(), com.Y(), com.Z()],
        "face_count": face_count,
        "edge_count": edge_count,
    }

    logger.info(f"Properties: {face_count} faces, volume={volume:.1f}mm³, area={surface_area:.1f}mm²")
    return result
