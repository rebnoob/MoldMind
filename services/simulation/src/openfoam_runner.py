"""OpenFOAM VOF simulation runner — skeleton / availability check.

This module wraps a true 3D Volume-of-Fluid injection-molding simulation via
OpenFOAM's interFoam solver (with polymer rheology). The full stack required:

  1. OpenFOAM Docker container (v2312 or similar from opencfd-official)
  2. STEP → STL via pythonocc
  3. STL → polyMesh via snappyHexMesh (requires a `snappyHexMeshDict` template)
  4. Case directory: 0/, constant/, system/ populated per-part
  5. interFoam execution — 20-60 min for a realistic part on 4 cores
  6. Post-processing: VTK output → fill-time field per vertex → upload

As of 2026-04-18 none of this is wired up. The functions below return
structured "not available" diagnostics so the API + frontend can surface an
honest state. When the container is ready, fill in run_openfoam_simulation().
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def check_openfoam_available() -> dict[str, Any]:
    """Return a diagnostic dict describing whether OpenFOAM can be run here."""
    # Preferred: a docker-compose service named "openfoam"
    docker = shutil.which("docker")
    if not docker:
        return {
            "available": False,
            "reason": "docker_missing",
            "message": "Docker is not installed on the host.",
            "next_steps": [
                "Install Docker Desktop for macOS.",
                "Add an 'openfoam' service to docker-compose.yml using opencfd/openfoam-default:2312.",
                "Mount a shared volume for case directories.",
            ],
        }

    # Check if an openfoam container is running/reachable
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}", "--filter", "name=openfoam"],
            capture_output=True, text=True, timeout=5,
        )
        names = result.stdout.strip().splitlines()
    except Exception as e:
        return {
            "available": False,
            "reason": "docker_exec_failed",
            "message": f"docker ps failed: {e}",
            "next_steps": ["Start Docker Desktop.", "Verify the daemon is reachable."],
        }

    if not names:
        return {
            "available": False,
            "reason": "no_openfoam_container",
            "message": "No running container matches name~='openfoam'.",
            "next_steps": [
                "Add an openfoam service to docker-compose.yml:",
                "  openfoam:",
                "    image: opencfd/openfoam-default:2312",
                "    command: tail -f /dev/null",
                "    volumes:",
                "      - ./openfoam_cases:/cases",
                "Then: docker compose up -d openfoam",
            ],
        }

    return {
        "available": True,
        "reason": "ok",
        "message": f"OpenFOAM container detected: {names[0]}",
        "container": names[0],
    }


def _container_name() -> str | None:
    """Return the currently running openfoam container name, or None."""
    docker = shutil.which("docker")
    if not docker:
        return None
    try:
        r = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}", "--filter", "name=openfoam"],
            capture_output=True, text=True, timeout=5,
        )
        names = [n for n in r.stdout.strip().splitlines() if n]
        return names[0] if names else None
    except Exception:
        return None


def exec_in_container(
    cmd: str,
    *,
    timeout: int = 60,
    workdir: str = "/cases",
) -> subprocess.CompletedProcess:
    """Run a shell command inside the openfoam container via `docker exec`.

    The OpenFOAM env is sourced implicitly by the login shell (-lc). Raises
    RuntimeError if no openfoam container is running.
    """
    name = _container_name()
    if not name:
        raise RuntimeError("No running openfoam container. Run: docker compose up -d openfoam")
    return subprocess.run(
        ["docker", "exec", "-w", workdir, name, "bash", "-lc", cmd],
        capture_output=True, text=True, timeout=timeout,
    )


def smoke_test() -> dict[str, Any]:
    """Run the bundled smoke-test script (/templates/smoke/Allrun) in the
    container. Confirms the OpenFOAM env loads, blockMesh/checkMesh work, and
    the required solver binaries are on PATH.

    Returns a dict with stdout/stderr and a parsed pass/fail. Safe to call
    from the API.
    """
    status = check_openfoam_available()
    if not status.get("available"):
        return {"ok": False, "reason": "container_unavailable", "diagnostic": status}
    try:
        r = exec_in_container("/templates/smoke/Allrun", timeout=120)
    except Exception as e:
        return {"ok": False, "reason": "exec_failed", "error": str(e)}

    ok = r.returncode == 0 and "All smoke checks passed" in r.stdout
    return {
        "ok": ok,
        "returncode": r.returncode,
        "stdout": r.stdout,
        "stderr": r.stderr[-2000:] if r.stderr else "",
    }


def export_step_to_stl(step_path: str | Path, stl_path: str | Path, linear_deflection: float = 0.1) -> dict[str, Any]:
    """Tessellate a STEP file and write an ASCII STL. Linear deflection is in
    the STEP's native units (mm for most CAD). A deflection of ~0.1 mm gives
    a fairly tight surface that snappyHexMesh can refine against without
    being dominated by tessellation noise.
    """
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.StlAPI import StlAPI_Writer
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib

    step_path = Path(step_path)
    stl_path = Path(stl_path)
    stl_path.parent.mkdir(parents=True, exist_ok=True)

    reader = STEPControl_Reader()
    if reader.ReadFile(str(step_path)) != IFSelect_RetDone:
        raise RuntimeError(f"STEP read failed: {step_path}")
    reader.TransferRoots()
    shape = reader.OneShape()
    if shape.IsNull():
        raise RuntimeError("STEP contained no geometry")

    # Bounding box (mm) — returned so callers can size the background mesh.
    bbox = Bnd_Box()
    brepbndlib.Add(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

    # Tessellate + write. OCC's STL writer emits mm units by default; snappy
    # expects the same unit as blockMeshDict (we use metres via scale 1 + the
    # STL coords converted in case_generator).
    BRepMesh_IncrementalMesh(shape, linear_deflection, False, 0.5, True)
    writer = StlAPI_Writer()
    writer.SetASCIIMode(True)
    ok = writer.Write(shape, str(stl_path))
    if not ok:
        raise RuntimeError(f"STL write failed: {stl_path}")

    # Rewrite file with coords converted mm → m (OpenFOAM scale: 1 in blockMesh,
    # so STL and block mesh must be in the same unit). Simpler path: scale the
    # blockMeshDict via `scale 0.001` — but we picked scale 1 in case_generator,
    # so convert STL coords here.
    import re
    def _vertex_mm_to_m(match: re.Match) -> str:
        # Preserves the captured leading whitespace so one-vertex-per-line layout stays.
        x = float(match.group("x")) / 1000.0
        y = float(match.group("y")) / 1000.0
        z = float(match.group("z")) / 1000.0
        return f"{match.group('lead')}vertex {x:.8e} {y:.8e} {z:.8e}"
    txt = stl_path.read_text()
    converted = re.sub(
        r"(?P<lead>^\s*)vertex\s+(?P<x>\S+)\s+(?P<y>\S+)\s+(?P<z>\S+)",
        _vertex_mm_to_m, txt, flags=re.MULTILINE,
    )
    stl_path.write_text(converted)

    return {
        "stl_path": str(stl_path),
        "bbox_mm": {
            "min": [xmin, ymin, zmin],
            "max": [xmax, ymax, zmax],
        },
        "linear_deflection_mm": linear_deflection,
    }


def prepare_case(
    step_path: str | Path,
    case_dir: str | Path,
    *,
    gate_pos_mm: tuple[float, float, float] | None = None,
    inlet_velocity: float = 0.1,
    polymer_viscosity: float = 1000.0,
    polymer_density: float = 1000.0,
    block_mesh_cells: int = 32,
    refinement: tuple[int, int] = (1, 2),
    end_time_s: float = 2.0,
) -> dict[str, Any]:
    """Build a ready-to-run interFoam case directory from a STEP file.

    Writes:
        <case_dir>/constant/triSurface/part.stl
        <case_dir>/system/{blockMeshDict, snappyHexMeshDict, controlDict,
                            fvSchemes, fvSolution, decomposeParDict}
        <case_dir>/constant/{transportProperties, turbulenceProperties, g}
        <case_dir>/0/{alpha.polymer, U, p_rgh}

    Does NOT execute any solver. Call run_openfoam_simulation() to do that.
    The separation exists so users can inspect/edit the case before running.
    """
    from .case_generator import CaseParams, write_case_dir

    case = Path(case_dir)
    stl_rel = "constant/triSurface/part.stl"
    stl_info = export_step_to_stl(step_path, case / stl_rel)

    bbox = stl_info["bbox_mm"]
    if gate_pos_mm is None:
        # Default: top-center of the bbox (matches the Simple Model's "top_z" default).
        gate_pos_mm = (
            (bbox["min"][0] + bbox["max"][0]) / 2.0,
            (bbox["min"][1] + bbox["max"][1]) / 2.0,
            bbox["max"][2],
        )

    params = CaseParams(
        bbox_min_mm=tuple(bbox["min"]),
        bbox_max_mm=tuple(bbox["max"]),
        gate_pos_mm=tuple(gate_pos_mm),
        block_mesh_cells_per_axis=block_mesh_cells,
        snappy_refinement_level=refinement,
        polymer_density=polymer_density,
        polymer_viscosity=polymer_viscosity,
        inlet_velocity=inlet_velocity,
        end_time_s=end_time_s,
    )
    files = write_case_dir(case, params)

    return {
        "case_dir": str(case),
        "stl": stl_info,
        "gate_pos_mm": list(gate_pos_mm),
        "params": {
            "bbox_min_mm": list(params.bbox_min_mm),
            "bbox_max_mm": list(params.bbox_max_mm),
            "block_mesh_cells_per_axis": params.block_mesh_cells_per_axis,
            "refinement": list(params.snappy_refinement_level),
            "polymer_density": params.polymer_density,
            "polymer_viscosity": params.polymer_viscosity,
            "inlet_velocity": params.inlet_velocity,
            "end_time_s": params.end_time_s,
        },
        "files_written": sorted(files.keys()),
    }


def run_openfoam_simulation(
    step_path: str | Path,
    output_dir: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    """Full pipeline — prepare_case + meshing + solve + post-process.

    Only the `prepare` stage is implemented in session 1. Sessions 2+ will
    fill in the `meshing` and `solve` stages. This stub exists so callers can
    reference the final entry point today.
    """
    raise NotImplementedError(
        "Session 1 shipped prepare_case() — use that to write case files. "
        "Sessions 2-3 will add meshing + interFoam execution."
    )
