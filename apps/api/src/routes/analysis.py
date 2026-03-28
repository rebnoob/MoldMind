from uuid import UUID
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.auth import get_current_user, TokenData
from ..models.part import Part
from ..models.analysis import AnalysisJob, DfmResult, DfmIssue

router = APIRouter()


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
