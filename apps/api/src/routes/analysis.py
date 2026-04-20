import sys, os
from uuid import UUID
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from ..core.database import get_db
from ..core.auth import get_current_user, TokenData
from ..models.part import Part
from ..models.analysis import AnalysisJob, DfmResult, DfmIssue

router = APIRouter()


@router.get("/simulation/openfoam/status")
async def openfoam_status():
    """Report whether the OpenFOAM backend is configured on this host.

    Public endpoint — frontend calls it to decide whether to enable the
    'OpenFOAM' model option or show a setup card.
    """
    from services.simulation.src.openfoam_runner import check_openfoam_available
    return check_openfoam_available()


@router.get("/simulation/select-solver/{part_id}")
async def select_solver_for_part(
    part_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Recommend the cheapest solver that captures the part's physics.

    Pulls geometry features from fill_time.json + molding_plan.json (produced
    by the upload pipeline) and runs the adaptive selector. Response includes
    the recommendation, reasoning, and a full list of alternatives with
    availability flags.
    """
    import json as _json
    from ..core.storage import download_file
    from services.simulation.src.solver_selector import PartFeatures, select_solver

    r = await db.execute(select(Part).where(Part.id == part_id, Part.user_id == current_user.user_id))
    part = r.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    if not part.mesh_key:
        raise HTTPException(status_code=400, detail="Part not yet processed — wait for the pipeline to finish")

    # Load auxiliary JSONs produced by the pipeline
    def _try_load(key: str) -> dict | None:
        try:
            return _json.loads(download_file(key).decode("utf-8"))
        except Exception:
            return None

    fill_meta = _try_load(part.mesh_key.replace("mesh.glb", "fill_time.json"))
    plan = _try_load(part.mesh_key.replace("mesh.glb", "molding_plan.json"))
    topology = _try_load(part.mesh_key.replace("mesh.glb", "topology.json"))

    # Extract features with graceful fallbacks
    thickness_stats = (fill_meta or {}).get("thickness_stats") or {}
    med_h = float(thickness_stats.get("median_mm", 3.0))
    min_h = float(thickness_stats.get("min_mm", med_h * 0.5))
    max_h = float(thickness_stats.get("max_mm", med_h * 2.0))

    tooling = (plan or {}).get("tooling", {})
    pressure = (plan or {}).get("pressure", {})
    undercut_count = int(tooling.get("undercut_count", 0))
    parting_ratio = tooling.get("parting_ratio")
    flow_length = float(pressure.get("flow_length_mm", 100.0))

    # Heuristic for "has 3D features": non-trivial feature variety in topology
    has_3d = False
    if topology:
        feat_types = set()
        for f in topology.get("faces", []):
            if f.get("feature_type"):
                feat_types.add(f["feature_type"])
        # If the part has any of these, it's not a pure shell
        has_3d = bool(feat_types & {"boss", "rib", "hub", "pocket"})

    features = PartFeatures(
        median_thickness_mm=med_h,
        min_thickness_mm=min_h,
        max_thickness_mm=max_h,
        flow_length_mm=flow_length,
        volume_mm3=float(part.volume_mm3 or 0.0),
        undercut_count=undercut_count,
        parting_ratio=parting_ratio,
        face_count=part.face_count,
        has_3d_features=has_3d,
    )
    return select_solver(features)


@router.get("/simulation/gate/optimize/{part_id}")
async def optimize_gate_for_part(
    part_id: UUID,
    strategy: str = "symmetric_centers",
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rank candidate gate positions for a part.

    strategy:
      - "symmetric_centers" (3 candidates on XY/XZ/YZ plane centres — fastest)
      - "com_axes" (9 candidates along axis-parallel lines through the centre of mass)
      - "exhaustive_xy_grid" (25 candidates on a 5x5 grid on the top XY face — ~30 s)

    See llm_wiki_for_physics/wiki/concepts/gate_optimization.md for the rationale.
    """
    import asyncio, os, tempfile
    from ..core.storage import download_file

    r = await db.execute(select(Part).where(Part.id == part_id, Part.user_id == current_user.user_id))
    part = r.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    if strategy not in ("symmetric_centers", "com_axes", "exhaustive_xy_grid"):
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy}")

    def _run():
        from services.geometry.src.step_parser import parse_step_file
        from services.geometry.src.tessellator import tessellate_shape
        from services.simulation.src.gate_optimizer import optimize_gate
        step_bytes = download_file(part.file_key)
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as f:
            f.write(step_bytes)
            tmp = f.name
        try:
            shape = parse_step_file(tmp)
            mesh = tessellate_shape(shape)
            return optimize_gate(
                mesh["vertices"], mesh.get("indices"),
                strategy=strategy, max_grid=64,
            )
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


@router.post("/simulation/openfoam/prepare/{part_id}")
async def openfoam_prepare_case(
    part_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Session 1: write a ready-to-run interFoam case into openfoam_cases/<part_id>/.

    Does NOT execute any solver — just generates the case directory from the
    part's STEP file. Use this to inspect the generated dicts before sessions
    2-3 add the actual meshing + interFoam run.
    """
    import asyncio, os
    from ..core.storage import download_file
    from services.simulation.src.openfoam_runner import prepare_case

    r = await db.execute(select(Part).where(Part.id == part_id, Part.user_id == current_user.user_id))
    part = r.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")

    # Drop the STEP bytes into a scratch file, prepare the case, return the summary.
    def _run():
        import tempfile
        step_bytes = download_file(part.file_key)
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as f:
            f.write(step_bytes)
            tmp = f.name
        try:
            # Case dir lives in the bind-mounted openfoam_cases so the container sees it.
            repo_root = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
            case_dir = os.path.abspath(os.path.join(repo_root, "openfoam_cases", str(part_id)))
            return prepare_case(tmp, case_dir)
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


@router.post("/simulation/openfoam/smoke-test")
async def openfoam_smoke_test(current_user: TokenData = Depends(get_current_user)):
    """Run the bundled smoke-test inside the openfoam container.

    Verifies the env loads, required solver binaries (blockMesh, snappyHexMesh,
    interFoam, checkMesh) are on PATH, and blockMesh+checkMesh can execute a
    trivial unit-cube mesh. Takes ~5-15s on first run. Auth-gated because it
    shells into a container.
    """
    import asyncio
    from services.simulation.src.openfoam_runner import smoke_test
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, smoke_test)
    return result


class StartAnalysisRequest(BaseModel):
    part_id: UUID
    pull_direction: list[float] = [0.0, 0.0, 1.0]  # Default: Z-up
    material_id: str = "default"


class AnalysisJobResponse(BaseModel):
    id: UUID
    part_id: UUID
    job_type: str
    status: str
    progress: int
    created_at: str


class DfmIssueResponse(BaseModel):
    id: UUID
    rule_id: str
    severity: str
    category: str
    title: str
    description: str
    suggestion: str | None
    affected_faces: list[int] | None
    measured_value: float | None
    threshold_value: float | None
    unit: str | None


class DfmResultResponse(BaseModel):
    id: UUID
    job_id: UUID
    part_id: UUID
    moldability_score: int
    pull_direction: list[float]
    summary: dict
    issues: list[DfmIssueResponse]
    created_at: str


@router.post("/dfm", response_model=AnalysisJobResponse)
async def start_dfm_analysis(
    req: StartAnalysisRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate part exists and belongs to user
    result = await db.execute(
        select(Part).where(Part.id == req.part_id, Part.user_id == current_user.user_id)
    )
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    if part.status not in ("ready", "uploaded"):
        raise HTTPException(status_code=400, detail=f"Part is not ready for analysis (status: {part.status})")

    # Validate pull direction
    if len(req.pull_direction) != 3:
        raise HTTPException(status_code=400, detail="Pull direction must be [x, y, z]")

    # Create analysis job
    job = AnalysisJob(
        part_id=req.part_id,
        user_id=current_user.user_id,
        job_type="dfm_analysis",
        pull_direction=req.pull_direction,
        material_id=req.material_id,
    )
    db.add(job)
    await db.flush()

    # TODO: Dispatch to Celery worker
    # from ..workers.tasks import run_dfm_analysis
    # run_dfm_analysis.delay(str(job.id))

    return AnalysisJobResponse(
        id=job.id,
        part_id=job.part_id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        created_at=job.created_at.isoformat(),
    )


@router.get("/dfm/{part_id}/latest", response_model=DfmResultResponse)
async def get_latest_dfm_result(
    part_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Get latest completed result for this part
    result = await db.execute(
        select(DfmResult)
        .where(DfmResult.part_id == part_id)
        .order_by(DfmResult.created_at.desc())
        .limit(1)
    )
    dfm_result = result.scalar_one_or_none()
    if not dfm_result:
        raise HTTPException(status_code=404, detail="No DFM results found for this part")

    # Get issues
    issues_result = await db.execute(
        select(DfmIssue)
        .where(DfmIssue.result_id == dfm_result.id)
        .order_by(DfmIssue.severity, DfmIssue.category)
    )
    issues = issues_result.scalars().all()

    return DfmResultResponse(
        id=dfm_result.id,
        job_id=dfm_result.job_id,
        part_id=dfm_result.part_id,
        moldability_score=dfm_result.moldability_score,
        pull_direction=dfm_result.pull_direction,
        summary=dfm_result.summary,
        issues=[
            DfmIssueResponse(
                id=i.id, rule_id=i.rule_id, severity=i.severity, category=i.category,
                title=i.title, description=i.description, suggestion=i.suggestion,
                affected_faces=i.affected_faces, measured_value=i.measured_value,
                threshold_value=i.threshold_value, unit=i.unit,
            )
            for i in issues
        ],
        created_at=dfm_result.created_at.isoformat(),
    )
