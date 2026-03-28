from uuid import UUID
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.auth import get_current_user, TokenData
from ..models.analysis import AnalysisJob

router = APIRouter()


class JobStatusResponse(BaseModel):
    id: UUID
    part_id: UUID
    job_type: str
    status: str
    progress: int
    error_message: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AnalysisJob).where(AnalysisJob.id == job_id, AnalysisJob.user_id == current_user.user_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        id=job.id,
        part_id=job.part_id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        error_message=job.error_message,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        created_at=job.created_at.isoformat(),
    )


@router.get("/", response_model=list[JobStatusResponse])
async def list_jobs(
    part_id: UUID | None = None,
    status: str | None = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(AnalysisJob).where(AnalysisJob.user_id == current_user.user_id)
    if part_id:
        query = query.where(AnalysisJob.part_id == part_id)
    if status:
        query = query.where(AnalysisJob.status == status)
    query = query.order_by(AnalysisJob.created_at.desc()).limit(50)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return [
        JobStatusResponse(
            id=j.id, part_id=j.part_id, job_type=j.job_type, status=j.status,
            progress=j.progress, error_message=j.error_message,
            started_at=j.started_at.isoformat() if j.started_at else None,
            completed_at=j.completed_at.isoformat() if j.completed_at else None,
            created_at=j.created_at.isoformat(),
        )
        for j in jobs
    ]
