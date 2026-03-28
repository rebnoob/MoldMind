"""STEP file parser using OpenCascade (pythonocc-core).

This module handles loading STEP files into OpenCascade TopoDS_Shape objects,
which are the B-Rep representation used for all downstream geometry analysis.
"""

import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Type alias — actual import requires pythonocc-core installed
Shape = object  # Will be OCC.Core.TopoDS.TopoDS_Shape at runtime


def parse_step_file(filepath: str | Path) -> Shape:
    """Parse a STEP file from disk into an OpenCascade shape.

    Args:
        filepath: Path to .step/.stp file

    Returns:
        TopoDS_Shape (the root shape from the STEP file)

    Raises:
        ValueError: If the file cannot be parsed or contains no geometry
    """
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.IFSelect import IFSelect_RetDone

    reader = STEPControl_Reader()
    status = reader.ReadFile(str(filepath))

    if status != IFSelect_RetDone:
        raise ValueError(f"Failed to read STEP file: {filepath} (status: {status})")

    reader.TransferRoots()
    shape = reader.OneShape()

    if shape.IsNull():
        raise ValueError(f"STEP file contains no geometry: {filepath}")

    logger.info(f"Parsed STEP file: {filepath}")
    return shape


def parse_step_bytes(data: bytes) -> Shape:
    """Parse STEP data from bytes (e.g., downloaded from object storage).

    Writes to a temp file because OpenCascade's STEP reader requires a file path.
    """
    with tempfile.NamedTemporaryFile(suffix=".step", delete=True) as f:
        f.write(data)
        f.flush()
        return parse_step_file(f.name)
