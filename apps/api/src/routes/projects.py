from uuid import UUID
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.auth import get_current_user, TokenData
from ..models.project import Project

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str
    description: str | None = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: str


@router.post("/", response_model=ProjectResponse)
async def create_project(
    req: CreateProjectRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = Project(user_id=current_user.user_id, name=req.name, description=req.description)
    db.add(project)
    await db.flush()
    return ProjectResponse(
        id=project.id, name=project.name, description=project.description, created_at=project.created_at.isoformat()
    )


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.user_id == current_user.user_id).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    return [
        ProjectResponse(id=p.id, name=p.name, description=p.description, created_at=p.created_at.isoformat())
        for p in projects
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(
        id=project.id, name=project.name, description=project.description, created_at=project.created_at.isoformat()
    )
