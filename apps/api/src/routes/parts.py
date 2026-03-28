import asyncio
from uuid import UUID, uuid4
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.auth import get_current_user, TokenData
from ..core.storage import upload_file, generate_presigned_url
from ..models.part import Part
from ..models.project import Project
from ..models.analysis import AnalysisJob

router = APIRouter()

ALLOWED_EXTENSIONS = {".step", ".stp", ".STEP", ".STP"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


class PartResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    filename: str
    file_size_bytes: int | None
    units: str
    status: str
    bounding_box: dict | None
    face_count: int | None
    volume_mm3: float | None
    surface_area_mm2: float | None
    created_at: str
    error_message: str | None = None
    mesh_url: str | None = None
    facemap_url: str | None = None
    topology_url: str | None = None
    molding_plan_url: str | None = None
    ceramic_feasibility_url: str | None = None


async def _enrich_part(part: Part, db: AsyncSession) -> PartResponse:
    """Build PartResponse."""
    mesh_url = None
    facemap_url = None
    topology_url = None
    molding_plan_url = None
    ceramic_feasibility_url = None
    if part.mesh_key:
        mesh_url = generate_presigned_url(part.mesh_key)
        facemap_key = part.mesh_key.replace("mesh.glb", "facemap.json")
        facemap_url = generate_presigned_url(facemap_key)
        topology_key = part.mesh_key.replace("mesh.glb", "topology.json")
        topology_url = generate_presigned_url(topology_key)
        plan_key = part.mesh_key.replace("mesh.glb", "molding_plan.json")
        molding_plan_url = generate_presigned_url(plan_key)
        ceramic_key = part.mesh_key.replace("mesh.glb", "ceramic_feasibility.json")
        ceramic_feasibility_url = generate_presigned_url(ceramic_key)

    return PartResponse(
        id=part.id,
        project_id=part.project_id,
        name=part.name,
        filename=part.filename,
        file_size_bytes=part.file_size_bytes,
        units=part.units,
        status=part.status,
        bounding_box=part.bounding_box,
        face_count=part.face_count,
        volume_mm3=part.volume_mm3,
        surface_area_mm2=part.surface_area_mm2,
        created_at=part.created_at.isoformat(),
        error_message=part.error_message,
        mesh_url=mesh_url,
        facemap_url=facemap_url,
        topology_url=topology_url,
        molding_plan_url=molding_plan_url,
        ceramic_feasibility_url=ceramic_feasibility_url,
    )


@router.post("/upload", response_model=PartResponse)
async def upload_part(
    project_id: UUID = Form(...),
    name: str = Form(...),
    file: UploadFile = File(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate file extension
    filename = file.filename or "unknown.step"
    ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Only STEP files are accepted. Got: {ext}")

    # Read file
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 100MB)")

    # Upload to object storage
    part_id = uuid4()
    file_key = f"parts/{part_id}/original{ext}"
    upload_file(file_key, data, content_type="application/step")

    # Create part record
    part = Part(
        id=part_id,
        project_id=project_id,
        user_id=current_user.user_id,
        name=name,
        filename=filename,
        file_key=file_key,
        file_size_bytes=len(data),
        status="uploaded",
    )
    db.add(part)
    await db.flush()

    # Create analysis job and dispatch background task
    job = AnalysisJob(
        part_id=part_id,
        user_id=current_user.user_id,
        job_type="dfm_analysis",
        status="queued",
        pull_direction=[0.0, 0.0, 1.0],
        material_id="default",
    )
    db.add(job)
    await db.flush()

    # Schedule background geometry processing + DFM analysis
    from ..workers.tasks import process_geometry_and_analyze
    asyncio.create_task(process_geometry_and_analyze(str(job.id), str(part_id), [0.0, 0.0, 1.0]))

    return await _enrich_part(part, db)


@router.get("/all", response_model=list[PartResponse])
async def list_all_parts(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all parts for the current user across all projects."""
    result = await db.execute(
        select(Part).where(Part.user_id == current_user.user_id).order_by(Part.created_at.desc())
    )
    parts = result.scalars().all()
    return [await _enrich_part(p, db) for p in parts]


@router.get("/{part_id}", response_model=PartResponse)
async def get_part(
    part_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Part).where(Part.id == part_id, Part.user_id == current_user.user_id)
    )
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    return await _enrich_part(part, db)


@router.get("/", response_model=list[PartResponse])
async def list_parts(
    project_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Part).where(Part.project_id == project_id, Part.user_id == current_user.user_id)
        .order_by(Part.created_at.desc())
    )
    parts = result.scalars().all()
    return [await _enrich_part(p, db) for p in parts]
