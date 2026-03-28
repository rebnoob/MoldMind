import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, SmallInteger, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..core.types import GUID, JSONType, IntArrayType


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    part_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("parts.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    progress: Mapped[int] = mapped_column(SmallInteger, default=0)
    pull_direction: Mapped[dict | None] = mapped_column(JSONType())
    material_id: Mapped[str | None] = mapped_column(String(100))
    parameters: Mapped[dict] = mapped_column(JSONType(), default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    worker_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DfmResult(Base):
    __tablename__ = "dfm_results"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("analysis_jobs.id"), nullable=False)
    part_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("parts.id"), nullable=False)
    moldability_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    pull_direction: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    summary: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    analysis_metadata: Mapped[dict] = mapped_column(JSONType(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DfmIssue(Base):
    __tablename__ = "dfm_issues"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    result_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("dfm_results.id"), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[str | None] = mapped_column(Text)
    affected_faces: Mapped[list | None] = mapped_column(IntArrayType())
    affected_region: Mapped[dict | None] = mapped_column(JSONType())
    measured_value: Mapped[float | None] = mapped_column(Float)
    threshold_value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(20))
    issue_metadata: Mapped[dict] = mapped_column(JSONType(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
