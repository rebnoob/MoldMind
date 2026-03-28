from uuid import UUID, uuid4
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.auth import get_current_user, TokenData
from ..core.storage import upload_file, generate_presigned_url
from ..models.part import Part
from ..models.project import Project

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
    mesh_url: str | None = None


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

    # TODO: Dispatch geometry processing job (tessellation, basic properties)

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
    )


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

    mesh_url = None
    if part.mesh_key:
        mesh_url = generate_presigned_url(part.mesh_key)

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
        mesh_url=mesh_url,
    )


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
    return [
        PartResponse(
            id=p.id, project_id=p.project_id, name=p.name, filename=p.filename,
            file_size_bytes=p.file_size_bytes, units=p.units, status=p.status,
            bounding_box=p.bounding_box, face_count=p.face_count,
            volume_mm3=p.volume_mm3, surface_area_mm2=p.surface_area_mm2,
            created_at=p.created_at.isoformat(),
        )
        for p in parts
    ]
