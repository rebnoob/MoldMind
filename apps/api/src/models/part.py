import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, BigInteger, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..core.types import GUID, JSONType


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mesh_key: Mapped[str | None] = mapped_column(String(512))
    thumbnail_key: Mapped[str | None] = mapped_column(String(512))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    units: Mapped[str] = mapped_column(String(10), default="mm")
    bounding_box: Mapped[dict | None] = mapped_column(JSONType())
    face_count: Mapped[int | None] = mapped_column(Integer)
    volume_mm3: Mapped[float | None] = mapped_column(Float)
    surface_area_mm2: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), default="uploaded")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
